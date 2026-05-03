import {
  ListItem,
  Stack,
  Text,
  UnorderedList,
} from "@chakra-ui/react";

import type { IngredientSection } from "../../types/recipe";
import { RecipeDiffText } from "./RecipeDiffText";

type RecipeIngredientsDisplayProps = {
  originalRows: string[];
  scaledVisibleIngredients: string[];
  visibleIngredientSections: IngredientSection[] | null;
  originalIngredientSections: IngredientSection[] | null;
  scaleFactor: number;
};

function renderIngredientText(
  originalValue: string,
  editedValue: string,
  keyPrefix: string,
  scaleFactor: number,
) {
  if (Math.abs(scaleFactor - 1) > 0.001) {
    return editedValue;
  }

  return (
    <RecipeDiffText
      originalValue={originalValue}
      editedValue={editedValue}
      keyPrefix={keyPrefix}
    />
  );
}

export function RecipeIngredientsDisplay({
  originalRows,
  scaledVisibleIngredients,
  visibleIngredientSections,
  originalIngredientSections,
  scaleFactor,
}: RecipeIngredientsDisplayProps) {
  if (visibleIngredientSections) {
    return (
      <Stack spacing={4}>
        {visibleIngredientSections.map((section, sectionIndex) => {
          const sectionStart =
            originalIngredientSections
              ?.slice(0, sectionIndex)
              .reduce((count, item) => count + item.items.length, 0) ?? 0;

          return (
            <Stack key={`${section.title ?? "ingredients"}-${sectionIndex}`} spacing={2}>
              {section.title ? <Text fontWeight="700">{section.title}</Text> : null}
              <UnorderedList spacing={2} className="recipeDetailCard__list">
                {section.items.map((ingredient, itemIndex) => {
                  const rowIndex = sectionStart + itemIndex;

                  return (
                    <ListItem key={`ingredient-${rowIndex}`}>
                      {renderIngredientText(
                        originalRows[rowIndex] ?? "",
                        ingredient,
                        `ingredient-${rowIndex}`,
                        scaleFactor,
                      )}
                    </ListItem>
                  );
                })}
              </UnorderedList>
            </Stack>
          );
        })}
      </Stack>
    );
  }

  return (
    <UnorderedList spacing={2} className="recipeDetailCard__list">
      {scaledVisibleIngredients.map((ingredient, rowIndex) => (
        <ListItem key={`ingredient-${rowIndex}`}>
          {renderIngredientText(
            originalRows[rowIndex] ?? "",
            ingredient,
            `ingredient-${rowIndex}`,
            scaleFactor,
          )}
        </ListItem>
      ))}
    </UnorderedList>
  );
}
