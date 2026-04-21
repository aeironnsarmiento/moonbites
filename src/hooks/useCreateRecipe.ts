import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createManualRecipe } from "../controllers/recipeController";
import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";

type CreateRecipePayload = {
  recipe: NormalizedRecipe;
  title?: string;
};

export function useCreateRecipe() {
  const queryClient = useQueryClient();

  const mutation = useMutation<RecipeImportRecord, Error, CreateRecipePayload>({
    mutationFn: async ({ recipe, title }) => createManualRecipe(recipe, title),
    onSuccess: async (record) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({ queryKey: ["recipe-detail", record.id] }),
      ]);
    },
  });

  return {
    createRecipe: async (payload: CreateRecipePayload) => mutation.mutateAsync(payload),
    isLoading: mutation.isPending,
    error: mutation.error?.message ?? "",
  };
}