import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { VideoEmbedSource, VideoPlatform } from "../../utils/videoEmbed";
import type { YouTubePlayerInstance } from "../../utils/youtubeIframeApi";
import { loadYouTubeIframeApi } from "../../utils/youtubeIframeApi";
import "./VideoEmbed.scss";

const PLATFORM_LABELS: Record<VideoPlatform, string> = {
  youtube: "YouTube",
  tiktok: "TikTok",
};

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

function TikTokFrame({ embed, title }: { embed: VideoEmbedSource; title: string }) {
  return (
    <div className="videoEmbed__player">
      <iframe
        className="videoEmbed__frame"
        src={embed.embedUrl}
        title={title}
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
  // Stable so mounting the player does not re-run on every parent render.
  const handleUnavailable = useCallback(() => setStatus("unavailable"), []);
  const platformLabel = PLATFORM_LABELS[embed.platform];

  return (
    <div className="videoEmbed">
      <div className={`videoEmbed__stage videoEmbed__stage--${embed.orientation}`}>
        {status === "playing" ? (
          embed.platform === "youtube" ? (
            <YouTubeFrame embed={embed} title={title} onUnavailable={handleUnavailable} />
          ) : (
            <TikTokFrame embed={embed} title={title} />
          )
        ) : null}

        {status === "facade" ? (
          <button
            type="button"
            className="videoEmbed__facade"
            aria-label={`Play video: ${title}`}
            onClick={() => setStatus("playing")}
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
            <p className="videoEmbed__notice" role="status">
              This video can’t be played here. Watch it on {platformLabel} instead.
            </p>
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
