import { Checkbox, Stack, Text } from "@chakra-ui/react";

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

function IngredientCheckboxRow({
  children,
  rowKey,
}: {
  children: React.ReactNode;
  rowKey: string;
}) {
  return (
    <Checkbox
      key={rowKey}
      size="lg"
      colorScheme="brand"
      alignItems="flex-start"
      sx={{
        ".chakra-checkbox__control": {
          borderRadius: "8px",
          marginTop: "2px",
        },
        "&[data-checked] .chakra-checkbox__label": {
          opacity: 0.55,
          textDecoration: "line-through",
        },
      }}
    >
      <Text as="span" fontSize="md">
        {children}
      </Text>
    </Checkbox>
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
              <Stack spacing={2} className="recipeDetailCard__list">
                {section.items.map((ingredient, itemIndex) => {
                  const rowIndex = sectionStart + itemIndex;

                  return (
                    <IngredientCheckboxRow
                      key={`ingredient-${rowIndex}`}
                      rowKey={`ingredient-${rowIndex}`}
                    >
                      {renderIngredientText(
                        originalRows[rowIndex] ?? "",
                        ingredient,
                        `ingredient-${rowIndex}`,
                        scaleFactor,
                      )}
                    </IngredientCheckboxRow>
                  );
                })}
              </Stack>
            </Stack>
          );
        })}
      </Stack>
    );
  }

  return (
    <Stack spacing={2} className="recipeDetailCard__list">
      {scaledVisibleIngredients.map((ingredient, rowIndex) => (
        <IngredientCheckboxRow
          key={`ingredient-${rowIndex}`}
          rowKey={`ingredient-${rowIndex}`}
        >
          {renderIngredientText(
            originalRows[rowIndex] ?? "",
            ingredient,
            `ingredient-${rowIndex}`,
            scaleFactor,
          )}
        </IngredientCheckboxRow>
      ))}
    </Stack>
  );
}
