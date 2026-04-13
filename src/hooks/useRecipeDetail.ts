import { useQuery } from "@tanstack/react-query";

import { getRecipeImportDetail } from "../controllers/recipeController";
import type { RecipeImportRecord } from "../types/recipe";

export function useRecipeDetail(recipeImportId: string | undefined) {
  const query = useQuery<RecipeImportRecord>({
    queryKey: ["recipe-detail", recipeImportId],
    queryFn: async () => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return getRecipeImportDetail(recipeImportId);
    },
    enabled: Boolean(recipeImportId),
    staleTime: 1000 * 60 * 10,
  });

  const error = !recipeImportId
    ? "Missing recipe id."
    : query.error instanceof Error
      ? query.error.message
      : query.error
        ? "Unable to load that recipe."
        : "";

  return {
    recipeImport: query.data ?? null,
    isLoading: recipeImportId ? query.isLoading : false,
    isFetching: query.isFetching,
    error,
    refresh: async () => {
      await query.refetch();
    },
  };
}
