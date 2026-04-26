import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adjustRecipeImportTimesCooked,
  deleteRecipeImport,
  getRecipeImportDetail,
  updateRecipeImportMetadata,
  updateRecipeServings,
  updateRecipeImportOverrides,
} from "../controllers/recipeController";
import type {
  RecipeImportRecord,
  UpdateRecipeMetadataPayload,
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

  const deleteRecipeMutation = useMutation({
    mutationFn: () => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return deleteRecipeImport(recipeImportId);
    },
    onSuccess: async ({ id }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({ queryKey: ["highlighted-recipes"] }),
      ]);
      queryClient.removeQueries({ queryKey: ["recipe-detail", id], exact: true });
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

  const updateServingsMutation = useMutation({
    mutationFn: (servings: number) => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return updateRecipeServings(recipeImportId, servings);
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

  const updateMetadataMutation = useMutation({
    mutationFn: (payload: UpdateRecipeMetadataPayload) => {
      if (!recipeImportId) {
        throw new Error("Missing recipe id.");
      }

      return updateRecipeImportMetadata(recipeImportId, payload);
    },
    onSuccess: async (record) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({ queryKey: ["highlighted-recipes"] }),
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
      : deleteRecipeMutation.error instanceof Error
        ? deleteRecipeMutation.error.message
      : updateTimesCookedMutation.error instanceof Error
        ? updateTimesCookedMutation.error.message
        : updateOverridesMutation.error instanceof Error
          ? updateOverridesMutation.error.message
          : updateServingsMutation.error instanceof Error
            ? updateServingsMutation.error.message
            : updateMetadataMutation.error instanceof Error
              ? updateMetadataMutation.error.message
              : query.error
                ? "Unable to load that recipe."
                : deleteRecipeMutation.error
                  ? "Unable to delete recipe."
                : updateTimesCookedMutation.error
                  ? "Unable to update cooked count."
                  : updateOverridesMutation.error
                    ? "Unable to save recipe edits."
                    : updateServingsMutation.error
                      ? "Unable to update servings."
                      : updateMetadataMutation.error
                        ? "Unable to update recipe details."
                        : "";

  return {
    recipeImport: query.data ?? null,
    isLoading: recipeImportId ? query.isLoading : false,
    isFetching: query.isFetching,
    isDeleting: deleteRecipeMutation.isPending,
    isUpdatingTimesCooked: updateTimesCookedMutation.isPending,
    isSavingOverrides: updateOverridesMutation.isPending,
    isSavingServings: updateServingsMutation.isPending,
    isSavingMetadata: updateMetadataMutation.isPending,
    error,
    updateTimesCooked: async (delta: -1 | 1) => {
      await updateTimesCookedMutation.mutateAsync({ delta });
    },
    deleteRecipe: async () => {
      await deleteRecipeMutation.mutateAsync();
    },
    saveOverrides: async (payload: UpdateRecipeOverridesPayload) => {
      await updateOverridesMutation.mutateAsync(payload);
    },
    saveServings: async (servings: number) => {
      await updateServingsMutation.mutateAsync(servings);
    },
    saveMetadata: async (payload: UpdateRecipeMetadataPayload) => {
      await updateMetadataMutation.mutateAsync(payload);
    },
    refresh: async () => {
      await query.refetch();
    },
  };
}
