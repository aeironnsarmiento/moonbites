import { useQuery } from "@tanstack/react-query";

import { getRecipeListPage } from "../controllers/recipeController";
import type { RecipeCardItem } from "../types/recipe";

export type HighlightedRecipes = {
  favorites: RecipeCardItem[];
  mostCooked: RecipeCardItem[];
};

export function useHighlightedRecipes() {
  const query = useQuery<HighlightedRecipes>({
    queryKey: ["highlighted-recipes"],
    queryFn: async () => {
      const [favorites, mostCooked] = await Promise.all([
        getRecipeListPage({
          page: 1,
          limit: 4,
          sort: "recent",
          cuisine: null,
          favorite: true,
        }),
        getRecipeListPage({
          page: 1,
          limit: 4,
          sort: "times_cooked",
          cuisine: null,
        }),
      ]);

      return {
        favorites: favorites.items,
        mostCooked: mostCooked.items,
      };
    },
    staleTime: 1000 * 60 * 5,
  });

  return {
    data: query.data ?? { favorites: [], mostCooked: [] },
    isLoading: query.isLoading,
    error:
      query.error instanceof Error
        ? query.error.message
        : query.error
          ? "Unable to load highlighted recipes."
          : "",
  };
}
