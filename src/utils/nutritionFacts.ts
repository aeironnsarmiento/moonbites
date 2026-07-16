export type NutritionFactEntry = {
  id: string;
  label: string;
  isCanonical: boolean;
  amount: number | null;
  unit: string | null;
  display: string;
};

export type NutritionFacts = {
  entries: NutritionFactEntry[];
  servingSize: string | null;
  perServing: boolean;
};

const CANONICAL_FIELDS: Array<{ id: string; label: string; aliases: string[] }> = [
  { id: "calories", label: "Calories", aliases: ["calories", "calorie", "energy"] },
  { id: "fat", label: "Fat", aliases: ["fat", "fatcontent", "totalfat"] },
  {
    id: "carbohydrates",
    label: "Carbohydrates",
    aliases: [
      "carbohydrates",
      "carbohydrate",
      "carbohydratecontent",
      "carbs",
      "totalcarbohydrate",
    ],
  },
  { id: "protein", label: "Protein", aliases: ["protein", "proteincontent"] },
  { id: "sodium", label: "Sodium", aliases: ["sodium", "sodiumcontent"] },
  {
    id: "fiber",
    label: "Fiber",
    aliases: ["fiber", "fibre", "fibercontent", "dietaryfiber"],
  },
  { id: "sugar", label: "Sugar", aliases: ["sugar", "sugars", "sugarcontent"] },
];

const SERVING_SIZE_ALIASES = new Set(["servingsize"]);

const UNIT_LABELS: Record<string, string> = {
  kcal: "kcal",
  calories: "kcal",
  calorie: "kcal",
  cal: "kcal",
  g: "g",
  gram: "g",
  grams: "g",
  mg: "mg",
  milligram: "mg",
  milligrams: "mg",
  mcg: "mcg",
  "µg": "mcg",
  "μg": "mcg",
  microgram: "mcg",
  micrograms: "mcg",
  "%": "%",
};

function foldKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z]/g, "");
}

function canonicalFieldFor(key: string) {
  const folded = foldKey(key);
  return CANONICAL_FIELDS.find((field) => field.aliases.includes(folded)) ?? null;
}

function cleanLabel(key: string): string {
  const spaced = key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();
  return spaced
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function parseAmount(text: string): number | null {
  const thousands = /^\d{1,3}(,\d{3})+(\.\d+)?$/.test(text)
    ? text.replace(/,/g, "")
    : text;
  if (!/^\d+(\.\d+)?$/.test(thousands)) {
    return null;
  }
  const value = Number(thousands);
  return Number.isFinite(value) ? value : null;
}

type ParsedNutrient = {
  amount: number;
  unit: string | null;
};

export function parseNutrientValue(
  raw: string,
  options: { isCalories?: boolean } = {},
): ParsedNutrient | null {
  const match = raw.trim().match(/^([\d.,]+)\s*([A-Za-zµμ%]+)?\.?$/u);
  if (!match) {
    return null;
  }

  const amount = parseAmount(match[1]);
  if (amount === null) {
    return null;
  }

  let unit: string | null = null;
  if (match[2]) {
    unit = UNIT_LABELS[match[2].toLowerCase()] ?? null;
    if (!unit) {
      return null;
    }
  }

  if (!unit && options.isCalories) {
    unit = "kcal";
  }

  return { amount, unit };
}

export function formatAmount(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

function formatDisplay(amount: number, unit: string | null): string {
  if (!unit) {
    return formatAmount(amount);
  }
  if (unit === "%") {
    return `${formatAmount(amount)}%`;
  }
  return `${formatAmount(amount)} ${unit}`;
}

export function isBatchScalable(entry: NutritionFactEntry): boolean {
  return entry.amount !== null && entry.unit !== "%";
}

export function scaleNutritionEntry(
  entry: NutritionFactEntry,
  servingCount: number,
): string {
  if (entry.amount === null) {
    return entry.display;
  }
  const total = entry.amount * servingCount;
  const rounded = entry.unit === "kcal" ? Math.round(total) : total;
  return formatDisplay(rounded, entry.unit);
}

export function buildNutritionFacts(
  nutrition: Record<string, string> | null | undefined,
  servings: number | null,
): NutritionFacts | null {
  if (!nutrition) {
    return null;
  }

  let servingSize: string | null = null;
  const canonical = new Map<string, NutritionFactEntry>();
  const others: NutritionFactEntry[] = [];
  const seenOther = new Set<string>();

  for (const [key, rawValue] of Object.entries(nutrition)) {
    const value = rawValue?.trim();
    if (!value) {
      continue;
    }

    if (SERVING_SIZE_ALIASES.has(foldKey(key))) {
      servingSize = servingSize ?? value;
      continue;
    }

    const field = canonicalFieldFor(key);
    if (field) {
      if (canonical.has(field.id)) {
        continue;
      }
      const parsed = parseNutrientValue(value, {
        isCalories: field.id === "calories",
      });
      canonical.set(field.id, {
        id: field.id,
        label: field.label,
        isCanonical: true,
        amount: parsed?.amount ?? null,
        unit: parsed?.unit ?? null,
        display: parsed ? formatDisplay(parsed.amount, parsed.unit) : value,
      });
      continue;
    }

    const label = cleanLabel(key);
    const identity = label.toLowerCase();
    if (seenOther.has(identity)) {
      continue;
    }
    seenOther.add(identity);
    const parsed = parseNutrientValue(value);
    others.push({
      id: foldKey(key) || identity,
      label,
      isCanonical: false,
      amount: parsed?.amount ?? null,
      unit: parsed?.unit ?? null,
      display: parsed ? formatDisplay(parsed.amount, parsed.unit) : value,
    });
  }

  const entries = [
    ...CANONICAL_FIELDS.flatMap((field) => {
      const entry = canonical.get(field.id);
      return entry ? [entry] : [];
    }),
    ...others,
  ];

  if (entries.length === 0 && !servingSize) {
    return null;
  }

  const hasServingCount = servings !== null && servings > 0;

  return {
    entries,
    servingSize,
    perServing: Boolean(servingSize) || hasServingCount,
  };
}
