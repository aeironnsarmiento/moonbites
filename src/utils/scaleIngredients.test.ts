import { describe, expect, it } from "vitest";

import { scaleIngredient } from "./scaleIngredients";

describe("scaleIngredient", () => {
  it("scales parseable leading quantities", () => {
    expect(scaleIngredient("1 1/2 cups flour", 2)).toBe("3 cups flour");
    expect(scaleIngredient("1/2 tsp salt", 3)).toBe("1 1/2 tsp salt");
    expect(scaleIngredient("2 eggs", 0.5)).toBe("1 eggs");
  });

  it("scales formats that used to split into two numbers", () => {
    expect(scaleIngredient("1½ cups flour", 2)).toBe("3 cups flour");
    expect(scaleIngredient("1 ⅛ tsp salt", 2)).toBe("2 1/4 tsp salt");
    expect(scaleIngredient("⅛ tsp salt", 2)).toBe("1/4 tsp salt");
    expect(scaleIngredient("1.5kg beef", 2)).toBe("3kg beef");
    expect(scaleIngredient("1,000 g rice", 2)).toBe("2000 g rice");
    expect(scaleIngredient("200g flour", 2)).toBe("400g flour");
    expect(scaleIngredient("1 1/2-inch piece ginger", 2)).toBe(
      "3-inch piece ginger",
    );
  });

  it("scales both ends of a range", () => {
    expect(scaleIngredient("1-2 tbsp oil", 2)).toBe("2-4 tbsp oil");
    expect(scaleIngredient("1 to 2 cloves garlic", 2)).toBe(
      "2 to 4 cloves garlic",
    );
    expect(scaleIngredient("1 – 2 cups stock", 3)).toBe("3 – 6 cups stock");
  });

  it("scales a count followed by a package size, not the size", () => {
    expect(scaleIngredient("1 - 400g can tomatoes", 2)).toBe(
      "2 - 400g can tomatoes",
    );
  });

  it("leaves unparseable lines unchanged", () => {
    expect(scaleIngredient("a pinch of salt", 2)).toBe("a pinch of salt");
  });
});
