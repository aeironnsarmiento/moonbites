import { ChakraProvider } from "@chakra-ui/react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { useTitleCleanup } from "../../hooks/useTitleCleanup";
import { RecipeTitleCleanupPage } from "./RecipeTitleCleanupPage";
import type { TitleCleanupPreview } from "../../types/recipe";

vi.mock("../../hooks/useTitleCleanup", () => ({
  useTitleCleanup: vi.fn(),
}));

const mockedUseTitleCleanup = vi.mocked(useTitleCleanup);

const loadPreview = vi.fn();
const applyTitles = vi.fn();

function preview(overrides: Partial<TitleCleanupPreview> = {}): TitleCleanupPreview {
  return {
    suggestions: [
      {
        recipeImportId: "a",
        currentTitle: "The BEST Garlic Noodles!!",
        suggestedTitle: "Garlic Noodles",
        source: "ai",
        reason: null,
      },
      {
        recipeImportId: "b",
        currentTitle: "INSANE Chicken Adobo you'll LOVE",
        suggestedTitle: "Chicken Adobo",
        source: "ai",
        reason: null,
      },
      {
        recipeImportId: "c",
        currentTitle: "Beef Chili Recipe",
        suggestedTitle: "Beef Chili",
        source: "ai",
        reason: null,
      },
    ],
    skipped: [],
    nextCursor: null,
    degradedReason: null,
    ...overrides,
  };
}

function mockHook(current: TitleCleanupPreview | null) {
  mockedUseTitleCleanup.mockReturnValue({
    preview: current,
    isPreviewing: false,
    previewError: null,
    loadPreview,
    isApplying: false,
    applyError: null,
    applyTitles,
  } as ReturnType<typeof useTitleCleanup>);
}

function renderPage() {
  return render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter>
        <RecipeTitleCleanupPage />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

describe("RecipeTitleCleanupPage", () => {
  beforeEach(() => {
    loadPreview.mockReset();
    applyTitles.mockReset();
    applyTitles.mockResolvedValue({ results: [], appliedCount: 0 });
  });

  it("does not fetch suggestions on mount", () => {
    // Each preview spends Gemini quota, so it must be an explicit action.
    mockHook(null);
    renderPage();

    expect(loadPreview).not.toHaveBeenCalled();
  });

  it("loads suggestions when asked", async () => {
    mockHook(null);
    loadPreview.mockResolvedValue(preview());
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /load suggestions/i }));

    await waitFor(() => expect(loadPreview).toHaveBeenCalledWith(null));
  });

  it("renders a row per suggestion, pre-filled and accepted by default", () => {
    mockHook(preview());
    renderPage();

    expect(screen.getByText(/Currently: The BEST Garlic Noodles!!/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /apply 3 titles/i })).toBeTruthy();
  });

  it("applies exactly the accepted and modified rows", async () => {
    // Covers AE5: reject one, modify another, accept the rest.
    mockHook(preview());
    loadPreview.mockResolvedValue(preview());
    renderPage();

    fireEvent.change(
      screen.getByLabelText("New title for INSANE Chicken Adobo you'll LOVE"),
      { target: { value: "Mom's Chicken Adobo" } },
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Reject" })[2]);

    fireEvent.click(screen.getByRole("button", { name: /apply 2 titles/i }));

    await waitFor(() =>
      expect(applyTitles).toHaveBeenCalledWith([
        { recipeImportId: "a", title: "Garlic Noodles" },
        { recipeImportId: "b", title: "Mom's Chicken Adobo" },
      ]),
    );
  });

  it("disables apply when every row is rejected", () => {
    mockHook(preview({ suggestions: preview().suggestions.slice(0, 1) }));
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    const applyButton = screen.getByRole("button", { name: /apply 0 titles/i });
    expect(applyButton.hasAttribute("disabled")).toBe(true);
  });

  it("lists skipped recipes with their reasons", () => {
    mockHook(
      preview({
        suggestions: [],
        skipped: [
          {
            recipeImportId: "edited",
            currentTitle: "Mom's Adobo",
            reason: "You titled this recipe, so it was left alone.",
          },
        ],
      }),
    );
    renderPage();

    expect(screen.getByText(/Skipped \(1\)/)).toBeTruthy();
    expect(
      screen.getByText(/Mom's Adobo — You titled this recipe, so it was left alone\./),
    ).toBeTruthy();
  });

  it("flags fallback suggestions so the admin knows what they are approving", () => {
    mockHook(
      preview({
        suggestions: [
          {
            recipeImportId: "a",
            currentTitle: "The BEST Garlic Noodles!!",
            suggestedTitle: "Garlic Noodles",
            source: "fallback",
            reason: "The model could not name the dish.",
          },
        ],
      }),
    );
    renderPage();

    expect(screen.getByText(/cleaned source title/i)).toBeTruthy();
  });

  it("does not flag confident AI suggestions", () => {
    mockHook(preview());
    renderPage();

    expect(screen.queryByText(/cleaned source title/i)).toBeNull();
  });

  it("offers the next batch only while a cursor remains", () => {
    mockHook(preview({ nextCursor: "2026-01-01T00:00:00Z" }));
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /load next batch/i }));

    expect(loadPreview).toHaveBeenCalledWith("2026-01-01T00:00:00Z");
  });

  it("hides the next batch button on the last page", () => {
    mockHook(preview({ nextCursor: null }));
    renderPage();

    expect(screen.queryByRole("button", { name: /load next batch/i })).toBeNull();
  });

  it("renders an honest empty state", () => {
    mockHook(preview({ suggestions: [], skipped: [] }));
    renderPage();

    expect(screen.getByText(/No recipes need a new title right now\./)).toBeTruthy();
  });
});
