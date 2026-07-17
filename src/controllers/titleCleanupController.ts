import {
  postTitleCleanupApply,
  postTitleCleanupPreview,
} from "../services/titleCleanupService";
import type {
  ApplyTitleItem,
  ApplyTitlesResult,
  TitleCleanupPreview,
} from "../types/recipe";

export async function getTitleCleanupPreview(
  cursor: string | null,
  limit = 10,
): Promise<TitleCleanupPreview> {
  const response = await postTitleCleanupPreview(cursor, limit);
  if (
    !response ||
    !Array.isArray(response.suggestions) ||
    !Array.isArray(response.skipped)
  ) {
    throw new Error("Title cleanup API returned an invalid preview response.");
  }

  return {
    suggestions: response.suggestions.map((suggestion) => ({
      recipeImportId: suggestion.recipe_import_id,
      currentTitle: suggestion.current_title,
      suggestedTitle: suggestion.suggested_title,
      source: suggestion.source,
      reason: suggestion.reason,
    })),
    skipped: response.skipped.map((item) => ({
      recipeImportId: item.recipe_import_id,
      currentTitle: item.current_title,
      reason: item.reason,
    })),
    nextCursor: response.next_cursor ?? null,
    degradedReason: response.degraded_reason ?? null,
  };
}

export async function applyTitleCleanup(
  items: ApplyTitleItem[],
): Promise<ApplyTitlesResult> {
  const response = await postTitleCleanupApply(items);
  if (!response || !Array.isArray(response.results)) {
    throw new Error("Title cleanup API returned an invalid apply response.");
  }

  return {
    results: response.results.map((result) => ({
      recipeImportId: result.recipe_import_id,
      status: result.status,
      reason: result.reason,
    })),
    appliedCount: response.applied_count ?? 0,
  };
}
