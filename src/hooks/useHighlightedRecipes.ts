import { useQuery } from "@tanstack/react-query";

import {
  getHighlightedRecipes,
  type HighlightedRecipes,
} from "../controllers/recipeController";
import { HIGHLIGHTED_RECIPES_KEY } from "./recipeQueryKeys";

export type { HighlightedRecipes };

export function useHighlightedRecipes() {
  const query = useQuery<HighlightedRecipes>({
    queryKey: HIGHLIGHTED_RECIPES_KEY,
    queryFn: () => getHighlightedRecipes(),
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
