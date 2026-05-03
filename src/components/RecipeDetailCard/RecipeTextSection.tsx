import {
  Heading,
  HStack,
  ListItem,
  OrderedList,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
  UnorderedList,
} from "@chakra-ui/react";
import type { ReactNode } from "react";

import { ServingsStepper } from "../../components/ServingsStepper/ServingsStepper";
import type { IngredientSection } from "../../types/recipe";
import { buildDiffSegments } from "../../utils/recipeOverrides";

type ServingsControls = {
  currentServings: number;
  originalServings: number;
  isSaving: boolean;
  onDecrement: () => void;
  onIncrement: () => void;
  onSaveDefault?: (servings: number) => Promise<void>;
};

type IngredientsSectionProps = {
  section: "ingredients";
  isEditing: boolean;
  editorRows: ReactNode;
  originalRows: string[];
  scaledVisibleIngredients: string[];
  visibleIngredientSections: IngredientSection[] | null;
  originalIngredientSections: IngredientSection[] | null;
  scaleFactor: number;
  servingsControls: ServingsControls;
};

type InstructionsSectionProps = {
  section: "instructions";
  isEditing: boolean;
  editorRows: ReactNode;
  originalRows: string[];
  visibleRows: string[];
};

type RecipeTextSectionProps = IngredientsSectionProps | InstructionsSectionProps;

function renderDiffText(
  originalValue: string,
  editedValue: string,
  keyPrefix: string,
) {
  const diffSegments = buildDiffSegments(originalValue, editedValue);

  if (originalValue === editedValue) {
    return editedValue;
  }

  if (diffSegments.length === 0) {
    return (
      <Tooltip label={`Original: ${originalValue}`} hasArrow>
        <Text
          as="span"
          tabIndex={0}
          className="recipeDetailCard__diff recipeDetailCard__diff--changed"
        >
          (empty)
        </Text>
      </Tooltip>
    );
  }

  return diffSegments.map((segment, index) => {
    if (!segment.changed) {
      return (
        <Text as="span" key={`${keyPrefix}-${index}`}>
          {segment.text}
        </Text>
      );
    }

    return (
      <Tooltip
        key={`${keyPrefix}-${index}`}
        label={`Original: ${originalValue}`}
        hasArrow
      >
        <Text
          as="span"
          tabIndex={0}
          className="recipeDetailCard__diff recipeDetailCard__diff--changed"
        >
          {segment.text}
        </Text>
      </Tooltip>
    );
  });
}

function renderIngredientText(
  originalValue: string,
  editedValue: string,
  keyPrefix: string,
  scaleFactor: number,
) {
  if (Math.abs(scaleFactor - 1) > 0.001) {
    return editedValue;
  }

  return renderDiffText(originalValue, editedValue, keyPrefix);
}

function IngredientsDisplay({
  originalRows,
  scaledVisibleIngredients,
  visibleIngredientSections,
  originalIngredientSections,
  scaleFactor,
}: Pick<
  IngredientsSectionProps,
  | "originalRows"
  | "scaledVisibleIngredients"
  | "visibleIngredientSections"
  | "originalIngredientSections"
  | "scaleFactor"
>) {
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

export function RecipeTextSection(props: RecipeTextSectionProps) {
  if (props.section === "ingredients") {
    return (
      <Stack spacing={3} className="recipeDetailCard__section">
        <ServingsStepper
          currentServings={props.servingsControls.currentServings}
          originalServings={props.servingsControls.originalServings}
          isSaving={props.servingsControls.isSaving}
          onDecrement={props.servingsControls.onDecrement}
          onIncrement={props.servingsControls.onIncrement}
          onSaveDefault={props.servingsControls.onSaveDefault}
        />
        <HStack justify="space-between" wrap="wrap" spacing={3}>
          <Heading size="sm">Ingredients</Heading>
          {props.isEditing ? (
            <Text fontSize="sm" color="gray.500">
              Changed rows are tinted while you edit.
            </Text>
          ) : null}
        </HStack>
        {props.isEditing ? (
          props.editorRows
        ) : (
          <IngredientsDisplay
            originalRows={props.originalRows}
            scaledVisibleIngredients={props.scaledVisibleIngredients}
            visibleIngredientSections={props.visibleIngredientSections}
            originalIngredientSections={props.originalIngredientSections}
            scaleFactor={props.scaleFactor}
          />
        )}
      </Stack>
    );
  }

  return (
    <Stack spacing={3} className="recipeDetailCard__section">
      <Heading size="sm">Instructions</Heading>
      {props.isEditing ? (
        props.editorRows
      ) : (
        <OrderedList spacing={3} className="recipeDetailCard__list">
          {props.visibleRows.map((instruction, rowIndex) => (
            <ListItem key={`instruction-${rowIndex}`}>
              {renderDiffText(
                props.originalRows[rowIndex] ?? "",
                instruction,
                `instruction-${rowIndex}`,
              )}
            </ListItem>
          ))}
        </OrderedList>
      )}
    </Stack>
  );
}

type NutritionSectionProps = {
  nutrition: Record<string, string>;
};

export function NutritionSection({ nutrition }: NutritionSectionProps) {
  return (
    <Stack spacing={3} className="recipeDetailCard__section">
      <Heading size="sm">Nutrition</Heading>
      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
        {Object.entries(nutrition).map(([key, value]) => (
          <Text key={key}>
            <strong>{key}:</strong> {value}
          </Text>
        ))}
      </SimpleGrid>
    </Stack>
  );
}
