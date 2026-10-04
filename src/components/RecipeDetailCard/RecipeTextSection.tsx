import {
  Flex,
  Heading,
  HStack,
  Stack,
  Text,
} from "@chakra-ui/react";
import type { ReactNode } from "react";

import { ServingsStepper } from "../../components/ServingsStepper/ServingsStepper";
import type { RecipeRow } from "../../utils/recipeOverrides";
import { RecipeDiffText } from "./RecipeDiffText";
import {
  RecipeIngredientsDisplay,
  type VisibleIngredientSection,
} from "./RecipeIngredientsDisplay";

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
  visibleRows: RecipeRow[];
  visibleSections: VisibleIngredientSection[] | null;
  scaleFactor: number;
  servingsControls: ServingsControls;
};

type InstructionsSectionProps = {
  section: "instructions";
  isEditing: boolean;
  editorRows: ReactNode;
  visibleRows: RecipeRow[];
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
              Changed and new rows are tinted while you edit.
            </Text>
          ) : null}
        </HStack>
        {props.isEditing ? (
          props.editorRows
        ) : (
          <RecipeIngredientsDisplay
            visibleRows={props.visibleRows}
            visibleSections={props.visibleSections}
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
        <Stack as="ol" spacing={4} listStyleType="none" m={0} p={0}>
          {props.visibleRows.map((instruction, rowIndex) => (
            <HStack
              as="li"
              key={`instruction-${instruction.key}`}
              align="flex-start"
              spacing={4}
            >
              <Flex
                boxSize="28px"
                borderRadius="full"
                bg="brand.500"
                color="white"
                fontSize="sm"
                fontWeight="700"
                align="center"
                justify="center"
                flexShrink={0}
                aria-hidden="true"
              >
                {rowIndex + 1}
              </Flex>
              <Text pt="2px">
                <RecipeDiffText
                  originalValue={instruction.original}
                  editedValue={instruction.text}
                  keyPrefix={`instruction-${instruction.key}`}
                />
              </Text>
            </HStack>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
