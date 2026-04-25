import { formatQuantity, parseQuantity } from "./parseQuantity";

export function scaleIngredient(text: string, factor: number): string {
  const parsed = parseQuantity(text);
  if (!parsed) {
    return text;
  }

  return `${formatQuantity(parsed.value * factor)} ${parsed.rest}`.trim();
}

export function scaleIngredients(items: string[], factor: number): string[] {
  if (!Number.isFinite(factor) || factor <= 0 || Math.abs(factor - 1) <= 0.001) {
    return items;
  }

  return items.map((item) => scaleIngredient(item, factor));
}
