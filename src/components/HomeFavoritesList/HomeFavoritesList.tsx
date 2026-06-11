import type { RecipeCardItem } from "../../types/recipe";
import { BowlDoodle } from "../Icons";
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
      <div className="homeFavoritesList__empty">
        <BowlDoodle />
        <p>No favorites yet. Tap the heart on any recipe to pin it here.</p>
      </div>
    );
  }

  return (
    <div className="homeFavoritesList">
      {items.map((item, index) => (
        <RecipeItemLayout
          key={item.id}
          item={item}
          variant="favorite-row"
          canToggleFavorite={canToggleFavorite}
          entranceIndex={index}
        />
      ))}
    </div>
  );
}
