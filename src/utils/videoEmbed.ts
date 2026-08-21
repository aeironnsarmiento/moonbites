export type VideoPlatform = "youtube" | "tiktok" | "instagram";

export type VideoOrientation = "landscape" | "portrait";

export type VideoEmbedSource = {
  platform: VideoPlatform;
  videoId: string;
  embedUrl: string;
  orientation: VideoOrientation;
};

export type RecipeVideo = {
  embed: VideoEmbedSource;
  watchUrl: string;
  isFallback: boolean;
};

// Mirrors the host sets the backend extractors dispatch on
// (backend/app/services/youtube/extractor.py, .../tiktok/extractor.py).
const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
]);
const YOUTU_BE_HOSTS = new Set(["youtu.be", "www.youtu.be"]);
const TIKTOK_HOSTS = new Set([
  "tiktok.com",
  "www.tiktok.com",
  "m.tiktok.com",
  "vm.tiktok.com",
  "vt.tiktok.com",
]);
// Mirrors backend/app/services/instagram/urls.py's INSTAGRAM_HOSTS.
const INSTAGRAM_HOSTS = new Set([
  "instagram.com",
  "www.instagram.com",
  "m.instagram.com",
]);

const YOUTUBE_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;
const TIKTOK_ID_PATTERN = /^\d+$/;
const INSTAGRAM_SHORTCODE_PATTERN = /^[A-Za-z0-9_-]+$/;
const YOUTUBE_PATH_PREFIXES = ["shorts", "embed", "live"];

function parseHttpUrl(value: string | null | undefined): URL | null {
  if (!value) {
    return null;
  }

  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    // Not a URL at all — manual:// sentinels and free text land here.
    return null;
  }
}

function pathSegments(url: URL): string[] {
  return url.pathname.split("/").filter(Boolean);
}

function extractYouTubeVideoId(url: URL): string | null {
  const host = url.hostname.toLowerCase();

  if (YOUTU_BE_HOSTS.has(host)) {
    return pathSegments(url)[0] ?? null;
  }

  if (!YOUTUBE_HOSTS.has(host)) {
    return null;
  }

  const queryVideoId = url.searchParams.get("v");
  if (queryVideoId) {
    return queryVideoId;
  }

  const segments = pathSegments(url);
  if (segments.length >= 2 && YOUTUBE_PATH_PREFIXES.includes(segments[0].toLowerCase())) {
    return segments[1];
  }

  return null;
}

function extractTikTokVideoId(url: URL): string | null {
  if (!TIKTOK_HOSTS.has(url.hostname.toLowerCase())) {
    return null;
  }

  // Only the canonical /@handle/video/<id> form carries an embeddable id.
  // Short links (vm.tiktok.com/<code>) and photo posts (/photo/<id>) do not.
  const segments = pathSegments(url);
  const videoIndex = segments.findIndex((segment) => segment.toLowerCase() === "video");
  if (videoIndex === -1) {
    return null;
  }

  return segments[videoIndex + 1] ?? null;
}

function buildYouTubeEmbedUrl(videoId: string): string {
  // autoplay=1 does not violate the never-autoplay rule: this iframe is only
  // ever mounted in response to a click on the facade, so playback still
  // starts from a deliberate user action.
  const params = new URLSearchParams({
    autoplay: "1",
    rel: "0",
    playsinline: "1",
    enablejsapi: "1",
  });

  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${params}`;
}

function buildTikTokEmbedUrl(videoId: string): string {
  return `https://www.tiktok.com/embed/v2/${encodeURIComponent(videoId)}?autoplay=1`;
}

function extractInstagramShortcode(url: URL): string | null {
  if (!INSTAGRAM_HOSTS.has(url.hostname.toLowerCase())) {
    return null;
  }

  // Only the canonical /reel/<shortcode> form is playable here; /p/,
  // /stories/, profile pages, and extra path segments are all rejected,
  // mirroring backend/app/services/instagram/urls.py's strict parser.
  const segments = pathSegments(url);
  if (segments.length !== 2 || segments[0].toLowerCase() !== "reel") {
    return null;
  }

  return segments[1];
}

function buildInstagramEmbedUrl(shortcode: string): string {
  return `https://www.instagram.com/reel/${encodeURIComponent(shortcode)}/embed/`;
}

export function resolveVideoEmbed(value: string | null | undefined): VideoEmbedSource | null {
  const url = parseHttpUrl(value);
  if (!url) {
    return null;
  }

  const youtubeVideoId = extractYouTubeVideoId(url);
  if (youtubeVideoId && YOUTUBE_ID_PATTERN.test(youtubeVideoId)) {
    return {
      platform: "youtube",
      videoId: youtubeVideoId,
      embedUrl: buildYouTubeEmbedUrl(youtubeVideoId),
      orientation: "landscape",
    };
  }

  const tiktokVideoId = extractTikTokVideoId(url);
  if (tiktokVideoId && TIKTOK_ID_PATTERN.test(tiktokVideoId)) {
    return {
      platform: "tiktok",
      videoId: tiktokVideoId,
      embedUrl: buildTikTokEmbedUrl(tiktokVideoId),
      orientation: "portrait",
    };
  }

  const instagramShortcode = extractInstagramShortcode(url);
  if (instagramShortcode && INSTAGRAM_SHORTCODE_PATTERN.test(instagramShortcode)) {
    return {
      platform: "instagram",
      videoId: instagramShortcode,
      embedUrl: buildInstagramEmbedUrl(instagramShortcode),
      orientation: "portrait",
    };
  }

  return null;
}

/**
 * Picks the video to show on recipe detail. The recipe's own source always
 * wins; the admin-added fallback only stands in when that source cannot be
 * embedded, and never replaces the source as provenance.
 */
export function resolveRecipeVideo({
  submittedUrl,
  finalUrl,
  fallbackVideoUrl,
}: {
  submittedUrl: string;
  finalUrl: string;
  fallbackVideoUrl: string | null;
}): RecipeVideo | null {
  // finalUrl is the backstop for TikTok short links, which only resolve to a
  // canonical /@handle/video/<id> once the extractor has followed them.
  const primary = resolveVideoEmbed(submittedUrl) ?? resolveVideoEmbed(finalUrl);
  if (primary) {
    return { embed: primary, watchUrl: submittedUrl, isFallback: false };
  }

  if (fallbackVideoUrl) {
    const fallback = resolveVideoEmbed(fallbackVideoUrl);
    if (fallback) {
      return { embed: fallback, watchUrl: fallbackVideoUrl, isFallback: true };
    }
  }

  return null;
}
