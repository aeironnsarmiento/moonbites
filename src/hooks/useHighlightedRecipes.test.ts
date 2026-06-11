import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHighlightedRecipes } from "../controllers/recipeController";
import { useHighlightedRecipes } from "./useHighlightedRecipes";

vi.mock("../controllers/recipeController", () => ({
  getHighlightedRecipes: vi.fn(),
}));

const mockedGetHighlightedRecipes = vi.mocked(getHighlightedRecipes);

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
    mockedGetHighlightedRecipes.mockReset();
  });

  it("issues a single highlights request", async () => {
    mockedGetHighlightedRecipes.mockResolvedValue({
      recent: [],
      favorites: [],
      totalCount: 42,
      favoriteCount: 7,
    });

    const { result } = renderHook(() => useHighlightedRecipes(), {
      wrapper: wrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockedGetHighlightedRecipes).toHaveBeenCalledTimes(1);
  });

  it("exposes counts from the highlights response", async () => {
    mockedGetHighlightedRecipes.mockResolvedValue({
      recent: [],
      favorites: [],
      totalCount: 42,
      favoriteCount: 7,
    });

    const { result } = renderHook(() => useHighlightedRecipes(), {
      wrapper: wrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data.totalCount).toBe(42);
    expect(result.current.data.favoriteCount).toBe(7);
  });

  it("surfaces an error message when the request fails", async () => {
    mockedGetHighlightedRecipes.mockRejectedValue(
      new Error("Recipes API returned an invalid highlights response."),
    );

    const { result } = renderHook(() => useHighlightedRecipes(), {
      wrapper: wrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe(
      "Recipes API returned an invalid highlights response.",
    );
  });
});
