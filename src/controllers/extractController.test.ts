import { describe, expect, it } from "vitest";

import { buildExtractStatus } from "./extractController";
import type { ExtractResponse } from "../types/api";

function buildResponse(overrides: Partial<ExtractResponse>): ExtractResponse {
  return {
    source_url: "https://example.com/submitted",
    final_url: "https://example.com/final",
    title: "Recipe Page",
    recipe_count: 1,
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
          recipe_count: 0,
          recipes: [],
          database_saved: false,
          database_message: message,
        }),
      ),
    ).toBe(`No Recipe objects were found on that page, so nothing was saved. ${message}`);
  });
});
