from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx
from fastapi import HTTPException

from ...core.config import Settings, get_settings
from ...repositories.import_jobs import (
    ImportJobStorageError,
    checkpoint_job,
    find_existing_recipe_by_canonical_url,
    reconcile_provider_admission,
    reserve_provider_admission,
    release_provider_admission,
)
from ...repositories.recipe_imports import save_recipe_import
from ...schemas.extract import ExtractResponse, NormalizedRecipe
from ...schemas.import_jobs import ImportJobErrorCode, ImportJobRecord, ImportJobState
from ..blog.extractor import parse_recipes_from_html
from ..gemini.recipe_parser import ParsedCaption, parse_caption_with_gemini
from ..normalizer import normalize_recipe
from ..public_web import HTML_POLICY, IMAGE_POLICY, PublicWebError, safe_fetch
from ..recipe_match import RecipeCandidate, select_unique_match
from ..social.caption_recipe import MAX_CAPTION_LINKS
from ..social.recipe_links import extract_ranked_recipe_urls
from ..social.thumbnail_storage import (
    SocialThumbnailStorageError,
    delete_social_thumbnail,
    store_social_thumbnail,
)
from .apify import (
    PROFILE_MAX_CHARGE_USD,
    REEL_MAX_CHARGE_USD,
    ApifyClient,
)
from .creator_site_lookup import FetchedPage, find_creator_site_recipe
from .models import ApifyProviderError, ApifyRunStatus, InstagramReelMetadata
from .urls import InstagramReelIdentity, InstagramUrlError, parse_instagram_reel_url
from ..import_deadline import Deadline, DeadlineExceededError


POLL_RETRY_SECONDS = 7
STALE_WINDOW_SECONDS = 30 * 60
# How long past an Actor's own timeout a held admission slot must sit before
# another job may reclaim it. The slot is only ever reclaimed from a *terminal*
# holder; this grace keeps the fail-closed promise that no second run starts
# while the first one could still be executing server-side.
ADMISSION_RECLAIM_GRACE_SECONDS = 60
NOT_RECIPE_MESSAGE = (
    "Moonbites could not find one complete, confidently matching recipe."
)
SAVE_SUCCESS_MESSAGE = "Recipe saved to your collection."

logger = logging.getLogger(__name__)


class OrchestrationHalted(RuntimeError):
    """Internal control-flow signal: the lease/version CAS was lost mid-advance."""


@dataclass
class OrchestrationDeps:
    apify_transport: Optional[httpx.AsyncBaseTransport] = None
    safe_fetch_transport: Optional[httpx.AsyncBaseTransport] = None
    safe_fetch_resolver: Optional[Callable[[str, int], Awaitable[list[str]]]] = None
    gemini_parse: Callable[..., Awaitable[ParsedCaption]] = parse_caption_with_gemini


def _identity(job: ImportJobRecord) -> InstagramReelIdentity:
    try:
        return parse_instagram_reel_url(job.canonical_reel_url)
    except InstagramUrlError as error:
        raise RuntimeError(
            f"Job {job.id} holds a non-canonical Instagram URL"
        ) from error


def _apify_client(settings: Settings, deps: OrchestrationDeps) -> ApifyClient:
    return ApifyClient(settings, transport=deps.apify_transport)


async def _fetch_html_page(url: str, deps: OrchestrationDeps, deadline: Deadline) -> FetchedPage:
    kwargs: dict[str, Any] = {
        "deadline_seconds": max(1.0, min(15.0, deadline.budget_for_side_effect())),
        "transport": deps.safe_fetch_transport,
    }
    if deps.safe_fetch_resolver is not None:
        kwargs["resolver"] = deps.safe_fetch_resolver
    result = await safe_fetch(url, HTML_POLICY, **kwargs)
    return FetchedPage(
        final_url=result.final_url, html=result.body.decode("utf-8", errors="replace")
    )


def _not_recipe_result(identity: InstagramReelIdentity) -> dict:
    return ExtractResponse(
        source_url=identity.canonical_url,
        final_url=identity.canonical_url,
        title=None,
        image_url=None,
        recipes=[],
        database_saved=False,
        database_message="Skipped — not a recipe.",
        parse_status="not_recipe",
        parse_reason=NOT_RECIPE_MESSAGE,
        linked_recipe_url=None,
    ).model_dump(mode="json")


def _resolved_result(
    identity: InstagramReelIdentity, recipe, *, linked_recipe_url: Optional[str]
) -> dict:
    return ExtractResponse(
        source_url=identity.canonical_url,
        final_url=identity.canonical_url,
        title=recipe.name,
        image_url=None,
        recipes=[recipe],
        database_saved=False,
        database_message="",
        parse_status="recipe",
        parse_reason=None,
        linked_recipe_url=linked_recipe_url,
    ).model_dump(mode="json")


def _map_apify_error(error: ApifyProviderError) -> ImportJobErrorCode:
    return ImportJobErrorCode(error.code.value)


def _map_gemini_error(error: HTTPException) -> ImportJobErrorCode:
    if error.status_code == 504:
        return ImportJobErrorCode.PROVIDER_TIMEOUT
    if error.status_code == 502:
        return ImportJobErrorCode.PROVIDER_INVALID_RESPONSE
    return ImportJobErrorCode.PROVIDER_UNAVAILABLE


def _require(job: Optional[ImportJobRecord]) -> ImportJobRecord:
    if job is None:
        raise OrchestrationHalted("Lost the job lease mid-advance.")
    return job


async def _checkpoint(
    job: ImportJobRecord,
    *,
    state: ImportJobState,
    reel_run_id: Optional[str] = None,
    reel_dataset_id: Optional[str] = None,
    profile_run_id: Optional[str] = None,
    profile_dataset_id: Optional[str] = None,
    candidate_name: Optional[str] = None,
    normalized_result_json: Optional[dict] = None,
    linked_recipe_url: Optional[str] = None,
    recipe_id: Optional[str] = None,
    error_code: Optional[ImportJobErrorCode] = None,
    next_advance_seconds: int = 0,
    release_lease: bool = False,
) -> ImportJobRecord:
    assert job.lease_token is not None
    updated = checkpoint_job(
        job.id,
        job.lease_token,
        job.version,
        state=state.value,
        reel_run_id=reel_run_id,
        reel_dataset_id=reel_dataset_id,
        profile_run_id=profile_run_id,
        profile_dataset_id=profile_dataset_id,
        candidate_name=candidate_name,
        normalized_result_json=normalized_result_json,
        linked_recipe_url=linked_recipe_url,
        recipe_id=recipe_id,
        error_code=error_code.value if error_code else None,
        next_advance_seconds=next_advance_seconds,
        stale_window_seconds=STALE_WINDOW_SECONDS,
        release_lease=release_lease,
    )
    return _require(updated)


def _cleanup_orphaned_thumbnail(storage_path: Optional[str], settings: Settings) -> None:
    """Best-effort delete of a thumbnail mirrored just before a save that failed.

    A failed cleanup here must not change the job's own failure outcome, so
    it only logs -- the periodic thumbnail audit remains the backstop for
    whatever this misses.
    """
    if storage_path is None:
        return
    try:
        delete_social_thumbnail(storage_path, settings=settings)
    except SocialThumbnailStorageError:
        logger.warning(
            "Failed to clean up orphaned Instagram thumbnail %s after a failed save.",
            storage_path,
        )


def _reserve_with_reclaim(
    job_id: str,
    run_kind: str,
    max_charge_usd: float,
    *,
    actor_timeout_seconds: float,
) -> bool:
    """Reserve the singleton admission slot, reclaiming a dead one if needed.

    A job that crashed or failed ambiguously at its intent checkpoint keeps
    the slot reserved on purpose, so without this every later import would
    queue behind it forever. Reclaim is limited to holders that are already
    terminal *and* older than the Actor timeout plus a grace window.
    """
    if reserve_provider_admission(job_id, run_kind, max_charge_usd):
        return True

    reclaim_after = int(actor_timeout_seconds) + ADMISSION_RECLAIM_GRACE_SECONDS
    try:
        reclaimed = reconcile_provider_admission(
            dry_run=False, min_age_seconds=reclaim_after
        )
    except ImportJobStorageError:
        # Reclaim is opportunistic; a storage failure just leaves the job
        # queued for its next poll rather than failing the advance.
        logger.warning("Could not reconcile the provider admission slot for %s.", job_id)
        return False
    if not reclaimed:
        return False

    logger.warning(
        "Job %s reclaimed a stale Instagram provider admission slot "
        "(%d) held by a terminal job for over %ss.",
        job_id,
        len(reclaimed),
        reclaim_after,
    )
    return reserve_provider_admission(job_id, run_kind, max_charge_usd)


async def _fail(
    job: ImportJobRecord, error_code: ImportJobErrorCode, *, release_admission: bool = True
) -> ImportJobRecord:
    # The admission slot is released *before* the terminal checkpoint: if the
    # checkpoint were to fail afterwards the release would never run and the
    # slot would leak, wedging every later import. Freeing it early is the
    # safe direction -- the slot is keyed on this job id, so the worst case is
    # an already-free slot for a job that then retries.
    if release_admission:
        try:
            release_provider_admission(job.id)
        except ImportJobStorageError:
            logger.warning(
                "Could not release the provider admission slot for job %s.", job.id
            )
    return await _checkpoint(
        job, state=ImportJobState.FAILED, error_code=error_code, release_lease=True
    )


async def _not_recipe(job: ImportJobRecord, identity: InstagramReelIdentity) -> ImportJobRecord:
    updated = await _checkpoint(
        job,
        state=ImportJobState.NOT_RECIPE,
        normalized_result_json=_not_recipe_result(identity),
        release_lease=True,
    )
    release_provider_admission(job.id)
    return updated


# --- state handlers ----------------------------------------------------------


async def _handle_queued(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    identity = _identity(job)

    existing = find_existing_recipe_by_canonical_url(identity.canonical_url)
    if existing is not None:
        recipes = existing.get("recipes_json") or []
        return await _checkpoint(
            job,
            state=ImportJobState.SUCCEEDED,
            recipe_id=existing.get("id"),
            normalized_result_json=ExtractResponse(
                source_url=existing.get("submitted_url") or identity.canonical_url,
                final_url=existing.get("final_url") or identity.canonical_url,
                title=existing.get("page_title"),
                image_url=existing.get("image_url"),
                recipes=recipes,
                database_saved=True,
                database_message=SAVE_SUCCESS_MESSAGE,
                parse_status="recipe",
                linked_recipe_url=existing.get("linked_recipe_url"),
            ).model_dump(mode="json"),
            release_lease=True,
        )

    if not deadline.has_budget_for_side_effect():
        return await _fail(
            job, ImportJobErrorCode.RESOLUTION_TIMEOUT, release_admission=False
        )

    settings = get_settings()
    if not _reserve_with_reclaim(
        job.id,
        "reel",
        float(REEL_MAX_CHARGE_USD),
        actor_timeout_seconds=settings.instagram_reel_actor_timeout_seconds,
    ):
        return await _checkpoint(
            job, state=ImportJobState.QUEUED, next_advance_seconds=POLL_RETRY_SECONDS,
            release_lease=True,
        )

    # Everything up to the run-creating POST is side-effect free: building the
    # client only validates configuration, and the spend preflight is three
    # read-only GETs. Failing here charged nothing and started nothing, so the
    # admission slot is released rather than burned.
    try:
        client = _apify_client(settings, deps)
        await client.preflight_spend()
    except ApifyProviderError as error:
        logger.warning(
            "Instagram job %s could not start a reel run: %s", job.id, error.code.value
        )
        return await _fail(job, _map_apify_error(error))
    except Exception:
        logger.exception("Instagram job %s hit an unexpected reel preflight failure", job.id)
        return await _fail(job, ImportJobErrorCode.PROVIDER_UNAVAILABLE)

    job = await _checkpoint(job, state=ImportJobState.STARTING_REEL)

    try:
        run = await client.start_reel(identity, preflighted=True)
    except Exception:
        logger.exception(
            "Instagram job %s left the reel Actor start ambiguous; holding admission",
            job.id,
        )
        return await _fail(
            job, ImportJobErrorCode.AMBIGUOUS_EXTERNAL_OPERATION, release_admission=False
        )

    return await _checkpoint(
        job,
        state=ImportJobState.WAITING_REEL,
        reel_run_id=run.run_id,
        next_advance_seconds=POLL_RETRY_SECONDS,
        release_lease=True,
    )


async def _handle_stale_intent_state(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    """A crash between the intent checkpoint and its result checkpoint leaves
    the job here; the external operation's outcome is unknown, so this is
    always terminal -- it is never re-entered as a fresh transition. Any
    provider admission this job holds is left reserved for stale cleanup
    rather than released, since an Actor may genuinely have started. The
    reclaim path in `_reserve_with_reclaim` is what eventually frees it."""
    logger.warning(
        "Instagram job %s resumed in intent state %s; terminalizing as ambiguous.",
        job.id,
        job.state.value,
    )
    return await _fail(
        job, ImportJobErrorCode.AMBIGUOUS_EXTERNAL_OPERATION, release_admission=False
    )


async def _resolve_caption_links(
    job: ImportJobRecord,
    identity: InstagramReelIdentity,
    caption: str,
    candidate_name: str,
    *,
    deadline: Deadline,
    deps: OrchestrationDeps,
) -> tuple[Optional[RecipeCandidate], bool]:
    """Returns (match, timed_out)."""
    links = extract_ranked_recipe_urls(caption)[:MAX_CAPTION_LINKS]
    if not links:
        return None, False

    candidates: list[RecipeCandidate] = []
    for link in links:
        if not deadline.has_budget_for_side_effect():
            return None, True
        try:
            page = await _fetch_html_page(link, deps, deadline)
        except PublicWebError:
            continue
        parsed = parse_recipes_from_html(
            page.html, source_url=link, final_url=page.final_url
        )
        for recipe in parsed.recipes:
            candidates.append(
                RecipeCandidate(
                    canonical_url=page.final_url, title=recipe.name, result=parsed
                )
            )

    match = select_unique_match(candidates, candidate_name)
    return match, False


async def _handle_waiting_reel(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    identity = _identity(job)
    settings = get_settings()
    client = _apify_client(settings, deps)

    try:
        run = await client.get_run(job.reel_run_id)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    if run.status in (
        ApifyRunStatus.READY,
        ApifyRunStatus.RUNNING,
        ApifyRunStatus.TIMING_OUT,
        ApifyRunStatus.ABORTING,
    ):
        return await _checkpoint(
            job,
            state=ImportJobState.WAITING_REEL,
            next_advance_seconds=POLL_RETRY_SECONDS,
            release_lease=True,
        )

    if run.status is not ApifyRunStatus.SUCCEEDED:
        return await _fail(job, ImportJobErrorCode.INSTAGRAM_UNAVAILABLE)

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    try:
        reel = await client.get_reel_result(run.default_dataset_id, identity)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    job = await _checkpoint(job, state=ImportJobState.PARSING_CAPTION, reel_dataset_id=run.default_dataset_id)

    return await _handle_parsing_caption(job, deadline=deadline, deps=deps, reel=reel)


async def _handle_parsing_caption(
    job: ImportJobRecord,
    *,
    deadline: Deadline,
    deps: OrchestrationDeps,
    reel: Optional[InstagramReelMetadata] = None,
) -> ImportJobRecord:
    """Parse the reel's caption with Gemini, resuming here after a crash.

    Unlike STARTING_REEL/STARTING_PROFILE, this checkpoint does not follow a
    paid, non-idempotent Apify run -- the reel dataset it reads is already
    persisted as `job.reel_dataset_id`, and Gemini parsing has no side effect.
    A crash here can simply be retried from scratch, so this is not routed
    through `_handle_stale_intent_state`.

    `reel` is already in hand when entered straight from `_handle_waiting_reel`;
    a dispatch-table resume after a crash has no such value and re-fetches it
    from the persisted dataset id.
    """
    identity = _identity(job)
    settings = get_settings()
    client = _apify_client(settings, deps)

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    if reel is None:
        try:
            reel = await client.get_reel_result(job.reel_dataset_id, identity)
        except ApifyProviderError as error:
            return await _fail(job, _map_apify_error(error))

    try:
        parsed = await deps.gemini_parse(
            title="",
            caption=reel.caption or "",
            source_url=identity.canonical_url,
            allow_source_url_instruction_fallback=False,
        )
    except HTTPException as error:
        return await _fail(job, _map_gemini_error(error))

    if parsed.is_complete:
        recipe = normalize_recipe(parsed.raw_recipe)
        if recipe is None:
            return await _not_recipe(job, identity)
        return await _checkpoint(
            job,
            state=ImportJobState.SAVING,
            candidate_name=parsed.candidate_name,
            normalized_result_json=_resolved_result(identity, recipe, linked_recipe_url=None),
            release_lease=True,
        )

    if not parsed.candidate_name:
        return await _not_recipe(job, identity)

    return await _checkpoint(
        job,
        state=ImportJobState.RESOLVING_RECIPE,
        candidate_name=parsed.candidate_name,
        release_lease=True,
    )


async def _handle_resolving_recipe(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    identity = _identity(job)
    settings = get_settings()
    client = _apify_client(settings, deps)

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    try:
        reel = await client.get_reel_result(job.reel_dataset_id, identity)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    match, timed_out = await _resolve_caption_links(
        job, identity, reel.caption or "", job.candidate_name or "",
        deadline=deadline, deps=deps,
    )
    if timed_out:
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    if match is not None:
        recipe = next(r for r in match.result.recipes if r.name == match.title)
        return await _checkpoint(
            job,
            state=ImportJobState.SAVING,
            normalized_result_json=_resolved_result(
                identity, recipe, linked_recipe_url=match.canonical_url
            ),
            linked_recipe_url=match.canonical_url,
            release_lease=True,
        )

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    if not _reserve_with_reclaim(
        job.id,
        "profile",
        float(PROFILE_MAX_CHARGE_USD),
        actor_timeout_seconds=settings.instagram_profile_actor_timeout_seconds,
    ):
        return await _checkpoint(
            job, state=ImportJobState.RESOLVING_RECIPE,
            next_advance_seconds=POLL_RETRY_SECONDS, release_lease=True,
        )

    # Side-effect-free prologue, as in _handle_queued: a preflight failure
    # started no Actor run, so it must not burn the admission slot.
    try:
        await client.preflight_spend()
    except ApifyProviderError as error:
        logger.warning(
            "Instagram job %s could not start a profile run: %s",
            job.id,
            error.code.value,
        )
        return await _fail(job, _map_apify_error(error))
    except Exception:
        logger.exception(
            "Instagram job %s hit an unexpected profile preflight failure", job.id
        )
        return await _fail(job, ImportJobErrorCode.PROVIDER_UNAVAILABLE)

    job = await _checkpoint(job, state=ImportJobState.STARTING_PROFILE)

    try:
        run = await client.start_profile(reel.owner_username, preflighted=True)
    except Exception:
        logger.exception(
            "Instagram job %s left the profile Actor start ambiguous; holding admission",
            job.id,
        )
        return await _fail(
            job, ImportJobErrorCode.AMBIGUOUS_EXTERNAL_OPERATION, release_admission=False
        )

    return await _checkpoint(
        job,
        state=ImportJobState.WAITING_PROFILE,
        profile_run_id=run.run_id,
        next_advance_seconds=POLL_RETRY_SECONDS,
        release_lease=True,
    )


async def _handle_waiting_profile(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    identity = _identity(job)
    settings = get_settings()
    client = _apify_client(settings, deps)

    try:
        run = await client.get_run(job.profile_run_id)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    if run.status in (
        ApifyRunStatus.READY,
        ApifyRunStatus.RUNNING,
        ApifyRunStatus.TIMING_OUT,
        ApifyRunStatus.ABORTING,
    ):
        return await _checkpoint(
            job,
            state=ImportJobState.WAITING_PROFILE,
            next_advance_seconds=POLL_RETRY_SECONDS,
            release_lease=True,
        )

    if run.status is not ApifyRunStatus.SUCCEEDED:
        return await _not_recipe(job, identity)

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    try:
        reel = await client.get_reel_result(job.reel_dataset_id, identity)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    try:
        profile = await client.get_profile_result(
            run.default_dataset_id, reel.owner_username
        )
    except ApifyProviderError as error:
        if error.code.value == ImportJobErrorCode.INSTAGRAM_UNAVAILABLE.value:
            # Private/unavailable profile: an inconclusive resolution, not a
            # provider failure.
            return await _not_recipe(job, identity)
        return await _fail(job, _map_apify_error(error))

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    dish_name = job.candidate_name or ""

    async def _fetch_html(url: str) -> FetchedPage:
        return await _fetch_html_page(url, deps, deadline)

    result = await find_creator_site_recipe(
        profile.external_urls, dish_name, fetch_html=_fetch_html
    )

    if result is None or not result.recipes:
        return await _not_recipe(job, identity)

    recipe = result.recipes[0]
    return await _checkpoint(
        job,
        state=ImportJobState.SAVING,
        normalized_result_json=_resolved_result(
            identity, recipe, linked_recipe_url=result.final_url
        ),
        linked_recipe_url=result.final_url,
        release_lease=True,
    )


async def _handle_saving(
    job: ImportJobRecord, *, deadline: Deadline, deps: OrchestrationDeps
) -> ImportJobRecord:
    identity = _identity(job)

    if not deadline.has_budget_for_side_effect():
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)

    settings = get_settings()
    client = _apify_client(settings, deps)

    try:
        reel = await client.get_reel_result(job.reel_dataset_id, identity)
    except ApifyProviderError as error:
        return await _fail(job, _map_apify_error(error))

    managed_image_storage_path: Optional[str] = None
    managed_image_url: Optional[str] = None
    try:
        kwargs: dict[str, Any] = {
            "deadline_seconds": max(1.0, min(15.0, deadline.budget_for_side_effect())),
            "transport": deps.safe_fetch_transport,
        }
        if deps.safe_fetch_resolver is not None:
            kwargs["resolver"] = deps.safe_fetch_resolver
        fetched = await safe_fetch(reel.thumbnail_url, IMAGE_POLICY, **kwargs)
        mirrored = store_social_thumbnail(
            "instagram", job.id, fetched.body, fetched.content_type, settings=settings
        )
        managed_image_storage_path = mirrored.storage_path
        managed_image_url = mirrored.image_url
    except (PublicWebError, SocialThumbnailStorageError):
        return await _fail(job, ImportJobErrorCode.SAVE_FAILED)

    recipe_payload = (job.normalized_result_json or {}).get("recipes") or []
    if not recipe_payload:
        _cleanup_orphaned_thumbnail(managed_image_storage_path, settings)
        return await _fail(job, ImportJobErrorCode.SAVE_FAILED)

    recipe = NormalizedRecipe.model_validate(recipe_payload[0])

    save_result = await save_recipe_import(
        submitted_url=identity.canonical_url,
        final_url=identity.canonical_url,
        title=recipe.name,
        recipes=[recipe],
        image_url=managed_image_url,
        managed_image_storage_path=managed_image_storage_path,
        linked_recipe_url=job.linked_recipe_url,
    )

    if not save_result.saved:
        _cleanup_orphaned_thumbnail(managed_image_storage_path, settings)
        return await _fail(job, ImportJobErrorCode.SAVE_FAILED)

    saved_result = ExtractResponse(
        source_url=identity.canonical_url,
        final_url=identity.canonical_url,
        title=recipe.name,
        image_url=save_result.image_url,
        recipes=[recipe],
        database_saved=True,
        database_message=SAVE_SUCCESS_MESSAGE,
        parse_status="recipe",
        linked_recipe_url=job.linked_recipe_url,
    )
    updated = await _checkpoint(
        job,
        state=ImportJobState.SUCCEEDED,
        recipe_id=save_result.id,
        normalized_result_json=saved_result.model_dump(mode="json"),
        release_lease=True,
    )
    release_provider_admission(job.id)
    return updated


_STATE_HANDLERS: dict[
    ImportJobState,
    Callable[..., Awaitable[ImportJobRecord]],
] = {
    ImportJobState.QUEUED: _handle_queued,
    ImportJobState.STARTING_REEL: _handle_stale_intent_state,
    ImportJobState.WAITING_REEL: _handle_waiting_reel,
    ImportJobState.PARSING_CAPTION: _handle_parsing_caption,
    ImportJobState.RESOLVING_RECIPE: _handle_resolving_recipe,
    ImportJobState.STARTING_PROFILE: _handle_stale_intent_state,
    ImportJobState.WAITING_PROFILE: _handle_waiting_profile,
    ImportJobState.SAVING: _handle_saving,
}


async def advance_instagram_job(
    job: ImportJobRecord,
    *,
    deadline: Deadline,
    deps: Optional[OrchestrationDeps] = None,
) -> ImportJobRecord:
    resolved_deps = deps or OrchestrationDeps()
    handler = _STATE_HANDLERS.get(job.state)
    if handler is None:
        return await _fail(job, ImportJobErrorCode.PROVIDER_INVALID_RESPONSE)
    try:
        return await handler(job, deadline=deadline, deps=resolved_deps)
    except DeadlineExceededError:
        return await _fail(job, ImportJobErrorCode.RESOLUTION_TIMEOUT)
    except ApifyProviderError as error:
        # Reaching here means a handler built its ApifyClient outside a try --
        # configuration validation only, with no request issued. Without this
        # the error escapes to the route, which checkpoints nothing and
        # answers 202, leaving the job to spin in its state forever.
        logger.warning(
            "Instagram job %s failed in state %s before any provider call: %s",
            job.id,
            job.state.value,
            error.code.value,
        )
        return await _fail(job, _map_apify_error(error))
