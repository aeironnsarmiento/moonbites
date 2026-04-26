import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { RecipeSortOption } from "../types/api";

const RECIPE_LIST_PREFERENCES_KEY = ["recipe-list-preferences"] as const;
const RECIPE_LIST_PREFERENCES_STORAGE_KEY = "moonbites:recipe-list-preferences";
const VALID_SORT_OPTIONS = new Set<RecipeSortOption>([
  "recent",
  "az",
  "za",
  "times_cooked",
  "favorites",
]);

export type RecipeListPreferences = {
  sort: RecipeSortOption;
  cuisine: string;
};

const DEFAULT_RECIPE_LIST_PREFERENCES: RecipeListPreferences = {
  sort: "recent",
  cuisine: "",
};

function canUseSessionStorage() {
  return typeof window !== "undefined" && Boolean(window.sessionStorage);
}

function sanitizePreferences(value: unknown): RecipeListPreferences {
  if (!value || typeof value !== "object") {
    return DEFAULT_RECIPE_LIST_PREFERENCES;
  }

  const maybePreferences = value as Partial<RecipeListPreferences>;
  const sort = VALID_SORT_OPTIONS.has(maybePreferences.sort as RecipeSortOption)
    ? (maybePreferences.sort as RecipeSortOption)
    : DEFAULT_RECIPE_LIST_PREFERENCES.sort;
  const cuisine =
    typeof maybePreferences.cuisine === "string"
      ? maybePreferences.cuisine
      : DEFAULT_RECIPE_LIST_PREFERENCES.cuisine;

  return { sort, cuisine };
}

function readStoredPreferences(): RecipeListPreferences {
  if (!canUseSessionStorage()) {
    return DEFAULT_RECIPE_LIST_PREFERENCES;
  }

  try {
    const storedValue = window.sessionStorage.getItem(
      RECIPE_LIST_PREFERENCES_STORAGE_KEY,
    );
    if (!storedValue) {
      return DEFAULT_RECIPE_LIST_PREFERENCES;
    }

    return sanitizePreferences(JSON.parse(storedValue));
  } catch {
    return DEFAULT_RECIPE_LIST_PREFERENCES;
  }
}

function writeStoredPreferences(preferences: RecipeListPreferences) {
  if (!canUseSessionStorage()) {
    return;
  }

  try {
    window.sessionStorage.setItem(
      RECIPE_LIST_PREFERENCES_STORAGE_KEY,
      JSON.stringify(preferences),
    );
  } catch {
    // Ignore storage failures so private browsing or quota issues do not break sorting.
  }
}

export function useRecipeListPreferences() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: RECIPE_LIST_PREFERENCES_KEY,
    queryFn: readStoredPreferences,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  const preferences = query.data ?? DEFAULT_RECIPE_LIST_PREFERENCES;

  const setPreferences = (nextPreferences: RecipeListPreferences) => {
    const sanitizedPreferences = sanitizePreferences(nextPreferences);
    queryClient.setQueryData(
      RECIPE_LIST_PREFERENCES_KEY,
      sanitizedPreferences,
    );
    writeStoredPreferences(sanitizedPreferences);
  };

  return {
    sort: preferences.sort,
    cuisine: preferences.cuisine,
    setSort: (sort: RecipeSortOption) => {
      setPreferences({ ...preferences, sort });
    },
    setCuisine: (cuisine: string) => {
      setPreferences({ ...preferences, cuisine });
    },
  };
}
