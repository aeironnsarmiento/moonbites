import type { FormEvent } from "react";
import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { StatusBanner } from "../StatusBanner/StatusBanner";
import "./HomeHero.scss";

type HomeHeroProps = {
  isAdmin: boolean;
  totalCount: number;
  favoriteCount: number;
  isLoadingCounts: boolean;
  onSubmit: (url: string) => Promise<unknown>;
  isSubmitting: boolean;
  submitError: string;
  submitStatus: string;
};

export function HomeHero({
  isAdmin,
  totalCount,
  favoriteCount,
  isLoadingCounts,
  onSubmit,
  isSubmitting,
  submitError,
  submitStatus,
}: HomeHeroProps) {
  const [url, setUrl] = useState("");
  const [focused, setFocused] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    await onSubmit(trimmed);
    setUrl("");
  };

  return (
    <section className="homeHero">
      {/* Mascot */}
      <div className="homeHero__mascotWrap" aria-hidden="true">
        <div className="homeHero__halo" />
        <div className="homeHero__ring" />
        <div className="homeHero__shadow" />
        <img
          src="/homepagelogo.png"
          alt="Moonbites chef duck"
          className="homeHero__mascot"
        />
      </div>

      {/* Paste URL form — admin only */}
      {isAdmin && (
        <form className="homeHero__form" onSubmit={handleSubmit}>
          <div className={`homeHero__inputRow${focused ? " homeHero__inputRow--focused" : ""}`}>
            <span className="homeHero__linkIcon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/>
                <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>
              </svg>
            </span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Paste a recipe URL"
              className="homeHero__input"
            />
            <button
              type="submit"
              disabled={isSubmitting}
              className="homeHero__submit"
            >
              {isSubmitting ? "Saving…" : "Save recipe"}
            </button>
          </div>
          <RouterLink to="/recipes/create" className="homeHero__altLink">
            Or enter the details yourself →
          </RouterLink>
          {(submitError || submitStatus) && (
            <div className="homeHero__status">
              <StatusBanner error={submitError} status={submitStatus} />
            </div>
          )}
        </form>
      )}

      {/* Stat strip */}
      {!isLoadingCounts && (
        <div className="homeHero__stats">
          <div className="homeHero__stat">
            <span className="homeHero__statLabel">Saved</span>
            <span className="homeHero__statValue">{totalCount}</span>
          </div>
          <span className="homeHero__statDivider" aria-hidden="true" />
          <div className="homeHero__stat">
            <span className="homeHero__statLabel">Favorites</span>
            <span className="homeHero__statValue">{favoriteCount}</span>
          </div>
        </div>
      )}
    </section>
  );
}
