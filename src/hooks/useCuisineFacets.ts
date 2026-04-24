import { useQuery } from "@tanstack/react-query";

import { getCuisineFacets } from "../controllers/recipeController";

export function useCuisineFacets() {
  const query = useQuery({
    queryKey: ["cuisine-facets"],
    queryFn: getCuisineFacets,
    staleTime: 1000 * 60 * 10,
  });

  let error = "";
  if (query.error) {
    error =
      query.error instanceof Error
        ? query.error.message
        : "Unable to load cuisine filters.";
  }

  return {
    facets: query.data ?? [],
    isLoading: query.isLoading,
    error,
  };
}
