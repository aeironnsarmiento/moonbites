import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
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
import { forwardRef } from "react";

import type { CuisineFacet, RecipeSortOption } from "../../types/api";
import type { RecipeCardItem } from "../../types/recipe";
import { useAuth } from "../../hooks/useAuth";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import "./RecipeList.scss";

type RecipeListProps = {
  items: RecipeCardItem[];
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  sort: RecipeSortOption;
  onSortChange: (value: RecipeSortOption) => void;
  cuisine: string;
  onCuisineChange: (value: string) => void;
  cuisineFacets: CuisineFacet[];
  isLoading: boolean;
  error: string;
};

function SearchGlyph() {
  return (
    <svg
      aria-hidden="true"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function FilterSortIcon() {
  return (
    <svg
      aria-hidden="true"
      width="14"
      height="14"
      viewBox="0 0 20 20"
      fill="none"
    >
      <path
        d="M3 5h14M6 10h8M8.5 15h3"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

const SortChip = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
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
  error,
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
            placeholder="Filter recipes on this page"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
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
        <Stack align="center" justify="center" py={16}>
          <Spinner size="xl" color="brand.600" />
          <Text color="gray.500">Loading saved recipes…</Text>
        </Stack>
      ) : null}

      {!isLoading && error ? (
        <Alert status="error" borderRadius="18px">
          <AlertIcon />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <Box className="recipeList__empty">
          <Text fontWeight="600">No recipes match these filters.</Text>
          <Text color="gray.500">
            Try a different search term, sort, or cuisine.
          </Text>
        </Box>
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
          {items.map((item) => (
            <RecipeCard key={item.id} item={item} canToggleFavorite={isAdmin} />
          ))}
        </SimpleGrid>
      ) : null}
    </Stack>
  );
}
