import { ChakraProvider } from "@chakra-ui/react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import type { RecipeCardItem } from "../../types/recipe";
import { RecipeCard } from "./RecipeCard";

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

function renderCard() {
  const item: RecipeCardItem = {
    id: "recipe-1",
    title: "Miso Cookies",
    pageTitle: "Miso Cookies",
    submittedUrl: "https://example.com/miso-cookies",
    createdAtLabel: "Apr 24, 2026",
    recipeCount: 1,
    timesCooked: 0,
    imageUrl: null,
    isFavorite: false,
    servings: null,
    primaryRecipe: null,
  };

  render(
    <ChakraProvider theme={chakraTheme}>
      <RecipeCard item={item} />
    </ChakraProvider>,
  );
}

describe("RecipeCard", () => {
  beforeEach(() => {
    navigate.mockClear();
    mutateAsync.mockClear();
  });

  it("toggles favorite without navigating", () => {
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: /add miso cookies favorite/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("navigates when the card is clicked", () => {
    renderCard();

    fireEvent.click(screen.getByRole("link", { name: /miso cookies/i }));

    expect(navigate).toHaveBeenCalledWith("/recipes/recipe-1");
  });
});
