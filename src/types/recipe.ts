export type IngredientSection = {
  title: string | null;
  items: string[];
};

export type NormalizedRecipe = {
  name: string;
  recipeYield: string | null;
  cookTime: string | null;
  recipeCuisine: string[] | null;
  nutrition: Record<string, string> | null;
  ingredients: string[];
  ingredientSections: IngredientSection[] | null;
  instructions: string[];
};

// One displayed row: `source` is the parsed row index (null for an added
// row) and `text` replaces that row's text (null keeps the parsed text).
export type RecipeRowEntry = {
  source: number | null;
  text: string | null;
};

// Full row layout in display order; parsed rows missing from it are deleted.
// null means the section is shown as parsed.
export type RecipeRowLayout = RecipeRowEntry[] | null;

export type RecipeTextOverrides = {
  ingredients: RecipeRowLayout;
  instructions: RecipeRowLayout;
};

export type RecipeOverridesMap = Record<string, RecipeTextOverrides>;

export type UpdateRecipeOverridesPayload = {
  recipeIndex: number;
  overrides: RecipeTextOverrides;
};

export type UpdateRecipeMetadataPayload = {
  title: string;
  recipeYield: string | null;
  imageUrl: string | null;
  sourceUrl: string;
  fallbackVideoUrl: string | null;
};

export type RecipeImportRecord = {
  id: string;
  submitted_url: string;
  final_url: string;
  page_title: string | null;
  times_cooked: number;
  recipes_json: NormalizedRecipe[];
  recipe_overrides_json: RecipeOverridesMap;
  image_url: string | null;
  is_favorite: boolean;
  servings: number | null;
  fallback_video_url: string | null;
  linked_recipe_url: string | null;
  created_at: string;
};

export type RecipeCardItem = {
  id: string;
  title: string;
  pageTitle: string | null;
  submittedUrl: string;
  createdAtLabel: string;
  timesCooked: number;
  imageUrl: string | null;
  isFavorite: boolean;
  servings: number | null;
  primaryRecipe: NormalizedRecipe | null;
};
