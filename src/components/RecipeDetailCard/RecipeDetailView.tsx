import { Divider, Text } from "@chakra-ui/react";

import type { RecipeRow } from "../../utils/recipeOverrides";
import type { VisibleIngredientSection } from "./RecipeIngredientsDisplay";
import { RecipeTextSection } from "./RecipeTextSection";

type RecipeDetailViewProps = {
  showMetadataDivider: boolean;
  scaledIngredientRows: RecipeRow[];
  ingredientSections: VisibleIngredientSection[] | null;
  instructionRows: RecipeRow[];
  scaleFactor: number;
  servingsControls: {
    currentServings: number;
    originalServings: number;
    isSaving: boolean;
    onDecrement: () => void;
    onIncrement: () => void;
    onSaveDefault?: (servings: number) => Promise<void>;
  };
  error: string;
};

export function RecipeDetailView({
  showMetadataDivider,
  scaledIngredientRows,
  ingredientSections,
  instructionRows,
  scaleFactor,
  servingsControls,
  error,
}: RecipeDetailViewProps) {
  return (
    <>
      {showMetadataDivider ? <Divider /> : null}

      <RecipeTextSection
        section="ingredients"
        isEditing={false}
        editorRows={null}
        visibleRows={scaledIngredientRows}
        visibleSections={ingredientSections}
        scaleFactor={scaleFactor}
        servingsControls={servingsControls}
      />

      <RecipeTextSection
        section="instructions"
        isEditing={false}
        editorRows={null}
        visibleRows={instructionRows}
      />

      {error ? <Text color="red.500">{error}</Text> : null}
    </>
  );
}
