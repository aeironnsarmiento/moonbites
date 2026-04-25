import { describe, expect, it } from "vitest";

import { formatQuantity, parseQuantity } from "./parseQuantity";

describe("parseQuantity", () => {
  it("parses integers, decimals, fractions, and mixed quantities", () => {
    expect(parseQuantity("2 eggs")).toEqual({ value: 2, rest: "eggs" });
    expect(parseQuantity("1.5 cups flour")).toEqual({
      value: 1.5,
      rest: "cups flour",
    });
    expect(parseQuantity("1/2 tsp salt")).toEqual({
      value: 0.5,
      rest: "tsp salt",
    });
    expect(parseQuantity("1 1/2 cups milk")).toEqual({
      value: 1.5,
      rest: "cups milk",
    });
    expect(parseQuantity("1 ½ cups milk")).toEqual({
      value: 1.5,
      rest: "cups milk",
    });
  });

  it("returns null for unparseable quantities", () => {
    expect(parseQuantity("a pinch of salt")).toBeNull();
    expect(parseQuantity("to taste")).toBeNull();
  });

  it("formats clean fractions", () => {
    expect(formatQuantity(1.5)).toBe("1 1/2");
    expect(formatQuantity(0.75)).toBe("3/4");
    expect(formatQuantity(1.25)).toBe("1 1/4");
  });
});
