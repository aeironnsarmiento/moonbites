import { apiRequest } from "./apiClient";
import type { PaginatedRecipeImportsResponse } from "../types/api";
import type {
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";

export function fetchRecipeImports(
  page: number,
  pageSize: number,
): Promise<PaginatedRecipeImportsResponse> {
  const searchParams = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return apiRequest<PaginatedRecipeImportsResponse>(
    `/api/recipes?${searchParams.toString()}`,
  );
}

export function fetchRecipeImportById(
  recipeImportId: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(`/api/recipes/${recipeImportId}`);
}

export function updateRecipeImportTimesCooked(
  recipeImportId: string,
  delta: -1 | 1,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/times-cooked`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ delta }),
    },
  );
}

export function patchRecipeImportOverrides(
  recipeImportId: string,
  payload: UpdateRecipeOverridesPayload,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/overrides`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        recipe_index: payload.recipeIndex,
        overrides: payload.overrides,
      }),
    },
  );
}
