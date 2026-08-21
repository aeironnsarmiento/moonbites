import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { VideoEmbedSource, VideoPlatform } from "../../utils/videoEmbed";
import type { YouTubePlayerInstance } from "../../utils/youtubeIframeApi";
import { loadYouTubeIframeApi } from "../../utils/youtubeIframeApi";
import "./VideoEmbed.scss";

const PLATFORM_LABELS: Record<VideoPlatform, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
  instagram: "Instagram",
};

// Meta and TikTok do not treat their direct iframe embeds as a versioned
// API contract, so a generic no-API-error social iframe gets a load timeout
// instead of relying on a player callback the way YouTube's does.
const SOCIAL_LOAD_TIMEOUT_MS = 12000;

type VideoEmbedProps = {
  embed: VideoEmbedSource;
  watchUrl: string;
  thumbnailUrl: string | null;
  title: string;
  isFallback?: boolean;
  overlay?: ReactNode;
};

type PlaybackStatus = "facade" | "playing" | "unavailable";

function YouTubeFrame({
  embed,
  title,
  onUnavailable,
}: {
  embed: VideoEmbedSource;
  title: string;
  onUnavailable: () => void;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let player: YouTubePlayerInstance | null = null;
    let cancelled = false;

    loadYouTubeIframeApi()
      .then((api) => {
        if (cancelled || !frameRef.current) {
          return;
        }

        player = new api.Player(frameRef.current, {
          events: { onError: onUnavailable },
        });
      })
      .catch(() => {
        // Without the API we lose failure detection, but the iframe still
        // plays and the watch link is always available as a way out.
      });

    return () => {
      cancelled = true;
      player?.destroy();
    };
  }, [onUnavailable]);

  // The wrapper is load-bearing: player.destroy() removes the iframe itself,
  // so React must have an outer node of its own left to unmount.
  return (
    <div className="videoEmbed__player">
      <iframe
        ref={frameRef}
        className="videoEmbed__frame"
        src={embed.embedUrl}
        title={title}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}

function SocialFrame({
  embed,
  title,
  retryToken,
  onLoad,
}: {
  embed: VideoEmbedSource;
  title: string;
  retryToken: number;
  onLoad: () => void;
}) {
  return (
    <div className="videoEmbed__player">
      <iframe
        // Remounts the iframe on retry rather than relying on a src change
        // alone, since a stuck embed may not react to that.
        key={retryToken}
        className="videoEmbed__frame"
        src={embed.embedUrl}
        title={title}
        onLoad={onLoad}
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
      />
    </div>
  );
}

function VideoThumbnail({ thumbnailUrl }: { thumbnailUrl: string | null }) {
  if (!thumbnailUrl) {
    return <div className="videoEmbed__placeholder" aria-hidden="true" />;
  }

  return (
    <img
      className="videoEmbed__thumbnail"
      src={thumbnailUrl}
      alt=""
      loading="lazy"
      decoding="async"
    />
  );
}

export function VideoEmbed({
  embed,
  watchUrl,
  thumbnailUrl,
  title,
  isFallback = false,
  overlay,
}: VideoEmbedProps) {
  const [status, setStatus] = useState<PlaybackStatus>("facade");
  const [retryToken, setRetryToken] = useState(0);
  const loadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isGenericSocial = embed.platform !== "youtube";
  const platformLabel = PLATFORM_LABELS[embed.platform];

  const clearLoadTimeout = useCallback(() => {
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => clearLoadTimeout, [clearLoadTimeout]);

  // Stable so mounting the player does not re-run on every parent render.
  const handleUnavailable = useCallback(() => {
    clearLoadTimeout();
    setStatus("unavailable");
  }, [clearLoadTimeout]);

  const handleSocialLoad = useCallback(() => {
    clearLoadTimeout();
  }, [clearLoadTimeout]);

  const play = useCallback(() => {
    setStatus("playing");
    if (isGenericSocial) {
      clearLoadTimeout();
      loadTimeoutRef.current = setTimeout(handleUnavailable, SOCIAL_LOAD_TIMEOUT_MS);
    }
  }, [isGenericSocial, clearLoadTimeout, handleUnavailable]);

  const retry = useCallback(() => {
    setRetryToken((token) => token + 1);
    play();
  }, [play]);

  return (
    <div className="videoEmbed">
      <div className={`videoEmbed__stage videoEmbed__stage--${embed.orientation}`}>
        {status === "playing" ? (
          embed.platform === "youtube" ? (
            <YouTubeFrame embed={embed} title={title} onUnavailable={handleUnavailable} />
          ) : (
            <SocialFrame
              embed={embed}
              title={title}
              retryToken={retryToken}
              onLoad={handleSocialLoad}
            />
          )
        ) : null}

        {status === "facade" ? (
          <button
            type="button"
            className="videoEmbed__facade"
            aria-label={`Play video: ${title}`}
            onClick={play}
          >
            <VideoThumbnail thumbnailUrl={thumbnailUrl} />
            <span className="videoEmbed__play" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </span>
          </button>
        ) : null}

        {status === "unavailable" ? (
          <>
            <VideoThumbnail thumbnailUrl={thumbnailUrl} />
            <div className="videoEmbed__unavailable">
              <p className="videoEmbed__notice" role="status">
                This video can’t be played here. Watch it on {platformLabel} instead.
              </p>
              {isGenericSocial ? (
                <button
                  type="button"
                  className="videoEmbed__retry"
                  onClick={retry}
                >
                  Retry playback
                </button>
              ) : null}
            </div>
          </>
        ) : null}

        {overlay}
      </div>

      <div className="videoEmbed__meta">
        {isFallback ? (
          <span className="videoEmbed__badge">Added video</span>
        ) : null}
        <a
          className="videoEmbed__link"
          href={watchUrl}
          target="_blank"
          rel="noreferrer noopener"
        >
          {isFallback ? `Watch on ${platformLabel}` : "View original"}
        </a>
      </div>
    </div>
  );
}
