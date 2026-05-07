import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  createManualRecipe,
  mapRecipeImportToCard,
} from "../controllers/recipeController";
import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";
import {
  HIGHLIGHTED_RECIPES_KEY,
  invalidateRecipeQueries,
} from "./recipeQueryKeys";
import type { HighlightedRecipes } from "./useHighlightedRecipes";

type CreateRecipePayload = {
  recipe: NormalizedRecipe;
  title?: string;
};

const HOME_RECENT_LIMIT = 5;

function prependToHighlighted(
  data: HighlightedRecipes | undefined,
  record: RecipeImportRecord,
): HighlightedRecipes | undefined {
  if (!data) {
    return data;
  }

  const card = mapRecipeImportToCard(record);
  const recent = [card, ...data.recent.filter((item) => item.id !== card.id)].slice(
    0,
    HOME_RECENT_LIMIT,
  );

  return {
    ...data,
    recent,
    totalCount: data.totalCount + 1,
  };
}

export function useCreateRecipe() {
  const queryClient = useQueryClient();

  const mutation = useMutation<RecipeImportRecord, Error, CreateRecipePayload>({
    mutationFn: async ({ recipe, title }) => createManualRecipe(recipe, title),
    onSuccess: async (record) => {
      queryClient.setQueryData<HighlightedRecipes | undefined>(
        HIGHLIGHTED_RECIPES_KEY,
        (current) => prependToHighlighted(current, record),
      );

      await invalidateRecipeQueries(queryClient, { detailId: record.id });
    },
  });

  return {
    createRecipe: async (payload: CreateRecipePayload) => mutation.mutateAsync(payload),
    isLoading: mutation.isPending,
    error: mutation.error?.message ?? "",
  };
}
