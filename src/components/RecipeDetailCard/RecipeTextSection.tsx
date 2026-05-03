import {
  Heading,
  HStack,
  ListItem,
  OrderedList,
  SimpleGrid,
  Stack,
  Text,
} from "@chakra-ui/react";
import type { ReactNode } from "react";

import { ServingsStepper } from "../../components/ServingsStepper/ServingsStepper";
import type { IngredientSection } from "../../types/recipe";
import { RecipeDiffText } from "./RecipeDiffText";
import { RecipeIngredientsDisplay } from "./RecipeIngredientsDisplay";

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
          <RecipeIngredientsDisplay
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
              <RecipeDiffText
                originalValue={props.originalRows[rowIndex] ?? ""}
                editedValue={instruction}
                keyPrefix={`instruction-${rowIndex}`}
              />
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
