import {
  Badge,
  Button,
  ButtonGroup,
  Heading,
  HStack,
  Icon,
  IconButton,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
} from "@chakra-ui/react";

import { CardImage } from "../RecipeCard/CardImage";

type MetadataItem = {
  label: string;
  value: string;
};

type RecipeDetailHeroProps = {
  imageUrl: string | null;
  title: string;
  isFavorite: boolean;
  isTogglingFavorite: boolean;
  onToggleFavorite?: () => void;
};

type RecipeDetailHeaderProps = {
  title: string;
  metadataItems: MetadataItem[];
  timesCooked: number;
  isEditing: boolean;
  canEdit: boolean;
  showTimesCookedControls: boolean;
  isUpdatingTimesCooked: boolean;
  isSavingOverrides: boolean;
  isSavingMetadata: boolean;
  isDeleting: boolean;
  hasUnsavedChanges: boolean;
  onAdjustTimesCooked?: (delta: -1 | 1) => Promise<void>;
  onStartEditing: () => void;
  onCancelEditing: () => void;
  onSaveEdits: () => void;
  onOpenDeleteDialog: () => void;
  canDelete: boolean;
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

function DeleteRecipeIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={5}>
      <path
        fill="currentColor"
        d="M9 3h6l1 2h5v2H3V5h5l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9zm-1 12c-1.1 0-2-.9-2-2V8h16v11c0 1.1-.9 2-2 2H6z"
      />
    </Icon>
  );
}

export function RecipeDetailHero({
  imageUrl,
  title,
  isFavorite,
  isTogglingFavorite,
  onToggleFavorite,
}: RecipeDetailHeroProps) {
  return (
    <div className="recipeDetailCard__hero">
      <CardImage
        imageUrl={imageUrl}
        title={title}
        isFavorite={isFavorite}
        isTogglingFavorite={isTogglingFavorite}
        onToggleFavorite={onToggleFavorite}
      />
    </div>
  );
}

export function RecipeDetailHeader({
  title,
  metadataItems,
  timesCooked,
  isEditing,
  canEdit,
  showTimesCookedControls,
  isUpdatingTimesCooked,
  isSavingOverrides,
  isSavingMetadata,
  isDeleting,
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
                  isDisabled={isSavingOverrides || isSavingMetadata || isDeleting}
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
                    isDisabled={isSavingOverrides || isSavingMetadata || isDeleting}
                    isLoading={isDeleting}
                  />
                </Tooltip>
              ) : null}
            </HStack>
          ) : canEdit ? (
            <ButtonGroup size="sm">
              <Button
                variant="ghost"
                onClick={onCancelEditing}
                isDisabled={isSavingOverrides || isSavingMetadata || isDeleting}
              >
                Cancel
              </Button>
              <Button
                bg="brand.600"
                color="white"
                _hover={{ bg: "brand.700" }}
                onClick={onSaveEdits}
                isLoading={isSavingOverrides || isSavingMetadata}
                isDisabled={!hasUnsavedChanges || isDeleting}
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
