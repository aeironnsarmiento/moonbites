import { ChakraProvider } from "@chakra-ui/react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import type { RecipeListPageData } from "../../controllers/recipeController";
import { useRecipeList } from "../../hooks/useRecipeList";
import { RecipeListPage } from "./RecipeListPage";

vi.mock("../../hooks/useRecipeList", () => ({
  useRecipeList: vi.fn(),
}));

vi.mock("../../hooks/useCuisineFacets", () => ({
  useCuisineFacets: () => ({ facets: [] }),
}));

const setSort = vi.fn();
const setCuisine = vi.fn();
let preferences = { sort: "recent" as const, cuisine: "" };

vi.mock("../../hooks/useRecipeListPreferences", () => ({
  useRecipeListPreferences: () => ({ ...preferences, setSort, setCuisine }),
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({ isAdmin: false }),
}));

const mockedUseRecipeList = vi.mocked(useRecipeList);

type ListResult = ReturnType<typeof useRecipeList>;

function listResult(
  dataOverrides: Partial<RecipeListPageData> = {},
  resultOverrides: Partial<ListResult> = {},
): ListResult {
  return {
    data: {
      items: [],
      page: 1,
      page_size: 10,
      total_count: 0,
      total_pages: 1,
      ...dataOverrides,
    },
    isLoading: false,
    isFetching: false,
    error: "",
    refresh: vi.fn(),
    ...resultOverrides,
  };
}

function LocationSpy() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderPage(initialEntry = "/recipes") {
  return render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <RecipeListPage />
        <LocationSpy />
        <Link to="/recipes">Recipe List nav</Link>
      </MemoryRouter>
    </ChakraProvider>,
  );
}

function lastListCall() {
  return mockedUseRecipeList.mock.calls[
    mockedUseRecipeList.mock.calls.length - 1
  ][0];
}

describe("RecipeListPage", () => {
  beforeEach(() => {
    mockedUseRecipeList.mockReset();
    mockedUseRecipeList.mockReturnValue(listResult());
    setSort.mockReset();
    setCuisine.mockReset();
    preferences = { sort: "recent", cuisine: "" };
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("restores a bookmarked search from the URL", () => {
    renderPage("/recipes?q=adobo");

    expect(screen.getByDisplayValue("adobo")).toBeInTheDocument();
    expect(lastListCall()).toMatchObject({ search: "adobo" });
  });

  it("treats a one-character query as no search", () => {
    vi.useFakeTimers();
    renderPage();

    fireEvent.change(screen.getByPlaceholderText(/search all recipes/i), {
      target: { value: "a" },
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(lastListCall()).toMatchObject({ search: null });

    fireEvent.change(screen.getByPlaceholderText(/search all recipes/i), {
      target: { value: "ad" },
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(lastListCall()).toMatchObject({ search: "ad" });
  });

  it("keeps the favorite flag in the URL and query while searching", () => {
    vi.useFakeTimers();
    renderPage("/recipes?favorite=true");

    fireEvent.change(screen.getByPlaceholderText(/search all recipes/i), {
      target: { value: "soup" },
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    const location = screen.getByTestId("location").textContent ?? "";
    expect(location).toContain("favorite=true");
    expect(location).toContain("q=soup");
    expect(lastListCall()).toMatchObject({ favorite: true, search: "soup" });
  });

  it("resets to page 1 when the debounced search changes", () => {
    vi.useFakeTimers();
    mockedUseRecipeList.mockReturnValue(
      listResult({ total_count: 25, total_pages: 3 }),
    );
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(lastListCall()).toMatchObject({ page: 2 });

    fireEvent.change(screen.getByPlaceholderText(/search all recipes/i), {
      target: { value: "stew" },
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(lastListCall()).toMatchObject({ page: 1, search: "stew" });
  });

  it("shows the active filter restriction alongside search results", () => {
    preferences = { sort: "recent", cuisine: "Italian" };
    mockedUseRecipeList.mockReturnValue(
      listResult({ total_count: 3, total_pages: 1 }),
    );
    renderPage("/recipes?q=soup");

    expect(screen.getByText(/italian cuisine/i)).toBeInTheDocument();
    expect(screen.getByText(/3 matching/i)).toBeInTheDocument();

    fireEvent.click(
      screen.getAllByRole("button", { name: /clear filters/i })[0],
    );

    expect(setCuisine).toHaveBeenCalledWith("");
  });

  it("removes q from the URL and reverts to no search when cleared", () => {
    vi.useFakeTimers();
    renderPage("/recipes?q=soup");

    expect(lastListCall()).toMatchObject({ search: "soup" });

    fireEvent.click(
      screen.getAllByRole("button", { name: /clear search/i })[0],
    );
    act(() => {
      vi.advanceTimersByTime(300);
    });

    const location = screen.getByTestId("location").textContent ?? "";
    expect(location).not.toContain("q=");
    expect(lastListCall()).toMatchObject({ search: null });
  });

  it("resyncs the search input when navigation strips q from the URL", () => {
    vi.useFakeTimers();
    renderPage("/recipes?q=adobo");

    expect(screen.getByDisplayValue("adobo")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: /recipe list nav/i }));
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(screen.queryByDisplayValue("adobo")).not.toBeInTheDocument();
    expect(lastListCall()).toMatchObject({ search: null });
  });

  it("shows a placeholder count in the restriction banner while fetching", () => {
    preferences = { sort: "recent", cuisine: "Italian" };
    mockedUseRecipeList.mockReturnValue(
      listResult({ total_count: 3, total_pages: 1 }, { isFetching: true }),
    );
    renderPage("/recipes?q=soup");

    expect(screen.queryByText(/3 matching/i)).not.toBeInTheDocument();
    expect(screen.getByText(/matching recipes/i)).toBeInTheDocument();
  });

  it("keeps previous results visible with a refresh indicator while fetching", () => {
    mockedUseRecipeList.mockReturnValue(
      listResult({}, { isFetching: true }),
    );
    renderPage("/recipes?q=soup");

    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
