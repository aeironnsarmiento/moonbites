import { beforeEach, describe, expect, it, vi } from "vitest";

import { applyTitleCleanup, getTitleCleanupPreview } from "./titleCleanupController";
import {
  postTitleCleanupApply,
  postTitleCleanupPreview,
} from "../services/titleCleanupService";

vi.mock("../services/titleCleanupService", () => ({
  postTitleCleanupPreview: vi.fn(),
  postTitleCleanupApply: vi.fn(),
}));

const mockedPreview = vi.mocked(postTitleCleanupPreview);
const mockedApply = vi.mocked(postTitleCleanupApply);

describe("getTitleCleanupPreview", () => {
  beforeEach(() => {
    mockedPreview.mockReset();
  });

  it("maps the wire shape into camelCase", async () => {
    mockedPreview.mockResolvedValue({
      suggestions: [
        {
          recipe_import_id: "abc",
          current_title: "The BEST Garlic Noodles!!",
          suggested_title: "Garlic Noodles",
          source: "ai",
          reason: null,
        },
      ],
      skipped: [
        {
          recipe_import_id: "edited",
          current_title: "Mom's Adobo",
          reason: "You titled this recipe, so it was left alone.",
        },
      ],
      next_cursor: "2026-01-01T00:00:00Z",
      degraded_reason: null,
    });

    const preview = await getTitleCleanupPreview(null);

    expect(preview.suggestions[0]).toEqual({
      recipeImportId: "abc",
      currentTitle: "The BEST Garlic Noodles!!",
      suggestedTitle: "Garlic Noodles",
      source: "ai",
      reason: null,
    });
    expect(preview.skipped[0].recipeImportId).toBe("edited");
    expect(preview.nextCursor).toBe("2026-01-01T00:00:00Z");
  });

  it("carries a degraded reason through", async () => {
    mockedPreview.mockResolvedValue({
      suggestions: [],
      skipped: [],
      next_cursor: null,
      degraded_reason: "The title generator is busy.",
    });

    const preview = await getTitleCleanupPreview(null);

    expect(preview.degradedReason).toBe("The title generator is busy.");
  });

  it("throws on an invalid response shape", async () => {
    // @ts-expect-error deliberately malformed
    mockedPreview.mockResolvedValue({ suggestions: "nope" });

    await expect(getTitleCleanupPreview(null)).rejects.toThrow(
      "invalid preview response",
    );
  });
});

describe("applyTitleCleanup", () => {
  beforeEach(() => {
    mockedApply.mockReset();
  });

  it("maps the apply results", async () => {
    mockedApply.mockResolvedValue({
      results: [
        { recipe_import_id: "abc", status: "applied", reason: null },
        { recipe_import_id: "edited", status: "skipped", reason: "You titled it." },
      ],
      applied_count: 1,
    });

    const result = await applyTitleCleanup([
      { recipeImportId: "abc", title: "Garlic Noodles" },
    ]);

    expect(result.appliedCount).toBe(1);
    expect(result.results[1]).toEqual({
      recipeImportId: "edited",
      status: "skipped",
      reason: "You titled it.",
    });
  });

  it("throws on an invalid response shape", async () => {
    // @ts-expect-error deliberately malformed
    mockedApply.mockResolvedValue({ results: null });

    await expect(
      applyTitleCleanup([{ recipeImportId: "abc", title: "Garlic Noodles" }]),
    ).rejects.toThrow("invalid apply response");
  });
});
