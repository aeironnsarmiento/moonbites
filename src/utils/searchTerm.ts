export const MIN_SEARCH_LENGTH = 2;
export const MAX_SEARCH_LENGTH = 100;

export function normalizeSearchTerm(
  value: string | null | undefined,
): string | null {
  const trimmed = (value ?? "").trim();
  if (trimmed.length < MIN_SEARCH_LENGTH) {
    return null;
  }
  return trimmed.slice(0, MAX_SEARCH_LENGTH).trimEnd();
}
