import { useMutation, useQueryClient } from "@tanstack/react-query";

import { toggleFavorite } from "../controllers/recipeController";
import {
  HIGHLIGHTED_RECIPES_KEY,
  RECIPE_LIST_KEY,
  invalidateRecipeQueries,
  recipeDetailKey,
} from "./recipeQueryKeys";
import type { HighlightedRecipes } from "./useHighlightedRecipes";
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

function setListItemFavorite(
  data: unknown,
  recipeImportId: string,
  isFavorite: boolean,
): unknown {
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
      item.id === recipeImportId ? { ...item, isFavorite } : item,
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

function setDetailRecordFavorite(
  data: unknown,
  recipeImportId: string,
  isFavorite: boolean,
): unknown {
  if (!data || typeof data !== "object") {
    return data;
  }

  const record = data as Partial<RecipeImportRecord>;
  if (record.id !== recipeImportId) {
    return data;
  }

  return {
    ...record,
    is_favorite: isFavorite,
  };
}

function isHighlightedRecipes(data: unknown): data is HighlightedRecipes {
  return Boolean(
    data &&
      typeof data === "object" &&
      "favorites" in data &&
      "recent" in data,
  );
}

function findHighlightedItem(
  data: HighlightedRecipes,
  recipeImportId: string,
): RecipeCardItem | null {
  return (
    [...data.favorites, ...data.recent].find(
      (item) => item.id === recipeImportId,
    ) ?? null
  );
}

function toggleHighlightedList(
  items: RecipeCardItem[],
  recipeImportId: string,
): RecipeCardItem[] {
  return items.map((item) =>
    item.id === recipeImportId
      ? { ...item, isFavorite: !item.isFavorite }
      : item,
  );
}

function setHighlightedListFavorite(
  items: RecipeCardItem[],
  recipeImportId: string,
  isFavorite: boolean,
): RecipeCardItem[] {
  return items.map((item) =>
    item.id === recipeImportId ? { ...item, isFavorite } : item,
  );
}

export function toggleHighlightedRecipesData(
  data: unknown,
  recipeImportId: string,
): HighlightedRecipes | undefined {
  if (!isHighlightedRecipes(data)) {
    return data as HighlightedRecipes | undefined;
  }

  const currentItem = findHighlightedItem(data, recipeImportId);
  if (!currentItem) {
    return data;
  }

  const nextIsFavorite = !currentItem.isFavorite;
  const updatedItem = { ...currentItem, isFavorite: nextIsFavorite };
  const toggledFavorites = toggleHighlightedList(
    data.favorites,
    recipeImportId,
  );
  const favorites = nextIsFavorite
    ? toggledFavorites.some((item) => item.id === recipeImportId)
      ? toggledFavorites
      : [updatedItem, ...toggledFavorites].slice(0, 4)
    : toggledFavorites.filter((item) => item.id !== recipeImportId);

  return {
    ...data,
    favorites,
    recent: toggleHighlightedList(data.recent, recipeImportId),
    favoriteCount: Math.max(
      0,
      data.favoriteCount + (nextIsFavorite ? 1 : -1),
    ),
  };
}

function setHighlightedRecipesFavorite(
  data: unknown,
  recipeImportId: string,
  isFavorite: boolean,
): HighlightedRecipes | undefined {
  if (!isHighlightedRecipes(data)) {
    return data as HighlightedRecipes | undefined;
  }

  const currentItem = findHighlightedItem(data, recipeImportId);
  if (!currentItem) {
    return data;
  }

  const updatedItem = { ...currentItem, isFavorite };
  const updatedFavorites = setHighlightedListFavorite(
    data.favorites,
    recipeImportId,
    isFavorite,
  );
  const favorites = isFavorite
    ? updatedFavorites.some((item) => item.id === recipeImportId)
      ? updatedFavorites
      : [updatedItem, ...updatedFavorites].slice(0, 4)
    : updatedFavorites.filter((item) => item.id !== recipeImportId);
  const favoriteCountDelta =
    currentItem.isFavorite === isFavorite ? 0 : isFavorite ? 1 : -1;

  return {
    ...data,
    favorites,
    recent: setHighlightedListFavorite(
      data.recent,
      recipeImportId,
      isFavorite,
    ),
    favoriteCount: Math.max(0, data.favoriteCount + favoriteCountDelta),
  };
}

export function useToggleFavorite(recipeImportId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => toggleFavorite(recipeImportId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: RECIPE_LIST_KEY });
      await queryClient.cancelQueries({ queryKey: HIGHLIGHTED_RECIPES_KEY });
      await queryClient.cancelQueries({
        queryKey: recipeDetailKey(recipeImportId),
      });

      const listSnapshots = queryClient
        .getQueriesData({ queryKey: RECIPE_LIST_KEY })
        .map(([queryKey, data]) => ({ queryKey, data }));
      const detailSnapshot = queryClient.getQueryData(
        recipeDetailKey(recipeImportId),
      );
      const highlightedSnapshot = queryClient.getQueryData(
        HIGHLIGHTED_RECIPES_KEY,
      );

      for (const { queryKey, data } of listSnapshots) {
        queryClient.setQueryData(queryKey, toggleListItem(data, recipeImportId));
      }
      queryClient.setQueryData(
        recipeDetailKey(recipeImportId),
        toggleDetailRecord(detailSnapshot, recipeImportId),
      );
      queryClient.setQueryData(
        HIGHLIGHTED_RECIPES_KEY,
        toggleHighlightedRecipesData(highlightedSnapshot, recipeImportId),
      );

      return { listSnapshots, detailSnapshot, highlightedSnapshot };
    },
    onError: (_error, _variables, context) => {
      for (const snapshot of context?.listSnapshots ?? []) {
        queryClient.setQueryData(snapshot.queryKey, snapshot.data);
      }
      queryClient.setQueryData(
        recipeDetailKey(recipeImportId),
        context?.detailSnapshot,
      );
      queryClient.setQueryData(
        HIGHLIGHTED_RECIPES_KEY,
        context?.highlightedSnapshot,
      );
    },
    onSuccess: (record) => {
      const updatedRecipeImportId = record.id;
      const isFavorite = record.is_favorite;
      const listSnapshots = queryClient.getQueriesData({
        queryKey: RECIPE_LIST_KEY,
      });

      for (const [queryKey, data] of listSnapshots) {
        queryClient.setQueryData(
          queryKey,
          setListItemFavorite(data, updatedRecipeImportId, isFavorite),
        );
      }
      queryClient.setQueryData(
        recipeDetailKey(updatedRecipeImportId),
        setDetailRecordFavorite(
          queryClient.getQueryData(recipeDetailKey(updatedRecipeImportId)),
          updatedRecipeImportId,
          isFavorite,
        ),
      );
      queryClient.setQueryData(
        HIGHLIGHTED_RECIPES_KEY,
        setHighlightedRecipesFavorite(
          queryClient.getQueryData(HIGHLIGHTED_RECIPES_KEY),
          updatedRecipeImportId,
          isFavorite,
        ),
      );
    },
    onSettled: async (record) => {
      await invalidateRecipeQueries(queryClient, {
        detailId: record?.id ?? recipeImportId,
      });
    },
  });
}
