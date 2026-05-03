import type { RecipeCardItem } from "../../types/recipe";
import { RecipeItemLayout } from "../RecipeItemLayout/RecipeItemLayout";
import "./HomeRecentGrid.scss";

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
      <RecipeItemLayout
        item={first}
        variant="recent-tile"
        span={rest.length > 0}
        canToggleFavorite={canToggleFavorite}
      />
      {rest.map((item) => (
        <RecipeItemLayout
          key={item.id}
          item={item}
          variant="recent-tile"
          canToggleFavorite={canToggleFavorite}
        />
      ))}
    </div>
  );
}
