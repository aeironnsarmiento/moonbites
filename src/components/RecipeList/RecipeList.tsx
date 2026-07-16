import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  Button,
  HStack,
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverContent,
  PopoverTrigger,
  Select,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";
import { type ButtonHTMLAttributes, forwardRef } from "react";

import type { CuisineFacet, RecipeSortOption } from "../../types/api";
import type { RecipeCardItem } from "../../types/recipe";
import { useAuth } from "../../hooks/useAuth";
import { BowlDoodle, FilterSortIcon, SearchGlyph } from "../Icons";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import { RecipeCardSkeleton } from "../RecipeCard/RecipeCardSkeleton";
import "./RecipeList.scss";

export type RecipeListProps = {
  items: RecipeCardItem[];
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  sort: RecipeSortOption;
  onSortChange: (value: RecipeSortOption) => void;
  cuisine: string;
  onCuisineChange: (value: string) => void;
  cuisineFacets: CuisineFacet[];
  isLoading: boolean;
  isRefreshing?: boolean;
  error: string;
  onClearFilters?: () => void;
};

const SortChip = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement>>(
  function SortChip(props, ref) {
    return (
      <button
        ref={ref}
        type="button"
        className="recipeList__sortChip"
        aria-label="Sort and filter"
        {...props}
      >
        <FilterSortIcon />
        <span>Sort</span>
      </button>
    );
  }
);

export function RecipeList({
  items,
  searchTerm,
  onSearchTermChange,
  sort,
  onSortChange,
  cuisine,
  onCuisineChange,
  cuisineFacets,
  isLoading,
  isRefreshing = false,
  error,
  onClearFilters,
}: RecipeListProps) {
  const { isAdmin } = useAuth();

  return (
    <Stack spacing={5} className="recipeList">
      <Box className="recipeList__controls">
        <div className="recipeList__search">
          <span className="recipeList__searchGlyph">
            <SearchGlyph />
          </span>
          <input
            className="recipeList__searchInput"
            placeholder="Search all recipes"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
          {isRefreshing ? (
            <span
              className="recipeList__refreshIndicator"
              role="status"
              aria-label="Updating results"
            >
              <Spinner size="sm" color="brand.500" />
            </span>
          ) : null}
          {searchTerm ? (
            <button
              type="button"
              className="recipeList__clearSearch"
              aria-label="Clear search"
              onClick={() => onSearchTermChange("")}
            >
              ×
            </button>
          ) : null}
          <span className="recipeList__searchDivider" aria-hidden="true" />
          <Popover placement="bottom-end">
            <PopoverTrigger>
              <SortChip />
            </PopoverTrigger>
            <PopoverContent className="recipeList__popover">
              <PopoverArrow />
              <PopoverBody className="recipeList__popoverBody">
                <Box>
                  <Text className="recipeList__controlLabel">Sort</Text>
                  <Select
                    aria-label="Sort recipes"
                    value={sort}
                    onChange={(event) =>
                      onSortChange(event.target.value as RecipeSortOption)
                    }
                  >
                    <option value="recent">Recently uploaded</option>
                    <option value="az">A-Z</option>
                    <option value="za">Z-A</option>
                    <option value="times_cooked">Most cooked</option>
                    <option value="favorites">Favorites</option>
                  </Select>
                </Box>

                <Box>
                  <Text className="recipeList__controlLabel">Cuisine</Text>
                  <Select
                    aria-label="Filter by cuisine"
                    value={cuisine}
                    onChange={(event) => onCuisineChange(event.target.value)}
                  >
                    <option value="">All cuisines</option>
                    {cuisineFacets.map((facet) => (
                      <option key={facet.label} value={facet.label}>
                        {facet.label} ({facet.count})
                      </option>
                    ))}
                  </Select>
                </Box>
              </PopoverBody>
            </PopoverContent>
          </Popover>
        </div>
      </Box>

      {isLoading ? (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
          {Array.from({ length: 6 }, (_, index) => (
            <RecipeCardSkeleton key={index} />
          ))}
        </SimpleGrid>
      ) : null}

      {!isLoading && error ? (
        <Alert status="error" borderRadius="18px">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <Box className="recipeList__empty" textAlign="center">
          <Box color="brand.600" display="inline-flex" mb={3}>
            <BowlDoodle />
          </Box>
          <Text fontWeight="600">No recipes match these filters.</Text>
          <Text color="gray.500">
            Try a different search term, sort, or cuisine.
          </Text>
          {searchTerm || onClearFilters ? (
            <HStack justify="center" spacing={3} mt={4}>
              {searchTerm ? (
                <Button
                  size="sm"
                  variant="outline"
                  colorScheme="brand"
                  onClick={() => onSearchTermChange("")}
                >
                  Clear search
                </Button>
              ) : null}
              {onClearFilters ? (
                <Button
                  size="sm"
                  variant="ghost"
                  colorScheme="brand"
                  onClick={onClearFilters}
                >
                  Clear filters
                </Button>
              ) : null}
            </HStack>
          ) : null}
        </Box>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
          {items.map((item, index) => (
            <RecipeCard
              key={item.id}
              item={item}
              canToggleFavorite={isAdmin}
              entranceIndex={index}
            />
          ))}
        </SimpleGrid>
      ) : null}
    </Stack>
  );
}
