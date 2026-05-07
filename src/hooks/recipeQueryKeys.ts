import type { QueryClient } from "@tanstack/react-query";

export const RECIPE_LIST_KEY = ["recipe-list"] as const;
export const HIGHLIGHTED_RECIPES_KEY = ["highlighted-recipes"] as const;

export function recipeDetailKey(recipeImportId: string) {
  return ["recipe-detail", recipeImportId] as const;
}

export type InvalidateRecipeQueriesOptions = {
  detailId?: string;
};

export async function invalidateRecipeQueries(
  queryClient: QueryClient,
  { detailId }: InvalidateRecipeQueriesOptions = {},
) {
  const tasks = [
    queryClient.invalidateQueries({ queryKey: RECIPE_LIST_KEY }),
    queryClient.invalidateQueries({ queryKey: HIGHLIGHTED_RECIPES_KEY }),
  ];

  if (detailId) {
    tasks.push(
      queryClient.invalidateQueries({ queryKey: recipeDetailKey(detailId) }),
    );
  }

  await Promise.all(tasks);
}
