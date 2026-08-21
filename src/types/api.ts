import type { NormalizedRecipe, RecipeImportRecord } from "./recipe";

export type ExtractResponse = {
  source_url: string;
  final_url: string;
  title: string | null;
  image_url?: string | null;
  recipes: NormalizedRecipe[];
  database_saved: boolean;
  database_message: string | null;
  parse_status?: "recipe" | "not_recipe";
  parse_reason?: string | null;
  linked_recipe_url?: string | null;
};

export type ImportJobState =
  | "queued"
  | "starting_reel"
  | "waiting_reel"
  | "parsing_caption"
  | "resolving_recipe"
  | "starting_profile"
  | "waiting_profile"
  | "saving"
  | "succeeded"
  | "not_recipe"
  | "failed";

export type ImportJobErrorCode =
  | "instagram_unavailable"
  | "provider_unavailable"
  | "provider_timeout"
  | "provider_invalid_response"
  | "resolution_timeout"
  | "ambiguous_external_operation"
  | "job_stalled"
  | "save_failed";

export type PendingImportResponse = {
  kind: "pending";
  job_id: string;
  state: ImportJobState;
  retry_after_ms: number;
};

export type ResultImportResponse = {
  kind: "result";
  result: ExtractResponse;
};

export type FailedImportResponse = {
  kind: "failed";
  job_id: string;
  error_code: ImportJobErrorCode;
  message: string;
};

export type ImportJobResponse =
  | PendingImportResponse
  | ResultImportResponse
  | FailedImportResponse;

export type ExtractApiResponse = ExtractResponse | ImportJobResponse;

export function isImportJobResponse(
  value: ExtractApiResponse,
): value is ImportJobResponse {
  return typeof value === "object" && value !== null && "kind" in value;
}

export type PaginatedRecipeImportsResponse = {
  items: RecipeImportRecord[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

export type HighlightedRecipesResponse = {
  recent: RecipeImportRecord[];
  favorites: RecipeImportRecord[];
  total_count: number;
  favorite_count: number;
};

export type RecipeSortOption = "recent" | "az" | "za" | "times_cooked" | "favorites";

export type RecipeListQuery = {
  page: number;
  pageSize?: number;
  limit?: number;
  sort: RecipeSortOption;
  cuisine: string | null;
  favorite?: boolean | null;
  search?: string | null;
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
