import { describe, expect, it } from "vitest";

import { PLACEHOLDER_RECIPE_TITLE, resolveDisplayTitle } from "./recipeTitle";
import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";

function recipe(name: string): NormalizedRecipe {
  return {
    name,
    recipeYield: null,
    cookTime: null,
    recipeCuisine: null,
    nutrition: null,
    ingredients: ["1 cup rice"],
    ingredientSections: null,
    instructions: ["Cook."],
  };
}

function record(overrides: Partial<RecipeImportRecord> = {}): RecipeImportRecord {
  return {
    id: "abc",
    submitted_url: "https://old.test/source",
    final_url: "https://old.test/source",
    page_title: "The BEST Garlic Noodles!!",
    display_title: null,
    display_title_source: "fallback",
    times_cooked: 0,
    recipes_json: [recipe("Garlic Noodles")],
    recipe_overrides_json: {},
    image_url: null,
    is_favorite: false,
    servings: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("resolveDisplayTitle", () => {
  it("prefers the display title", () => {
    expect(
      resolveDisplayTitle(record({ display_title: "Creamy Garlic Pasta" })),
    ).toBe("Creamy Garlic Pasta");
  });

  it("falls back to the recipe name when there is no display title", () => {
    // Records imported before this feature have a null display_title and must
    // keep rendering exactly as they did.
    expect(resolveDisplayTitle(record())).toBe("Garlic Noodles");
  });

  it("falls back to the page title when there are no recipes", () => {
    expect(resolveDisplayTitle(record({ recipes_json: [] }))).toBe(
      "The BEST Garlic Noodles!!",
    );
  });

  it("falls back to the placeholder when nothing names the record", () => {
    expect(
      resolveDisplayTitle(record({ recipes_json: [], page_title: null })),
    ).toBe(PLACEHOLDER_RECIPE_TITLE);
  });

  it("ignores a blank display title", () => {
    expect(resolveDisplayTitle(record({ display_title: "   " }))).toBe(
      "Garlic Noodles",
    );
  });

  it("trims the display title", () => {
    expect(resolveDisplayTitle(record({ display_title: "  Pasta Bowl  " }))).toBe(
      "Pasta Bowl",
    );
  });
});
