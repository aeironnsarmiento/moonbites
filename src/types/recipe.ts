export type NormalizedRecipe = {
  name: string;
  recipeYield: string | null;
  cookTime: string | null;
  recipeCuisine: string[] | null;
  nutrition: Record<string, string> | null;
  ingredients: string[];
  instructions: string[];
};

export type RecipeImportRecord = {
  id: string;
  submitted_url: string;
  final_url: string;
  page_title: string | null;
  recipe_count: number;
  recipes_json: NormalizedRecipe[];
  created_at: string;
};

export type RecipeCardItem = {
  id: string;
  title: string;
  pageTitle: string | null;
  submittedUrl: string;
  createdAtLabel: string;
  recipeCount: number;
  primaryRecipe: NormalizedRecipe | null;
};
