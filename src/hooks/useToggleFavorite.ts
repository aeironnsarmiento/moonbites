import { useMutation, useQueryClient } from "@tanstack/react-query";

import { toggleFavorite } from "../controllers/recipeController";
import type { RecipeCardItem, RecipeImportRecord } from "../types/recipe";

type RecipeListLike = {
  items?: RecipeCardItem[];
};

function toggleListItem(data: unknown, recipeImportId: string): unknown {
  if (!data || typeof data !== "object" || !("items" in data)) {
    return data;
  }

  const listData = data as RecipeListLike;
  if (!Array.isArray(listData.items)) {
    return data;
  }

  return {
    ...listData,
    items: listData.items.map((item) =>
      item.id === recipeImportId
        ? { ...item, isFavorite: !item.isFavorite }
        : item,
    ),
  };
}

function toggleDetailRecord(data: unknown, recipeImportId: string): unknown {
  if (!data || typeof data !== "object") {
    return data;
  }

  const record = data as Partial<RecipeImportRecord>;
  if (record.id !== recipeImportId) {
    return data;
  }

  return {
    ...record,
    is_favorite: !record.is_favorite,
  };
}

export function useToggleFavorite(recipeImportId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => toggleFavorite(recipeImportId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["recipe-list"] });
      await queryClient.cancelQueries({
        queryKey: ["recipe-detail", recipeImportId],
      });

      const listSnapshots = queryClient
        .getQueriesData({ queryKey: ["recipe-list"] })
        .map(([queryKey, data]) => ({ queryKey, data }));
      const detailSnapshot = queryClient.getQueryData([
        "recipe-detail",
        recipeImportId,
      ]);

      for (const { queryKey, data } of listSnapshots) {
        queryClient.setQueryData(queryKey, toggleListItem(data, recipeImportId));
      }
      queryClient.setQueryData(
        ["recipe-detail", recipeImportId],
        toggleDetailRecord(detailSnapshot, recipeImportId),
      );

      return { listSnapshots, detailSnapshot };
    },
    onError: (_error, _variables, context) => {
      for (const snapshot of context?.listSnapshots ?? []) {
        queryClient.setQueryData(snapshot.queryKey, snapshot.data);
      }
      queryClient.setQueryData(
        ["recipe-detail", recipeImportId],
        context?.detailSnapshot,
      );
    },
    onSettled: async (record) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe-list"] }),
        queryClient.invalidateQueries({ queryKey: ["highlighted-recipes"] }),
        queryClient.invalidateQueries({
          queryKey: ["recipe-detail", record?.id ?? recipeImportId],
        }),
      ]);
    },
  });
}
