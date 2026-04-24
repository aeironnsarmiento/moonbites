import { apiRequest } from "./apiClient";
import type {
  CuisineFacetsResponse,
  PaginatedRecipeImportsResponse,
  RecipeListQuery,
} from "../types/api";
import type {
  NormalizedRecipe,
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";

export function fetchRecipeImports({
  page,
  pageSize,
  sort,
  cuisine,
}: RecipeListQuery): Promise<PaginatedRecipeImportsResponse> {
  const searchParams = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort,
  });

  if (cuisine) {
    searchParams.set("cuisine", cuisine);
  }

  return apiRequest<PaginatedRecipeImportsResponse>(
    `/api/recipes?${searchParams.toString()}`,
  );
}

export function fetchCuisineFacets(): Promise<CuisineFacetsResponse> {
  return apiRequest<CuisineFacetsResponse>("/api/recipes/cuisines");
}

export function fetchRecipeImportById(
  recipeImportId: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(`/api/recipes/${recipeImportId}`);
}

export function createManualRecipeImport(
  recipe: NormalizedRecipe,
  title?: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>("/api/recipes/manual", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      recipe,
      title: title?.trim() || null,
    }),
  });
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
