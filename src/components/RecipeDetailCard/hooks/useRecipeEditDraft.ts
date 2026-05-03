import { useState } from "react";

import type {
  NormalizedRecipe,
  RecipeTextOverrides,
  UpdateRecipeMetadataPayload,
} from "../../../types/recipe";
import {
  areRowsEqual,
  buildRowOverrides,
} from "../../../utils/recipeOverrides";

type UseRecipeEditDraftOptions = {
  recipe: NormalizedRecipe;
  recipeIndex: number;
  recordTitle: string | null;
  imageUrl: string | null;
  sourceUrl: string;
  visibleIngredients: string[];
  visibleInstructions: string[];
  canEditMetadata: boolean;
  onSaveMetadata?: (metadata: UpdateRecipeMetadataPayload) => Promise<void>;
  onSaveOverrides?: (
    recipeIndex: number,
    overrides: RecipeTextOverrides,
  ) => Promise<void>;
};

export function useRecipeEditDraft({
  recipe,
  recipeIndex,
  recordTitle,
  imageUrl,
  sourceUrl,
  visibleIngredients,
  visibleInstructions,
  canEditMetadata,
  onSaveMetadata,
  onSaveOverrides,
}: UseRecipeEditDraftOptions) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftIngredients, setDraftIngredients] =
    useState<string[]>(visibleIngredients);
  const [draftInstructions, setDraftInstructions] =
    useState<string[]>(visibleInstructions);
  const [draftTitle, setDraftTitle] = useState(recordTitle ?? recipe.name);
  const [draftYield, setDraftYield] = useState(recipe.recipeYield ?? "");
  const [draftImageUrl, setDraftImageUrl] = useState(imageUrl ?? "");
  const [draftSourceUrl, setDraftSourceUrl] = useState(sourceUrl);
  const [saveError, setSaveError] = useState("");

  const seedDrafts = () => {
    setDraftIngredients([...visibleIngredients]);
    setDraftInstructions([...visibleInstructions]);
    setDraftTitle(recordTitle ?? recipe.name);
    setDraftYield(recipe.recipeYield ?? "");
    setDraftImageUrl(imageUrl ?? "");
    setDraftSourceUrl(sourceUrl);
    setSaveError("");
  };

  const startEditing = () => {
    seedDrafts();
    setIsEditing(true);
  };

  const cancelEditing = () => {
    seedDrafts();
    setIsEditing(false);
  };

  const hasMetadataChanges =
    canEditMetadata &&
    (draftTitle.trim() !== (recordTitle ?? recipe.name) ||
      (draftYield.trim() || null) !== (recipe.recipeYield ?? null) ||
      (draftImageUrl.trim() || null) !== (imageUrl ?? null) ||
      draftSourceUrl.trim() !== sourceUrl);

  const hasUnsavedChanges =
    !areRowsEqual(draftIngredients, visibleIngredients) ||
    !areRowsEqual(draftInstructions, visibleInstructions) ||
    hasMetadataChanges;

  const save = async () => {
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

  return {
    isEditing,
    saveError,
    draftIngredients,
    draftInstructions,
    draftTitle,
    draftYield,
    draftImageUrl,
    draftSourceUrl,
    hasMetadataChanges,
    hasUnsavedChanges,
    setDraftIngredients,
    setDraftInstructions,
    setDraftTitle,
    setDraftYield,
    setDraftImageUrl,
    setDraftSourceUrl,
    setSaveError,
    startEditing,
    cancelEditing,
    save,
  };
}
