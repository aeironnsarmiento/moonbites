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

export function useRecipeList(page: number, pageSize: number) {
  const queryClient = useQueryClient();
  const query = useQuery<RecipeListPageData>({
    queryKey: ["recipe-list", page, pageSize],
    queryFn: () => getRecipeListPage(page, pageSize),
    placeholderData: keepPreviousData,
  });

  const totalPages = query.data?.total_pages ?? 0;
  const nextPage = page + 1;

  useEffect(() => {
    if (nextPage > totalPages) {
      return;
    }

    void queryClient.prefetchQuery({
      queryKey: ["recipe-list", nextPage, pageSize],
      queryFn: () => getRecipeListPage(nextPage, pageSize),
      staleTime: 1000 * 60 * 5,
    });
  }, [nextPage, pageSize, queryClient, totalPages]);

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
