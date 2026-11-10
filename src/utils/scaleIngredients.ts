import { formatQuantity, parseQuantity } from "./parseQuantity";

export function scaleIngredient(text: string, factor: number): string {
  const parsed = parseQuantity(text);
  if (!parsed) {
    return text;
  }

  let quantity = formatQuantity(parsed.value * factor);
  if (parsed.upperValue !== undefined) {
    quantity += `${parsed.rangeSeparator ?? "-"}${formatQuantity(
      parsed.upperValue * factor,
    )}`;
  }

  if (!parsed.rest) {
    return quantity;
  }

  // Keep the original spacing ("200g" stays attached), but never glue a
  // spelled-out quantity to a word it was separated from.
  const separator = parsed.separator ?? " ";
  return `${quantity}${separator}${parsed.rest}`;
}

export function scaleIngredients(items: string[], factor: number): string[] {
  if (!Number.isFinite(factor) || factor <= 0 || Math.abs(factor - 1) <= 0.001) {
    return items;
  }

  return items.map((item) => scaleIngredient(item, factor));
}
