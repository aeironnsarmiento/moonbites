import {
  Card,
  CardBody,
  Divider,
  Heading,
  ListItem,
  OrderedList,
  SimpleGrid,
  Stack,
  Text,
  UnorderedList,
} from "@chakra-ui/react";

import type { NormalizedRecipe } from "../../types/recipe";
import "./RecipeDetailCard.scss";

type RecipeDetailCardProps = {
  recipe: NormalizedRecipe;
  index: number;
};

export function RecipeDetailCard({ recipe, index }: RecipeDetailCardProps) {
  const metadataItems = [
    recipe.recipeYield ? { label: "Yield", value: recipe.recipeYield } : null,
    recipe.cookTime ? { label: "Cook time", value: recipe.cookTime } : null,
    recipe.recipeCuisine && recipe.recipeCuisine.length > 0
      ? { label: "Cuisine", value: recipe.recipeCuisine.join(", ") }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  return (
    <Card className="recipeDetailCard">
      <CardBody>
        <Stack spacing={6}>
          <Stack spacing={2}>
            <Text color="brand.600" fontWeight="700" fontSize="sm">
              Recipe {index}
            </Text>
            <Heading size="lg">{recipe.name}</Heading>
            {metadataItems.length > 0 ? (
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                {metadataItems.map((item) => (
                  <Text key={item.label}>
                    <strong>{item.label}:</strong> {item.value}
                  </Text>
                ))}
              </SimpleGrid>
            ) : null}
          </Stack>

          {metadataItems.length > 0 ? <Divider /> : null}

          <Stack spacing={3}>
            <Heading size="sm">Ingredients</Heading>
            <UnorderedList spacing={2} className="recipeDetailCard__list">
              {recipe.ingredients.map((ingredient) => (
                <ListItem key={ingredient}>{ingredient}</ListItem>
              ))}
            </UnorderedList>
          </Stack>

          <Stack spacing={3}>
            <Heading size="sm">Instructions</Heading>
            <OrderedList spacing={3} className="recipeDetailCard__list">
              {recipe.instructions.map((instruction) => (
                <ListItem key={instruction}>{instruction}</ListItem>
              ))}
            </OrderedList>
          </Stack>

          {recipe.nutrition ? (
            <Stack spacing={3}>
              <Heading size="sm">Nutrition</Heading>
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
                {Object.entries(recipe.nutrition).map(([key, value]) => (
                  <Text key={key}>
                    <strong>{key}:</strong> {value}
                  </Text>
                ))}
              </SimpleGrid>
            </Stack>
          ) : null}
        </Stack>
      </CardBody>
    </Card>
  );
}
