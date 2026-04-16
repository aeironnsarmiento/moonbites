import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";

const TRACKING_QUERY_PARAMS = new Set([
  "fbclid",
  "gclid",
  "mc_cid",
  "mc_eid",
  "mkt_tok",
  "ref",
  "spm",
  "utm_campaign",
  "utm_content",
  "utm_id",
  "utm_medium",
  "utm_name",
  "utm_source",
  "utm_term",
]);

function canonicalizeUrl(value: string) {
  try {
    const url = new URL(value.trim());
    const pathname =
      url.pathname !== "/" ? url.pathname.replace(/\/+$/, "") || "/" : "/";

    const filteredParams = [...url.searchParams.entries()]
      .filter(([key]) => !TRACKING_QUERY_PARAMS.has(key.toLowerCase()))
      .sort(([leftKey, leftValue], [rightKey, rightValue]) => {
        if (leftKey === rightKey) {
          return leftValue.localeCompare(rightValue);
        }

        return leftKey.localeCompare(rightKey);
      });

    url.hash = "";
    url.username = "";
    url.password = "";
    url.protocol = url.protocol.toLowerCase();
    url.hostname = url.hostname.toLowerCase();
    url.pathname = pathname;

    if (
      (url.protocol === "http:" && url.port === "80") ||
      (url.protocol === "https:" && url.port === "443")
    ) {
      url.port = "";
    }

    url.search = "";
    for (const [key, paramValue] of filteredParams) {
      url.searchParams.append(key, paramValue);
    }

    return url.toString();
  } catch {
    return value.trim();
  }
}

export function buildRecipeFingerprint(recipe: NormalizedRecipe) {
  return JSON.stringify({
    cookTime: recipe.cookTime,
    ingredients: recipe.ingredients,
    instructions: recipe.instructions,
    name: recipe.name.toLocaleLowerCase(),
    nutrition: recipe.nutrition,
    recipeCuisine: recipe.recipeCuisine,
    recipeYield: recipe.recipeYield,
  });
}

export function dedupeNormalizedRecipes(recipes: NormalizedRecipe[]) {
  const seen = new Set<string>();
  const uniqueRecipes: NormalizedRecipe[] = [];

  for (const recipe of recipes) {
    const fingerprint = buildRecipeFingerprint(recipe);
    if (seen.has(fingerprint)) {
      continue;
    }

    seen.add(fingerprint);
    uniqueRecipes.push(recipe);
  }

  return uniqueRecipes;
}

export function dedupeRecipeImportRecord(record: RecipeImportRecord) {
  const recipes = dedupeNormalizedRecipes(record.recipes_json);

  return {
    ...record,
    recipe_count: recipes.length,
    recipes_json: recipes,
  };
}

export function dedupeRecipeImports(records: RecipeImportRecord[]) {
  const seen = new Set<string>();
  const uniqueRecords: RecipeImportRecord[] = [];

  for (const record of records) {
    const dedupedRecord = dedupeRecipeImportRecord(record);
    const keys = [
      canonicalizeUrl(dedupedRecord.submitted_url),
      canonicalizeUrl(dedupedRecord.final_url),
    ];

    if (keys.some((key) => seen.has(key))) {
      continue;
    }

    keys.forEach((key) => seen.add(key));
    uniqueRecords.push(dedupedRecord);
  }

  return uniqueRecords;
}