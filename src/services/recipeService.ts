import { apiRequest } from "./apiClient";
import { normalizeSearchTerm } from "../utils/searchTerm";
import type {
  CuisineFacetsResponse,
  DeleteRecipeImportResponse,
  HighlightedRecipesResponse,
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
  search,
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

  const normalizedSearch = normalizeSearchTerm(search);
  if (normalizedSearch) {
    searchParams.set("search", normalizedSearch);
  }

  return apiRequest<PaginatedRecipeImportsResponse>(
    `/api/recipes?${searchParams.toString()}`,
  );
}

export function fetchHighlightedRecipes(
  recentLimit: number,
  favoriteLimit: number,
): Promise<HighlightedRecipesResponse> {
  const searchParams = new URLSearchParams({
    recent_limit: String(recentLimit),
    favorite_limit: String(favoriteLimit),
  });

  return apiRequest<HighlightedRecipesResponse>(
    `/api/recipes/highlights?${searchParams.toString()}`,
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

export function deleteRecipeImport(
  recipeImportId: string,
): Promise<DeleteRecipeImportResponse> {
  return apiRequest<DeleteRecipeImportResponse>(`/api/recipes/${recipeImportId}`, {
    method: "DELETE",
  });
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
