import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRecipeListPage } from "../controllers/recipeController";
import { useHighlightedRecipes } from "./useHighlightedRecipes";

vi.mock("../controllers/recipeController", () => ({
  getRecipeListPage: vi.fn(),
}));

const mockedGetRecipeListPage = vi.mocked(getRecipeListPage);

function emptyPage(totalCount: number) {
  return {
    items: [],
    page: 1,
    page_size: 10,
    total_count: totalCount,
    total_pages: 1,
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

describe("useHighlightedRecipes", () => {
  beforeEach(() => {
    mockedGetRecipeListPage.mockReset();
  });

  it("issues exactly 2 list requests (favorites + recent)", async () => {
    mockedGetRecipeListPage.mockImplementation(async (query) =>
      query.favorite ? emptyPage(7) : emptyPage(42),
    );

    const { result } = renderHook(() => useHighlightedRecipes(), {
      wrapper: wrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockedGetRecipeListPage).toHaveBeenCalledTimes(2);
  });

  it("derives totalCount from recent and favoriteCount from favorites", async () => {
    mockedGetRecipeListPage.mockImplementation(async (query) =>
      query.favorite ? emptyPage(7) : emptyPage(42),
    );

    const { result } = renderHook(() => useHighlightedRecipes(), {
      wrapper: wrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data.totalCount).toBe(42);
    expect(result.current.data.favoriteCount).toBe(7);
  });
});
