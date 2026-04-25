import { apiRequest } from "./apiClient";
import type {
  CuisineFacetsResponse,
  PaginatedRecipeImportsResponse,
  RecipeListQuery,
} from "../types/api";
import type {
  NormalizedRecipe,
  RecipeImportRecord,
  UpdateRecipeMetadataPayload,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";

export function fetchRecipeImports({
  page,
  pageSize,
  limit,
  sort,
  cuisine,
  favorite,
}: RecipeListQuery): Promise<PaginatedRecipeImportsResponse> {
  const searchParams = new URLSearchParams({
    page: String(page),
    sort,
  });

  if (pageSize) {
    searchParams.set("page_size", String(pageSize));
  }

  if (limit) {
    searchParams.set("limit", String(limit));
  }

  if (cuisine) {
    searchParams.set("cuisine", cuisine);
  }

  if (favorite != null) {
    searchParams.set("favorite", String(favorite));
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

export function toggleRecipeImportFavorite(
  recipeImportId: string,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/favorite`,
    {
      method: "PATCH",
    },
  );
}

export function updateRecipeImportServings(
  recipeImportId: string,
  servings: number,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/servings`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ servings }),
    },
  );
}

export function patchRecipeImportMetadata(
  recipeImportId: string,
  payload: UpdateRecipeMetadataPayload,
): Promise<RecipeImportRecord> {
  return apiRequest<RecipeImportRecord>(
    `/api/recipes/${recipeImportId}/metadata`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: payload.title,
        recipe_yield: payload.recipeYield,
        image_url: payload.imageUrl,
        source_url: payload.sourceUrl,
      }),
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
