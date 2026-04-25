import { describe, expect, it } from "vitest";

import { scaleIngredient } from "./scaleIngredients";

describe("scaleIngredient", () => {
  it("scales parseable leading quantities", () => {
    expect(scaleIngredient("1 1/2 cups flour", 2)).toBe("3 cups flour");
    expect(scaleIngredient("1/2 tsp salt", 3)).toBe("1 1/2 tsp salt");
    expect(scaleIngredient("2 eggs", 0.5)).toBe("1 eggs");
  });

  it("leaves unparseable lines unchanged", () => {
    expect(scaleIngredient("a pinch of salt", 2)).toBe("a pinch of salt");
  });
});
