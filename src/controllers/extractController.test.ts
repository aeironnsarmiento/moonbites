import { describe, expect, it } from "vitest";

import { buildExtractStatus } from "./extractController";
import type { ExtractResponse } from "../types/api";

function buildResponse(overrides: Partial<ExtractResponse>): ExtractResponse {
  return {
    source_url: "https://example.com/submitted",
    final_url: "https://example.com/final",
    title: "Recipe Page",
    recipes: [
      {
        name: "Soup",
        recipeYield: null,
        cookTime: null,
        recipeCuisine: null,
        nutrition: null,
        ingredients: ["1 cup stock"],
        ingredientSections: null,
        instructions: ["Warm stock."],
      },
    ],
    database_saved: true,
    database_message: null,
    ...overrides,
  };
}

describe("buildExtractStatus", () => {
  it("does not expose Supabase table names from save success messages", () => {
    const status = buildExtractStatus(
      buildResponse({
        database_message: "Saved to Supabase table 'recipe_imports'.",
      }),
    );

    expect(status).toBe("Found 1 unique recipe. Recipe saved to your collection.");
    expect(status).not.toContain("Supabase");
    expect(status).not.toContain("recipe_imports");
  });

  it("keeps specific no-save messages", () => {
    const message =
      "Nothing was saved because no Recipe objects were found on that page.";

    expect(
      buildExtractStatus(
      buildResponse({
          recipes: [],
          database_saved: false,
          database_message: message,
        }),
      ),
    ).toBe(`No Recipe objects were found on that page, so nothing was saved. ${message}`);
  });

  it("prefers the backend parse_reason for no-recipe results", () => {
    const status = buildExtractStatus(
      buildResponse({
        recipes: [],
        database_saved: false,
        database_message: "Skipped — not a recipe.",
        parse_status: "not_recipe",
        parse_reason: "No recipe was found in the TikTok caption.",
      }),
    );

    expect(status).toBe(
      "No recipe was found in the TikTok caption. Skipped — not a recipe.",
    );
    expect(status).not.toContain("Recipe objects");
  });

  it("falls back to the generic copy when parse_reason is absent", () => {
    const status = buildExtractStatus(
      buildResponse({
        recipes: [],
        database_saved: false,
        database_message: null,
      }),
    );

    expect(status).toBe(
      "No Recipe objects were found on that page, so nothing was saved.",
    );
  });
});
