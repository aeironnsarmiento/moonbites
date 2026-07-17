import { beforeEach, describe, expect, it, vi } from "vitest";

import { postTitleCleanupApply, postTitleCleanupPreview } from "./titleCleanupService";
import { apiRequest } from "./apiClient";

vi.mock("./apiClient", () => ({
  apiRequest: vi.fn(),
}));

const mockedApiRequest = vi.mocked(apiRequest);

function requestBody(): unknown {
  const init = mockedApiRequest.mock.calls[0][1];
  return JSON.parse(String(init?.body));
}

describe("postTitleCleanupPreview", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
    mockedApiRequest.mockResolvedValue({
      suggestions: [],
      skipped: [],
      next_cursor: null,
      degraded_reason: null,
    });
  });

  it("posts the cursor and limit", async () => {
    await postTitleCleanupPreview("2026-01-01T00:00:00Z", 5);

    expect(mockedApiRequest.mock.calls[0][0]).toBe("/api/recipes/titles/preview");
    expect(mockedApiRequest.mock.calls[0][1]?.method).toBe("POST");
    expect(requestBody()).toEqual({ cursor: "2026-01-01T00:00:00Z", limit: 5 });
  });

  it("posts a null cursor for the first page", async () => {
    await postTitleCleanupPreview(null, 10);

    expect(requestBody()).toEqual({ cursor: null, limit: 10 });
  });
});

describe("postTitleCleanupApply", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
    mockedApiRequest.mockResolvedValue({ results: [], applied_count: 0 });
  });

  it("maps camelCase payloads onto the snake_case wire shape", async () => {
    await postTitleCleanupApply([
      { recipeImportId: "abc", title: "Garlic Noodles" },
      { recipeImportId: "def", title: "Chicken Adobo" },
    ]);

    expect(mockedApiRequest.mock.calls[0][0]).toBe("/api/recipes/titles/apply");
    expect(requestBody()).toEqual({
      items: [
        { recipe_import_id: "abc", title: "Garlic Noodles" },
        { recipe_import_id: "def", title: "Chicken Adobo" },
      ],
    });
  });
});
