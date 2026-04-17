import {
  Badge,
  Button,
  ButtonGroup,
  Card,
  CardBody,
  Divider,
  Heading,
  HStack,
  Icon,
  IconButton,
  ListItem,
  OrderedList,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Tooltip,
  UnorderedList,
} from "@chakra-ui/react";
import { useState } from "react";

import type { NormalizedRecipe, RecipeTextOverrides } from "../../types/recipe";
import {
  applyRowOverrides,
  areRowsEqual,
  buildDiffSegments,
  buildRowOverrides,
  getRecipeTextOverrides,
} from "../../utils/recipeOverrides";
import "./RecipeDetailCard.scss";

type RecipeDetailCardProps = {
  recipe: NormalizedRecipe;
  recipeIndex: number;
  index: number;
  timesCooked: number;
  overrides?: RecipeTextOverrides;
  isUpdatingTimesCooked?: boolean;
  isSavingOverrides?: boolean;
  onAdjustTimesCooked?: (delta: -1 | 1) => Promise<void>;
  onSaveOverrides?: (
    recipeIndex: number,
    overrides: RecipeTextOverrides,
  ) => Promise<void>;
  showTimesCookedControls?: boolean;
};

function EditRecipeIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={5}>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm17.71-10.04a.996.996 0 0 0 0-1.41l-2.5-2.5a.996.996 0 0 0-1.41 0l-1.96 1.96 3.75 3.75 1.92-1.8z"
      />
    </Icon>
  );
}

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

export function RecipeDetailCard({
  recipe,
  recipeIndex,
  index,
  timesCooked,
  overrides,
  isUpdatingTimesCooked = false,
  isSavingOverrides = false,
  onAdjustTimesCooked,
  onSaveOverrides,
  showTimesCookedControls = false,
}: RecipeDetailCardProps) {
  const savedOverrides = getRecipeTextOverrides(overrides);
  const visibleIngredients = applyRowOverrides(
    recipe.ingredients,
    savedOverrides.ingredients,
  );
  const visibleInstructions = applyRowOverrides(
    recipe.instructions,
    savedOverrides.instructions,
  );
  const [isEditing, setIsEditing] = useState(false);
  const [draftIngredients, setDraftIngredients] =
    useState<string[]>(visibleIngredients);
  const [draftInstructions, setDraftInstructions] =
    useState<string[]>(visibleInstructions);
  const [saveError, setSaveError] = useState("");

  const metadataItems = [
    recipe.recipeYield ? { label: "Yield", value: recipe.recipeYield } : null,
    recipe.cookTime ? { label: "Cook time", value: recipe.cookTime } : null,
    recipe.recipeCuisine && recipe.recipeCuisine.length > 0
      ? { label: "Cuisine", value: recipe.recipeCuisine.join(", ") }
      : null,
  ].filter((item): item is { label: string; value: string } => item !== null);

  const handleAdjustTimesCooked = (delta: -1 | 1) => async () => {
    await onAdjustTimesCooked?.(delta);
  };

  const hasUnsavedChanges =
    !areRowsEqual(draftIngredients, visibleIngredients) ||
    !areRowsEqual(draftInstructions, visibleInstructions);

  const startEditing = () => {
    setDraftIngredients([...visibleIngredients]);
    setDraftInstructions([...visibleInstructions]);
    setSaveError("");
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraftIngredients([...visibleIngredients]);
    setDraftInstructions([...visibleInstructions]);
    setSaveError("");
    setIsEditing(false);
  };

  const handleSaveOverrides = async () => {
    if (!onSaveOverrides) {
      return;
    }

    setSaveError("");

    try {
      await onSaveOverrides(recipeIndex, {
        ingredients: buildRowOverrides(recipe.ingredients, draftIngredients),
        instructions: buildRowOverrides(recipe.instructions, draftInstructions),
      });
      setIsEditing(false);
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Unable to save recipe edits.",
      );
    }
  };

  const renderEditorRows = (
    section: "ingredients" | "instructions",
    rows: string[],
    originals: string[],
    setRows: (rows: string[]) => void,
  ) => (
    <Stack spacing={3}>
      {rows.map((row, rowIndex) => {
        const changed = row !== originals[rowIndex];

        return (
          <Stack
            key={`${section}-${rowIndex}`}
            spacing={2}
            className={`recipeDetailCard__editorRow${changed ? " recipeDetailCard__editorRow--changed" : ""}`}
          >
            <Text
              fontSize="sm"
              fontWeight="600"
              color={changed ? "orange.600" : "gray.500"}
            >
              {section === "ingredients" ? "Ingredient" : "Step"} {rowIndex + 1}
            </Text>
            <Textarea
              value={row}
              onChange={(event) => {
                const nextRows = [...rows];
                nextRows[rowIndex] = event.target.value;
                setRows(nextRows);
              }}
              className="recipeDetailCard__editor"
              minH="unset"
              resize="vertical"
            />
          </Stack>
        );
      })}
    </Stack>
  );

  return (
    <Card className="recipeDetailCard">
      <CardBody>
        <Stack spacing={6}>
          <Stack spacing={2}>
            <HStack justify="space-between" align="start" wrap="wrap">
              <Text color="brand.600" fontWeight="700" fontSize="sm">
                Recipe {index}
              </Text>
              <HStack spacing={2} align="center" wrap="wrap" justify="flex-end">
                {showTimesCookedControls ? (
                  <>
                    {timesCooked > 0 ? (
                      <Badge colorScheme="brand">Cooked {timesCooked}x</Badge>
                    ) : null}
                    <ButtonGroup isAttached size="sm" variant="outline">
                      <Button
                        aria-label={`Decrease cooked count for ${recipe.name}`}
                        onClick={handleAdjustTimesCooked(-1)}
                        isDisabled={
                          isUpdatingTimesCooked || timesCooked <= 0 || isEditing
                        }
                      >
                        -
                      </Button>
                      <Button
                        aria-label={`Increase cooked count for ${recipe.name}`}
                        onClick={handleAdjustTimesCooked(1)}
                        isLoading={isUpdatingTimesCooked}
                        isDisabled={isEditing}
                      >
                        +
                      </Button>
                    </ButtonGroup>
                  </>
                ) : null}

                {!isEditing ? (
                  <Tooltip label="Edit ingredients and instructions" hasArrow>
                    <IconButton
                      aria-label={`Edit ${recipe.name}`}
                      icon={<EditRecipeIcon />}
                      variant="outline"
                      onClick={startEditing}
                      isDisabled={isSavingOverrides}
                    />
                  </Tooltip>
                ) : (
                  <ButtonGroup size="sm">
                    <Button
                      variant="ghost"
                      onClick={cancelEditing}
                      isDisabled={isSavingOverrides}
                    >
                      Cancel
                    </Button>
                    <Button
                      bg="brand.600"
                      color="white"
                      _hover={{ bg: "brand.700" }}
                      onClick={handleSaveOverrides}
                      isLoading={isSavingOverrides}
                      isDisabled={!hasUnsavedChanges}
                    >
                      Save edits
                    </Button>
                  </ButtonGroup>
                )}
              </HStack>
            </HStack>
            <Heading size="lg">{recipe.name}</Heading>
            {metadataItems.length > 0 ? (
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                {metadataItems.map((item) => (
                  <Text key={item.label}>
                    <strong>{item.label}:</strong> {item.value}
                  </Text>
                ))}
              </SimpleGrid>
            ) : null}
          </Stack>

          {metadataItems.length > 0 ? <Divider /> : null}

          <Stack spacing={3}>
            <HStack justify="space-between" wrap="wrap" spacing={3}>
              <Heading size="sm">Ingredients</Heading>
              {isEditing ? (
                <Text fontSize="sm" color="gray.500">
                  Changed rows are tinted while you edit.
                </Text>
              ) : null}
            </HStack>
            {isEditing ? (
              renderEditorRows(
                "ingredients",
                draftIngredients,
                recipe.ingredients,
                setDraftIngredients,
              )
            ) : (
              <UnorderedList spacing={2} className="recipeDetailCard__list">
                {visibleIngredients.map((ingredient, rowIndex) => (
                  <ListItem key={`ingredient-${rowIndex}`}>
                    {renderDiffText(
                      recipe.ingredients[rowIndex] ?? "",
                      ingredient,
                      `ingredient-${rowIndex}`,
                    )}
                  </ListItem>
                ))}
              </UnorderedList>
            )}
          </Stack>

          <Stack spacing={3}>
            <Heading size="sm">Instructions</Heading>
            {isEditing ? (
              renderEditorRows(
                "instructions",
                draftInstructions,
                recipe.instructions,
                setDraftInstructions,
              )
            ) : (
              <OrderedList spacing={3} className="recipeDetailCard__list">
                {visibleInstructions.map((instruction, rowIndex) => (
                  <ListItem key={`instruction-${rowIndex}`}>
                    {renderDiffText(
                      recipe.instructions[rowIndex] ?? "",
                      instruction,
                      `instruction-${rowIndex}`,
                    )}
                  </ListItem>
                ))}
              </OrderedList>
            )}
          </Stack>

          {isEditing && saveError ? (
            <Text color="red.500">{saveError}</Text>
          ) : null}

          {recipe.nutrition ? (
            <Stack spacing={3}>
              <Heading size="sm">Nutrition</Heading>
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
                {Object.entries(recipe.nutrition).map(([key, value]) => (
                  <Text key={key}>
                    <strong>{key}:</strong> {value}
                  </Text>
                ))}
              </SimpleGrid>
            </Stack>
          ) : null}
        </Stack>
      </CardBody>
    </Card>
  );
}
