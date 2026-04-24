import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  IconButton,
  Input,
  InputGroup,
  InputLeftElement,
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

import type { CuisineFacet, RecipeSortOption } from "../../types/api";
import type { RecipeCardItem } from "../../types/recipe";
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

function FilterSortIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      focusable="false"
      height="20"
      viewBox="0 0 20 20"
      width="20"
    >
      <path
        d="M3 5h14M6 10h8M8.5 15h3"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  );
}

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
  return (
    <Stack spacing={5} className="recipeList">
      <Box className="recipeList__controls">
        <InputGroup className="recipeList__search">
          <InputLeftElement pointerEvents="none">⌕</InputLeftElement>
          <Input
            placeholder="Filter recipes on this page"
            value={searchTerm}
            onChange={(event) => onSearchTermChange(event.target.value)}
          />
        </InputGroup>

        <Popover placement="bottom-end">
          <PopoverTrigger>
            <IconButton
              aria-label="Open sort and filter options"
              className="recipeList__filterButton"
              icon={<FilterSortIcon />}
              variant="outline"
            />
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
            <RecipeCard key={item.id} item={item} />
          ))}
        </SimpleGrid>
      ) : null}
    </Stack>
  );
}
