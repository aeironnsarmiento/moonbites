import { ChakraProvider } from "@chakra-ui/react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import type { NormalizedRecipe, RecipeTextOverrides } from "../../types/recipe";
import { RecipeDetailCard } from "./RecipeDetailCard";

const mutateAsync = vi.fn();
const localStorageData = new Map<string, string>();

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: {
    getItem: (key: string) => localStorageData.get(key) ?? null,
    setItem: (key: string, value: string) => {
      localStorageData.set(key, value);
    },
    removeItem: (key: string) => {
      localStorageData.delete(key);
    },
    clear: () => {
      localStorageData.clear();
    },
    key: (index: number) => Array.from(localStorageData.keys())[index] ?? null,
    get length() {
      return localStorageData.size;
    },
  },
});

vi.mock("../../hooks/useToggleFavorite", () => ({
  useToggleFavorite: () => ({
    isPending: false,
    mutateAsync,
  }),
}));

const recipe: NormalizedRecipe = {
  name: "Chocolate Cake",
  recipeYield: "8 servings",
  cookTime: "45 minutes",
  recipeCuisine: ["American"],
  nutrition: {
    calories: "320 kcal",
  },
  ingredients: ["1 cup sugar", "2 cups flour"],
  ingredientSections: [
    {
      title: "Batter",
      items: ["1 cup sugar", "2 cups flour"],
    },
  ],
  instructions: ["Mix ingredients.", "Bake until set."],
};

const overrides: RecipeTextOverrides = {
  ingredients: {
    "0": "1 cup brown sugar",
  },
  instructions: {
    "1": "Bake until center is set.",
  },
};

function renderCard(
  props: Partial<React.ComponentProps<typeof RecipeDetailCard>> = {},
) {
  const defaultProps: React.ComponentProps<typeof RecipeDetailCard> = {
    recipeImportId: "import-1",
    recipe,
    recipeIndex: 3,
    recordTitle: "Saved Chocolate Cake",
    timesCooked: 2,
    imageUrl: "https://example.com/cake.jpg",
    isFavorite: false,
    servings: 8,
    sourceUrl: "https://example.com/cake",
    overrides,
    onAdjustTimesCooked: vi.fn(() => Promise.resolve()),
    onDelete: vi.fn(() => Promise.resolve()),
    onSaveServings: vi.fn(() => Promise.resolve()),
    onSaveMetadata: vi.fn(() => Promise.resolve()),
    onSaveOverrides: vi.fn(() => Promise.resolve()),
    showTimesCookedControls: true,
    canEdit: true,
  };

  const mergedProps = { ...defaultProps, ...props };

  render(
    <ChakraProvider theme={chakraTheme}>
      <RecipeDetailCard {...mergedProps} />
    </ChakraProvider>,
  );

  return mergedProps;
}

describe("RecipeDetailCard", () => {
  beforeEach(() => {
    localStorageData.clear();
    mutateAsync.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders recipe detail content in view mode", () => {
    renderCard();

    expect(screen.getByRole("img", { name: "Chocolate Cake" })).toHaveAttribute(
      "src",
      "https://example.com/cake.jpg",
    );
    expect(
      screen.getByRole("heading", { name: "Chocolate Cake" }),
    ).toBeInTheDocument();
    expect(document.body).toHaveTextContent("8 servings");
    expect(document.body).toHaveTextContent("45 minutes");
    expect(document.body).toHaveTextContent("American");
    expect(screen.getByText("Batter")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("1 cup brown sugar");
    expect(screen.getByText("2 cups flour")).toBeInTheDocument();
    expect(screen.getByText("Mix ingredients.")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("Bake until center is set.");
    expect(document.body).toHaveTextContent("calories: 320 kcal");
  });

  it("toggles favorite when editing is allowed", () => {
    renderCard();

    fireEvent.click(
      screen.getByRole("button", { name: /add chocolate cake favorite/i }),
    );

    expect(mutateAsync).toHaveBeenCalledTimes(1);
  });

  it("updates cooked count controls and disables decrement at zero", () => {
    const onAdjustTimesCooked = vi.fn(() => Promise.resolve());
    renderCard({ onAdjustTimesCooked });

    fireEvent.click(
      screen.getByRole("button", {
        name: /increase cooked count for chocolate cake/i,
      }),
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: /decrease cooked count for chocolate cake/i,
      }),
    );

    expect(onAdjustTimesCooked).toHaveBeenNthCalledWith(1, 1);
    expect(onAdjustTimesCooked).toHaveBeenNthCalledWith(2, -1);

    renderCard({ timesCooked: 0 });

    expect(
      screen.getAllByRole("button", {
        name: /decrease cooked count for chocolate cake/i,
      })[1],
    ).toBeDisabled();
  });

  it("saves metadata and row override edits with recipe index", async () => {
    const onSaveMetadata = vi.fn(() => Promise.resolve());
    const onSaveOverrides = vi.fn(() => Promise.resolve());
    renderCard({ onSaveMetadata, onSaveOverrides });

    fireEvent.click(screen.getByRole("button", { name: /edit chocolate cake/i }));
    fireEvent.change(screen.getByDisplayValue("Saved Chocolate Cake"), {
      target: { value: "Better Chocolate Cake" },
    });
    fireEvent.change(screen.getByDisplayValue("8 servings"), {
      target: { value: "10 servings" },
    });
    fireEvent.change(screen.getByDisplayValue("https://example.com/cake.jpg"), {
      target: { value: "https://example.com/new-cake.jpg" },
    });
    fireEvent.change(screen.getByDisplayValue("https://example.com/cake"), {
      target: { value: "https://example.com/new-cake" },
    });
    fireEvent.change(screen.getByDisplayValue("1 cup brown sugar"), {
      target: { value: "2 cups brown sugar" },
    });
    fireEvent.change(screen.getByDisplayValue("Bake until center is set."), {
      target: { value: "Bake until center is set and cool." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save edits" }));

    await waitFor(() => {
      expect(onSaveMetadata).toHaveBeenCalledWith({
        title: "Better Chocolate Cake",
        recipeYield: "10 servings",
        imageUrl: "https://example.com/new-cake.jpg",
        sourceUrl: "https://example.com/new-cake",
      });
      expect(onSaveOverrides).toHaveBeenCalledWith(3, {
        ingredients: {
          "0": "2 cups brown sugar",
        },
        instructions: {
          "1": "Bake until center is set and cool.",
        },
      });
    });
  });

  it("cancels edit mode without saving", () => {
    const onSaveMetadata = vi.fn(() => Promise.resolve());
    const onSaveOverrides = vi.fn(() => Promise.resolve());
    renderCard({ onSaveMetadata, onSaveOverrides });

    fireEvent.click(screen.getByRole("button", { name: /edit chocolate cake/i }));
    fireEvent.change(screen.getByDisplayValue("Saved Chocolate Cake"), {
      target: { value: "Draft Cake" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByDisplayValue("Draft Cake")).not.toBeInTheDocument();
    expect(onSaveMetadata).not.toHaveBeenCalled();
    expect(onSaveOverrides).not.toHaveBeenCalled();
  });

  it("confirms recipe deletion from the delete dialog", async () => {
    const onDelete = vi.fn(() => Promise.resolve());
    renderCard({ onDelete });

    fireEvent.click(
      screen.getByRole("button", { name: /delete chocolate cake/i }),
    );
    expect(
      screen.getByRole("alertdialog", { name: "Delete saved recipe?" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onDelete).not.toHaveBeenCalled();

    fireEvent.click(
      screen.getByRole("button", { name: /delete chocolate cake/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete recipe" }));

    await waitFor(() => expect(onDelete).toHaveBeenCalledTimes(1));
  });

  it("hides edit and favorite controls when editing is not allowed", () => {
    renderCard({ canEdit: false });

    expect(
      screen.queryByRole("button", { name: /add chocolate cake favorite/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /edit chocolate cake/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /delete chocolate cake/i }),
    ).not.toBeInTheDocument();
  });
});
