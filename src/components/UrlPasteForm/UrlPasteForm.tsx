import type { FormEvent } from "react";

import {
  Button,
  Card,
  CardBody,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";

import "./UrlPasteForm.scss";

type UrlPasteFormProps = {
  url: string;
  isLoading: boolean;
  onUrlChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function UrlPasteForm({
  url,
  isLoading,
  onUrlChange,
  onSubmit,
}: UrlPasteFormProps) {
  return (
    <Card className="urlPasteForm">
      <CardBody>
        <Stack spacing={6}>
          <Stack spacing={3}>
            <Text className="urlPasteForm__eyebrow">Import recipe</Text>
            <Heading size="xl">Paste a recipe URL</Heading>
            <Text color="gray.600">
              Submit any public recipe page to normalize the JSON-LD, save it to
              Supabase, and keep the cleaned result in your saved recipe list.
            </Text>
          </Stack>

          <form className="urlPasteForm__form" onSubmit={onSubmit}>
            <FormControl isRequired>
              <FormLabel htmlFor="recipe-url">URL</FormLabel>
              <Input
                id="recipe-url"
                size="lg"
                placeholder="https://example.com/recipe"
                value={url}
                onChange={(event) => onUrlChange(event.target.value)}
              />
            </FormControl>

            <Button
              type="submit"
              size="lg"
              isLoading={isLoading}
              loadingText="Processing"
            >
              Save recipe
            </Button>
          </form>
        </Stack>
      </CardBody>
    </Card>
  );
}
