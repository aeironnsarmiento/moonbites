import {
  Badge,
  Button,
  ButtonGroup,
  Heading,
  HStack,
  IconButton,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from "@chakra-ui/react";

import { DeleteRecipeIcon, EditRecipeIcon } from "../Icons";

export type MetadataItem = {
  label: string;
  value: string;
};

type RecipeDetailHeaderProps = {
  title: string;
  metadataItems: MetadataItem[];
  timesCooked: number;
  isEditing: boolean;
  canEdit: boolean;
  showTimesCookedControls: boolean;
  isUpdatingTimesCooked: boolean;
  isBusy: boolean;
  hasUnsavedChanges: boolean;
  onAdjustTimesCooked?: (delta: -1 | 1) => Promise<void>;
  onStartEditing: () => void;
  onCancelEditing: () => void;
  onSaveEdits: () => void;
  onOpenDeleteDialog: () => void;
  canDelete: boolean;
};

export function RecipeDetailHeader({
  title,
  metadataItems,
  timesCooked,
  isEditing,
  canEdit,
  showTimesCookedControls,
  isUpdatingTimesCooked,
  isBusy,
  hasUnsavedChanges,
  onAdjustTimesCooked,
  onStartEditing,
  onCancelEditing,
  onSaveEdits,
  onOpenDeleteDialog,
  canDelete,
}: RecipeDetailHeaderProps) {
  const handleAdjustTimesCooked = (delta: -1 | 1) => async () => {
    await onAdjustTimesCooked?.(delta);
  };

  return (
    <Stack spacing={2}>
      <HStack justify="space-between" align="start" wrap="wrap">
        <span aria-hidden="true" />
        <HStack spacing={2} align="center" wrap="wrap" justify="flex-end">
          {canEdit && showTimesCookedControls ? (
            <>
              {timesCooked > 0 ? (
                <Badge colorScheme="brand">Cooked {timesCooked}x</Badge>
              ) : null}
              <ButtonGroup isAttached size="sm" variant="outline">
                <Button
                  aria-label={`Decrease cooked count for ${title}`}
                  onClick={handleAdjustTimesCooked(-1)}
                  isDisabled={
                    isUpdatingTimesCooked || timesCooked <= 0 || isEditing
                  }
                >
                  -
                </Button>
                <Button
                  aria-label={`Increase cooked count for ${title}`}
                  onClick={handleAdjustTimesCooked(1)}
                  isLoading={isUpdatingTimesCooked}
                  isDisabled={isEditing}
                >
                  +
                </Button>
              </ButtonGroup>
            </>
          ) : null}

          {canEdit && !isEditing ? (
            <HStack spacing={2}>
              <Tooltip label="Edit ingredients and instructions" hasArrow>
                <IconButton
                  aria-label={`Edit ${title}`}
                  icon={<EditRecipeIcon />}
                  variant="outline"
                  onClick={onStartEditing}
                  isDisabled={isBusy}
                />
              </Tooltip>
              {canDelete ? (
                <Tooltip label="Delete saved recipe" hasArrow>
                  <IconButton
                    aria-label={`Delete ${title}`}
                    icon={<DeleteRecipeIcon />}
                    variant="outline"
                    colorScheme="red"
                    onClick={onOpenDeleteDialog}
                    isDisabled={isBusy}
                    isLoading={isBusy}
                  />
                </Tooltip>
              ) : null}
            </HStack>
          ) : canEdit ? (
            <ButtonGroup size="sm">
              <Button
                variant="ghost"
                onClick={onCancelEditing}
                isDisabled={isBusy}
              >
                Cancel
              </Button>
              <Button
                bg="brand.600"
                color="white"
                _hover={{ bg: "brand.700" }}
                onClick={onSaveEdits}
                isLoading={isBusy}
                isDisabled={!hasUnsavedChanges}
              >
                Save edits
              </Button>
            </ButtonGroup>
          ) : null}
        </HStack>
      </HStack>
      <Heading size="lg">{title}</Heading>
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
  );
}
