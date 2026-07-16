import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  getRecipeListPage,
  type RecipeListPageData,
} from "../controllers/recipeController";
import type { RecipeSortOption } from "../types/api";
import { normalizeSearchTerm } from "../utils/searchTerm";
import { RECIPE_LIST_KEY } from "./recipeQueryKeys";

type UseRecipeListParams = {
  page: number;
  pageSize: number;
  sort: RecipeSortOption;
  cuisine: string | null;
  favorite?: boolean | null;
  search?: string | null;
};

function recipeListQueryKey(
  page: number,
  pageSize: number,
  sort: RecipeSortOption,
  cuisine: string | null,
  favorite: boolean | null,
  search: string | null,
) {
  const key = [...RECIPE_LIST_KEY, page, pageSize, sort, cuisine, favorite];
  return search ? [...key, search] : key;
}

export function useRecipeList({
  page,
  pageSize,
  sort,
  cuisine,
  favorite = null,
  search = null,
}: UseRecipeListParams) {
  const queryClient = useQueryClient();
  const normalizedCuisine = cuisine && cuisine.length > 0 ? cuisine : null;
  const normalizedSearch = normalizeSearchTerm(search);
  const query = useQuery<RecipeListPageData>({
    queryKey: recipeListQueryKey(
      page,
      pageSize,
      sort,
      normalizedCuisine,
      favorite,
      normalizedSearch,
    ),
    queryFn: () =>
      getRecipeListPage({
        page,
        pageSize,
        sort,
        cuisine: normalizedCuisine,
        favorite,
        search: normalizedSearch,
      }),
    placeholderData: keepPreviousData,
  });

  const [lastGoodData, setLastGoodData] = useState<RecipeListPageData | null>(
    null,
  );
  if (query.data && query.data !== lastGoodData) {
    setLastGoodData(query.data);
  }
  const data = query.data ?? (query.error ? lastGoodData : null);

  const totalPages = query.data?.total_pages ?? 0;
  const nextPage = page + 1;
  const isPlaceholder = query.isPlaceholderData;

  useEffect(() => {
    if (isPlaceholder || nextPage > totalPages) {
      return;
    }

    void queryClient.prefetchQuery({
      queryKey: recipeListQueryKey(
        nextPage,
        pageSize,
        sort,
        normalizedCuisine,
        favorite,
        normalizedSearch,
      ),
      queryFn: () =>
        getRecipeListPage({
          page: nextPage,
          pageSize,
          sort,
          cuisine: normalizedCuisine,
          favorite,
          search: normalizedSearch,
        }),
      staleTime: 1000 * 60 * 5,
    });
  }, [
    isPlaceholder,
    nextPage,
    pageSize,
    queryClient,
    sort,
    normalizedCuisine,
    normalizedSearch,
    totalPages,
    favorite,
  ]);

  let error = "";
  if (query.error) {
    error =
      query.error instanceof Error
        ? query.error.message
        : "Unable to load recipes.";
  }

  return {
    data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error,
    refresh: async () => {
      await query.refetch();
    },
  };
}
