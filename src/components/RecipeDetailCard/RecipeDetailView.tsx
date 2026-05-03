import { Divider, Text } from "@chakra-ui/react";

import type {
  IngredientSection,
  NormalizedRecipe,
} from "../../types/recipe";
import { NutritionSection, RecipeTextSection } from "./RecipeTextSection";

type RecipeDetailViewProps = {
  recipe: NormalizedRecipe;
  showMetadataDivider: boolean;
  scaledVisibleIngredients: string[];
  visibleIngredientSections: IngredientSection[] | null;
  visibleInstructions: string[];
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
  recipe,
  showMetadataDivider,
  scaledVisibleIngredients,
  visibleIngredientSections,
  visibleInstructions,
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
        originalRows={recipe.ingredients}
        scaledVisibleIngredients={scaledVisibleIngredients}
        visibleIngredientSections={visibleIngredientSections}
        originalIngredientSections={recipe.ingredientSections}
        scaleFactor={scaleFactor}
        servingsControls={servingsControls}
      />

      <RecipeTextSection
        section="instructions"
        isEditing={false}
        editorRows={null}
        originalRows={recipe.instructions}
        visibleRows={visibleInstructions}
      />

      {error ? <Text color="red.500">{error}</Text> : null}

      {recipe.nutrition ? (
        <NutritionSection nutrition={recipe.nutrition} />
      ) : null}
    </>
  );
}
