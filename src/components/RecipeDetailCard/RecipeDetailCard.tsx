import { Card, CardBody, Stack } from "@chakra-ui/react";
import { useState } from "react";

import { useConfirmDialog } from "../../hooks/useConfirmDialog";
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
  getRecipeTextOverrides,
} from "../../utils/recipeOverrides";
import { scaleIngredients } from "../../utils/scaleIngredients";
import { DeleteRecipeDialog } from "./DeleteRecipeDialog";
import { RecipeDetailEditor } from "./RecipeDetailEditor";
import { RecipeDetailHeader } from "./RecipeDetailHeader";
import { RecipeDetailHero } from "./RecipeDetailHero";
import { RecipeDetailView } from "./RecipeDetailView";
import { useRecipeEditDraft } from "./hooks/useRecipeEditDraft";
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
  const deleteDialog = useConfirmDialog();
  const [deleteError, setDeleteError] = useState("");
  const editDraft = useRecipeEditDraft({
    recipe,
    recipeIndex,
    recordTitle,
    imageUrl,
    sourceUrl,
    visibleIngredients,
    visibleInstructions,
    canEditMetadata: canEdit && showTimesCookedControls,
    onSaveMetadata,
    onSaveOverrides,
  });

  const metadataItems = [
    recipe.recipeYield ? { label: "Yield", value: recipe.recipeYield } : null,
    recipe.cookTime ? { label: "Cook time", value: recipe.cookTime } : null,
    recipe.recipeCuisine && recipe.recipeCuisine.length > 0
      ? { label: "Cuisine", value: recipe.recipeCuisine.join(", ") }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  const openDeleteDialog = () => {
    editDraft.setSaveError("");
    setDeleteError("");
    deleteDialog.open();
  };

  const closeDeleteDialog = () => {
    if (!isDeleting) {
      deleteDialog.close();
    }
  };

  const handleDeleteRecipe = async () => {
    if (!onDelete) {
      return;
    }

    setDeleteError("");

    try {
      await deleteDialog.confirm(onDelete);
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Unable to delete recipe.",
      );
    }
  };
  const isDeleteProcessing = isDeleting || deleteDialog.isProcessing;
  const isBusy = isSavingOverrides || isSavingMetadata || isDeleteProcessing;
  const servingsControls = {
    currentServings: servingsScale.currentServings,
    originalServings: servingsScale.originalServings,
    isSaving: isSavingServings,
    onDecrement: servingsScale.decrement,
    onIncrement: servingsScale.increment,
    onSaveDefault: canEdit ? onSaveServings : undefined,
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
            isEditing={editDraft.isEditing}
            canEdit={canEdit}
            showTimesCookedControls={showTimesCookedControls}
            isUpdatingTimesCooked={isUpdatingTimesCooked}
            isBusy={isBusy}
            hasUnsavedChanges={editDraft.hasUnsavedChanges}
            onAdjustTimesCooked={onAdjustTimesCooked}
            onStartEditing={editDraft.startEditing}
            onCancelEditing={editDraft.cancelEditing}
            onSaveEdits={() => {
              void editDraft.save();
            }}
            onOpenDeleteDialog={openDeleteDialog}
            canDelete={canEdit && showTimesCookedControls && Boolean(onDelete)}
          />

          {editDraft.isEditing ? (
            <RecipeDetailEditor
              recipeImportId={recipeImportId}
              recipe={recipe}
              showMetadataDivider={metadataItems.length > 0}
              showMetadataEditor={canEdit && showTimesCookedControls}
              draftIngredients={editDraft.draftIngredients}
              draftInstructions={editDraft.draftInstructions}
              draftTitle={editDraft.draftTitle}
              draftYield={editDraft.draftYield}
              draftImageUrl={editDraft.draftImageUrl}
              draftSourceUrl={editDraft.draftSourceUrl}
              scaledVisibleIngredients={scaledVisibleIngredients}
              visibleIngredientSections={visibleIngredientSections}
              scaleFactor={servingsScale.scaleFactor}
              servingsControls={servingsControls}
              saveError={editDraft.saveError}
              onChangeIngredients={editDraft.setDraftIngredients}
              onChangeInstructions={editDraft.setDraftInstructions}
              onChangeTitle={editDraft.setDraftTitle}
              onChangeYield={editDraft.setDraftYield}
              onChangeImageUrl={editDraft.setDraftImageUrl}
              onChangeSourceUrl={editDraft.setDraftSourceUrl}
            />
          ) : (
            <RecipeDetailView
              recipe={recipe}
              showMetadataDivider={metadataItems.length > 0}
              scaledVisibleIngredients={scaledVisibleIngredients}
              visibleIngredientSections={visibleIngredientSections}
              visibleInstructions={visibleInstructions}
              scaleFactor={servingsScale.scaleFactor}
              servingsControls={servingsControls}
              error={deleteError}
            />
          )}
        </Stack>
      </CardBody>
      <DeleteRecipeDialog
        isOpen={deleteDialog.isOpen}
        isDeleting={isDeleteProcessing}
        onClose={closeDeleteDialog}
        onDelete={() => {
          void handleDeleteRecipe();
        }}
      />
    </Card>
  );
}
