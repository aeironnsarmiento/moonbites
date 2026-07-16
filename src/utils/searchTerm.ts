export const MIN_SEARCH_LENGTH = 2;

export function normalizeSearchTerm(
  value: string | null | undefined,
): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed.length >= MIN_SEARCH_LENGTH ? trimmed : null;
}
