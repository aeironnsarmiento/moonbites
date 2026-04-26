import { useNavigate } from "react-router-dom";

import { useToggleFavorite } from "../../hooks/useToggleFavorite";
import type { RecipeCardItem } from "../../types/recipe";
import { FavoriteToggleButton } from "../FavoriteToggleButton/FavoriteToggleButton";
import "./HomeFavoritesList.scss";

type FavoriteRowProps = {
  item: RecipeCardItem;
  canToggleFavorite: boolean;
};

function FavoriteRow({ item, canToggleFavorite }: FavoriteRowProps) {
  const navigate = useNavigate();
  const toggleFavorite = useToggleFavorite(item.id);
  const cuisine = item.primaryRecipe?.recipeCuisine?.join(", ") ?? null;

  return (
    <div
      className="favoriteRow"
      onClick={() => navigate(`/recipes/${item.id}`)}
      role="link"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/recipes/${item.id}`);
        }
      }}
    >
      <div className="favoriteRow__thumb">
        {item.imageUrl ? (
          <img
            src={item.imageUrl}
            alt={item.title}
            className="favoriteRow__thumbImage"
          />
        ) : null}
      </div>
      <div className="favoriteRow__info">
        <div className="favoriteRow__title">{item.title}</div>
        <div className="favoriteRow__meta">
          {cuisine ? `${cuisine} · ` : ""}cooked {item.timesCooked}×
        </div>
      </div>
      {canToggleFavorite ? (
        <FavoriteToggleButton
          title={item.title}
          isFavorite={item.isFavorite}
          isTogglingFavorite={toggleFavorite.isPending}
          onToggleFavorite={() => {
            void toggleFavorite.mutateAsync();
          }}
          className="favoriteRow__heart"
          activeClassName="favoriteRow__heart--active"
        />
      ) : null}
    </div>
  );
}

type HomeFavoritesListProps = {
  items: RecipeCardItem[];
  canToggleFavorite?: boolean;
};

export function HomeFavoritesList({
  items,
  canToggleFavorite = true,
}: HomeFavoritesListProps) {
  if (items.length === 0) {
    return (
      <p className="homeFavoritesList__empty">
        No favorites yet. Tap the heart on any recipe.
      </p>
    );
  }

  return (
    <div className="homeFavoritesList">
      {items.map((item) => (
        <FavoriteRow
          key={item.id}
          item={item}
          canToggleFavorite={canToggleFavorite}
        />
      ))}
    </div>
  );
}
