import type { NormalizedRecipe, RecipeImportRecord } from "./recipe";

export type ExtractResponse = {
  source_url: string;
  final_url: string;
  title: string | null;
  image_url?: string | null;
  recipes: NormalizedRecipe[];
  database_saved: boolean;
  database_message: string | null;
  parse_status?: string;
  parse_reason?: string | null;
  extraction_method?: "gemini" | "manual_fallback" | null;
  normalization_model?: string | null;
  warnings?: string[];
  fallback_reason?: string | null;
};

export type PaginatedRecipeImportsResponse = {
  items: RecipeImportRecord[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

export type RecipeSortOption = "recent" | "az" | "za" | "times_cooked" | "favorites";

export type RecipeListQuery = {
  page: number;
  pageSize?: number;
  limit?: number;
  sort: RecipeSortOption;
  cuisine: string | null;
  favorite?: boolean | null;
};

export type CuisineFacet = {
  label: string;
  count: number;
};

export type CuisineFacetsResponse = {
  facets: CuisineFacet[];
};

export type DeleteRecipeImportResponse = {
  id: string;
};

export type ApiErrorResponse = {
  detail?: unknown;
};
