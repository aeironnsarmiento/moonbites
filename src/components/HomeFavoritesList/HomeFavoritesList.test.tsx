import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RecipeCardItem } from "../../types/recipe";
import { HomeFavoritesList } from "./HomeFavoritesList";

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
  primaryRecipe: null,
};

describe("HomeFavoritesList", () => {
  beforeEach(() => {
    navigate.mockClear();
    mutateAsync.mockClear();
  });

  it("toggles favorite without navigating", () => {
    render(<HomeFavoritesList items={[item]} canToggleFavorite />);

    fireEvent.click(screen.getByRole("button", { name: /remove miso cookies favorite/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("hides favorite button when toggling is not allowed", () => {
    render(<HomeFavoritesList items={[item]} canToggleFavorite={false} />);

    expect(screen.queryByRole("button", { name: /favorite/i })).not.toBeInTheDocument();
  });

  it("navigates on Enter and Space key presses", () => {
    render(<HomeFavoritesList items={[item]} canToggleFavorite={false} />);
    const link = screen.getByRole("link", { name: /miso cookies/i });

    fireEvent.keyDown(link, { key: "Enter" });
    fireEvent.keyDown(link, { key: " " });

    expect(navigate).toHaveBeenNthCalledWith(1, "/recipes/recipe-1");
    expect(navigate).toHaveBeenNthCalledWith(2, "/recipes/recipe-1");
  });
});
