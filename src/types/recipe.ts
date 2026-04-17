export type NormalizedRecipe = {
  name: string;
  recipeYield: string | null;
  cookTime: string | null;
  recipeCuisine: string[] | null;
  nutrition: Record<string, string> | null;
  ingredients: string[];
  instructions: string[];
};

export type RecipeRowOverrides = Record<string, string>;

export type RecipeTextOverrides = {
  ingredients: RecipeRowOverrides;
  instructions: RecipeRowOverrides;
};

export type RecipeOverridesMap = Record<string, RecipeTextOverrides>;

export type UpdateRecipeOverridesPayload = {
  recipeIndex: number;
  overrides: RecipeTextOverrides;
};

export type RecipeImportRecord = {
  id: string;
  submitted_url: string;
  final_url: string;
  page_title: string | null;
  recipe_count: number;
  times_cooked: number;
  recipes_json: NormalizedRecipe[];
  recipe_overrides_json: RecipeOverridesMap;
  created_at: string;
};

export type RecipeCardItem = {
  id: string;
  title: string;
  pageTitle: string | null;
  submittedUrl: string;
  createdAtLabel: string;
  recipeCount: number;
  timesCooked: number;
  primaryRecipe: NormalizedRecipe | null;
};
