import { useState } from "react";

import { Button, Heading, HStack, Stack, Text } from "@chakra-ui/react";
import { useSearchParams } from "react-router-dom";

import { PaginationControls } from "../../components/PaginationControls/PaginationControls";
import { RecipeList } from "../../components/RecipeList/RecipeList";
import { useCuisineFacets } from "../../hooks/useCuisineFacets";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useRecipeList } from "../../hooks/useRecipeList";
import { useRecipeListPreferences } from "../../hooks/useRecipeListPreferences";
import type { RecipeSortOption } from "../../types/api";
import { normalizeSearchTerm } from "../../utils/searchTerm";
import "./RecipeListPage.scss";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 300;

export function RecipeListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const urlSearchTerm = searchParams.get("q") ?? "";
  const [searchTerm, setSearchTerm] = useState(urlSearchTerm);
  const [syncedSearchTerm, setSyncedSearchTerm] = useState(urlSearchTerm);
  if (syncedSearchTerm !== urlSearchTerm) {
    setSyncedSearchTerm(urlSearchTerm);
    setSearchTerm(urlSearchTerm);
  }
  const { sort, cuisine, setSort, setCuisine } = useRecipeListPreferences();

  const favoriteOnly = searchParams.get("favorite") === "true";
  const debouncedSearchTerm = useDebouncedValue(searchTerm, SEARCH_DEBOUNCE_MS);
  const activeSearch = normalizeSearchTerm(debouncedSearchTerm);

  const [previousSearch, setPreviousSearch] = useState(activeSearch);
  if (previousSearch !== activeSearch) {
    setPreviousSearch(activeSearch);
    setPage(1);
  }

  const { data, error, isLoading, isFetching } = useRecipeList({
    page,
    pageSize: PAGE_SIZE,
    sort,
    cuisine: cuisine || null,
    favorite: favoriteOnly ? true : null,
    search: activeSearch,
  });
  const { facets: cuisineFacets } = useCuisineFacets();

  const handleSearchTermChange = (value: string) => {
    setSearchTerm(value);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set("q", value);
        } else {
          next.delete("q");
        }
        return next;
      },
      { replace: true },
    );
  };

  const handleSortChange = (nextSort: RecipeSortOption) => {
    setSort(nextSort);
    setPage(1);
  };

  const handleCuisineChange = (nextCuisine: string) => {
    setCuisine(nextCuisine);
    setPage(1);
  };

  const hasRestrictingFilters = Boolean(cuisine) || favoriteOnly;

  const handleClearFilters = () => {
    setCuisine("");
    setPage(1);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("favorite");
        return next;
      },
      { replace: true },
    );
  };

  const restrictionLabel = [
    cuisine ? `${cuisine} cuisine` : null,
    favoriteOnly ? "favorites" : null,
  ]
    .filter(Boolean)
    .join(" and ");

  return (
    <Stack spacing={8} className="recipeListPage">
      <Stack spacing={2}>
        <Text color="brand.600" fontWeight="700" fontSize="sm">
          Saved recipes
        </Text>
        <Heading size="xl">Recipe list</Heading>
        <Text color="gray.600">All your saved recipes.</Text>
      </Stack>

      {activeSearch && hasRestrictingFilters ? (
        <HStack
          className="recipeListPage__restriction"
          justify="space-between"
          flexWrap="wrap"
        >
          <Text color="gray.600">
            Searching within {restrictionLabel} —{" "}
            {isFetching ? "…" : (data?.total_count ?? 0)} matching recipes
          </Text>
          <Button
            size="sm"
            variant="ghost"
            colorScheme="brand"
            onClick={handleClearFilters}
          >
            Clear filters
          </Button>
        </HStack>
      ) : null}

      <RecipeList
        items={data?.items ?? []}
        searchTerm={searchTerm}
        onSearchTermChange={handleSearchTermChange}
        sort={sort}
        onSortChange={handleSortChange}
        cuisine={cuisine}
        onCuisineChange={handleCuisineChange}
        cuisineFacets={cuisineFacets}
        isLoading={isLoading}
        isRefreshing={isFetching && !isLoading}
        error={error}
        onClearFilters={hasRestrictingFilters ? handleClearFilters : undefined}
      />

      <PaginationControls
        page={data?.page ?? page}
        totalPages={data?.total_pages ?? 1}
        totalCount={data?.total_count ?? 0}
        onPageChange={setPage}
        isDisabled={isLoading}
      />
    </Stack>
  );
}
