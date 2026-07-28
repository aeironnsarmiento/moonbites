import { beforeEach, describe, expect, it, vi } from "vitest";

import { getHighlightedRecipes, getRecipeListPage } from "./recipeController";
import {
  fetchHighlightedRecipes,
  fetchRecipeImports,
} from "../services/recipeService";
import type { RecipeImportRecord } from "../types/recipe";

vi.mock("../services/recipeService", () => ({
  fetchHighlightedRecipes: vi.fn(),
  fetchRecipeImports: vi.fn(),
}));

const mockedFetchHighlightedRecipes = vi.mocked(fetchHighlightedRecipes);
const mockedFetchRecipeImports = vi.mocked(fetchRecipeImports);

function record(id: string, url: string): RecipeImportRecord {
  return {
    id,
    submitted_url: url,
    final_url: url,
    page_title: `Recipe ${id}`,
    times_cooked: 2,
    recipes_json: [],
    recipe_overrides_json: {},
    image_url: null,
    is_favorite: false,
    servings: null,
    fallback_video_url: null,
    created_at: "2026-06-01T00:00:00Z",
  };
}

describe("getHighlightedRecipes", () => {
  beforeEach(() => {
    mockedFetchHighlightedRecipes.mockReset();
  });

  it("maps recent and favorites to card items with counts", async () => {
    mockedFetchHighlightedRecipes.mockResolvedValue({
      recent: [record("1", "https://example.com/a")],
      favorites: [record("2", "https://example.com/b")],
      total_count: 12,
      favorite_count: 3,
    });

    const result = await getHighlightedRecipes();

    expect(mockedFetchHighlightedRecipes).toHaveBeenCalledWith(5, 4);
    expect(result.totalCount).toBe(12);
    expect(result.favoriteCount).toBe(3);
    expect(result.recent).toHaveLength(1);
    expect(result.recent[0].id).toBe("1");
    expect(result.favorites[0].id).toBe("2");
  });

  it("throws on an invalid response shape", async () => {
    mockedFetchHighlightedRecipes.mockResolvedValue(
      {} as Awaited<ReturnType<typeof fetchHighlightedRecipes>>,
    );

    await expect(getHighlightedRecipes()).rejects.toThrow(
      "Recipes API returned an invalid highlights response.",
    );
  });
});

describe("getRecipeListPage", () => {
  beforeEach(() => {
    mockedFetchRecipeImports.mockReset();
  });

  it("forwards the search term to the service", async () => {
    mockedFetchRecipeImports.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 10,
      total_count: 0,
      total_pages: 1,
    });

    await getRecipeListPage({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
      favorite: null,
      search: "curry",
    });

    expect(mockedFetchRecipeImports).toHaveBeenCalledWith(
      expect.objectContaining({ search: "curry" }),
    );
  });
});
