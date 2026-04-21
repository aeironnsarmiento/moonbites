import {
  createManualRecipeImport,
  fetchRecipeImportById,
  fetchRecipeImports,
  patchRecipeImportOverrides,
  updateRecipeImportTimesCooked,
} from "../services/recipeService";
import type { PaginatedRecipeImportsResponse } from "../types/api";
import type {
  NormalizedRecipe,
  RecipeCardItem,
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";
import {
  dedupeRecipeImportRecord,
  dedupeRecipeImports,
} from "../utils/recipeDedup";

function isManualRecipeUrl(value: string) {
  return value.trim().toLowerCase().startsWith("manual://");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function mapRecipeImportToCard(record: RecipeImportRecord): RecipeCardItem {
  const primaryRecipe = record.recipes_json[0] ?? null;
  const manualRecord = isManualRecipeUrl(record.submitted_url);

  return {
    id: record.id,
    title: primaryRecipe?.name ?? record.page_title ?? "Untitled recipe import",
    pageTitle: manualRecord ? record.page_title ?? "Manual recipe" : record.page_title,
    submittedUrl: manualRecord ? "Manual recipe" : record.submitted_url,
    createdAtLabel: formatDate(record.created_at),
    recipeCount: record.recipe_count,
    timesCooked: record.times_cooked,
    primaryRecipe,
  };
}

export async function getRecipeListPage(page: number, pageSize: number) {
  const response = await fetchRecipeImports(page, pageSize);
  if (!response || !Array.isArray(response.items)) {
    throw new Error("Recipes API returned an invalid list response.");
  }

  const items = dedupeRecipeImports(response.items);

  return {
    ...response,
    items: items.map(mapRecipeImportToCard),
  };
}

export async function getRecipeImportDetail(recipeImportId: string) {
  const record = await fetchRecipeImportById(recipeImportId);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid detail response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function createManualRecipe(
  recipe: NormalizedRecipe,
  title?: string,
) {
  const record = await createManualRecipeImport(recipe, title);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid create response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function adjustRecipeImportTimesCooked(
  recipeImportId: string,
  delta: -1 | 1,
) {
  const record = await updateRecipeImportTimesCooked(recipeImportId, delta);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid update response.");
  }

  return dedupeRecipeImportRecord(record);
}

export async function updateRecipeImportOverrides(
  recipeImportId: string,
  payload: UpdateRecipeOverridesPayload,
) {
  const record = await patchRecipeImportOverrides(recipeImportId, payload);

  if (!record || !Array.isArray(record.recipes_json)) {
    throw new Error("Recipes API returned an invalid update response.");
  }

  return dedupeRecipeImportRecord(record);
}

export type RecipeListPageData = Omit<
  PaginatedRecipeImportsResponse,
  "items"
> & {
  items: RecipeCardItem[];
};
