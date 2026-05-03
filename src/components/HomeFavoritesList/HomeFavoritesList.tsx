import type { RecipeCardItem } from "../../types/recipe";
import { RecipeItemLayout } from "../RecipeItemLayout/RecipeItemLayout";
import "./HomeFavoritesList.scss";

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
        <RecipeItemLayout
          key={item.id}
          item={item}
          variant="favorite-row"
          canToggleFavorite={canToggleFavorite}
        />
      ))}
    </div>
  );
}
