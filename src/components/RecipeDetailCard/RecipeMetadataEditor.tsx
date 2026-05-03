import {
  FormControl,
  FormLabel,
  Heading,
  Input,
  SimpleGrid,
  Stack,
} from "@chakra-ui/react";

type RecipeMetadataEditorProps = {
  recipeImportId: string;
  draftTitle: string;
  draftYield: string;
  draftImageUrl: string;
  draftSourceUrl: string;
  onChangeTitle: (value: string) => void;
  onChangeYield: (value: string) => void;
  onChangeImageUrl: (value: string) => void;
  onChangeSourceUrl: (value: string) => void;
};

export function RecipeMetadataEditor({
  recipeImportId,
  draftTitle,
  draftYield,
  draftImageUrl,
  draftSourceUrl,
  onChangeTitle,
  onChangeYield,
  onChangeImageUrl,
  onChangeSourceUrl,
}: RecipeMetadataEditorProps) {
  return (
    <Stack spacing={4} className="recipeDetailCard__section">
      <Heading size="sm">Recipe details</Heading>
      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
        <FormControl isRequired>
          <FormLabel htmlFor={`recipe-title-${recipeImportId}`}>Title</FormLabel>
          <Input
            id={`recipe-title-${recipeImportId}`}
            value={draftTitle}
            onChange={(event) => onChangeTitle(event.target.value)}
          />
        </FormControl>
        <FormControl>
          <FormLabel htmlFor={`recipe-yield-${recipeImportId}`}>Yield</FormLabel>
          <Input
            id={`recipe-yield-${recipeImportId}`}
            value={draftYield}
            onChange={(event) => onChangeYield(event.target.value)}
            placeholder="4 servings"
          />
        </FormControl>
        <FormControl>
          <FormLabel htmlFor={`recipe-image-${recipeImportId}`}>
            Image URL
          </FormLabel>
          <Input
            id={`recipe-image-${recipeImportId}`}
            value={draftImageUrl}
            onChange={(event) => onChangeImageUrl(event.target.value)}
            placeholder="https://example.com/image.jpg"
          />
        </FormControl>
        <FormControl isRequired>
          <FormLabel htmlFor={`recipe-source-${recipeImportId}`}>
            Source link
          </FormLabel>
          <Input
            id={`recipe-source-${recipeImportId}`}
            value={draftSourceUrl}
            onChange={(event) => onChangeSourceUrl(event.target.value)}
            placeholder="https://example.com/recipe"
          />
        </FormControl>
      </SimpleGrid>
    </Stack>
  );
}
