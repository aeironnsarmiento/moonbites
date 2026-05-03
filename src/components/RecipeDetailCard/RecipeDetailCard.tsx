import { Card, CardBody, Divider, Stack, Text } from "@chakra-ui/react";
import { useState } from "react";

import { useServingsScale } from "../../hooks/useServingsScale";
import { useToggleFavorite } from "../../hooks/useToggleFavorite";
import type {
  IngredientSection,
  NormalizedRecipe,
  RecipeTextOverrides,
  UpdateRecipeMetadataPayload,
} from "../../types/recipe";
import {
  applyRowOverrides,
  areRowsEqual,
  buildRowOverrides,
  getRecipeTextOverrides,
} from "../../utils/recipeOverrides";
import { scaleIngredients } from "../../utils/scaleIngredients";
import { DeleteRecipeDialog } from "./DeleteRecipeDialog";
import {
  RecipeDetailHeader,
  RecipeDetailHero,
} from "./RecipeDetailHeader";
import { RecipeMetadataEditor } from "./RecipeMetadataEditor";
import { RecipeTextEditorRows } from "./RecipeTextEditorRows";
import { NutritionSection, RecipeTextSection } from "./RecipeTextSection";
import "./RecipeDetailCard.scss";

type RecipeDetailCardProps = {
  recipeImportId: string;
  recipe: NormalizedRecipe;
  recipeIndex: number;
  recordTitle: string | null;
  timesCooked: number;
  imageUrl: string | null;
  isFavorite: boolean;
  servings: number | null;
  sourceUrl: string;
  overrides?: RecipeTextOverrides;
  isUpdatingTimesCooked?: boolean;
  isSavingOverrides?: boolean;
  isSavingServings?: boolean;
  isSavingMetadata?: boolean;
  isDeleting?: boolean;
  onAdjustTimesCooked?: (delta: -1 | 1) => Promise<void>;
  onDelete?: () => Promise<void>;
  onSaveServings?: (servings: number) => Promise<void>;
  onSaveMetadata?: (metadata: UpdateRecipeMetadataPayload) => Promise<void>;
  onSaveOverrides?: (
    recipeIndex: number,
    overrides: RecipeTextOverrides,
  ) => Promise<void>;
  showTimesCookedControls?: boolean;
  canEdit?: boolean;
};

function buildVisibleIngredientSections(
  recipe: NormalizedRecipe,
  visibleIngredients: string[],
): IngredientSection[] | null {
  if (!recipe.ingredientSections || recipe.ingredientSections.length === 0) {
    return null;
  }

  let offset = 0;

  return recipe.ingredientSections.map((section) => {
    const items = visibleIngredients.slice(offset, offset + section.items.length);
    offset += section.items.length;

    return {
      title: section.title,
      items,
    };
  });
}

export function RecipeDetailCard({
  recipeImportId,
  recipe,
  recipeIndex,
  recordTitle,
  timesCooked,
  imageUrl,
  isFavorite,
  servings,
  sourceUrl,
  overrides,
  isUpdatingTimesCooked = false,
  isSavingOverrides = false,
  isSavingServings = false,
  isSavingMetadata = false,
  isDeleting = false,
  onAdjustTimesCooked,
  onDelete,
  onSaveServings,
  onSaveMetadata,
  onSaveOverrides,
  showTimesCookedControls = false,
  canEdit = true,
}: RecipeDetailCardProps) {
  const toggleFavorite = useToggleFavorite(recipeImportId);
  const servingsScale = useServingsScale(recipeImportId, servings);
  const savedOverrides = getRecipeTextOverrides(overrides);
  const visibleIngredients = applyRowOverrides(
    recipe.ingredients,
    savedOverrides.ingredients,
  );
  const scaledVisibleIngredients = scaleIngredients(
    visibleIngredients,
    servingsScale.scaleFactor,
  );
  const visibleIngredientSections = buildVisibleIngredientSections(
    recipe,
    scaledVisibleIngredients,
  );
  const visibleInstructions = applyRowOverrides(
    recipe.instructions,
    savedOverrides.instructions,
  );
  const [isEditing, setIsEditing] = useState(false);
  const [draftIngredients, setDraftIngredients] =
    useState<string[]>(visibleIngredients);
  const [draftInstructions, setDraftInstructions] =
    useState<string[]>(visibleInstructions);
  const [draftTitle, setDraftTitle] = useState(recordTitle ?? recipe.name);
  const [draftYield, setDraftYield] = useState(recipe.recipeYield ?? "");
  const [draftImageUrl, setDraftImageUrl] = useState(imageUrl ?? "");
  const [draftSourceUrl, setDraftSourceUrl] = useState(sourceUrl);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [saveError, setSaveError] = useState("");

  const metadataItems = [
    recipe.recipeYield ? { label: "Yield", value: recipe.recipeYield } : null,
    recipe.cookTime ? { label: "Cook time", value: recipe.cookTime } : null,
    recipe.recipeCuisine && recipe.recipeCuisine.length > 0
      ? { label: "Cuisine", value: recipe.recipeCuisine.join(", ") }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  const hasMetadataChanges =
    canEdit &&
    showTimesCookedControls &&
    (draftTitle.trim() !== (recordTitle ?? recipe.name) ||
      (draftYield.trim() || null) !== (recipe.recipeYield ?? null) ||
      (draftImageUrl.trim() || null) !== (imageUrl ?? null) ||
      draftSourceUrl.trim() !== sourceUrl);

  const hasUnsavedChanges =
    !areRowsEqual(draftIngredients, visibleIngredients) ||
    !areRowsEqual(draftInstructions, visibleInstructions) ||
    hasMetadataChanges;

  const startEditing = () => {
    setDraftIngredients([...visibleIngredients]);
    setDraftInstructions([...visibleInstructions]);
    setDraftTitle(recordTitle ?? recipe.name);
    setDraftYield(recipe.recipeYield ?? "");
    setDraftImageUrl(imageUrl ?? "");
    setDraftSourceUrl(sourceUrl);
    setSaveError("");
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraftIngredients([...visibleIngredients]);
    setDraftInstructions([...visibleInstructions]);
    setDraftTitle(recordTitle ?? recipe.name);
    setDraftYield(recipe.recipeYield ?? "");
    setDraftImageUrl(imageUrl ?? "");
    setDraftSourceUrl(sourceUrl);
    setSaveError("");
    setIsEditing(false);
  };

  const openDeleteDialog = () => {
    setSaveError("");
    setIsDeleteDialogOpen(true);
  };

  const closeDeleteDialog = () => {
    if (!isDeleting) {
      setIsDeleteDialogOpen(false);
    }
  };

  const handleSaveOverrides = async () => {
    if (!onSaveOverrides && !onSaveMetadata) {
      return;
    }

    setSaveError("");

    try {
      if (hasMetadataChanges && onSaveMetadata) {
        await onSaveMetadata({
          title: draftTitle.trim(),
          recipeYield: draftYield.trim() || null,
          imageUrl: draftImageUrl.trim() || null,
          sourceUrl: draftSourceUrl.trim(),
        });
      }

      if (onSaveOverrides) {
        await onSaveOverrides(recipeIndex, {
          ingredients: buildRowOverrides(recipe.ingredients, draftIngredients),
          instructions: buildRowOverrides(recipe.instructions, draftInstructions),
        });
      }
      setIsEditing(false);
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Unable to save recipe edits.",
      );
    }
  };

  const handleDeleteRecipe = async () => {
    if (!onDelete) {
      return;
    }

    setSaveError("");

    try {
      await onDelete();
      setIsDeleteDialogOpen(false);
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Unable to delete recipe.",
      );
    }
  };

  return (
    <Card className="recipeDetailCard">
      <RecipeDetailHero
        imageUrl={imageUrl}
        title={recipe.name}
        isFavorite={isFavorite}
        isTogglingFavorite={toggleFavorite.isPending}
        onToggleFavorite={
          canEdit
            ? () => {
                void toggleFavorite.mutateAsync();
              }
            : undefined
        }
      />
      <CardBody>
        <Stack spacing={6}>
          <RecipeDetailHeader
            title={recipe.name}
            metadataItems={metadataItems}
            timesCooked={timesCooked}
            isEditing={isEditing}
            canEdit={canEdit}
            showTimesCookedControls={showTimesCookedControls}
            isUpdatingTimesCooked={isUpdatingTimesCooked}
            isSavingOverrides={isSavingOverrides}
            isSavingMetadata={isSavingMetadata}
            isDeleting={isDeleting}
            hasUnsavedChanges={hasUnsavedChanges}
            onAdjustTimesCooked={onAdjustTimesCooked}
            onStartEditing={startEditing}
            onCancelEditing={cancelEditing}
            onSaveEdits={() => {
              void handleSaveOverrides();
            }}
            onOpenDeleteDialog={openDeleteDialog}
            canDelete={canEdit && showTimesCookedControls && Boolean(onDelete)}
          />

          {metadataItems.length > 0 ? <Divider /> : null}

          {canEdit && isEditing && showTimesCookedControls ? (
            <RecipeMetadataEditor
              recipeImportId={recipeImportId}
              draftTitle={draftTitle}
              draftYield={draftYield}
              draftImageUrl={draftImageUrl}
              draftSourceUrl={draftSourceUrl}
              onChangeTitle={setDraftTitle}
              onChangeYield={setDraftYield}
              onChangeImageUrl={setDraftImageUrl}
              onChangeSourceUrl={setDraftSourceUrl}
            />
          ) : null}

          <RecipeTextSection
            section="ingredients"
            isEditing={isEditing}
            editorRows={
              <RecipeTextEditorRows
                section="ingredients"
                rows={draftIngredients}
                originals={recipe.ingredients}
                onChangeRows={setDraftIngredients}
              />
            }
            originalRows={recipe.ingredients}
            scaledVisibleIngredients={scaledVisibleIngredients}
            visibleIngredientSections={visibleIngredientSections}
            originalIngredientSections={recipe.ingredientSections}
            scaleFactor={servingsScale.scaleFactor}
            servingsControls={{
              currentServings: servingsScale.currentServings,
              originalServings: servingsScale.originalServings,
              isSaving: isSavingServings,
              onDecrement: servingsScale.decrement,
              onIncrement: servingsScale.increment,
              onSaveDefault: canEdit ? onSaveServings : undefined,
            }}
          />

          <RecipeTextSection
            section="instructions"
            isEditing={isEditing}
            editorRows={
              <RecipeTextEditorRows
                section="instructions"
                rows={draftInstructions}
                originals={recipe.instructions}
                onChangeRows={setDraftInstructions}
              />
            }
            originalRows={recipe.instructions}
            visibleRows={visibleInstructions}
          />

          {saveError ? <Text color="red.500">{saveError}</Text> : null}

          {recipe.nutrition ? (
            <NutritionSection nutrition={recipe.nutrition} />
          ) : null}
        </Stack>
      </CardBody>
      <DeleteRecipeDialog
        isOpen={isDeleteDialogOpen}
        isDeleting={isDeleting}
        onClose={closeDeleteDialog}
        onDelete={() => {
          void handleDeleteRecipe();
        }}
      />
    </Card>
  );
}
