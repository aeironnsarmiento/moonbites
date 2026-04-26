import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { toggleFavorite } from "../controllers/recipeController";
import type { HighlightedRecipes } from "./useHighlightedRecipes";
import { toggleHighlightedRecipesData, useToggleFavorite } from "./useToggleFavorite";
import type { RecipeCardItem, RecipeImportRecord } from "../types/recipe";

vi.mock("../controllers/recipeController", () => ({
  toggleFavorite: vi.fn(),
}));

const mockedToggleFavorite = vi.mocked(toggleFavorite);

function recipe(overrides: Partial<RecipeCardItem>): RecipeCardItem {
  return {
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
    ...overrides,
  };
}

function highlighted(overrides: Partial<HighlightedRecipes> = {}): HighlightedRecipes {
  return {
    favorites: [],
    mostCooked: [],
    recent: [],
    totalCount: 0,
    favoriteCount: 0,
    ...overrides,
  };
}

function record(overrides: Partial<RecipeImportRecord> = {}): RecipeImportRecord {
  return {
    id: "recipe-1",
    submitted_url: "https://example.com/miso-cookies",
    final_url: "https://example.com/miso-cookies",
    page_title: "Miso Cookies",
    recipe_count: 1,
    times_cooked: 0,
    recipes_json: [],
    recipe_overrides_json: {},
    image_url: null,
    is_favorite: false,
    servings: null,
    created_at: new Date("2026-04-24T00:00:00.000Z").toISOString(),
    ...overrides,
  };
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function wrapper(queryClient: QueryClient) {
  return function TestWrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("toggleHighlightedRecipesData", () => {
  it("favorites a visible recent recipe and adds it to home favorites", () => {
    const visibleRecipe = recipe({ id: "recipe-1", isFavorite: false });
    const result = toggleHighlightedRecipesData(
      highlighted({ recent: [visibleRecipe], favoriteCount: 0 }),
      "recipe-1",
    );

    expect(result?.recent[0].isFavorite).toBe(true);
    expect(result?.favorites).toEqual([{ ...visibleRecipe, isFavorite: true }]);
    expect(result?.favoriteCount).toBe(1);
  });

  it("unfavorites a home favorite and removes it from home favorites", () => {
    const visibleRecipe = recipe({ id: "recipe-1", isFavorite: true });
    const result = toggleHighlightedRecipesData(
      highlighted({
        favorites: [visibleRecipe],
        recent: [visibleRecipe],
        favoriteCount: 1,
      }),
      "recipe-1",
    );

    expect(result?.recent[0].isFavorite).toBe(false);
    expect(result?.favorites).toEqual([]);
    expect(result?.favoriteCount).toBe(0);
  });
});

describe("useToggleFavorite", () => {
  beforeEach(() => {
    mockedToggleFavorite.mockReset();
  });

  it("reconciles list and detail caches from the server favorite value", async () => {
    const queryClient = createQueryClient();
    const visibleRecipe = recipe({ id: "recipe-1", isFavorite: false });
    const listKey = ["recipe-list", 1, 10, "recent", null, null] as const;
    queryClient.setQueryData(listKey, {
      items: [visibleRecipe],
      page: 1,
      page_size: 10,
      total_count: 1,
      total_pages: 1,
    });
    queryClient.setQueryData(["recipe-detail", "recipe-1"], record({ is_favorite: false }));
    mockedToggleFavorite.mockResolvedValue(record({ is_favorite: false }));

    const { result } = renderHook(() => useToggleFavorite("recipe-1"), {
      wrapper: wrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(queryClient.getQueryData<{ items: RecipeCardItem[] }>(listKey)?.items[0].isFavorite).toBe(false);
    expect(
      queryClient.getQueryData<RecipeImportRecord>(["recipe-detail", "recipe-1"])
        ?.is_favorite,
    ).toBe(false);
  });

  it("restores optimistic cache changes when favorite update fails", async () => {
    const queryClient = createQueryClient();
    const visibleRecipe = recipe({ id: "recipe-1", isFavorite: false });
    const listKey = ["recipe-list", 1, 10, "recent", null, null] as const;
    queryClient.setQueryData(listKey, {
      items: [visibleRecipe],
      page: 1,
      page_size: 10,
      total_count: 1,
      total_pages: 1,
    });
    queryClient.setQueryData(["recipe-detail", "recipe-1"], record({ is_favorite: false }));
    mockedToggleFavorite.mockRejectedValue(new Error("denied"));

    const { result } = renderHook(() => useToggleFavorite("recipe-1"), {
      wrapper: wrapper(queryClient),
    });

    await expect(result.current.mutateAsync()).rejects.toThrow("denied");

    expect(queryClient.getQueryData<{ items: RecipeCardItem[] }>(listKey)?.items[0].isFavorite).toBe(false);
    expect(
      queryClient.getQueryData<RecipeImportRecord>(["recipe-detail", "recipe-1"])
        ?.is_favorite,
    ).toBe(false);
  });
});
