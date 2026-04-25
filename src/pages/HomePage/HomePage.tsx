import { Button, Heading, Spinner, Stack, Text } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";

import { RecipeCardGrid } from "../../components/RecipeCardGrid/RecipeCardGrid";
import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useHighlightedRecipes } from "../../hooks/useHighlightedRecipes";
import "./HomePage.scss";

export function HomePage() {
  const { data, error, isLoading } = useHighlightedRecipes();
  const mostCooked = data.mostCooked.some((item) => item.timesCooked > 0)
    ? data.mostCooked
    : [];

  return (
    <Stack spacing={10} className="homePage">
      <Stack spacing={2} className="homePage__welcome">
        <Heading size="xl">Welcome back.</Heading>
        <Text color="gray.600">Your kitchen, in one place.</Text>
      </Stack>

      {isLoading ? (
        <Stack align="center" py={8}>
          <Spinner color="brand.600" />
        </Stack>
      ) : null}

      {!isLoading ? <StatusBanner error={error} /> : null}

      {!isLoading ? (
        <>
          <Stack spacing={4} as="section">
            <Heading size="lg">Favorites</Heading>
            {data.favorites.length > 0 ? (
              <RecipeCardGrid items={data.favorites} />
            ) : (
              <Text color="gray.600">No favorites yet. Tap the heart on any recipe.</Text>
            )}
            <Button
              as={RouterLink}
              to="/recipes?favorite=true"
              variant="ghost"
              alignSelf="flex-start"
            >
              See all favorites
            </Button>
          </Stack>

          <Stack spacing={4} as="section">
            <Heading size="lg">Most Cooked</Heading>
            {mostCooked.length > 0 ? (
              <RecipeCardGrid items={mostCooked} />
            ) : (
              <Text color="gray.600">Saved recipes will appear here.</Text>
            )}
            <Button as={RouterLink} to="/recipes" variant="ghost" alignSelf="flex-start">
              Browse all recipes
            </Button>
          </Stack>
        </>
      ) : null}
    </Stack>
  );
}
