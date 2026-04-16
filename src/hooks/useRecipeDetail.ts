import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adjustRecipeImportTimesCooked,
  getRecipeImportDetail,
} from "../controllers/recipeController";
import type { RecipeImportRecord } from "../types/recipe";

export function useRecipeDetail(recipeImportId: string | undefined) {
  const queryClient = useQueryClient();
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

  const updateTimesCookedMutation = useMutation({
    mutationFn: ({ delta }: { delta: -1 | 1 }) => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return adjustRecipeImportTimesCooked(recipeImportId, delta);
    },
    onSuccess: async (record) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({ queryKey: ["recipe-detail", record.id] }),
      ]);
    },
  });

  const error = !recipeImportId
    ? "Missing recipe id."
    : query.error instanceof Error
      ? query.error.message
      : updateTimesCookedMutation.error instanceof Error
        ? updateTimesCookedMutation.error.message
      : query.error
        ? "Unable to load that recipe."
        : updateTimesCookedMutation.error
          ? "Unable to update cooked count."
        : "";

  return {
    recipeImport: query.data ?? null,
    isLoading: recipeImportId ? query.isLoading : false,
    isFetching: query.isFetching,
    isUpdatingTimesCooked: updateTimesCookedMutation.isPending,
    error,
    updateTimesCooked: async (delta: -1 | 1) => {
      await updateTimesCookedMutation.mutateAsync({ delta });
    },
    refresh: async () => {
      await query.refetch();
    },
  };
}
