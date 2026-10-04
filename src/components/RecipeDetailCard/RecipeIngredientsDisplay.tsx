import { Checkbox, Stack, Text } from "@chakra-ui/react";

import type { RecipeRow } from "../../utils/recipeOverrides";
import { RecipeDiffText } from "./RecipeDiffText";

export type VisibleIngredientSection = {
  title: string | null;
  rows: RecipeRow[];
};

type RecipeIngredientsDisplayProps = {
  visibleRows: RecipeRow[];
  visibleSections: VisibleIngredientSection[] | null;
  scaleFactor: number;
};

function renderIngredientText(row: RecipeRow, scaleFactor: number) {
  if (Math.abs(scaleFactor - 1) > 0.001) {
    return row.text;
  }

  return (
    <RecipeDiffText
      originalValue={row.original}
      editedValue={row.text}
      keyPrefix={`ingredient-${row.key}`}
    />
  );
}

function IngredientCheckboxRow({ children }: { children: React.ReactNode }) {
  return (
    <Checkbox
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

function IngredientRows({
  rows,
  scaleFactor,
}: {
  rows: RecipeRow[];
  scaleFactor: number;
}) {
  return (
    <Stack spacing={2} className="recipeDetailCard__list">
      {rows.map((row) => (
        <IngredientCheckboxRow key={`ingredient-${row.key}`}>
          {renderIngredientText(row, scaleFactor)}
        </IngredientCheckboxRow>
      ))}
    </Stack>
  );
}

export function RecipeIngredientsDisplay({
  visibleRows,
  visibleSections,
  scaleFactor,
}: RecipeIngredientsDisplayProps) {
  if (visibleSections) {
    return (
      <Stack spacing={4}>
        {visibleSections.map((section, sectionIndex) => (
          <Stack
            key={`${section.title ?? "ingredients"}-${sectionIndex}`}
            spacing={2}
          >
            {section.title ? <Text fontWeight="700">{section.title}</Text> : null}
            <IngredientRows rows={section.rows} scaleFactor={scaleFactor} />
          </Stack>
        ))}
      </Stack>
    );
  }

  return <IngredientRows rows={visibleRows} scaleFactor={scaleFactor} />;
}
