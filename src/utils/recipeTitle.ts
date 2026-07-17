import type { RecipeImportRecord } from "../types/recipe";

export const PLACEHOLDER_RECIPE_TITLE = "Untitled recipe import";

/**
 * The name a user should see for a record.
 *
 * Mirrors the display_title_sort generated column in SQL and
 * resolve_display_title in the backend, so cards, sorting, and the API all
 * agree. A null display_title falls through to the pre-feature precedence,
 * which is why records imported before this feature still render correctly.
 */
export function resolveDisplayTitle(record: RecipeImportRecord): string {
  const displayTitle = record.display_title?.trim();
  if (displayTitle) {
    return displayTitle;
  }

  const recipeName = record.recipes_json[0]?.name?.trim();
  if (recipeName) {
    return recipeName;
  }

  const pageTitle = record.page_title?.trim();
  if (pageTitle) {
    return pageTitle;
  }

  return PLACEHOLDER_RECIPE_TITLE;
}
