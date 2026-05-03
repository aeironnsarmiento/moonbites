import type { RecipeCardItem } from "../../types/recipe";
import { RecipeItemLayout } from "../RecipeItemLayout/RecipeItemLayout";
import "./RecipeCard.scss";

type RecipeCardProps = {
  item: RecipeCardItem;
  canToggleFavorite?: boolean;
};

export function RecipeCard({ item, canToggleFavorite = true }: RecipeCardProps) {
  return (
    <RecipeItemLayout
      item={item}
      variant="recipe-card"
      canToggleFavorite={canToggleFavorite}
    />
  );
}
