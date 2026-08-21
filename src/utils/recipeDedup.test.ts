import { describe, expect, it } from "vitest";

import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";
import {
  buildRecipeFingerprint,
  dedupeNormalizedRecipes,
  dedupeRecipeImportRecord,
  dedupeRecipeImports,
} from "./recipeDedup";

function recipe(overrides: Partial<NormalizedRecipe> = {}): NormalizedRecipe {
  return {
    name: "Miso Salmon Rice",
    recipeYield: null,
    cookTime: null,
    recipeCuisine: null,
    nutrition: null,
    ingredients: ["1 cup rice"],
    ingredientSections: null,
    instructions: ["Cook rice."],
    ...overrides,
  };
}

function record(overrides: Partial<RecipeImportRecord> = {}): RecipeImportRecord {
  return {
    id: "recipe-1",
    submitted_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
    final_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
    page_title: "Miso Salmon Rice",
    times_cooked: 0,
    recipes_json: [recipe()],
    recipe_overrides_json: {},
    image_url: null,
    is_favorite: false,
    servings: null,
    fallback_video_url: null,
    linked_recipe_url: null,
    created_at: "2026-08-20T00:00:00.000Z",
    ...overrides,
  };
}

describe("dedupeNormalizedRecipes", () => {
  it("removes recipes with an identical fingerprint", () => {
    const recipes = [recipe(), recipe(), recipe({ name: "Different Dish" })];

    const result = dedupeNormalizedRecipes(recipes);

    expect(result).toHaveLength(2);
  });
});

describe("dedupeRecipeImportRecord", () => {
  it("dedupes the recipes embedded in a single record", () => {
    const result = dedupeRecipeImportRecord(
      record({ recipes_json: [recipe(), recipe()] }),
    );

    expect(result.recipes_json).toHaveLength(1);
  });
});

describe("dedupeRecipeImports", () => {
  it("collapses records that share a canonical submitted or final URL", () => {
    const records = [
      record({ id: "a" }),
      record({ id: "b", submitted_url: "https://www.instagram.com/reel/DZuzc9PNedT" }),
    ];

    const result = dedupeRecipeImports(records);

    expect(result).toHaveLength(1);
    expect(result[0]?.id).toBe("a");
  });

  it("keeps two different Reels that share the same linked_recipe_url", () => {
    const records = [
      record({
        id: "a",
        submitted_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
        final_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
        linked_recipe_url: "https://tasty.co/recipe/miso-salmon-rice",
      }),
      record({
        id: "b",
        submitted_url: "https://www.instagram.com/reel/DcMelrnkfZe/",
        final_url: "https://www.instagram.com/reel/DcMelrnkfZe/",
        linked_recipe_url: "https://tasty.co/recipe/miso-salmon-rice",
      }),
    ];

    const result = dedupeRecipeImports(records);

    expect(result).toHaveLength(2);
  });

  it("does not use linked_recipe_url to collapse otherwise-distinct records", () => {
    const records = [
      record({
        id: "a",
        submitted_url: "https://blog.example/recipe-a",
        final_url: "https://blog.example/recipe-a",
        linked_recipe_url: null,
      }),
      record({
        id: "b",
        submitted_url: "https://blog.example/recipe-b",
        final_url: "https://blog.example/recipe-b",
        linked_recipe_url: null,
      }),
    ];

    const result = dedupeRecipeImports(records);

    expect(result.map((item) => item.id)).toEqual(["a", "b"]);
  });
});

describe("buildRecipeFingerprint", () => {
  it("is case-insensitive on the recipe name", () => {
    const lower = buildRecipeFingerprint(recipe({ name: "miso salmon rice" }));
    const upper = buildRecipeFingerprint(recipe({ name: "MISO SALMON RICE" }));

    expect(lower).toBe(upper);
  });
});
