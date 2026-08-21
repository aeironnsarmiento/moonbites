import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resolveVideoEmbed } from "../../utils/videoEmbed";
import { VideoEmbed } from "./VideoEmbed";

const YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
const TIKTOK_URL = "https://www.tiktok.com/@chef/video/7301234567890123456";
const INSTAGRAM_URL = "https://www.instagram.com/reel/DZuzc9PNedT/";

function embedFor(url: string) {
  const embed = resolveVideoEmbed(url);
  if (!embed) {
    throw new Error(`Expected ${url} to resolve to an embed.`);
  }
  return embed;
}

let capturedOnError: (() => void) | null = null;
let destroyPlayer: ReturnType<typeof vi.fn>;

function stubYouTubeApi() {
  destroyPlayer = vi.fn();
  capturedOnError = null;

  window.YT = {
    // Must be a real function: the component calls it with `new`.
    Player: vi.fn(function (
      _element: HTMLElement,
      options: { events?: { onError?: () => void } },
    ) {
      capturedOnError = options?.events?.onError ?? null;
      return { destroy: destroyPlayer };
    }),
  } as unknown as typeof window.YT;
}

function renderEmbed(props: Partial<React.ComponentProps<typeof VideoEmbed>> = {}) {
  return render(
    <VideoEmbed
      embed={embedFor(YOUTUBE_URL)}
      watchUrl={YOUTUBE_URL}
      thumbnailUrl="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
      title="Miso Cookies"
      {...props}
    />,
  );
}

afterEach(() => {
  cleanup();
  delete window.YT;
  vi.restoreAllMocks();
});

describe("VideoEmbed", () => {
  it("does not touch the video platform until the viewer asks to play", () => {
    renderEmbed();

    expect(document.querySelector("iframe")).toBeNull();
    expect(document.querySelectorAll('script[src*="youtube.com"]')).toHaveLength(0);
    expect(document.querySelector(".videoEmbed__thumbnail")).toHaveAttribute(
      "src",
      "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    );
  });

  it("labels the facade for assistive technology", () => {
    renderEmbed();

    expect(screen.getByRole("button", { name: "Play video: Miso Cookies" })).toBeInTheDocument();
  });

  it("falls back to a placeholder when no thumbnail was stored", () => {
    renderEmbed({ thumbnailUrl: null });

    expect(document.querySelector(".videoEmbed__thumbnail")).toBeNull();
    expect(document.querySelector(".videoEmbed__placeholder")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Play video: Miso Cookies" })).toBeInTheDocument();
  });

  it("always offers a link to the original", () => {
    renderEmbed();

    expect(screen.getByRole("link", { name: "View original" })).toHaveAttribute(
      "href",
      YOUTUBE_URL,
    );
  });

  it("labels an admin-added video distinctly from the recipe source", () => {
    renderEmbed({ isFallback: true });

    expect(screen.getByText("Added video")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Watch on YouTube" })).toHaveAttribute(
      "href",
      YOUTUBE_URL,
    );
  });

  describe("once the viewer plays", () => {
    beforeEach(() => {
      stubYouTubeApi();
    });

    it("loads the youtube player only after the click", () => {
      renderEmbed();
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      const frame = document.querySelector("iframe");
      expect(frame).toHaveAttribute(
        "src",
        expect.stringContaining("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
      );
      expect(screen.queryByRole("button", { name: /^Play video/ })).not.toBeInTheDocument();
    });

    it("loads a portrait tiktok player", () => {
      renderEmbed({ embed: embedFor(TIKTOK_URL), watchUrl: TIKTOK_URL });
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      expect(document.querySelector("iframe")).toHaveAttribute(
        "src",
        "https://www.tiktok.com/embed/v2/7301234567890123456?autoplay=1",
      );
      expect(document.querySelector(".videoEmbed__stage--portrait")).toBeInTheDocument();
    });

    it("loads a portrait instagram reel player", () => {
      renderEmbed({ embed: embedFor(INSTAGRAM_URL), watchUrl: INSTAGRAM_URL });
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      expect(document.querySelector("iframe")).toHaveAttribute(
        "src",
        "https://www.instagram.com/reel/DZuzc9PNedT/embed/",
      );
      expect(document.querySelector(".videoEmbed__stage--portrait")).toBeInTheDocument();
    });

    it("degrades to the thumbnail and link when youtube refuses to embed", async () => {
      renderEmbed();
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      await waitFor(() => expect(capturedOnError).not.toBeNull());
      act(() => capturedOnError?.());

      expect(document.querySelector("iframe")).toBeNull();
      expect(screen.getByRole("status")).toHaveTextContent(
        "This video can’t be played here. Watch it on YouTube instead.",
      );
      expect(document.querySelector(".videoEmbed__thumbnail")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View original" })).toBeInTheDocument();
      expect(destroyPlayer).toHaveBeenCalled();
    });
  });

  describe("generic social iframe load timeout", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("shows the fallback and a Retry playback control after 12 seconds without a load event", () => {
      renderEmbed({ embed: embedFor(INSTAGRAM_URL), watchUrl: INSTAGRAM_URL });
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      expect(document.querySelector("iframe")).not.toBeNull();

      act(() => {
        vi.advanceTimersByTime(12000);
      });

      expect(document.querySelector("iframe")).toBeNull();
      expect(screen.getByRole("status")).toHaveTextContent(
        "This video can’t be played here. Watch it on Instagram instead.",
      );
      expect(
        screen.getByRole("button", { name: "Retry playback" }),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View original" })).toBeInTheDocument();
    });

    it("cancels the timeout once the iframe reports it loaded", () => {
      renderEmbed({ embed: embedFor(TIKTOK_URL), watchUrl: TIKTOK_URL });
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      const frame = document.querySelector("iframe");
      expect(frame).not.toBeNull();
      fireEvent.load(frame as HTMLIFrameElement);

      act(() => {
        vi.advanceTimersByTime(12000);
      });

      expect(document.querySelector("iframe")).not.toBeNull();
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });

    it("remounts a fresh iframe when Retry playback is clicked", () => {
      renderEmbed({ embed: embedFor(INSTAGRAM_URL), watchUrl: INSTAGRAM_URL });
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));
      act(() => {
        vi.advanceTimersByTime(12000);
      });

      fireEvent.click(screen.getByRole("button", { name: "Retry playback" }));

      expect(document.querySelector("iframe")).toHaveAttribute(
        "src",
        "https://www.instagram.com/reel/DZuzc9PNedT/embed/",
      );
      expect(
        screen.queryByRole("button", { name: "Retry playback" }),
      ).not.toBeInTheDocument();
    });

    it("does not offer Retry playback for the youtube unavailable state", async () => {
      vi.useRealTimers();
      stubYouTubeApi();
      renderEmbed();
      fireEvent.click(screen.getByRole("button", { name: "Play video: Miso Cookies" }));

      await waitFor(() => expect(capturedOnError).not.toBeNull());
      act(() => capturedOnError?.());

      expect(
        screen.queryByRole("button", { name: "Retry playback" }),
      ).not.toBeInTheDocument();
    });
  });
});
