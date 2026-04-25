import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import {
  Button,
  Card,
  CardBody,
  Divider,
  FormControl,
  FormHelperText,
  FormLabel,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { UrlPasteForm } from "../../components/UrlPasteForm/UrlPasteForm";
import { useCreateRecipe } from "../../hooks/useCreateRecipe";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import type { NormalizedRecipe } from "../../types/recipe";

type RecipeFormState = {
  title: string;
  name: string;
  recipeYield: string;
  cookTime: string;
  recipeCuisine: string;
  ingredients: string;
  instructions: string;
};

const EMPTY_FORM: RecipeFormState = {
  title: "",
  name: "",
  recipeYield: "",
  cookTime: "",
  recipeCuisine: "",
  ingredients: "",
  instructions: "",
};

function parseLineList(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseCuisineList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildRecipePayload(form: RecipeFormState): NormalizedRecipe {
  const ingredients = parseLineList(form.ingredients);
  const instructions = parseLineList(form.instructions);
  const cuisines = parseCuisineList(form.recipeCuisine);

  return {
    name: form.name.trim(),
    recipeYield: form.recipeYield.trim() || null,
    cookTime: form.cookTime.trim() || null,
    recipeCuisine: cuisines.length > 0 ? cuisines : null,
    nutrition: null,
    ingredients,
    ingredientSections: null,
    instructions,
  };
}

export function RecipeCreatePage() {
  const navigate = useNavigate();
  const { createRecipe, error, isLoading } = useCreateRecipe();
  const {
    error: extractError,
    isLoading: isExtracting,
    status: extractStatus,
    submitRecipe,
  } = useExtractRecipe();
  const [form, setForm] = useState<RecipeFormState>(EMPTY_FORM);
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState("");

  const fieldError = validationError || error;

  const previewCounts = useMemo(
    () => ({
      ingredients: parseLineList(form.ingredients).length,
      instructions: parseLineList(form.instructions).length,
    }),
    [form.ingredients, form.instructions],
  );

  const updateField = (field: keyof RecipeFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setValidationError("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const recipe = buildRecipePayload(form);
    if (!recipe.name || recipe.ingredients.length === 0 || recipe.instructions.length === 0) {
      setValidationError(
        "Recipe name, at least one ingredient, and at least one instruction are required.",
      );
      return;
    }

    const record = await createRecipe({
      recipe,
      title: form.title.trim() || `Manual recipe: ${recipe.name}`,
    });

    navigate(`/recipes/${record.id}`);
  };

  const handleUrlSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitRecipe(url);
  };

  return (
    <Stack spacing={8}>
      <Stack spacing={2}>
        <Text color="brand.600" fontWeight="700" fontSize="sm">
          Create recipe
        </Text>
        <Heading size="xl">Add a recipe</Heading>
      </Stack>

      <Stack spacing={4}>
        <Heading size="md">Paste a URL to import.</Heading>
        <UrlPasteForm
          url={url}
          isLoading={isExtracting}
          onUrlChange={setUrl}
          onSubmit={handleUrlSubmit}
        />
        <StatusBanner error={extractError} status={extractStatus} />
      </Stack>

      <HStack spacing={4}>
        <Divider />
        <Text color="gray.600" fontSize="sm" whiteSpace="nowrap">
          or
        </Text>
        <Divider />
      </HStack>

      <Card>
        <CardBody>
          <form onSubmit={handleSubmit}>
            <Stack spacing={6}>
              <Stack spacing={1}>
                <Heading size="md">Or enter the details yourself.</Heading>
              </Stack>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                <FormControl>
                  <FormLabel htmlFor="manual-title">Record title</FormLabel>
                  <Input
                    id="manual-title"
                    value={form.title}
                    onChange={(event) => updateField("title", event.target.value)}
                    placeholder="Manual recipe: Yuzu Cheesecake"
                  />
                  <FormHelperText>
                    Optional label for the saved record in the recipe list.
                  </FormHelperText>
                </FormControl>

                <FormControl isRequired>
                  <FormLabel htmlFor="manual-name">Recipe name</FormLabel>
                  <Input
                    id="manual-name"
                    value={form.name}
                    onChange={(event) => updateField("name", event.target.value)}
                    placeholder="Yuzu Cheesecake"
                  />
                </FormControl>
              </SimpleGrid>

              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
                <FormControl>
                  <FormLabel htmlFor="manual-yield">Yield</FormLabel>
                  <Input
                    id="manual-yield"
                    value={form.recipeYield}
                    onChange={(event) => updateField("recipeYield", event.target.value)}
                    placeholder="8 slices"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="manual-cook-time">Cook time</FormLabel>
                  <Input
                    id="manual-cook-time"
                    value={form.cookTime}
                    onChange={(event) => updateField("cookTime", event.target.value)}
                    placeholder="1 hour 20 minutes"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="manual-cuisine">Cuisine</FormLabel>
                  <Input
                    id="manual-cuisine"
                    value={form.recipeCuisine}
                    onChange={(event) => updateField("recipeCuisine", event.target.value)}
                    placeholder="Japanese, Dessert"
                  />
                  <FormHelperText>Separate multiple cuisines with commas.</FormHelperText>
                </FormControl>
              </SimpleGrid>

              <FormControl isRequired>
                <FormLabel htmlFor="manual-ingredients">Ingredients</FormLabel>
                <Textarea
                  id="manual-ingredients"
                  minH="220px"
                  resize="vertical"
                  value={form.ingredients}
                  onChange={(event) => updateField("ingredients", event.target.value)}
                  placeholder={"1 package graham crackers\n6 tablespoons unsalted butter, melted\n1.5 pounds cream cheese"}
                />
                <FormHelperText>
                  Enter one ingredient per line. {previewCounts.ingredients} line
                  {previewCounts.ingredients === 1 ? "" : "s"} detected.
                </FormHelperText>
              </FormControl>

              <FormControl isRequired>
                <FormLabel htmlFor="manual-instructions">Instructions</FormLabel>
                <Textarea
                  id="manual-instructions"
                  minH="220px"
                  resize="vertical"
                  value={form.instructions}
                  onChange={(event) => updateField("instructions", event.target.value)}
                  placeholder={"Preheat the oven to 325F.\nMix the crust ingredients.\nBake until just set."}
                />
                <FormHelperText>
                  Enter one instruction step per line. {previewCounts.instructions} step
                  {previewCounts.instructions === 1 ? "" : "s"} detected.
                </FormHelperText>
              </FormControl>

              <StatusBanner error={fieldError} />

              <SimpleGrid columns={{ base: 1, sm: 2 }} spacing={3}>
                <Button variant="outline" as={RouterLink} to="/">
                  Back to import
                </Button>
                <Button type="submit" colorScheme="brand" isLoading={isLoading}>
                  Save manual recipe
                </Button>
              </SimpleGrid>
            </Stack>
          </form>
        </CardBody>
      </Card>
    </Stack>
  );
}
