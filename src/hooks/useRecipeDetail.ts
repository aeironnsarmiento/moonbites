import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adjustRecipeImportTimesCooked,
  getRecipeImportDetail,
  updateRecipeImportOverrides,
} from "../controllers/recipeController";
import type {
  RecipeImportRecord,
  UpdateRecipeOverridesPayload,
} from "../types/recipe";

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
        queryClient.invalidateQueries({
          queryKey: ["recipe-detail", record.id],
        }),
      ]);
    },
  });

  const updateOverridesMutation = useMutation({
    mutationFn: (payload: UpdateRecipeOverridesPayload) => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return updateRecipeImportOverrides(recipeImportId, payload);
    },
    onSuccess: async (record) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({
          queryKey: ["recipe-detail", record.id],
        }),
      ]);
    },
  });

  const error = !recipeImportId
    ? "Missing recipe id."
    : query.error instanceof Error
      ? query.error.message
      : updateTimesCookedMutation.error instanceof Error
        ? updateTimesCookedMutation.error.message
        : updateOverridesMutation.error instanceof Error
          ? updateOverridesMutation.error.message
          : query.error
            ? "Unable to load that recipe."
            : updateTimesCookedMutation.error
              ? "Unable to update cooked count."
              : updateOverridesMutation.error
                ? "Unable to save recipe edits."
                : "";

  return {
    recipeImport: query.data ?? null,
    isLoading: recipeImportId ? query.isLoading : false,
    isFetching: query.isFetching,
    isUpdatingTimesCooked: updateTimesCookedMutation.isPending,
    isSavingOverrides: updateOverridesMutation.isPending,
    error,
    updateTimesCooked: async (delta: -1 | 1) => {
      await updateTimesCookedMutation.mutateAsync({ delta });
    },
    saveOverrides: async (payload: UpdateRecipeOverridesPayload) => {
      await updateOverridesMutation.mutateAsync(payload);
    },
    refresh: async () => {
      await query.refetch();
    },
  };
}
