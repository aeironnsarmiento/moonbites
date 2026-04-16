import {
  fetchRecipeImportById,
  fetchRecipeImports,
} from "../services/recipeService";
import type { PaginatedRecipeImportsResponse } from "../types/api";
import type { RecipeCardItem, RecipeImportRecord } from "../types/recipe";
import {
  dedupeRecipeImportRecord,
  dedupeRecipeImports,
} from "../utils/recipeDedup";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function mapRecipeImportToCard(record: RecipeImportRecord): RecipeCardItem {
  const primaryRecipe = record.recipes_json[0] ?? null;

  return {
    id: record.id,
    title: primaryRecipe?.name ?? record.page_title ?? "Untitled recipe import",
    pageTitle: record.page_title,
    submittedUrl: record.submitted_url,
    createdAtLabel: formatDate(record.created_at),
    recipeCount: record.recipe_count,
    primaryRecipe,
  };
}

export async function getRecipeListPage(page: number, pageSize: number) {
  const response = await fetchRecipeImports(page, pageSize);
  const items = dedupeRecipeImports(response.items);

  return {
    ...response,
    items: items.map(mapRecipeImportToCard),
  };
}

export async function getRecipeImportDetail(recipeImportId: string) {
  const record = await fetchRecipeImportById(recipeImportId);
  return dedupeRecipeImportRecord(record);
}

export type RecipeListPageData = Omit<
  PaginatedRecipeImportsResponse,
  "items"
> & {
  items: RecipeCardItem[];
};
