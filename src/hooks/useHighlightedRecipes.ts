import { useQuery } from "@tanstack/react-query";

import { getRecipeListPage } from "../controllers/recipeController";
import { HIGHLIGHTED_RECIPES_KEY } from "./recipeQueryKeys";
import type { RecipeCardItem } from "../types/recipe";

export type HighlightedRecipes = {
  favorites: RecipeCardItem[];
  recent: RecipeCardItem[];
  totalCount: number;
  favoriteCount: number;
};

export function useHighlightedRecipes() {
  const query = useQuery<HighlightedRecipes>({
    queryKey: HIGHLIGHTED_RECIPES_KEY,
    queryFn: async () => {
      const [favorites, recent] = await Promise.all([
        getRecipeListPage({ page: 1, limit: 4, sort: "recent", cuisine: null, favorite: true }),
        getRecipeListPage({ page: 1, limit: 5, sort: "recent", cuisine: null }),
      ]);

      return {
        favorites: favorites.items,
        recent: recent.items,
        totalCount: recent.total_count,
        favoriteCount: favorites.total_count,
      };
    },
    staleTime: 1000 * 60 * 5,
  });

  return {
    data: query.data ?? {
      favorites: [],
      recent: [],
      totalCount: 0,
      favoriteCount: 0,
    },
    isLoading: query.isLoading,
    error:
      query.error instanceof Error
        ? query.error.message
        : query.error
          ? "Unable to load highlighted recipes."
          : "",
  };
}
