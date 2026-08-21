import { describe, expect, it } from "vitest";

import { resolveRecipeVideo, resolveVideoEmbed } from "./videoEmbed";

const YOUTUBE_ID = "dQw4w9WgXcQ";

describe("resolveVideoEmbed", () => {
  it("reads a youtube id from the v query param", () => {
    const embed = resolveVideoEmbed(`https://www.youtube.com/watch?v=${YOUTUBE_ID}`);

    expect(embed).toMatchObject({
      platform: "youtube",
      videoId: YOUTUBE_ID,
      orientation: "landscape",
    });
  });

  it.each([
    ["youtu.be short links", `https://youtu.be/${YOUTUBE_ID}`],
    ["shorts", `https://www.youtube.com/shorts/${YOUTUBE_ID}`],
    ["embed paths", `https://www.youtube.com/embed/${YOUTUBE_ID}`],
    ["live paths", `https://m.youtube.com/live/${YOUTUBE_ID}`],
  ])("reads a youtube id from %s", (_label, url) => {
    expect(resolveVideoEmbed(url)?.videoId).toBe(YOUTUBE_ID);
  });

  it("embeds youtube through the no-cookie host with the js api enabled", () => {
    const embed = resolveVideoEmbed(`https://www.youtube.com/watch?v=${YOUTUBE_ID}`);

    expect(embed?.embedUrl).toContain(`https://www.youtube-nocookie.com/embed/${YOUTUBE_ID}`);
    expect(embed?.embedUrl).toContain("enablejsapi=1");
  });

  it("rejects a youtube id that is not the documented 11-character format", () => {
    expect(resolveVideoEmbed("https://www.youtube.com/watch?v=nope")).toBeNull();
  });

  it("reads a tiktok id from the canonical post url", () => {
    const embed = resolveVideoEmbed("https://www.tiktok.com/@chef/video/7301234567890123456");

    expect(embed).toMatchObject({
      platform: "tiktok",
      videoId: "7301234567890123456",
      orientation: "portrait",
      embedUrl: "https://www.tiktok.com/embed/v2/7301234567890123456?autoplay=1",
    });
  });

  it("does not embed tiktok photo posts", () => {
    expect(
      resolveVideoEmbed("https://www.tiktok.com/@chef/photo/7301234567890123456"),
    ).toBeNull();
  });

  it("does not embed an unresolved tiktok short link", () => {
    expect(resolveVideoEmbed("https://vm.tiktok.com/ZM8Abc123/")).toBeNull();
  });

  it("reads an instagram shortcode from the canonical reel url", () => {
    const embed = resolveVideoEmbed("https://www.instagram.com/reel/DZuzc9PNedT/");

    expect(embed).toMatchObject({
      platform: "instagram",
      videoId: "DZuzc9PNedT",
      orientation: "portrait",
      embedUrl: "https://www.instagram.com/reel/DZuzc9PNedT/embed/",
    });
  });

  it("resolves an instagram reel url carrying a query string", () => {
    const embed = resolveVideoEmbed(
      "https://instagram.com/reel/DZuzc9PNedT?igsh=abc123",
    );

    expect(embed).toMatchObject({ platform: "instagram", videoId: "DZuzc9PNedT" });
  });

  it.each([
    ["a photo post", "https://www.instagram.com/p/DZuzc9PNedT/"],
    ["a stories url", "https://www.instagram.com/stories/chef/123/"],
    ["a profile url", "https://www.instagram.com/chef/"],
    [
      "an extra path segment",
      "https://www.instagram.com/reel/DZuzc9PNedT/comments/",
    ],
    ["a lookalike host", "https://instagram.example/reel/DZuzc9PNedT/"],
  ])("does not embed %s", (_label, value) => {
    expect(resolveVideoEmbed(value)).toBeNull();
  });

  it.each([
    ["a blog url", "https://smittenkitchen.com/miso-cookies"],
    ["a manual sentinel", "manual://8f2c"],
    ["free text", "not a url"],
    ["an empty value", ""],
    ["null", null],
  ])("returns null for %s", (_label, value) => {
    expect(resolveVideoEmbed(value)).toBeNull();
  });

  it("ignores non-http schemes that still parse as urls", () => {
    expect(resolveVideoEmbed(`javascript:https://youtu.be/${YOUTUBE_ID}`)).toBeNull();
  });
});

describe("resolveRecipeVideo", () => {
  it("embeds the recipe's own video source", () => {
    const video = resolveRecipeVideo({
      submittedUrl: `https://www.youtube.com/watch?v=${YOUTUBE_ID}`,
      finalUrl: `https://www.youtube.com/watch?v=${YOUTUBE_ID}`,
      fallbackVideoUrl: null,
    });

    expect(video).toMatchObject({ isFallback: false });
    expect(video?.embed.platform).toBe("youtube");
  });

  it("falls back to final_url when the submitted tiktok link is unresolved", () => {
    const video = resolveRecipeVideo({
      submittedUrl: "https://vm.tiktok.com/ZM8Abc123/",
      finalUrl: "https://www.tiktok.com/@chef/video/7301234567890123456",
      fallbackVideoUrl: null,
    });

    expect(video).toMatchObject({
      isFallback: false,
      // Provenance stays on what was submitted, not on the resolved form.
      watchUrl: "https://vm.tiktok.com/ZM8Abc123/",
    });
    expect(video?.embed.videoId).toBe("7301234567890123456");
  });

  it("uses the admin fallback when the source cannot be embedded", () => {
    const video = resolveRecipeVideo({
      submittedUrl: "https://smittenkitchen.com/miso-cookies",
      finalUrl: "https://smittenkitchen.com/miso-cookies",
      fallbackVideoUrl: `https://www.youtube.com/watch?v=${YOUTUBE_ID}`,
    });

    expect(video).toMatchObject({
      isFallback: true,
      watchUrl: `https://www.youtube.com/watch?v=${YOUTUBE_ID}`,
    });
    expect(video?.embed.videoId).toBe(YOUTUBE_ID);
  });

  it("ignores a fallback that is not an embeddable video", () => {
    expect(
      resolveRecipeVideo({
        submittedUrl: "https://smittenkitchen.com/miso-cookies",
        finalUrl: "https://smittenkitchen.com/miso-cookies",
        fallbackVideoUrl: "https://vimeo.com/12345",
      }),
    ).toBeNull();
  });

  it("never lets the fallback override an embeddable source", () => {
    const video = resolveRecipeVideo({
      submittedUrl: "https://www.tiktok.com/@chef/video/7301234567890123456",
      finalUrl: "https://www.tiktok.com/@chef/video/7301234567890123456",
      fallbackVideoUrl: `https://www.youtube.com/watch?v=${YOUTUBE_ID}`,
    });

    expect(video).toMatchObject({ isFallback: false });
    expect(video?.embed.platform).toBe("tiktok");
  });

  it("returns null when neither the source nor the fallback is a video", () => {
    expect(
      resolveRecipeVideo({
        submittedUrl: "https://smittenkitchen.com/miso-cookies",
        finalUrl: "https://smittenkitchen.com/miso-cookies",
        fallbackVideoUrl: null,
      }),
    ).toBeNull();
  });
});
