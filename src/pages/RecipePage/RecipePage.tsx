import {
  Button,
  Heading,
  HStack,
  Link,
  Spinner,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";

import { RecipeDetailCard } from "../../components/RecipeDetailCard/RecipeDetailCard";
import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useAuth } from "../../hooks/useAuth";
import { useRecipeDetail } from "../../hooks/useRecipeDetail";
import type { RecipeTextOverrides } from "../../types/recipe";
import { resolveRecipeVideo } from "../../utils/videoEmbed";
import "./RecipePage.scss";

function isManualRecipeUrl(value: string) {
  return value.trim().toLowerCase().startsWith("manual://");
}

export function RecipePage() {
  const navigate = useNavigate();
  const { recipeImportId } = useParams();
  const { isAdmin } = useAuth();
  const [savingRecipeIndex, setSavingRecipeIndex] = useState<number | null>(
    null,
  );
  const {
    error,
    isLoading,
    isDeleting,
    isSavingOverrides,
    isUpdatingTimesCooked,
    isSavingServings,
    isSavingMetadata,
    deleteRecipe,
    recipeImport,
    saveServings,
    saveMetadata,
    saveOverrides,
    updateTimesCooked,
  } = useRecipeDetail(recipeImportId);

  const video = useMemo(
    () =>
      recipeImport
        ? resolveRecipeVideo({
            submittedUrl: recipeImport.submitted_url,
            finalUrl: recipeImport.final_url,
            fallbackVideoUrl: recipeImport.fallback_video_url,
          })
        : null,
    [recipeImport],
  );

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

  const handleDeleteRecipe = async () => {
    await deleteRecipe();
    navigate("/recipes");
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
          <Text color="gray.500">
            Source:{" "}
            {isManualRecipeUrl(recipeImport.submitted_url) ? (
              // A manual:// sentinel is provenance, not somewhere to navigate.
              "Manual recipe"
            ) : (
              <Link
                href={recipeImport.submitted_url}
                isExternal
                color="brand.700"
                textDecoration="underline"
              >
                {recipeImport.submitted_url}
              </Link>
            )}
          </Text>
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
              recipeImportId={recipeImport.id}
              recipe={recipe}
              recipeIndex={index}
              recordTitle={recipeImport.page_title}
              timesCooked={recipeImport.times_cooked}
              imageUrl={recipeImport.image_url}
              isFavorite={recipeImport.is_favorite}
              servings={recipeImport.servings}
              sourceUrl={recipeImport.submitted_url}
              fallbackVideoUrl={recipeImport.fallback_video_url}
              video={index === 0 ? video : null}
              overrides={recipeImport.recipe_overrides_json[String(index)]}
              isUpdatingTimesCooked={isUpdatingTimesCooked}
              isSavingServings={isSavingServings}
              isSavingMetadata={isSavingMetadata}
              isSavingOverrides={
                isSavingOverrides && savingRecipeIndex === index
              }
              isDeleting={isDeleting}
              onAdjustTimesCooked={updateTimesCooked}
              onDelete={index === 0 ? handleDeleteRecipe : undefined}
              onSaveServings={saveServings}
              onSaveMetadata={saveMetadata}
              onSaveOverrides={handleSaveOverrides}
              showTimesCookedControls={index === 0}
              canEdit={isAdmin}
            />
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
