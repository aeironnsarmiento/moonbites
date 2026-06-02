import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createManualRecipe } from "../controllers/recipeController";
import { useCreateRecipe } from "./useCreateRecipe";
import type { HighlightedRecipes } from "./useHighlightedRecipes";
import type { NormalizedRecipe, RecipeImportRecord } from "../types/recipe";

vi.mock("../controllers/recipeController", async () => {
  const actual = await vi.importActual<typeof import("../controllers/recipeController")>(
    "../controllers/recipeController",
  );
  return {
    ...actual,
    createManualRecipe: vi.fn(),
  };
});

const mockedCreate = vi.mocked(createManualRecipe);

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

function recipe(overrides: Partial<NormalizedRecipe> = {}): NormalizedRecipe {
  return {
    name: "New Recipe",
    ingredients: ["one"],
    instructions: ["do it"],
    ...overrides,
  } as NormalizedRecipe;
}

function record(overrides: Partial<RecipeImportRecord> = {}): RecipeImportRecord {
  return {
    id: "new-id",
    submitted_url: "manual://new-id",
    final_url: "manual://new-id",
    page_title: "New Recipe",
    times_cooked: 0,
    recipes_json: [recipe()],
    recipe_overrides_json: {},
    image_url: null,
    is_favorite: false,
    servings: null,
    created_at: new Date("2026-05-06T00:00:00.000Z").toISOString(),
    ...overrides,
  };
}

describe("useCreateRecipe", () => {
  beforeEach(() => {
    mockedCreate.mockReset();
  });

  it("optimistically prepends the new card to homepage recent and bumps totalCount", async () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData<HighlightedRecipes>(["highlighted-recipes"], {
      favorites: [],
      recent: [],
      totalCount: 3,
      favoriteCount: 1,
    });
    mockedCreate.mockResolvedValue(record());

    const { result } = renderHook(() => useCreateRecipe(), {
      wrapper: wrapper(queryClient),
    });

    await act(async () => {
      await result.current.createRecipe({ recipe: recipe() });
    });

    const updated = queryClient.getQueryData<HighlightedRecipes>([
      "highlighted-recipes",
    ]);
    expect(updated?.recent[0]?.id).toBe("new-id");
    expect(updated?.totalCount).toBe(4);
  });

  it("invalidates both recipe-list and highlighted-recipes on success", async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    mockedCreate.mockResolvedValue(record());

    const { result } = renderHook(() => useCreateRecipe(), {
      wrapper: wrapper(queryClient),
    });

    await act(async () => {
      await result.current.createRecipe({ recipe: recipe() });
    });

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      ([options]) => (options as { queryKey: readonly unknown[] }).queryKey,
    );
    expect(invalidatedKeys).toEqual(
      expect.arrayContaining([["recipe-list"], ["highlighted-recipes"]]),
    );
  });
});
