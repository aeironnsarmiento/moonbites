import { useMemo, useState } from "react";

import { Heading, Stack, Text } from "@chakra-ui/react";

import { PaginationControls } from "../../components/PaginationControls/PaginationControls";
import { RecipeList } from "../../components/RecipeList/RecipeList";
import { useRecipeList } from "../../hooks/useRecipeList";
import "./RecipeListPage.scss";

const PAGE_SIZE = 10;

export function RecipeListPage() {
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const { data, error, isLoading } = useRecipeList(page, PAGE_SIZE);

  const filteredItems = useMemo(() => {
    if (!data) {
      return [];
    }

    const normalizedQuery = searchTerm.trim().toLowerCase();
    if (!normalizedQuery) {
      return data.items;
    }

    return data.items.filter((item) => {
      const haystacks = [
        item.title,
        item.pageTitle ?? "",
        item.submittedUrl,
        item.primaryRecipe?.cookTime ?? "",
        item.primaryRecipe?.recipeYield ?? "",
      ];

      return haystacks.some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      );
    });
  }, [data, searchTerm]);

  return (
    <Stack spacing={8} className="recipeListPage">
      <Stack spacing={2}>
        <Text color="brand.600" fontWeight="700" fontSize="sm">
          Saved recipes
        </Text>
        <Heading size="xl">Recipe list</Heading>
        <Text color="gray.600">
          Browse saved recipe imports, filter them on the client, and open a
          recipe page for the full normalized JSON.
        </Text>
      </Stack>

      <RecipeList
        items={filteredItems}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
        isLoading={isLoading}
        error={error}
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
