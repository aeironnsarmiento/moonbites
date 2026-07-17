"""Retroactive display-title cleanup (R11-R14).

Bounded and batched rather than a background job: the repo has no job
infrastructure, and at a few requests per minute a one-call-per-recipe preview
would block an HTTP request for minutes. One cursor page of candidates rides in
a single Gemini call, and the admin pages through.
"""

from __future__ import annotations

from typing import Optional

from ..repositories.recipe_imports import (
    is_manual_recipe_url,
    list_recipe_import_records_for_title_cleanup,
)
from ..schemas.extract import (
    DisplayTitleSource,
    RecipeImportRecord,
    SkippedTitleCleanupItem,
    TitleCleanupPreviewResponse,
    TitleSuggestion,
)
from .display_titles import resolve_display_title
from .gemini.title_generator import TitleRequest, generate_display_titles


USER_EDITED_REASON = "You titled this recipe, so it was left alone."
MANUAL_RECIPE_REASON = "Manual recipes keep the name you gave them."


def _current_title(record: RecipeImportRecord) -> str:
    return resolve_display_title(
        record.display_title,
        record.recipes_json,
        record.page_title,
    )


def _skip_reason(record: RecipeImportRecord) -> Optional[str]:
    # R13 and R10, enforced here rather than in the UI.
    if record.display_title_source == DisplayTitleSource.user:
        return USER_EDITED_REASON
    if is_manual_recipe_url(record.submitted_url):
        return MANUAL_RECIPE_REASON
    return None


async def preview_title_cleanup(
    *,
    cursor: Optional[str] = None,
    limit: int = 10,
) -> TitleCleanupPreviewResponse:
    records = list_recipe_import_records_for_title_cleanup(
        cursor=cursor, batch_size=limit
    )

    skipped: list[SkippedTitleCleanupItem] = []
    candidates: list[RecipeImportRecord] = []

    for record in records:
        reason = _skip_reason(record)
        if reason is not None:
            skipped.append(
                SkippedTitleCleanupItem(
                    recipe_import_id=record.id,
                    current_title=_current_title(record),
                    reason=reason,
                )
            )
            continue
        candidates.append(record)

    # The cursor tracks the last record READ, not the last suggested: deriving
    # it from suggestions would re-read skipped rows forever.
    next_cursor = (
        records[-1].created_at.isoformat() if len(records) == limit and records else None
    )

    if not candidates:
        return TitleCleanupPreviewResponse(
            suggestions=[],
            skipped=skipped,
            next_cursor=next_cursor,
        )

    batch = await generate_display_titles(
        [
            TitleRequest(source_title=record.page_title, recipes=record.recipes_json)
            for record in candidates
        ]
    )

    suggestions = [
        TitleSuggestion(
            recipe_import_id=record.id,
            current_title=_current_title(record),
            suggested_title=title.value,
            source=DisplayTitleSource(title.source),
            reason=title.reason,
        )
        for record, title in zip(candidates, batch.titles)
    ]

    return TitleCleanupPreviewResponse(
        suggestions=suggestions,
        skipped=skipped,
        next_cursor=next_cursor,
        degraded_reason=batch.degraded_reason,
    )
