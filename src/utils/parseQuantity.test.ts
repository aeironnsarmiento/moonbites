import { describe, expect, it } from "vitest";

import { formatQuantity, parseQuantity } from "./parseQuantity";

describe("parseQuantity", () => {
  it("parses integers, decimals, fractions, and mixed quantities", () => {
    expect(parseQuantity("2 eggs")).toMatchObject({ value: 2, rest: "eggs" });
    expect(parseQuantity("1.5 cups flour")).toMatchObject({
      value: 1.5,
      rest: "cups flour",
    });
    expect(parseQuantity("1/2 tsp salt")).toMatchObject({
      value: 0.5,
      rest: "tsp salt",
    });
    expect(parseQuantity("1 1/2 cups milk")).toMatchObject({
      value: 1.5,
      rest: "cups milk",
    });
    expect(parseQuantity("1 ½ cups milk")).toMatchObject({
      value: 1.5,
      rest: "cups milk",
    });
    expect(parseQuantity("1½ cups milk")).toMatchObject({
      value: 1.5,
      rest: "cups milk",
    });
    expect(parseQuantity("⅛ tsp salt")).toMatchObject({
      value: 0.125,
      rest: "tsp salt",
    });
    expect(parseQuantity("1,000 g rice")).toMatchObject({
      value: 1000,
      rest: "g rice",
    });
    expect(parseQuantity("200g flour")).toMatchObject({
      value: 200,
      rest: "g flour",
      separator: "",
    });
  });

  it("parses ranges", () => {
    expect(parseQuantity("1-2 tbsp oil")).toMatchObject({
      value: 1,
      upperValue: 2,
      rangeSeparator: "-",
      rest: "tbsp oil",
    });
    expect(parseQuantity("1 to 2 cloves")).toMatchObject({
      value: 1,
      upperValue: 2,
      rangeSeparator: " to ",
      rest: "cloves",
    });
    expect(parseQuantity("2 tomatoes")).not.toHaveProperty("upperValue");
  });

  it("does not misread decimal commas", () => {
    expect(parseQuantity("1,5 kg beef")).toBeNull();
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
