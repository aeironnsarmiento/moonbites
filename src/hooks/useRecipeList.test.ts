import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getRecipeListPage,
  type RecipeListPageData,
} from "../controllers/recipeController";
import { useRecipeList } from "./useRecipeList";

vi.mock("../controllers/recipeController", () => ({
  getRecipeListPage: vi.fn(),
}));

const mockedGetRecipeListPage = vi.mocked(getRecipeListPage);

function pageData(overrides: Partial<RecipeListPageData> = {}): RecipeListPageData {
  return {
    items: [],
    page: 1,
    page_size: 10,
    total_count: 0,
    total_pages: 1,
    ...overrides,
  };
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
}

function wrapper(queryClient: QueryClient) {
  return function TestWrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

const baseParams = {
  page: 1,
  pageSize: 10,
  sort: "recent" as const,
  cuisine: null,
  favorite: null,
};

describe("useRecipeList", () => {
  beforeEach(() => {
    mockedGetRecipeListPage.mockReset();
    mockedGetRecipeListPage.mockResolvedValue(pageData());
  });

  it("keeps the query key shape unchanged when no search is set", async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useRecipeList(baseParams), {
      wrapper: wrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const keys = queryClient.getQueryCache().getAll().map((entry) => entry.queryKey);
    expect(keys).toContainEqual(["recipe-list", 1, 10, "recent", null, null]);
  });

  it("includes the normalized search term in the query key", async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(
      () => useRecipeList({ ...baseParams, search: "  curry  " }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const keys = queryClient.getQueryCache().getAll().map((entry) => entry.queryKey);
    expect(keys).toContainEqual([
      "recipe-list",
      1,
      10,
      "recent",
      null,
      null,
      "curry",
    ]);
    expect(mockedGetRecipeListPage).toHaveBeenCalledWith(
      expect.objectContaining({ search: "curry" }),
    );
  });

  it("treats an under-two-character search as no search", async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(
      () => useRecipeList({ ...baseParams, search: "a" }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const keys = queryClient.getQueryCache().getAll().map((entry) => entry.queryKey);
    expect(keys).toContainEqual(["recipe-list", 1, 10, "recent", null, null]);
    expect(mockedGetRecipeListPage).toHaveBeenCalledWith(
      expect.objectContaining({ search: null }),
    );
  });

  it("includes the search term in the next-page prefetch key", async () => {
    mockedGetRecipeListPage.mockResolvedValue(
      pageData({ total_count: 20, total_pages: 2 }),
    );
    const queryClient = createQueryClient();
    const { result } = renderHook(
      () => useRecipeList({ ...baseParams, search: "curry" }),
      { wrapper: wrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await waitFor(() => {
      const keys = queryClient
        .getQueryCache()
        .getAll()
        .map((entry) => entry.queryKey);
      expect(keys).toContainEqual([
        "recipe-list",
        2,
        10,
        "recent",
        null,
        null,
        "curry",
      ]);
    });
    expect(mockedGetRecipeListPage).toHaveBeenCalledWith(
      expect.objectContaining({ page: 2, search: "curry" }),
    );
  });

  it("refetches under a fresh key when the search term changes", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ search }) => useRecipeList({ ...baseParams, search }),
      { wrapper: wrapper(queryClient), initialProps: { search: "curry" } },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    rerender({ search: "adobo" });

    await waitFor(() =>
      expect(mockedGetRecipeListPage).toHaveBeenCalledWith(
        expect.objectContaining({ search: "adobo" }),
      ),
    );
  });

  it("keeps previous results visible while a new search resolves", async () => {
    const populated = pageData({ total_count: 1 });
    mockedGetRecipeListPage.mockResolvedValueOnce(populated);

    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ search }) => useRecipeList({ ...baseParams, search }),
      { wrapper: wrapper(queryClient), initialProps: { search: "curry" } },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    mockedGetRecipeListPage.mockImplementation(() => new Promise(() => {}));
    rerender({ search: "adobo" });

    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toEqual(populated);
  });
});
