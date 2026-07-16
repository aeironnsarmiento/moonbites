import { ChakraProvider } from "@chakra-ui/react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import type { RecipeListProps } from "./RecipeList";
import { RecipeList } from "./RecipeList";

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ isAdmin: false }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("../../hooks/useToggleFavorite", () => ({
  useToggleFavorite: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

function renderList(overrides: Partial<RecipeListProps> = {}): RecipeListProps {
  const props: RecipeListProps = {
    items: [],
    searchTerm: "",
    onSearchTermChange: vi.fn(),
    sort: "recent",
    onSortChange: vi.fn(),
    cuisine: "",
    onCuisineChange: vi.fn(),
    cuisineFacets: [],
    isLoading: false,
    error: "",
    ...overrides,
  };

  render(
    <ChakraProvider theme={chakraTheme}>
      <RecipeList {...props} />
    </ChakraProvider>,
  );

  return props;
}

describe("RecipeList", () => {
  it("labels the search input as collection-wide", () => {
    renderList();

    expect(
      screen.getByPlaceholderText(/search all recipes/i),
    ).toBeInTheDocument();
  });

  it("hides the clear-search control when there is no search term", () => {
    renderList();

    expect(
      screen.queryByRole("button", { name: /clear search/i }),
    ).not.toBeInTheDocument();
  });

  it("clears the search from every clear-search control", () => {
    const props = renderList({ searchTerm: "curry" });

    const clearButtons = screen.getAllByRole("button", {
      name: /clear search/i,
    });
    expect(clearButtons.length).toBeGreaterThanOrEqual(1);

    clearButtons.forEach((button) => fireEvent.click(button));

    expect(props.onSearchTermChange).toHaveBeenCalledWith("");
  });

  it("shows a non-destructive refresh indicator while results update", () => {
    renderList({ isRefreshing: true });

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("keeps previous results on screen alongside a search error", () => {
    renderList({
      searchTerm: "curry",
      error: "Supabase read failed: schema not applied",
      items: [
        {
          id: "recipe-1",
          title: "Miso Cookies",
          pageTitle: "Miso Cookies",
          submittedUrl: "https://example.com/miso-cookies",
          createdAtLabel: "Apr 24, 2026",
          timesCooked: 0,
          imageUrl: null,
          isFavorite: false,
          servings: null,
          primaryRecipe: null,
        },
      ],
    });

    expect(screen.getByText(/schema not applied/i)).toBeInTheDocument();
    expect(screen.getByText("Miso Cookies")).toBeInTheDocument();
    expect(screen.queryByText(/no recipes match/i)).not.toBeInTheDocument();
  });

  it("offers clearing filters from the no-results state", () => {
    const props = renderList({
      searchTerm: "curry",
      onClearFilters: vi.fn(),
    });

    expect(screen.getByText(/no recipes match/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));

    expect(props.onClearFilters).toHaveBeenCalledTimes(1);
  });
});
