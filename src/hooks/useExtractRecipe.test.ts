import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { submitRecipeImport } from "../controllers/extractController";
import { useExtractRecipe } from "./useExtractRecipe";

vi.mock("../controllers/extractController", async () => {
  const actual = await vi.importActual<typeof import("../controllers/extractController")>(
    "../controllers/extractController",
  );
  return {
    ...actual,
    submitRecipeImport: vi.fn(),
  };
});

const mockedSubmit = vi.mocked(submitRecipeImport);

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

describe("useExtractRecipe", () => {
  beforeEach(() => {
    mockedSubmit.mockReset();
  });

  it("invalidates both recipe-list and highlighted-recipes after a successful save", async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    mockedSubmit.mockResolvedValue({
      source_url: "https://example.com",
      final_url: "https://example.com",
      title: "Soup",
      recipes: [
        {
          name: "Soup",
          ingredients: ["water"],
          instructions: ["boil"],
        } as never,
      ],
      database_saved: true,
      database_message: "Recipe saved to your collection.",
    });

    const { result } = renderHook(() => useExtractRecipe(), {
      wrapper: wrapper(queryClient),
    });

    await act(async () => {
      await result.current.submitRecipe("https://example.com");
    });

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      ([options]) => (options as { queryKey: readonly unknown[] }).queryKey,
    );
    expect(invalidatedKeys).toEqual(
      expect.arrayContaining([["recipe-list"], ["highlighted-recipes"]]),
    );
  });

  it("does not invalidate when database_saved is false", async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    mockedSubmit.mockResolvedValue({
      source_url: "https://example.com",
      final_url: "https://example.com",
      title: null,
      recipes: [],
      database_saved: false,
      database_message: null,
    });

    const { result } = renderHook(() => useExtractRecipe(), {
      wrapper: wrapper(queryClient),
    });

    await act(async () => {
      await result.current.submitRecipe("https://example.com");
    });

    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
