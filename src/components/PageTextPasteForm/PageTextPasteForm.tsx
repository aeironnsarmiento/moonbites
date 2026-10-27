import type { FormEvent } from "react";

import {
  Button,
  Card,
  CardBody,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";

import "./PageTextPasteForm.scss";

type PageTextPasteFormProps = {
  url: string;
  pageText: string;
  isLoading: boolean;
  onPageTextChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

/** Offered when a recipe site blocks the backend's fetch: the admin pastes the page's text instead. */
export function PageTextPasteForm({
  url,
  pageText,
  isLoading,
  onPageTextChange,
  onSubmit,
}: PageTextPasteFormProps) {
  return (
    <Card className="pageTextPasteForm">
      <CardBody>
        <form className="pageTextPasteForm__form" onSubmit={onSubmit}>
          <Stack spacing={2}>
            <Heading size="md">Paste the recipe text</Heading>
            <Text color="gray.600">
              This site blocks automated imports. Open{" "}
              <a
                className="pageTextPasteForm__link"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                the recipe page
              </a>
              , select the recipe (or the whole page), copy it, and paste it
              here. The recipe is saved with this URL as its source.
            </Text>
          </Stack>

          <FormControl isRequired>
            <FormLabel htmlFor="recipe-page-text">Recipe text</FormLabel>
            <Textarea
              id="recipe-page-text"
              minH="220px"
              resize="vertical"
              value={pageText}
              onChange={(event) => onPageTextChange(event.target.value)}
              placeholder={"Ingredients\n1 cup flour\n...\n\nInstructions\n1. Preheat the oven..."}
            />
            <FormHelperText>
              Include the ingredients and the steps.
            </FormHelperText>
          </FormControl>

          <Button
            type="submit"
            colorScheme="brand"
            isLoading={isLoading}
            loadingText="Reading"
            isDisabled={!pageText.trim()}
          >
            Import from text
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
