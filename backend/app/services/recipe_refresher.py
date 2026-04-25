from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException

from ..repositories.recipe_imports import (
    get_recipe_import,
    is_manual_recipe_url,
    list_recipe_import_records_for_refresh,
    update_recipe_import_from_extraction,
)
from ..schemas.extract import RecipeImportRecord
from .extractor import ExtractionResult, extract_recipes_from_url


@dataclass(frozen=True)
class RefetchRecipeImportResult:
    recipe_import_id: str
    status: str
    url: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class RefetchRecipeImportsSummary:
    total: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    no_recipe_found: int = 0
    results: list[RefetchRecipeImportResult] = field(default_factory=list)


def _limited_records(
    records: list[RecipeImportRecord],
    limit: Optional[int],
) -> list[RecipeImportRecord]:
    if limit is None:
        return records
    return records[:limit]


def _source_urls(record: RecipeImportRecord) -> list[str]:
    urls: list[str] = []
    for value in (record.final_url, record.submitted_url):
        if value not in urls:
            urls.append(value)
    return urls


def _http_exception_message(error: HTTPException) -> str:
    return str(error.detail or error.status_code)


async def _extract_with_fallbacks(
    record: RecipeImportRecord,
) -> tuple[Optional[ExtractionResult], Optional[str], Optional[str]]:
    last_error: Optional[str] = None

    for url in _source_urls(record):
        try:
            return await extract_recipes_from_url(url), url, None
        except HTTPException as error:
            last_error = _http_exception_message(error)
        except Exception as error:  # pragma: no cover - defensive for network clients
            last_error = str(error)

    return None, None, last_error


def _summary_from_results(
    results: list[RefetchRecipeImportResult],
) -> RefetchRecipeImportsSummary:
    counts = {
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "no_recipe_found": 0,
    }
    for result in results:
        if result.status in counts:
            counts[result.status] += 1

    return RefetchRecipeImportsSummary(
        total=len(results),
        updated=counts["updated"],
        skipped=counts["skipped"],
        failed=counts["failed"],
        no_recipe_found=counts["no_recipe_found"],
        results=results,
    )


def _records_for_refetch(
    recipe_import_id: Optional[str],
) -> list[RecipeImportRecord]:
    if recipe_import_id is None:
        return list_recipe_import_records_for_refresh()

    record = get_recipe_import(recipe_import_id)
    return [record] if record is not None else []


async def refetch_recipe_imports(
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    recipe_import_id: Optional[str] = None,
) -> RefetchRecipeImportsSummary:
    results: list[RefetchRecipeImportResult] = []
    records = _limited_records(_records_for_refetch(recipe_import_id), limit)

    if recipe_import_id is not None and not records:
        return _summary_from_results(
            [
                RefetchRecipeImportResult(
                    recipe_import_id=recipe_import_id,
                    status="failed",
                    message="Recipe import not found",
                )
            ]
        )

    for record in records:
        if is_manual_recipe_url(record.submitted_url) or is_manual_recipe_url(
            record.final_url
        ):
            results.append(
                RefetchRecipeImportResult(
                    recipe_import_id=record.id,
                    status="skipped",
                    message="Manual recipe imports cannot be refetched",
                )
            )
            continue

        extraction_result, fetched_url, error_message = await _extract_with_fallbacks(
            record
        )
        if extraction_result is None:
            results.append(
                RefetchRecipeImportResult(
                    recipe_import_id=record.id,
                    status="failed",
                    message=error_message or "Unable to fetch source URL",
                )
            )
            continue

        if not extraction_result.recipes:
            results.append(
                RefetchRecipeImportResult(
                    recipe_import_id=record.id,
                    status="no_recipe_found",
                    url=fetched_url,
                    message="No Recipe JSON-LD objects found",
                )
            )
            continue

        if not dry_run:
            updated_record = update_recipe_import_from_extraction(
                record.id,
                extraction_result,
            )
            if updated_record is None:
                results.append(
                    RefetchRecipeImportResult(
                        recipe_import_id=record.id,
                        status="failed",
                        url=fetched_url,
                        message="Recipe import disappeared before update",
                    )
                )
                continue

        results.append(
            RefetchRecipeImportResult(
                recipe_import_id=record.id,
                status="updated",
                url=fetched_url,
                message="Would update recipe import" if dry_run else "Updated recipe import",
            )
        )

    return _summary_from_results(results)
