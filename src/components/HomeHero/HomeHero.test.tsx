import { ChakraProvider } from "@chakra-ui/react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { HomeHero } from "./HomeHero";

function renderHero(props: Partial<React.ComponentProps<typeof HomeHero>> = {}) {
  const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue({ database_saved: true });

  render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter>
        <HomeHero
          isAdmin
          totalCount={0}
          favoriteCount={0}
          isLoadingCounts={false}
          onSubmit={onSubmit}
          isSubmitting={false}
          submitError=""
          submitStatus=""
          {...props}
        />
      </MemoryRouter>
    </ChakraProvider>,
  );

  return { onSubmit };
}

function urlInput() {
  return screen.getByPlaceholderText("Paste a recipe URL") as HTMLInputElement;
}

afterEach(cleanup);

describe("HomeHero", () => {
  it("clears the input after a successful import", async () => {
    const onSubmit = vi.fn().mockResolvedValue({ database_saved: true });
    renderHero({ onSubmit });

    const input = urlInput();
    fireEvent.change(input, { target: { value: "https://example.com/recipe" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("https://example.com/recipe"));
    await waitFor(() => expect(input.value).toBe(""));
  });

  it("keeps the pasted URL when the import fails", async () => {
    // A failed import resolves undefined (useExtractRecipe swallows the error).
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderHero({ onSubmit });

    const input = urlInput();
    fireEvent.change(input, { target: { value: "https://example.com/broken" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(input.value).toBe("https://example.com/broken");
  });

  it("offers a manual-creation path carrying the URL once an error is shown", () => {
    renderHero({ submitError: "no Recipe objects were found on that page." });

    const input = urlInput();
    fireEvent.change(input, { target: { value: "https://example.com/broken" } });

    const link = screen.getByRole("link", {
      name: "Create this recipe manually instead →",
    });
    expect(link).toHaveAttribute("href", "/recipes/create");
  });
});
