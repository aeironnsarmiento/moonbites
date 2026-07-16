import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchRecipeImports } from "./recipeService";
import { apiRequest } from "./apiClient";
import type { PaginatedRecipeImportsResponse } from "../types/api";

vi.mock("./apiClient", () => ({
  apiRequest: vi.fn(),
}));

const mockedApiRequest = vi.mocked(apiRequest);

const emptyPage: PaginatedRecipeImportsResponse = {
  items: [],
  page: 1,
  page_size: 10,
  total_count: 0,
  total_pages: 1,
};

function requestedParams(): URLSearchParams {
  const path = mockedApiRequest.mock.calls[0][0];
  return new URLSearchParams(path.split("?")[1]);
}

describe("fetchRecipeImports", () => {
  beforeEach(() => {
    mockedApiRequest.mockReset();
    mockedApiRequest.mockResolvedValue(emptyPage);
  });

  it("includes the search term in the query string when set", async () => {
    await fetchRecipeImports({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
      search: "chicken adobo",
    });

    expect(requestedParams().get("search")).toBe("chicken adobo");
  });

  it("omits search when absent", async () => {
    await fetchRecipeImports({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
    });

    expect(requestedParams().has("search")).toBe(false);
  });

  it("omits search terms under two characters", async () => {
    await fetchRecipeImports({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
      search: " a ",
    });

    expect(requestedParams().has("search")).toBe(false);
  });

  it("truncates search terms longer than 100 characters", async () => {
    await fetchRecipeImports({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
      search: "a".repeat(150),
    });

    expect(requestedParams().get("search")).toBe("a".repeat(100));
  });

  it("trims the search term before sending", async () => {
    await fetchRecipeImports({
      page: 1,
      pageSize: 10,
      sort: "recent",
      cuisine: null,
      search: "  curry  ",
    });

    expect(requestedParams().get("search")).toBe("curry");
  });

  it("keeps the other params when search is present", async () => {
    await fetchRecipeImports({
      page: 2,
      pageSize: 10,
      sort: "times_cooked",
      cuisine: "Italian",
      favorite: true,
      search: "soup",
    });

    const params = requestedParams();
    expect(params.get("page")).toBe("2");
    expect(params.get("page_size")).toBe("10");
    expect(params.get("sort")).toBe("times_cooked");
    expect(params.get("cuisine")).toBe("Italian");
    expect(params.get("favorite")).toBe("true");
    expect(params.get("search")).toBe("soup");
  });
});
