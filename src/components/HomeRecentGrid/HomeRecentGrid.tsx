import { useNavigate } from "react-router-dom";

import { useToggleFavorite } from "../../hooks/useToggleFavorite";
import type { RecipeCardItem } from "../../types/recipe";
import { FavoriteToggleButton } from "../FavoriteToggleButton/FavoriteToggleButton";
import "./HomeRecentGrid.scss";

type TileProps = {
  item: RecipeCardItem;
  span?: boolean;
  canToggleFavorite: boolean;
};

function RecentTile({ item, span, canToggleFavorite }: TileProps) {
  const navigate = useNavigate();
  const toggleFavorite = useToggleFavorite(item.id);
  const cuisine = item.primaryRecipe?.recipeCuisine?.[0] ?? null;

  return (
    <article
      className={`recentTile${span ? " recentTile--span" : ""}`}
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
      <div className="recentTile__imageWrap">
        {item.imageUrl ? (
          <img
            src={item.imageUrl}
            alt={item.title}
            className="recentTile__image"
          />
        ) : null}
        {canToggleFavorite ? (
          <FavoriteToggleButton
            title={item.title}
            isFavorite={item.isFavorite}
            isTogglingFavorite={toggleFavorite.isPending}
            onToggleFavorite={() => {
              void toggleFavorite.mutateAsync();
            }}
            className="recentTile__heart"
            activeClassName="recentTile__heart--active"
          />
        ) : null}
        {cuisine && (
          <div className="recentTile__cuisinePill">{cuisine}</div>
        )}
      </div>
      <div className="recentTile__body">
        <h3 className="recentTile__title">{item.title}</h3>
        <div className="recentTile__meta">
          <span>Cooked {item.timesCooked}×</span>
          <span>{item.createdAtLabel}</span>
        </div>
      </div>
    </article>
  );
}

type HomeRecentGridProps = {
  items: RecipeCardItem[];
  canToggleFavorite?: boolean;
};

export function HomeRecentGrid({
  items,
  canToggleFavorite = true,
}: HomeRecentGridProps) {
  if (items.length === 0) return null;

  const [first, ...rest] = items;

  return (
    <div className="homeRecentGrid">
      <RecentTile
        item={first}
        span={rest.length > 0}
        canToggleFavorite={canToggleFavorite}
      />
      {rest.map((item) => (
        <RecentTile
          key={item.id}
          item={item}
          canToggleFavorite={canToggleFavorite}
        />
      ))}
    </div>
  );
}
