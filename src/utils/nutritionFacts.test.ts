import { describe, expect, it } from "vitest";

import {
  buildNutritionFacts,
  isBatchScalable,
  parseNutrientValue,
  scaleNutritionEntry,
} from "./nutritionFacts";

describe("parseNutrientValue", () => {
  it("parses amount and normalizes unit labels", () => {
    expect(parseNutrientValue("320 kcal")).toEqual({ amount: 320, unit: "kcal" });
    expect(parseNutrientValue("320 calories")).toEqual({
      amount: 320,
      unit: "kcal",
    });
    expect(parseNutrientValue("12 grams")).toEqual({ amount: 12, unit: "g" });
    expect(parseNutrientValue("480 milligrams")).toEqual({
      amount: 480,
      unit: "mg",
    });
    expect(parseNutrientValue("12g")).toEqual({ amount: 12, unit: "g" });
  });

  it("treats a bare calories number as kcal", () => {
    expect(parseNutrientValue("320", { isCalories: true })).toEqual({
      amount: 320,
      unit: "kcal",
    });
  });

  it("keeps a bare non-calorie number unitless", () => {
    expect(parseNutrientValue("12")).toEqual({ amount: 12, unit: null });
  });

  it("returns null for unparseable values", () => {
    expect(parseNutrientValue("a pinch of sodium")).toBeNull();
    expect(parseNutrientValue("12 flurbs")).toBeNull();
    expect(parseNutrientValue("")).toBeNull();
  });
});

describe("buildNutritionFacts", () => {
  it("returns null when the source provided no nutrition", () => {
    expect(buildNutritionFacts(null, 4)).toBeNull();
    expect(buildNutritionFacts({}, 4)).toBeNull();
  });

  it("orders canonical fields before others regardless of source order", () => {
    const facts = buildNutritionFacts(
      {
        protein: "12 g",
        calories: "320 kcal",
        saturatedFat: "4 g",
        sodium: "480 mg",
      },
      4,
    );

    expect(facts?.entries.map((entry) => entry.label)).toEqual([
      "Calories",
      "Protein",
      "Sodium",
      "Saturated Fat",
    ]);
    expect(facts?.entries[0].display).toBe("320 kcal");
  });

  it("cleans labels for non-canonical nutrients", () => {
    const facts = buildNutritionFacts(
      { transFat: "0 g", cholesterol: "30 mg" },
      null,
    );

    expect(facts?.entries.map((entry) => entry.label)).toEqual([
      "Trans Fat",
      "Cholesterol",
    ]);
  });

  it("renders unparseable values verbatim without an amount", () => {
    const facts = buildNutritionFacts({ sodium: "a pinch of sodium" }, 4);
    const sodium = facts?.entries[0];

    expect(sodium?.display).toBe("a pinch of sodium");
    expect(sodium?.amount).toBeNull();
    expect(sodium && isBatchScalable(sodium)).toBe(false);
  });

  it("resolves conflicting duplicate fields first-encountered-wins", () => {
    const facts = buildNutritionFacts(
      { fat: "10 g", fatContent: "12 g" },
      null,
    );

    expect(facts?.entries).toHaveLength(1);
    expect(facts?.entries[0].display).toBe("10 g");
  });

  it("extracts serving size instead of listing it as a nutrient", () => {
    const facts = buildNutritionFacts(
      { calories: "320 kcal", servingSize: "1 slice" },
      null,
    );

    expect(facts?.servingSize).toBe("1 slice");
    expect(facts?.entries.map((entry) => entry.label)).toEqual(["Calories"]);
  });

  it("marks per-serving when a serving size or serving count exists", () => {
    expect(
      buildNutritionFacts({ calories: "320" }, 4)?.perServing,
    ).toBe(true);
    expect(
      buildNutritionFacts({ calories: "320", servingSize: "1 cup" }, null)
        ?.perServing,
    ).toBe(true);
    expect(buildNutritionFacts({ calories: "320" }, null)?.perServing).toBe(
      false,
    );
  });

  it("never invents a percent daily value", () => {
    const facts = buildNutritionFacts({ calories: "320 kcal" }, 4);
    expect(
      facts?.entries.some((entry) => entry.display.includes("%")),
    ).toBe(false);
  });
});

describe("scaleNutritionEntry", () => {
  it("multiplies per-serving values by the serving count", () => {
    const facts = buildNutritionFacts(
      { calories: "320 kcal", protein: "12 g" },
      4,
    );
    const [calories, protein] = facts!.entries;

    expect(scaleNutritionEntry(calories, 8)).toBe("2560 kcal");
    expect(scaleNutritionEntry(protein, 3)).toBe("36 g");
  });

  it("rounds fractional gram totals to one decimal", () => {
    const facts = buildNutritionFacts({ fiber: "1.5 g" }, 4);

    expect(scaleNutritionEntry(facts!.entries[0], 3)).toBe("4.5 g");
  });

  it("excludes percent values from batch scaling", () => {
    const facts = buildNutritionFacts({ vitaminC: "12%" }, 4);

    expect(isBatchScalable(facts!.entries[0])).toBe(false);
  });
});
