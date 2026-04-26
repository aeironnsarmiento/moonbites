import { useQuery } from "@tanstack/react-query";

import { getRecipeListPage } from "../controllers/recipeController";
import type { RecipeCardItem } from "../types/recipe";

export type HighlightedRecipes = {
  favorites: RecipeCardItem[];
  mostCooked: RecipeCardItem[];
  recent: RecipeCardItem[];
  totalCount: number;
  favoriteCount: number;
};

export function useHighlightedRecipes() {
  const query = useQuery<HighlightedRecipes>({
    queryKey: ["highlighted-recipes"],
    queryFn: async () => {
      const [favorites, mostCooked, recent, totalMeta, favoriteMeta] = await Promise.all([
        getRecipeListPage({ page: 1, limit: 4, sort: "recent", cuisine: null, favorite: true }),
        getRecipeListPage({ page: 1, limit: 4, sort: "times_cooked", cuisine: null }),
        getRecipeListPage({ page: 1, limit: 5, sort: "recent", cuisine: null }),
        getRecipeListPage({ page: 1, limit: 1, sort: "recent", cuisine: null }),
        getRecipeListPage({ page: 1, limit: 1, sort: "recent", cuisine: null, favorite: true }),
      ]);

      return {
        favorites: favorites.items,
        mostCooked: mostCooked.items,
        recent: recent.items,
        totalCount: totalMeta.total_count,
        favoriteCount: favoriteMeta.total_count,
      };
    },
    staleTime: 1000 * 60 * 5,
  });

  return {
    data: query.data ?? {
      favorites: [],
      mostCooked: [],
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
