export type YouTubePlayerErrorEvent = {
  data: number;
};

export type YouTubePlayerInstance = {
  destroy: () => void;
};

export type YouTubeIframeApi = {
  Player: new (
    element: HTMLElement,
    options: {
      events?: {
        onError?: (event: YouTubePlayerErrorEvent) => void;
      };
    },
  ) => YouTubePlayerInstance;
};

declare global {
  interface Window {
    YT?: YouTubeIframeApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}

const IFRAME_API_SRC = "https://www.youtube.com/iframe_api";

let apiPromise: Promise<YouTubeIframeApi> | null = null;

/**
 * Loads YouTube's iframe player API on demand. Only call this once the viewer
 * has asked to play something — importing it eagerly would put a request on
 * youtube.com for every visitor of every recipe.
 */
export function loadYouTubeIframeApi(): Promise<YouTubeIframeApi> {
  if (window.YT?.Player) {
    return Promise.resolve(window.YT);
  }

  if (apiPromise) {
    return apiPromise;
  }

  const pending = new Promise<YouTubeIframeApi>((resolve, reject) => {
    const previousReady = window.onYouTubeIframeAPIReady;

    window.onYouTubeIframeAPIReady = () => {
      previousReady?.();

      if (window.YT?.Player) {
        resolve(window.YT);
      } else {
        reject(new Error("The YouTube iframe API loaded without a player."));
      }
    };

    const script = document.createElement("script");
    script.src = IFRAME_API_SRC;
    script.async = true;
    script.onerror = () => reject(new Error("Unable to load the YouTube iframe API."));
    document.head.append(script);
  });

  // A blocked or failed script must not poison every later attempt.
  pending.catch(() => {
    apiPromise = null;
  });

  apiPromise = pending;
  return pending;
}
