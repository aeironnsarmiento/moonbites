import { useState } from "react";
import type { FormEvent } from "react";

import { Button, HStack, Stack, Text } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";

import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { UrlPasteForm } from "../../components/UrlPasteForm/UrlPasteForm";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import "./HomePage.scss";

export function HomePage() {
  const [url, setUrl] = useState("");
  const { error, isLoading, status, submitRecipe } = useExtractRecipe();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitRecipe(url);
  };

  return (
    <Stack spacing={8} className="homePage">
      <UrlPasteForm
        url={url}
        isLoading={isLoading}
        onUrlChange={setUrl}
        onSubmit={handleSubmit}
      />

      <StatusBanner error={error} status={status} />

      <HStack justify="space-between" className="homePage__footer" wrap="wrap">
        <Text color="gray.500">
          Imported recipes are saved to Supabase and can be browsed from the
          recipe list page.
        </Text>
        <Button as={RouterLink} to="/recipes" variant="outline">
          Browse recipe list
        </Button>
      </HStack>
    </Stack>
  );
}
