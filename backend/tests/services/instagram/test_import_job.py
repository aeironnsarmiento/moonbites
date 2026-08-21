from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest

from app.core.config import Settings
from app.schemas.extract import NormalizedRecipe
from app.schemas.import_jobs import ImportJobErrorCode, ImportJobRecord, ImportJobState
from app.services.gemini.recipe_parser import ParsedCaption
from app.services.import_deadline import Deadline
from app.services.instagram.import_job import (
    OrchestrationDeps,
    advance_instagram_job,
)
from app.services.instagram.creator_site_lookup import FetchedPage
from app.services.public_web import PublicWebError
from fastapi import HTTPException


REEL_ACTOR_ID = "xMc5Ga1oCONPmWJIa"
PROFILE_ACTOR_ID = "dSCLg0C3YEZ83HzYX"
CANONICAL_URL = "https://www.instagram.com/reel/DZuzc9PNedT/"


def _settings() -> Settings:
    return Settings(
        request_timeout_seconds=15.0,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_service_role_key=None,
        supabase_table_name="recipe_imports",
        admin_emails=(),
        cors_origins=("http://localhost:5173",),
        user_agent="test-agent",
        accept_header="text/html",
        accept_language_header="en-US",
        youtube_api_key=None,
        instagram_apify_token="secret-token",
    )


def _job(**overrides) -> ImportJobRecord:
    now = datetime.now(timezone.utc)
    fields = {
        "id": "job-1",
        "owner_email": "admin@example.com",
        "canonical_reel_url": CANONICAL_URL,
        "state": ImportJobState.QUEUED,
        "version": 3,
        "lease_token": "lease-abc",
        "next_advance_at": now,
        "stale_deadline": now + timedelta(minutes=30),
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return ImportJobRecord(**fields)


def _deadline(seconds: float = 45.0) -> Deadline:
    return Deadline.start(seconds)


def _json_response(payload, status=200):
    return httpx.Response(
        status, json=payload, headers={"content-type": "application/json"}
    )


def _preflight_response(request: httpx.Request):
    if request.url.path == "/v2/users/me":
        return _json_response(
            {
                "data": {
                    "isPaying": False,
                    "plan": {
                        "tier": "FREE",
                        "isEnabled": True,
                        "monthlyBasePriceUsd": 0,
                        "monthlyUsageCreditsUsd": 5,
                        "maxMonthlyUsageUsd": 5,
                    },
                }
            }
        )
    if request.url.path == "/v2/users/me/limits":
        return _json_response(
            {"data": {"limits": {"maxMonthlyUsageUsd": 5}, "current": {"monthlyUsageUsd": 1}}}
        )
    if request.url.path == "/v2/users/me/usage/monthly":
        return _json_response({"data": {"totalUsageCreditsUsdAfterVolumeDiscount": 1}})
    return None


class _ApifyScript:
    """Routes Apify calls by path; unhandled paths raise AssertionError."""

    def __init__(self, **handlers):
        self.handlers = handlers
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request):
        self.calls.append(request.url.path)
        if response := _preflight_response(request):
            return response
        for pattern, handler in self.handlers.items():
            if pattern in request.url.path:
                return handler(request)
        raise AssertionError(f"unscripted Apify call: {request.url.path}")


def _run_response(run_id="runreel1", status="SUCCEEDED", dataset_id="dataset1"):
    body = {"id": run_id, "status": status}
    if dataset_id is not None:
        body["defaultDatasetId"] = dataset_id
    return _json_response({"data": body}, 201)


def _reel_dataset_response(
    *, shortcode="DZuzc9PNedT", caption="Raspberry Chia Pudding recipe: 1 cup chia, mix well.",
    owner="creator.name",
):
    return _json_response(
        [
            {
                "shortCode": shortcode,
                "url": f"https://www.instagram.com/reel/{shortcode}/",
                "caption": caption,
                "displayUrl": "https://cdn.example/reel.jpg",
                "ownerUsername": owner,
            }
        ]
    )


def _profile_dataset_response(*, username="creator.name", private=False, external_urls=None):
    return _json_response(
        [
            {
                "username": username,
                "private": private,
                "externalUrl": (external_urls or [None])[0],
                "externalUrls": [
                    {"url": u} for u in (external_urls or [])[1:]
                ],
            }
        ]
    )


def _parsed(**overrides) -> ParsedCaption:
    fields = dict(
        raw_recipe={},
        ingredients=[],
        instructions=[],
        is_complete=False,
        parse_status="not_recipe",
        parse_reason=None,
        candidate_name=None,
        has_explicit_instructions=False,
    )
    fields.update(overrides)
    return ParsedCaption(**fields)


def _complete_parsed(name="Raspberry Chia Pudding") -> ParsedCaption:
    return _parsed(
        raw_recipe={
            "@type": "Recipe",
            "name": name,
            "recipeIngredient": ["1 cup chia seeds", "1 cup milk"],
            "recipeInstructions": ["Mix well.", "Chill overnight."],
        },
        ingredients=["1 cup chia seeds", "1 cup milk"],
        instructions=["Mix well.", "Chill overnight."],
        is_complete=True,
        parse_status="recipe",
        candidate_name=name,
        has_explicit_instructions=True,
    )


async def _fake_gemini(**kwargs):
    return kwargs["_result"]


def _gemini_deps(result: ParsedCaption, **extra) -> OrchestrationDeps:
    async def _parse(**kwargs):
        return result

    return OrchestrationDeps(gemini_parse=_parse, **extra)


def _run_advance(job, deps=None, deadline=None):
    with (
        patch("app.services.instagram.import_job.get_settings", return_value=_settings()),
    ):
        return asyncio.run(
            advance_instagram_job(job, deadline=deadline or _deadline(), deps=deps)
        )


# --- queued -------------------------------------------------------------------


def test_queued_short_circuits_when_recipe_already_saved():
    job = _job()
    existing = {
        "id": "recipe-99",
        "submitted_url": CANONICAL_URL,
        "final_url": CANONICAL_URL,
        "page_title": "Chia Pudding",
        "image_url": "https://cdn.example/x.jpg",
        "recipes_json": [
            {"name": "Chia Pudding", "ingredients": ["1 cup chia"], "instructions": ["Mix."]}
        ],
        "linked_recipe_url": None,
    }

    with (
        patch(
            "app.services.instagram.import_job.find_existing_recipe_by_canonical_url",
            return_value=existing,
        ),
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.reserve_provider_admission") as reserve,
    ):
        checkpoint.return_value = job.model_copy(
            update={"state": ImportJobState.SUCCEEDED, "recipe_id": "recipe-99"}
        )
        result = _run_advance(job)

    assert result.state == ImportJobState.SUCCEEDED
    reserve.assert_not_called()
    assert checkpoint.call_args.kwargs["state"] == "succeeded"
    assert checkpoint.call_args.kwargs["recipe_id"] == "recipe-99"


def test_queued_stays_queued_when_admission_busy():
    job = _job()

    with (
        patch(
            "app.services.instagram.import_job.find_existing_recipe_by_canonical_url",
            return_value=None,
        ),
        patch(
            "app.services.instagram.import_job.reserve_provider_admission",
            return_value=False,
        ),
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
    ):
        checkpoint.return_value = job
        result = _run_advance(job)

    assert result.state == ImportJobState.QUEUED
    assert checkpoint.call_args.kwargs["state"] == "queued"


def test_queued_fails_resolution_timeout_when_no_budget():
    job = _job()

    with (
        patch(
            "app.services.instagram.import_job.find_existing_recipe_by_canonical_url",
            return_value=None,
        ),
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission") as release,
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        result = _run_advance(job, deadline=Deadline.start(1.0, persistence_reserve_seconds=5.0))

    assert checkpoint.call_args.kwargs["error_code"] == "resolution_timeout"
    release.assert_not_called()


def test_queued_starts_reel_actor_and_checkpoints_waiting_reel():
    job = _job()
    script = _ApifyScript(
        **{f"/actors/{REEL_ACTOR_ID}/runs": lambda r: _run_response()},
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(
            update={"state": ImportJobState(kwargs["state"]), "version": job.version + len(checkpoints)}
        )

    with (
        patch(
            "app.services.instagram.import_job.find_existing_recipe_by_canonical_url",
            return_value=None,
        ),
        patch(
            "app.services.instagram.import_job.reserve_provider_admission",
            return_value=True,
        ),
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
    ):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert [c["state"] for c in checkpoints] == ["starting_reel", "waiting_reel"]
    assert checkpoints[-1]["reel_run_id"] == "runreel1"
    assert result.state == ImportJobState.WAITING_REEL


def test_queued_actor_start_failure_is_ambiguous_and_keeps_admission():
    job = _job()

    def _explode(_request):
        raise httpx.ConnectError("boom", request=_request)

    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with (
        patch(
            "app.services.instagram.import_job.find_existing_recipe_by_canonical_url",
            return_value=None,
        ),
        patch(
            "app.services.instagram.import_job.reserve_provider_admission",
            return_value=True,
        ),
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
        patch("app.services.instagram.import_job.release_provider_admission") as release,
    ):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(_explode))
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["error_code"] == "ambiguous_external_operation"
    release.assert_not_called()
    assert result.state == ImportJobState.FAILED


# --- stale intent states ------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [ImportJobState.STARTING_REEL, ImportJobState.STARTING_PROFILE],
)
def test_stale_intent_states_are_always_ambiguous(state):
    job = _job(state=state)

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission") as release,
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        result = _run_advance(job)

    assert checkpoint.call_args.kwargs["error_code"] == "ambiguous_external_operation"
    # An ambiguous Actor/Gemini-call outcome keeps its provider admission
    # reserved for stale cleanup rather than releasing it (KTD17): another
    # job must not be able to start a second concurrent Actor run while this
    # one might still be in flight server-side.
    release.assert_not_called()
    assert result.state == ImportJobState.FAILED


def test_parsing_caption_resumes_after_a_crash_instead_of_failing_ambiguous():
    # Unlike the states above, PARSING_CAPTION follows no paid Apify run --
    # only a persisted, already-complete reel_dataset_id and a Gemini call
    # with no side effect. A crash here must retry, not die as ambiguous.
    job = _job(state=ImportJobState.PARSING_CAPTION, reel_dataset_id="dataset1")
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response()}
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint):
        deps = _gemini_deps(_complete_parsed(), apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "saving"
    assert result.state == ImportJobState.SAVING


# --- waiting_reel --------------------------------------------------------------


def test_waiting_reel_stays_pending_while_actor_runs():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{f"/actor-runs/runreel1": lambda r: _run_response(status="RUNNING")}
    )

    with patch("app.services.instagram.import_job.checkpoint_job") as checkpoint:
        checkpoint.return_value = job
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["state"] == "waiting_reel"
    assert result.state == ImportJobState.WAITING_REEL


def test_waiting_reel_fails_instagram_unavailable_when_actor_run_fails():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{"/actor-runs/runreel1": lambda r: _run_response(status="FAILED", dataset_id=None)}
    )

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["error_code"] == "instagram_unavailable"


def test_waiting_reel_complete_caption_goes_straight_to_saving():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{
            "/actor-runs/runreel1": lambda r: _run_response(),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
        }
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint):
        deps = _gemini_deps(_complete_parsed(), apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert [c["state"] for c in checkpoints] == ["parsing_caption", "saving"]
    payload = checkpoints[-1]["normalized_result_json"]
    assert payload["recipes"][0]["name"] == "Raspberry Chia Pudding"
    assert result.state == ImportJobState.SAVING


def test_waiting_reel_incomplete_caption_without_name_is_not_recipe():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{
            "/actor-runs/runreel1": lambda r: _run_response(),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
        }
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with (
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
        patch("app.services.instagram.import_job.release_provider_admission"),
    ):
        deps = _gemini_deps(_parsed(), apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "not_recipe"
    assert result.state == ImportJobState.NOT_RECIPE


def test_waiting_reel_incomplete_with_name_moves_to_resolving_recipe():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{
            "/actor-runs/runreel1": lambda r: _run_response(),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
        }
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint):
        deps = _gemini_deps(
            _parsed(candidate_name="Raspberry Chia Pudding"),
            apify_transport=httpx.MockTransport(script),
        )
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "resolving_recipe"
    assert checkpoints[-1]["candidate_name"] == "Raspberry Chia Pudding"
    assert result.state == ImportJobState.RESOLVING_RECIPE


def test_waiting_reel_maps_gemini_timeout_to_provider_timeout():
    job = _job(state=ImportJobState.WAITING_REEL, reel_run_id="runreel1")
    script = _ApifyScript(
        **{
            "/actor-runs/runreel1": lambda r: _run_response(),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
        }
    )

    async def _raise_timeout(**kwargs):
        raise HTTPException(status_code=504, detail="timeout")

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(
            gemini_parse=_raise_timeout, apify_transport=httpx.MockTransport(script)
        )
        _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["error_code"] == "provider_timeout"


# --- resolving_recipe ----------------------------------------------------------


def test_resolving_recipe_matches_caption_link_and_moves_to_saving():
    job = _job(
        state=ImportJobState.RESOLVING_RECIPE,
        reel_dataset_id="dataset1",
        candidate_name="Raspberry Chia Pudding",
    )
    script = _ApifyScript(
        **{
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(
                caption="Full recipe here: https://tasty.co/recipe/raspberry-chia-pudding"
            ),
        }
    )

    async def _fetch_html_page_stub(url, _deps, _deadline):
        return FetchedPage(
            final_url=url,
            html=(
                '<html><head><script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"Recipe",'
                '"name":"Raspberry Chia Pudding","recipeIngredient":["1 cup chia"],'
                '"recipeInstructions":["Mix well."]}'
                "</script></head><body></body></html>"
            ),
        )

    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        with patch(
            "app.services.instagram.import_job._fetch_html_page",
            side_effect=_fetch_html_page_stub,
        ):
            result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "saving"
    assert checkpoints[-1]["linked_recipe_url"] == (
        "https://tasty.co/recipe/raspberry-chia-pudding"
    )
    assert result.state == ImportJobState.SAVING


def test_resolving_recipe_no_link_match_starts_profile():
    job = _job(
        state=ImportJobState.RESOLVING_RECIPE,
        reel_dataset_id="dataset1",
        candidate_name="Miso Salmon Rice",
    )
    script = _ApifyScript(
        **{
            "/datasets/dataset1/items": lambda r: (
                _reel_dataset_response(caption="Comment for the recipe!")
                if "reel" not in ""
                else None
            ),
            f"/actors/{PROFILE_ACTOR_ID}/runs": lambda r: _run_response(
                run_id="runprofile1", status="RUNNING", dataset_id=None
            ),
        }
    )
    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with (
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
        patch(
            "app.services.instagram.import_job.reserve_provider_admission",
            return_value=True,
        ),
    ):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert [c["state"] for c in checkpoints] == ["starting_profile", "waiting_profile"]
    assert checkpoints[-1]["profile_run_id"] == "runprofile1"
    assert result.state == ImportJobState.WAITING_PROFILE


def test_resolving_recipe_stays_put_when_profile_admission_busy():
    job = _job(
        state=ImportJobState.RESOLVING_RECIPE,
        reel_dataset_id="dataset1",
        candidate_name="Miso Salmon Rice",
    )
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response(caption="no links here")}
    )

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch(
            "app.services.instagram.import_job.reserve_provider_admission",
            return_value=False,
        ),
    ):
        checkpoint.return_value = job
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["state"] == "resolving_recipe"
    assert result.state == ImportJobState.RESOLVING_RECIPE


# --- waiting_profile -------------------------------------------------------------


def test_waiting_profile_private_profile_is_not_recipe():
    job = _job(
        state=ImportJobState.WAITING_PROFILE,
        profile_run_id="runprofile1",
        reel_dataset_id="dataset1",
        candidate_name="Miso Salmon Rice",
    )
    script = _ApifyScript(
        **{
            "/actor-runs/runprofile1": lambda r: _run_response(
                run_id="runprofile1", dataset_id="profiledataset1"
            ),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
            "/datasets/profiledataset1/items": lambda r: _profile_dataset_response(
                private=True
            ),
        }
    )

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.NOT_RECIPE})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["state"] == "not_recipe"
    assert result.state == ImportJobState.NOT_RECIPE


def test_waiting_profile_creator_site_match_moves_to_saving():
    job = _job(
        state=ImportJobState.WAITING_PROFILE,
        profile_run_id="runprofile1",
        reel_dataset_id="dataset1",
        candidate_name="Miso Salmon Rice",
    )
    script = _ApifyScript(
        **{
            "/actor-runs/runprofile1": lambda r: _run_response(
                run_id="runprofile1", dataset_id="profiledataset1"
            ),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
            "/datasets/profiledataset1/items": lambda r: _profile_dataset_response(
                external_urls=["https://tasty.co/"]
            ),
        }
    )

    async def _fake_find_creator_site_recipe(*_args, **_kwargs):
        from app.services.extraction_types import ExtractionResult

        return ExtractionResult(
            source_url="https://tasty.co/recipe/miso-salmon-rice",
            final_url="https://tasty.co/recipe/miso-salmon-rice",
            title="Miso Salmon Rice",
            image_url=None,
            recipe_node_count=1,
            recipes=[
                NormalizedRecipe(
                    name="Miso Salmon Rice",
                    ingredients=["1 cup rice"],
                    instructions=["Cook rice."],
                )
            ],
        )

    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with (
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
        patch(
            "app.services.instagram.import_job.find_creator_site_recipe",
            side_effect=_fake_find_creator_site_recipe,
        ),
    ):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "saving"
    assert checkpoints[-1]["linked_recipe_url"] == "https://tasty.co/recipe/miso-salmon-rice"
    assert result.state == ImportJobState.SAVING


def test_waiting_profile_no_creator_site_match_is_not_recipe():
    job = _job(
        state=ImportJobState.WAITING_PROFILE,
        profile_run_id="runprofile1",
        reel_dataset_id="dataset1",
        candidate_name="Miso Salmon Rice",
    )
    script = _ApifyScript(
        **{
            "/actor-runs/runprofile1": lambda r: _run_response(
                run_id="runprofile1", dataset_id="profiledataset1"
            ),
            "/datasets/dataset1/items": lambda r: _reel_dataset_response(),
            "/datasets/profiledataset1/items": lambda r: _profile_dataset_response(
                external_urls=["https://tasty.co/"]
            ),
        }
    )

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
        patch(
            "app.services.instagram.import_job.find_creator_site_recipe",
            return_value=None,
        ),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.NOT_RECIPE})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["state"] == "not_recipe"
    assert result.state == ImportJobState.NOT_RECIPE


# --- saving ----------------------------------------------------------------------


def test_saving_fails_resolution_timeout_when_no_budget_before_any_side_effect():
    job = _job(
        state=ImportJobState.SAVING,
        reel_dataset_id="dataset1",
        normalized_result_json={
            "source_url": CANONICAL_URL,
            "final_url": CANONICAL_URL,
            "title": "Raspberry Chia Pudding",
            "image_url": None,
            "recipes": [
                {
                    "name": "Raspberry Chia Pudding",
                    "ingredients": ["1 cup chia"],
                    "instructions": ["Mix well."],
                }
            ],
            "database_saved": False,
            "database_message": "",
            "parse_status": "recipe",
        },
    )

    def _explode(_request):
        raise AssertionError("no Apify call should happen when budget is exhausted")

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(_explode))
        result = _run_advance(
            job, deps=deps,
            deadline=Deadline.start(1.0, persistence_reserve_seconds=5.0),
        )

    assert checkpoint.call_args.kwargs["error_code"] == "resolution_timeout"
    assert result.state == ImportJobState.FAILED


def test_saving_success_checkpoints_succeeded_and_releases_admission():
    recipe_payload = {
        "name": "Raspberry Chia Pudding",
        "ingredients": ["1 cup chia"],
        "instructions": ["Mix well."],
    }
    job = _job(
        state=ImportJobState.SAVING,
        reel_dataset_id="dataset1",
        normalized_result_json={
            "source_url": CANONICAL_URL,
            "final_url": CANONICAL_URL,
            "title": "Raspberry Chia Pudding",
            "image_url": None,
            "recipes": [recipe_payload],
            "database_saved": False,
            "database_message": "",
            "parse_status": "recipe",
        },
    )
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response()}
    )

    async def _fetch_image(url, policy, **kwargs):
        from app.services.public_web import SafeFetchResult

        return SafeFetchResult(
            requested_url=url, final_url=url, status_code=200,
            content_type="image/jpeg", body=b"jpeg-bytes",
        )

    from app.services.social.thumbnail_storage import MirroredSocialThumbnail

    async def _fake_save(**kwargs):
        from app.repositories.recipe_imports import SaveRecipeImportResult

        return SaveRecipeImportResult(
            saved=True, message="ok", image_url="https://cdn.example/instagram/job-1/x.jpg",
            id="recipe-abc",
        )

    checkpoints: list[dict] = []

    def _checkpoint(*_args, **kwargs):
        checkpoints.append(kwargs)
        return job.model_copy(update={"state": ImportJobState(kwargs["state"])})

    with (
        patch("app.services.instagram.import_job.checkpoint_job", side_effect=_checkpoint),
        patch("app.services.instagram.import_job.release_provider_admission") as release,
        patch("app.services.instagram.import_job.safe_fetch", side_effect=_fetch_image),
        patch(
            "app.services.instagram.import_job.store_social_thumbnail",
            return_value=MirroredSocialThumbnail(
                image_url="https://cdn.example/instagram/job-1/x.jpg",
                storage_path="instagram/job-1/x.jpg",
            ),
        ),
        patch("app.services.instagram.import_job.save_recipe_import", side_effect=_fake_save),
    ):
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoints[-1]["state"] == "succeeded"
    assert checkpoints[-1]["recipe_id"] == "recipe-abc"
    release.assert_called_once_with("job-1")
    assert result.state == ImportJobState.SUCCEEDED


def test_saving_failure_when_save_recipe_import_does_not_save():
    recipe_payload = {
        "name": "Raspberry Chia Pudding",
        "ingredients": ["1 cup chia"],
        "instructions": ["Mix well."],
    }
    job = _job(
        state=ImportJobState.SAVING,
        reel_dataset_id="dataset1",
        normalized_result_json={
            "source_url": CANONICAL_URL,
            "final_url": CANONICAL_URL,
            "title": "Raspberry Chia Pudding",
            "image_url": None,
            "recipes": [recipe_payload],
            "database_saved": False,
            "database_message": "",
            "parse_status": "recipe",
        },
    )
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response()}
    )

    async def _fetch_image(url, policy, **kwargs):
        from app.services.public_web import SafeFetchResult

        return SafeFetchResult(
            requested_url=url, final_url=url, status_code=200,
            content_type="image/jpeg", body=b"jpeg-bytes",
        )

    from app.services.social.thumbnail_storage import MirroredSocialThumbnail

    async def _fake_save(**kwargs):
        from app.repositories.recipe_imports import SaveRecipeImportResult

        return SaveRecipeImportResult(saved=False, message="failed", image_url=None)

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
        patch("app.services.instagram.import_job.safe_fetch", side_effect=_fetch_image),
        patch(
            "app.services.instagram.import_job.store_social_thumbnail",
            return_value=MirroredSocialThumbnail(
                image_url="https://cdn.example/instagram/job-1/x.jpg",
                storage_path="instagram/job-1/x.jpg",
            ),
        ),
        patch("app.services.instagram.import_job.save_recipe_import", side_effect=_fake_save),
        patch(
            "app.services.instagram.import_job.delete_social_thumbnail"
        ) as delete_thumbnail,
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["error_code"] == "save_failed"
    assert result.state == ImportJobState.FAILED
    # The thumbnail was uploaded before the save failed -- it must not be
    # left orphaned in storage.
    delete_thumbnail.assert_called_once_with(
        "instagram/job-1/x.jpg", settings=delete_thumbnail.call_args.kwargs["settings"]
    )


def test_saving_failure_cleans_up_thumbnail_when_recipe_payload_is_missing():
    job = _job(
        state=ImportJobState.SAVING,
        reel_dataset_id="dataset1",
        normalized_result_json={
            "source_url": CANONICAL_URL,
            "final_url": CANONICAL_URL,
            "title": "Raspberry Chia Pudding",
            "image_url": None,
            "recipes": [],
            "database_saved": False,
            "database_message": "",
            "parse_status": "recipe",
        },
    )
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response()}
    )

    async def _fetch_image(url, policy, **kwargs):
        from app.services.public_web import SafeFetchResult

        return SafeFetchResult(
            requested_url=url, final_url=url, status_code=200,
            content_type="image/jpeg", body=b"jpeg-bytes",
        )

    from app.services.social.thumbnail_storage import MirroredSocialThumbnail

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
        patch("app.services.instagram.import_job.safe_fetch", side_effect=_fetch_image),
        patch(
            "app.services.instagram.import_job.store_social_thumbnail",
            return_value=MirroredSocialThumbnail(
                image_url="https://cdn.example/instagram/job-1/x.jpg",
                storage_path="instagram/job-1/x.jpg",
            ),
        ),
        patch(
            "app.services.instagram.import_job.delete_social_thumbnail"
        ) as delete_thumbnail,
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["error_code"] == "save_failed"
    assert result.state == ImportJobState.FAILED
    delete_thumbnail.assert_called_once_with(
        "instagram/job-1/x.jpg", settings=delete_thumbnail.call_args.kwargs["settings"]
    )


def test_saving_failure_when_thumbnail_download_fails():
    job = _job(
        state=ImportJobState.SAVING,
        reel_dataset_id="dataset1",
        normalized_result_json={
            "source_url": CANONICAL_URL,
            "final_url": CANONICAL_URL,
            "title": "Raspberry Chia Pudding",
            "image_url": None,
            "recipes": [
                {
                    "name": "Raspberry Chia Pudding",
                    "ingredients": ["1 cup chia"],
                    "instructions": ["Mix well."],
                }
            ],
            "database_saved": False,
            "database_message": "",
            "parse_status": "recipe",
        },
    )
    script = _ApifyScript(
        **{"/datasets/dataset1/items": lambda r: _reel_dataset_response()}
    )

    async def _explode(*_args, **_kwargs):
        raise PublicWebError("thumbnail unreachable")

    with (
        patch("app.services.instagram.import_job.checkpoint_job") as checkpoint,
        patch("app.services.instagram.import_job.release_provider_admission"),
        patch("app.services.instagram.import_job.safe_fetch", side_effect=_explode),
    ):
        checkpoint.return_value = job.model_copy(update={"state": ImportJobState.FAILED})
        deps = OrchestrationDeps(apify_transport=httpx.MockTransport(script))
        result = _run_advance(job, deps=deps)

    assert checkpoint.call_args.kwargs["error_code"] == "save_failed"
    assert result.state == ImportJobState.FAILED
