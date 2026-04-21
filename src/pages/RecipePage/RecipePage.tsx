import {
  Button,
  Heading,
  HStack,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import { RecipeDetailCard } from "../../components/RecipeDetailCard/RecipeDetailCard";
import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useRecipeDetail } from "../../hooks/useRecipeDetail";
import type { RecipeTextOverrides } from "../../types/recipe";
import "./RecipePage.scss";

function getSourceLabel(value: string) {
  return value.trim().toLowerCase().startsWith("manual://")
    ? "Manual recipe"
    : value;
}

export function RecipePage() {
  const { recipeImportId } = useParams();
  const [savingRecipeIndex, setSavingRecipeIndex] = useState<number | null>(
    null,
  );
  const {
    error,
    isLoading,
    isSavingOverrides,
    isUpdatingTimesCooked,
    recipeImport,
    saveOverrides,
    updateTimesCooked,
  } = useRecipeDetail(recipeImportId);

  const handleSaveOverrides = async (
    recipeIndex: number,
    overrides: RecipeTextOverrides,
  ) => {
    setSavingRecipeIndex(recipeIndex);

    try {
      await saveOverrides({ recipeIndex, overrides });
    } finally {
      setSavingRecipeIndex(null);
    }
  };

  return (
    <Stack spacing={8} className="recipePage">
      <Stack spacing={4}>
        <HStack justify="space-between" wrap="wrap">
          <Stack spacing={2}>
            <Text color="brand.600" fontWeight="700" fontSize="sm">
              Recipe detail
            </Text>
            <Heading size="xl">
              {recipeImport?.page_title ?? "Saved recipe import"}
            </Heading>
          </Stack>

          <Button as={RouterLink} to="/recipes" variant="outline">
            Back to recipe list
          </Button>
        </HStack>

        {recipeImport ? (
          <Text color="gray.500">Source: {getSourceLabel(recipeImport.submitted_url)}</Text>
        ) : null}
      </Stack>

      {isLoading ? (
        <Stack align="center" py={16}>
          <Spinner size="xl" color="brand.600" />
          <Text color="gray.500">Loading recipe…</Text>
        </Stack>
      ) : null}

      {!isLoading ? <StatusBanner error={error} /> : null}

      {!isLoading && recipeImport ? (
        <Stack spacing={6}>
          {recipeImport.recipes_json.map((recipe, index) => (
            <RecipeDetailCard
              key={`${recipeImport.id}-${index}`}
              recipe={recipe}
              recipeIndex={index}
              index={index + 1}
              timesCooked={recipeImport.times_cooked}
              overrides={recipeImport.recipe_overrides_json[String(index)]}
              isUpdatingTimesCooked={isUpdatingTimesCooked}
              isSavingOverrides={
                isSavingOverrides && savingRecipeIndex === index
              }
              onAdjustTimesCooked={updateTimesCooked}
              onSaveOverrides={handleSaveOverrides}
              showTimesCookedControls={index === 0}
            />
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
