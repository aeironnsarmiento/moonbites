import { ChakraProvider } from "@chakra-ui/react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { HomeHero } from "./HomeHero";

type HeroProps = React.ComponentProps<typeof HomeHero>;

function ControlledHero(props: Partial<HeroProps> & { initialUrl?: string }) {
  const { initialUrl = "", ...rest } = props;
  const [url, setUrl] = useState(initialUrl);

  return (
    <HomeHero
      isAdmin
      totalCount={0}
      favoriteCount={0}
      isLoadingCounts={false}
      onSubmit={vi.fn().mockResolvedValue({ database_saved: true })}
      isSubmitting={false}
      submitError=""
      submitStatus=""
      url={url}
      onUrlChange={setUrl}
      {...rest}
    />
  );
}

function renderHero(props: Partial<HeroProps> & { initialUrl?: string } = {}) {
  const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue({ database_saved: true });

  render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter>
        <ControlledHero {...props} onSubmit={onSubmit} />
      </MemoryRouter>
    </ChakraProvider>,
  );

  return { onSubmit };
}

function urlInput() {
  return screen.getByPlaceholderText(
    "Paste a recipe URL, TikTok, or Instagram Reel",
  ) as HTMLInputElement;
}

afterEach(cleanup);

describe("HomeHero", () => {
  it("submits the pasted URL", async () => {
    const onSubmit = vi.fn().mockResolvedValue({ database_saved: true });
    renderHero({ onSubmit });

    const input = urlInput();
    fireEvent.change(input, { target: { value: "https://example.com/recipe" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("https://example.com/recipe"));
  });

  it("does not clear the pasted URL itself -- clearing is driven by the caller's onSaved", async () => {
    // A pending Instagram job also resolves undefined from submitRecipe, so
    // HomeHero must never assume a resolved call means "done, clear the box";
    // only the caller (via onUrlChange) decides when to clear it.
    const onSubmit = vi.fn().mockResolvedValue({ database_saved: true });
    renderHero({ onSubmit });

    const input = urlInput();
    fireEvent.change(input, { target: { value: "https://example.com/recipe" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(input.value).toBe("https://example.com/recipe");
  });

  it("keeps the pasted URL when the import fails", async () => {
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

  it("disables submit while a job is pending and shows the pending status", () => {
    renderHero({ isPending: true, submitStatus: "Importing Reel…" });

    expect(urlInput().closest("form")?.querySelector("button[type=submit]")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Importing Reel…");
  });

  it("offers a Resume action when the import was interrupted", () => {
    const onResume = vi.fn();
    renderHero({
      isInterrupted: true,
      onResume,
      submitError: "Import paused The connection was interrupted.",
    });

    const resumeButton = screen.getByRole("button", { name: "Resume" });
    fireEvent.click(resumeButton);
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it("disables the Resume action while resuming", () => {
    renderHero({
      isInterrupted: true,
      isResuming: true,
      onResume: vi.fn(),
      submitError: "Import paused The connection was interrupted.",
    });

    expect(screen.getByRole("button", { name: /Resume/ })).toBeDisabled();
  });
});
