import { ChakraProvider } from "@chakra-ui/react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import { RecipeCreatePage } from "./RecipeCreatePage";

vi.mock("../../hooks/useExtractRecipe", () => ({
  useExtractRecipe: vi.fn(),
}));

vi.mock("../../hooks/useCreateRecipe", () => ({
  useCreateRecipe: () => ({ createRecipe: vi.fn(), error: "", isLoading: false }),
}));

const mockedUseExtractRecipe = vi.mocked(useExtractRecipe);
const BLOCKED_URL = "https://guarded.example.com/recipes/dip/";

type ExtractResult = ReturnType<typeof useExtractRecipe>;

function extractResult(overrides: Partial<ExtractResult> = {}): ExtractResult {
  return {
    isLoading: false,
    error: "",
    status: "",
    phase: "idle",
    isPending: false,
    isInterrupted: false,
    isResuming: false,
    resume: vi.fn(),
    blockedUrl: null,
    submitRecipe: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

function renderPage(state?: { importUrl?: string; siteBlocked?: boolean }) {
  render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter initialEntries={[{ pathname: "/recipes/create", state }]}>
        <RecipeCreatePage />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

function pageTextBox() {
  return screen.queryByLabelText(/Recipe text/);
}

beforeEach(() => {
  mockedUseExtractRecipe.mockReset();
});

afterEach(cleanup);

describe("RecipeCreatePage paste-text import", () => {
  it("hides the paste-text form until a site blocks the import", () => {
    mockedUseExtractRecipe.mockReturnValue(extractResult());
    renderPage({ importUrl: BLOCKED_URL });

    expect(pageTextBox()).toBeNull();
  });

  it("opens the paste-text form at once for a URL the home import found blocked", () => {
    mockedUseExtractRecipe.mockReturnValue(extractResult());
    renderPage({ importUrl: BLOCKED_URL, siteBlocked: true });

    expect(pageTextBox()).not.toBeNull();
    expect(screen.getByRole("link", { name: "the recipe page" })).toHaveAttribute(
      "href",
      BLOCKED_URL,
    );
  });

  it("submits the pasted text with the blocked URL", async () => {
    const submitRecipe = vi.fn().mockResolvedValue(undefined);
    mockedUseExtractRecipe.mockReturnValue(
      extractResult({ blockedUrl: BLOCKED_URL, submitRecipe }),
    );
    renderPage({ importUrl: BLOCKED_URL });

    fireEvent.change(pageTextBox()!, {
      target: { value: "Ingredients\n1 cup spinach\nInstructions\nMix." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import from text" }));

    await waitFor(() =>
      expect(submitRecipe).toHaveBeenCalledWith(
        BLOCKED_URL,
        "Ingredients\n1 cup spinach\nInstructions\nMix.",
      ),
    );
  });

  it("drops the paste-text form once the URL is changed", () => {
    mockedUseExtractRecipe.mockReturnValue(extractResult({ blockedUrl: BLOCKED_URL }));
    renderPage({ importUrl: BLOCKED_URL });

    fireEvent.change(screen.getByLabelText(/^URL/), {
      target: { value: "https://example.com/other" },
    });

    expect(pageTextBox()).toBeNull();
  });

  it("lets a fresh URL import decide again for a URL the home import found blocked", async () => {
    const submitRecipe = vi.fn().mockResolvedValue(undefined);
    mockedUseExtractRecipe.mockReturnValue(extractResult({ submitRecipe }));
    renderPage({ importUrl: BLOCKED_URL, siteBlocked: true });

    fireEvent.submit(screen.getByLabelText(/^URL/).closest("form")!);

    await waitFor(() => expect(submitRecipe).toHaveBeenCalledWith(BLOCKED_URL));
    expect(pageTextBox()).toBeNull();
  });
});
