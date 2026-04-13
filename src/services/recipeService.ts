import { apiRequest } from "./apiClient";
import type { PaginatedRecipeImportsResponse } from "../types/api";
import type { RecipeImportRecord } from "../types/recipe";

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
