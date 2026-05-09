import type { FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";

import {
  Box,
  Button,
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
import { useCreateRecipe } from "../../hooks/useCreateRecipe";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import type { NormalizedRecipe } from "../../types/recipe";
import "./RecipeCreatePage.scss";

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

type CreateRecipeTab = "url" | "manual";

const IMPORTED_FIELDS = [
  "Title",
  "Ingredients",
  "Steps",
  "Yield",
  "Cook time",
  "Cuisine",
  "Nutrition",
];

const SUPPORTED_SITES = [
  "NYT Cooking",
  "Serious Eats",
  "Bon Appetit",
  "Smitten Kitchen",
  "King Arthur",
];

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

function getUrlHost(value: string) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m20 6-11 11-5-5" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 1 0-7.07-7.07L11.5 4.5" />
      <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 1 0 7.07 7.07l1.5-1.5" />
    </svg>
  );
}

function PasteIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="8" y="2" width="8" height="4" rx="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  );
}

function SectionHeader({
  eyebrow,
  title,
  helper,
  aside,
}: {
  eyebrow: string;
  title: string;
  helper?: string;
  aside?: ReactNode;
}) {
  return (
    <HStack
      align={{ base: "flex-start", md: "flex-end" }}
      justify="space-between"
      gap={4}
      className="recipeCreatePage__sectionHeader"
    >
      <Stack spacing={1}>
        <Text className="recipeCreatePage__sectionEyebrow">{eyebrow}</Text>
        <Heading size="md">{title}</Heading>
        {helper ? <Text color="gray.600">{helper}</Text> : null}
      </Stack>
      {aside}
    </HStack>
  );
}

function CountPill({ count, noun }: { count: number; noun: string }) {
  return (
    <Text className="recipeCreatePage__countPill">
      {count} {noun}
      {count === 1 ? "" : "s"} detected
    </Text>
  );
}

function PreviewList({
  empty,
  items,
  ordered = false,
}: {
  empty: string;
  items: string[];
  ordered?: boolean;
}) {
  if (items.length === 0) {
    return <Box className="recipeCreatePage__previewEmpty">{empty}</Box>;
  }

  return (
    <Box
      as={ordered ? "ol" : "ul"}
      className="recipeCreatePage__previewList"
    >
      {items.map((item, index) => (
        <Box as="li" key={`${item}-${index}`}>
          <span>{ordered ? index + 1 : ""}</span>
          <Text>{item}</Text>
        </Box>
      ))}
    </Box>
  );
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
  const [activeTab, setActiveTab] = useState<CreateRecipeTab>("url");
  const [pasteStatus, setPasteStatus] = useState("");

  const fieldError = validationError || error;
  const urlHost = getUrlHost(url);
  const canSubmitUrl = url.trim().length > 0 && !isExtracting;

  const previewCounts = useMemo(
    () => ({
      ingredients: parseLineList(form.ingredients).length,
      instructions: parseLineList(form.instructions).length,
    }),
    [form.ingredients, form.instructions],
  );
  const previewItems = useMemo(
    () => ({
      ingredients: parseLineList(form.ingredients),
      instructions: parseLineList(form.instructions),
    }),
    [form.ingredients, form.instructions],
  );

  const updateField = (field: keyof RecipeFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setValidationError("");
  };

  const handlePasteUrl = async () => {
    try {
      const value = await navigator.clipboard.readText();
      if (!value.trim()) {
        return;
      }

      setUrl(value.trim());
      setPasteStatus("Pasted");
      window.setTimeout(() => setPasteStatus(""), 1400);
    } catch {
      setPasteStatus("Paste unavailable");
      window.setTimeout(() => setPasteStatus(""), 1800);
    }
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
    <Stack spacing={7} className="recipeCreatePage">
      <HStack
        align={{ base: "flex-start", md: "flex-end" }}
        justify="space-between"
        gap={5}
        wrap="wrap"
      >
        <Stack spacing={2} className="recipeCreatePage__intro">
          <Text className="recipeCreatePage__eyebrow">
            <SparkIcon />
            New recipe
          </Text>
          <Heading size="2xl">Add a recipe</Heading>
          <Text color="gray.600">
            Import from a link, or build it from scratch. Either way, it lands
            in your saved recipes.
          </Text>
        </Stack>

        <HStack className="recipeCreatePage__tabs" role="tablist">
          <Button
            type="button"
            className={activeTab === "url" ? "is-active" : ""}
            onClick={() => setActiveTab("url")}
            role="tab"
            aria-selected={activeTab === "url"}
            variant="ghost"
          >
            <LinkIcon />
            Import from URL
          </Button>
          <Button
            type="button"
            className={activeTab === "manual" ? "is-active" : ""}
            onClick={() => setActiveTab("manual")}
            role="tab"
            aria-selected={activeTab === "manual"}
            variant="ghost"
          >
            <PencilIcon />
            Enter manually
          </Button>
        </HStack>
      </HStack>

      {activeTab === "url" ? (
        <Stack spacing={5}>
          <Box className="recipeCreatePage__urlPanel">
            <form onSubmit={handleUrlSubmit}>
              <Stack spacing={6}>
                <Stack spacing={2}>
                  <Text className="recipeCreatePage__sectionEyebrow">
                    <SparkIcon />
                    Import recipe
                  </Text>
                  <Heading size="lg">Paste a recipe URL</Heading>
                  <Text color="gray.600">
                    Drop in a public recipe link. Moonbites reads the structured
                    recipe data, normalizes it, and saves the cleaned result.
                  </Text>
                </Stack>

                <Box className="recipeCreatePage__urlInputGroup">
                  <span aria-hidden="true">
                    <LinkIcon />
                  </span>
                  <Input
                    id="recipe-url"
                    required
                    placeholder="https://cooking.nytimes.com/recipes/..."
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="recipeCreatePage__pasteButton"
                    onClick={handlePasteUrl}
                  >
                    {pasteStatus === "Pasted" ? <CheckIcon /> : <PasteIcon />}
                    {pasteStatus || "Paste"}
                  </Button>
                  <Button
                    type="submit"
                    isLoading={isExtracting}
                    isDisabled={!canSubmitUrl}
                    className="recipeCreatePage__submitButton"
                  >
                    Save recipe
                    <ArrowIcon />
                  </Button>
                </Box>

                {urlHost ? (
                  <Text className="recipeCreatePage__hostPill">
                    Reading from <strong>{urlHost}</strong>
                  </Text>
                ) : null}

                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
                  <Stack spacing={3}>
                    <Text className="recipeCreatePage__helperLabel">
                      What gets imported
                    </Text>
                    <HStack wrap="wrap" gap={2}>
                      {IMPORTED_FIELDS.map((field) => (
                        <Text key={field} className="recipeCreatePage__chip">
                          <CheckIcon />
                          {field}
                        </Text>
                      ))}
                    </HStack>
                  </Stack>

                  <Stack spacing={3}>
                    <Text className="recipeCreatePage__helperLabel">
                      Works well with
                    </Text>
                    <HStack wrap="wrap" gap={2}>
                      {SUPPORTED_SITES.map((site) => (
                        <Text
                          key={site}
                          className="recipeCreatePage__chip recipeCreatePage__chip--site"
                        >
                          {site}
                        </Text>
                      ))}
                    </HStack>
                  </Stack>
                </SimpleGrid>
              </Stack>
            </form>
          </Box>

          <StatusBanner error={extractError} status={extractStatus} />

          <Button
            type="button"
            variant="outline"
            className="recipeCreatePage__switchButton"
            onClick={() => setActiveTab("manual")}
          >
            No link handy? Enter the recipe by hand
            <ArrowIcon />
          </Button>
        </Stack>
      ) : (
        <form onSubmit={handleSubmit}>
          <Stack spacing={5}>
            <Box className="recipeCreatePage__panel">
              <SectionHeader
                eyebrow="Step 1 - basics"
                title="Name & details"
                helper="The essentials so you can find this recipe later."
              />

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5} mt={5}>
                <FormControl isRequired>
                  <FormLabel htmlFor="manual-name">Recipe name</FormLabel>
                  <Input
                    id="manual-name"
                    value={form.name}
                    onChange={(event) => updateField("name", event.target.value)}
                    placeholder="Yuzu cheesecake"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="manual-title">Record title</FormLabel>
                  <Input
                    id="manual-title"
                    value={form.title}
                    onChange={(event) => updateField("title", event.target.value)}
                    placeholder="Manual recipe: Yuzu cheesecake"
                  />
                  <FormHelperText>
                    Optional label for the saved record.
                  </FormHelperText>
                </FormControl>
              </SimpleGrid>

              <SimpleGrid columns={{ base: 1, md: 3 }} spacing={5} mt={5}>
                <FormControl>
                  <FormLabel htmlFor="manual-yield">Yield</FormLabel>
                  <Input
                    id="manual-yield"
                    value={form.recipeYield}
                    onChange={(event) =>
                      updateField("recipeYield", event.target.value)
                    }
                    placeholder="8 slices"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="manual-cook-time">Cook time</FormLabel>
                  <Input
                    id="manual-cook-time"
                    value={form.cookTime}
                    onChange={(event) =>
                      updateField("cookTime", event.target.value)
                    }
                    placeholder="1 hour 20 minutes"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel htmlFor="manual-cuisine">Cuisine</FormLabel>
                  <Input
                    id="manual-cuisine"
                    value={form.recipeCuisine}
                    onChange={(event) =>
                      updateField("recipeCuisine", event.target.value)
                    }
                    placeholder="Japanese, Dessert"
                  />
                  <FormHelperText>Separate multiple cuisines with commas.</FormHelperText>
                </FormControl>
              </SimpleGrid>
            </Box>

            <Box className="recipeCreatePage__panel">
              <SectionHeader
                eyebrow="Step 2 - ingredients"
                title="Ingredients"
                helper="One ingredient per line."
                aside={
                  <CountPill
                    count={previewCounts.ingredients}
                    noun="item"
                  />
                }
              />
              <SimpleGrid
                columns={{ base: 1, lg: 2 }}
                spacing={5}
                mt={5}
                alignItems="stretch"
              >
                <FormControl isRequired>
                  <FormLabel htmlFor="manual-ingredients">Ingredients</FormLabel>
                  <Textarea
                    id="manual-ingredients"
                    minH="260px"
                    resize="vertical"
                    value={form.ingredients}
                    onChange={(event) =>
                      updateField("ingredients", event.target.value)
                    }
                    placeholder={
                      "1 package graham crackers\n6 tablespoons unsalted butter, melted\n1.5 pounds cream cheese"
                    }
                  />
                </FormControl>

                <PreviewList
                  empty="Detected ingredients will appear here as you type."
                  items={previewItems.ingredients}
                />
              </SimpleGrid>
            </Box>

            <Box className="recipeCreatePage__panel">
              <SectionHeader
                eyebrow="Step 3 - method"
                title="Instructions"
                helper="One step per line. Press Enter to add a step."
                aside={
                  <CountPill
                    count={previewCounts.instructions}
                    noun="step"
                  />
                }
              />
              <SimpleGrid
                columns={{ base: 1, lg: 2 }}
                spacing={5}
                mt={5}
                alignItems="stretch"
              >
                <FormControl isRequired>
                  <FormLabel htmlFor="manual-instructions">
                    Instructions
                  </FormLabel>
                  <Textarea
                    id="manual-instructions"
                    minH="260px"
                    resize="vertical"
                    value={form.instructions}
                    onChange={(event) =>
                      updateField("instructions", event.target.value)
                    }
                    placeholder={
                      "Preheat the oven to 325F.\nMix the crust ingredients.\nBake until just set."
                    }
                  />
                </FormControl>

                <PreviewList
                  empty="Numbered steps will preview here."
                  items={previewItems.instructions}
                  ordered
                />
              </SimpleGrid>
            </Box>

            <StatusBanner error={fieldError} />

            <HStack className="recipeCreatePage__saveBar">
              <Text>Manual recipe draft</Text>
              <Button variant="outline" as={RouterLink} to="/">
                Cancel
              </Button>
              <Button
                type="submit"
                isLoading={isLoading}
                className="recipeCreatePage__submitButton"
              >
                Save manual recipe
                <ArrowIcon />
              </Button>
            </HStack>
          </Stack>
        </form>
      )}
    </Stack>
  );
}
