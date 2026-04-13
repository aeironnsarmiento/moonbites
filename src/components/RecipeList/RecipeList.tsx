import {
  Alert,
  AlertDescription,
  AlertIcon,
  Box,
  Input,
  InputGroup,
  InputLeftElement,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";

import type { RecipeCardItem } from "../../types/recipe";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import "./RecipeList.scss";

type RecipeListProps = {
  items: RecipeCardItem[];
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  isLoading: boolean;
  error: string;
};

export function RecipeList({
  items,
  searchTerm,
  onSearchTermChange,
  isLoading,
  error,
}: RecipeListProps) {
  return (
    <Stack spacing={5} className="recipeList">
      <InputGroup>
        <InputLeftElement pointerEvents="none">⌕</InputLeftElement>
        <Input
          placeholder="Filter recipes on this page"
          value={searchTerm}
          onChange={(event) => onSearchTermChange(event.target.value)}
        />
      </InputGroup>

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
          <Text fontWeight="600">No recipes match this page filter.</Text>
          <Text color="gray.500">Try a different search term or page.</Text>
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
