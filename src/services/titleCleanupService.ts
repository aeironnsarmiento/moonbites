import { apiRequest } from "./apiClient";
import type { ApplyTitleItem, DisplayTitleSource } from "../types/recipe";

type TitleSuggestionResponse = {
  recipe_import_id: string;
  current_title: string;
  suggested_title: string;
  source: DisplayTitleSource;
  reason: string | null;
};

type SkippedTitleCleanupResponse = {
  recipe_import_id: string;
  current_title: string;
  reason: string;
};

export type TitleCleanupPreviewResponse = {
  suggestions: TitleSuggestionResponse[];
  skipped: SkippedTitleCleanupResponse[];
  next_cursor: string | null;
  degraded_reason: string | null;
};

export type ApplyTitlesResponse = {
  results: { recipe_import_id: string; status: string; reason: string | null }[];
  applied_count: number;
};

export function postTitleCleanupPreview(
  cursor: string | null,
  limit: number,
): Promise<TitleCleanupPreviewResponse> {
  return apiRequest<TitleCleanupPreviewResponse>("/api/recipes/titles/preview", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ cursor, limit }),
  });
}

export function postTitleCleanupApply(
  items: ApplyTitleItem[],
): Promise<ApplyTitlesResponse> {
  return apiRequest<ApplyTitlesResponse>("/api/recipes/titles/apply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      items: items.map((item) => ({
        recipe_import_id: item.recipeImportId,
        title: item.title,
      })),
    }),
  });
}
