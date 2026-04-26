import type { MouseEvent } from "react";

import "./FavoriteToggleButton.scss";

type FavoriteToggleButtonProps = {
  title: string;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  isTogglingFavorite?: boolean;
  className?: string;
  activeClassName?: string;
};

export function FavoriteToggleButton({
  title,
  isFavorite,
  onToggleFavorite,
  isTogglingFavorite = false,
  className = "",
  activeClassName = "",
}: FavoriteToggleButtonProps) {
  const classes = [
    "favoriteToggleButton",
    className,
    isFavorite ? "favoriteToggleButton--active" : "",
    isFavorite ? activeClassName : "",
  ]
    .filter(Boolean)
    .join(" ");

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    onToggleFavorite();
  };

  return (
    <button
      type="button"
      aria-label={`${isFavorite ? "Remove" : "Add"} ${title} favorite`}
      aria-busy={isTogglingFavorite}
      className={classes}
      disabled={isTogglingFavorite}
      onClick={handleClick}
    >
      <svg
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill={isFavorite ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78Z" />
      </svg>
    </button>
  );
}
