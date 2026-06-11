import type { RecipeCardItem } from "../../types/recipe";
import { RecipeItemLayout } from "../RecipeItemLayout/RecipeItemLayout";
import "./RecipeCard.scss";

type RecipeCardProps = {
  item: RecipeCardItem;
  canToggleFavorite?: boolean;
  entranceIndex?: number;
};

export function RecipeCard({
  item,
  canToggleFavorite = true,
  entranceIndex = 0,
}: RecipeCardProps) {
  return (
    <RecipeItemLayout
      item={item}
      variant="recipe-card"
      canToggleFavorite={canToggleFavorite}
      entranceIndex={entranceIndex}
    />
  );
}
