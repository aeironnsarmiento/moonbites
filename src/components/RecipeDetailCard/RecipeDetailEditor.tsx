import { Divider, Text } from "@chakra-ui/react";

import type {
  IngredientSection,
  NormalizedRecipe,
} from "../../types/recipe";
import { RecipeMetadataEditor } from "./RecipeMetadataEditor";
import { RecipeTextEditorRows } from "./RecipeTextEditorRows";
import { RecipeTextSection } from "./RecipeTextSection";

type RecipeDetailEditorProps = {
  recipeImportId: string;
  recipe: NormalizedRecipe;
  showMetadataDivider: boolean;
  showMetadataEditor: boolean;
  draftIngredients: string[];
  draftInstructions: string[];
  draftTitle: string;
  draftYield: string;
  draftImageUrl: string;
  draftSourceUrl: string;
  draftFallbackVideoUrl: string;
  canEmbedSourceVideo: boolean;
  scaledVisibleIngredients: string[];
  visibleIngredientSections: IngredientSection[] | null;
  scaleFactor: number;
  servingsControls: {
    currentServings: number;
    originalServings: number;
    isSaving: boolean;
    onDecrement: () => void;
    onIncrement: () => void;
    onSaveDefault?: (servings: number) => Promise<void>;
  };
  saveError: string;
  onChangeIngredients: (rows: string[]) => void;
  onChangeInstructions: (rows: string[]) => void;
  onChangeTitle: (value: string) => void;
  onChangeYield: (value: string) => void;
  onChangeImageUrl: (value: string) => void;
  onChangeSourceUrl: (value: string) => void;
  onChangeFallbackVideoUrl: (value: string) => void;
};

export function RecipeDetailEditor({
  recipeImportId,
  recipe,
  showMetadataDivider,
  showMetadataEditor,
  draftIngredients,
  draftInstructions,
  draftTitle,
  draftYield,
  draftImageUrl,
  draftSourceUrl,
  draftFallbackVideoUrl,
  canEmbedSourceVideo,
  scaledVisibleIngredients,
  visibleIngredientSections,
  scaleFactor,
  servingsControls,
  saveError,
  onChangeIngredients,
  onChangeInstructions,
  onChangeTitle,
  onChangeYield,
  onChangeImageUrl,
  onChangeSourceUrl,
  onChangeFallbackVideoUrl,
}: RecipeDetailEditorProps) {
  return (
    <>
      {showMetadataDivider ? <Divider /> : null}

      {showMetadataEditor ? (
        <RecipeMetadataEditor
          recipeImportId={recipeImportId}
          draftTitle={draftTitle}
          draftYield={draftYield}
          draftImageUrl={draftImageUrl}
          draftSourceUrl={draftSourceUrl}
          draftFallbackVideoUrl={draftFallbackVideoUrl}
          canEmbedSourceVideo={canEmbedSourceVideo}
          onChangeTitle={onChangeTitle}
          onChangeYield={onChangeYield}
          onChangeImageUrl={onChangeImageUrl}
          onChangeSourceUrl={onChangeSourceUrl}
          onChangeFallbackVideoUrl={onChangeFallbackVideoUrl}
        />
      ) : null}

      <RecipeTextSection
        section="ingredients"
        isEditing
        editorRows={
          <RecipeTextEditorRows
            section="ingredients"
            rows={draftIngredients}
            originals={recipe.ingredients}
            onChangeRows={onChangeIngredients}
          />
        }
        originalRows={recipe.ingredients}
        scaledVisibleIngredients={scaledVisibleIngredients}
        visibleIngredientSections={visibleIngredientSections}
        originalIngredientSections={recipe.ingredientSections}
        scaleFactor={scaleFactor}
        servingsControls={servingsControls}
      />

      <RecipeTextSection
        section="instructions"
        isEditing
        editorRows={
          <RecipeTextEditorRows
            section="instructions"
            rows={draftInstructions}
            originals={recipe.instructions}
            onChangeRows={onChangeInstructions}
          />
        }
        originalRows={recipe.instructions}
        visibleRows={draftInstructions}
      />

      {saveError ? <Text color="red.500">{saveError}</Text> : null}
    </>
  );
}
