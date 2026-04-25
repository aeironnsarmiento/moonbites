import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import {
  getRecipeListPage,
  type RecipeListPageData,
} from "../controllers/recipeController";
import type { RecipeSortOption } from "../types/api";

type UseRecipeListParams = {
  page: number;
  pageSize: number;
  sort: RecipeSortOption;
  cuisine: string | null;
  favorite?: boolean | null;
};

export function useRecipeList({
  page,
  pageSize,
  sort,
  cuisine,
  favorite = null,
}: UseRecipeListParams) {
  const queryClient = useQueryClient();
  const normalizedCuisine = cuisine && cuisine.length > 0 ? cuisine : null;
  const query = useQuery<RecipeListPageData>({
    queryKey: ["recipe-list", page, pageSize, sort, normalizedCuisine, favorite],
    queryFn: () =>
      getRecipeListPage({
        page,
        pageSize,
        sort,
        cuisine: normalizedCuisine,
        favorite,
      }),
    placeholderData: keepPreviousData,
  });

  const totalPages = query.data?.total_pages ?? 0;
  const nextPage = page + 1;

  useEffect(() => {
    if (nextPage > totalPages) {
      return;
    }

    void queryClient.prefetchQuery({
      queryKey: [
        "recipe-list",
        nextPage,
        pageSize,
        sort,
        normalizedCuisine,
        favorite,
      ],
      queryFn: () =>
        getRecipeListPage({
          page: nextPage,
          pageSize,
          sort,
          cuisine: normalizedCuisine,
          favorite,
        }),
      staleTime: 1000 * 60 * 5,
    });
  }, [
    nextPage,
    pageSize,
    queryClient,
    sort,
    normalizedCuisine,
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
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error,
    refresh: async () => {
      await query.refetch();
    },
  };
}
