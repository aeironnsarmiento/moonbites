import { ChakraProvider } from "@chakra-ui/react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import type { RecipeCardItem } from "../../types/recipe";
import { RecipeItemLayout } from "./RecipeItemLayout";

const navigate = vi.fn();
const mutateAsync = vi.fn();

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigate,
}));

vi.mock("../../hooks/useToggleFavorite", () => ({
  useToggleFavorite: () => ({
    isPending: false,
    mutateAsync,
  }),
}));

const item: RecipeCardItem = {
  id: "recipe-1",
  title: "Miso Cookies",
  pageTitle: "Miso Cookies",
  submittedUrl: "https://example.com/miso-cookies",
  createdAtLabel: "Apr 24, 2026",
  timesCooked: 2,
  imageUrl: null,
  isFavorite: true,
  servings: null,
  primaryRecipe: {
    name: "Miso Cookies",
    recipeYield: null,
    cookTime: null,
    recipeCuisine: ["Japanese", "Dessert"],
    nutrition: null,
    ingredients: [],
    ingredientSections: null,
    instructions: [],
  },
};

function renderLayout(
  props: Partial<React.ComponentProps<typeof RecipeItemLayout>> = {},
) {
  render(
    <ChakraProvider theme={chakraTheme}>
      <RecipeItemLayout
        item={item}
        variant="recent-tile"
        canToggleFavorite
        {...props}
      />
    </ChakraProvider>,
  );
}

describe("RecipeItemLayout", () => {
  beforeEach(() => {
    navigate.mockClear();
    mutateAsync.mockClear();
  });

  it.each([
    ["recent-tile" as const],
    ["favorite-row" as const],
    ["recipe-card" as const],
  ])("navigates on click for %s", (variant) => {
    renderLayout({ variant });

    fireEvent.click(screen.getByRole("link", { name: /miso cookies/i }));

    expect(navigate).toHaveBeenCalledWith("/recipes/recipe-1");
  });

  it("navigates on Enter and Space key presses", () => {
    renderLayout({ variant: "favorite-row" });
    const link = screen.getByRole("link", { name: /miso cookies/i });

    fireEvent.keyDown(link, { key: "Enter" });
    fireEvent.keyDown(link, { key: " " });

    expect(navigate).toHaveBeenNthCalledWith(1, "/recipes/recipe-1");
    expect(navigate).toHaveBeenNthCalledWith(2, "/recipes/recipe-1");
  });

  it("toggles favorite without navigating", () => {
    renderLayout({ variant: "recipe-card" });

    fireEvent.click(screen.getByRole("button", { name: /remove miso cookies favorite/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("hides favorite button when toggling is not allowed", () => {
    renderLayout({ canToggleFavorite: false });

    expect(screen.queryByRole("button", { name: /favorite/i })).not.toBeInTheDocument();
  });

  it("renders variant-specific metadata", () => {
    renderLayout({ variant: "recent-tile", span: true });
    expect(document.body).toHaveTextContent("Japanese");
    expect(document.querySelector(".recentTile--span")).toBeInTheDocument();

    renderLayout({ variant: "favorite-row" });
    expect(document.body).toHaveTextContent("Japanese, Dessert · cooked 2×");

    renderLayout({ variant: "recipe-card" });
    expect(document.body).toHaveTextContent("Apr 24, 2026");
    expect(document.body).toHaveTextContent("Cooked 2x");
  });
});
