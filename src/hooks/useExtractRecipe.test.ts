import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  advanceImportJob,
  submitRecipeImport,
} from "../controllers/extractController";
import { useExtractRecipe } from "./useExtractRecipe";

vi.mock("../controllers/extractController", async () => {
  const actual = await vi.importActual<typeof import("../controllers/extractController")>(
    "../controllers/extractController",
  );
  return {
    ...actual,
    submitRecipeImport: vi.fn(),
    advanceImportJob: vi.fn(),
  };
});

const mockedSubmit = vi.mocked(submitRecipeImport);
const mockedAdvance = vi.mocked(advanceImportJob);

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
    mockedAdvance.mockReset();
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

  it("enters pending phase without invalidating queries when the job is still pending", async () => {
    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    mockedSubmit.mockResolvedValue({
      kind: "pending",
      job_id: "job-1",
      state: "queued",
      retry_after_ms: 7000,
    });

    const { result } = renderHook(() => useExtractRecipe(), {
      wrapper: wrapper(queryClient),
    });

    let returned: unknown;
    await act(async () => {
      returned = await result.current.submitRecipe(
        "https://www.instagram.com/reel/DZuzc9PNedT/",
      );
    });

    expect(returned).toBeUndefined();
    expect(result.current.isPending).toBe(true);
    expect(result.current.error).toBe("");
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("polls at the server-directed cadence and invalidates queries on saved success", async () => {
    vi.useFakeTimers();
    try {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
      mockedSubmit.mockResolvedValue({
        kind: "pending",
        job_id: "job-1",
        state: "queued",
        retry_after_ms: 7000,
      });
      mockedAdvance.mockResolvedValue({
        kind: "result",
        result: {
          source_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          final_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          title: "Chia Pudding",
          recipes: [
            { name: "Chia Pudding", ingredients: ["1 cup chia"], instructions: ["Mix."] } as never,
          ],
          database_saved: true,
          database_message: "Recipe saved to your collection.",
          parse_status: "recipe",
        },
      });

      const { result } = renderHook(() => useExtractRecipe(), {
        wrapper: wrapper(queryClient),
      });

      await act(async () => {
        await result.current.submitRecipe(
          "https://www.instagram.com/reel/DZuzc9PNedT/",
        );
      });

      expect(mockedAdvance).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(7000);
      });

      expect(mockedAdvance).toHaveBeenCalledWith("job-1");
      expect(result.current.phase).toBe("done");
      const invalidatedKeys = invalidateSpy.mock.calls.map(
        ([options]) => (options as { queryKey: readonly unknown[] }).queryKey,
      );
      expect(invalidatedKeys).toEqual(
        expect.arrayContaining([["recipe-list"], ["highlighted-recipes"]]),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("reports not_recipe terminal results as a non-saving error", async () => {
    vi.useFakeTimers();
    try {
      const queryClient = createQueryClient();
      mockedSubmit.mockResolvedValue({
        kind: "pending",
        job_id: "job-1",
        state: "queued",
        retry_after_ms: 7000,
      });
      mockedAdvance.mockResolvedValue({
        kind: "result",
        result: {
          source_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          final_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          title: null,
          recipes: [],
          database_saved: false,
          database_message: null,
          parse_status: "not_recipe",
        },
      });

      const { result } = renderHook(() => useExtractRecipe(), {
        wrapper: wrapper(queryClient),
      });

      await act(async () => {
        await result.current.submitRecipe(
          "https://www.instagram.com/reel/DZuzc9PNedT/",
        );
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(7000);
      });

      expect(result.current.phase).toBe("done");
      expect(result.current.error).toContain("No recipe found");
    } finally {
      vi.useRealTimers();
    }
  });

  it("maps a failed terminal envelope to its interaction-state message", async () => {
    vi.useFakeTimers();
    try {
      const queryClient = createQueryClient();
      mockedSubmit.mockResolvedValue({
        kind: "pending",
        job_id: "job-1",
        state: "queued",
        retry_after_ms: 7000,
      });
      mockedAdvance.mockResolvedValue({
        kind: "failed",
        job_id: "job-1",
        error_code: "instagram_unavailable",
        message: "unavailable",
      });

      const { result } = renderHook(() => useExtractRecipe(), {
        wrapper: wrapper(queryClient),
      });

      await act(async () => {
        await result.current.submitRecipe(
          "https://www.instagram.com/reel/DZuzc9PNedT/",
        );
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(7000);
      });

      expect(result.current.phase).toBe("done");
      expect(result.current.error).toContain("Reel unavailable");
    } finally {
      vi.useRealTimers();
    }
  });

  it("pauses on a network failure during polling and resumes on demand", async () => {
    vi.useFakeTimers();
    try {
      const queryClient = createQueryClient();
      mockedSubmit.mockResolvedValue({
        kind: "pending",
        job_id: "job-1",
        state: "queued",
        retry_after_ms: 7000,
      });
      mockedAdvance.mockRejectedValueOnce(new Error("network down"));

      const { result } = renderHook(() => useExtractRecipe(), {
        wrapper: wrapper(queryClient),
      });

      await act(async () => {
        await result.current.submitRecipe(
          "https://www.instagram.com/reel/DZuzc9PNedT/",
        );
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(7000);
      });

      expect(result.current.isInterrupted).toBe(true);
      expect(result.current.error).toContain("Import paused");

      mockedAdvance.mockResolvedValue({
        kind: "result",
        result: {
          source_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          final_url: "https://www.instagram.com/reel/DZuzc9PNedT/",
          title: "Chia Pudding",
          recipes: [
            { name: "Chia Pudding", ingredients: ["1 cup chia"], instructions: ["Mix."] } as never,
          ],
          database_saved: true,
          database_message: "Recipe saved to your collection.",
          parse_status: "recipe",
        },
      });

      await act(async () => {
        await result.current.resume();
      });

      expect(mockedAdvance).toHaveBeenCalledTimes(2);
      expect(result.current.phase).toBe("done");
      expect(result.current.isInterrupted).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops polling once unmounted", async () => {
    vi.useFakeTimers();
    try {
      const queryClient = createQueryClient();
      mockedSubmit.mockResolvedValue({
        kind: "pending",
        job_id: "job-1",
        state: "queued",
        retry_after_ms: 7000,
      });

      const { result, unmount } = renderHook(() => useExtractRecipe(), {
        wrapper: wrapper(queryClient),
      });

      await act(async () => {
        await result.current.submitRecipe(
          "https://www.instagram.com/reel/DZuzc9PNedT/",
        );
      });

      unmount();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(7000);
      });

      expect(mockedAdvance).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
