import type { RecipeCardItem } from "../../types/recipe";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import "./RecipeCardGrid.scss";

type RecipeCardGridProps = {
  items: RecipeCardItem[];
};

export function RecipeCardGrid({ items }: RecipeCardGridProps) {
  return (
    <div className="recipeCardGrid">
      {items.map((item) => (
        <RecipeCard key={item.id} item={item} />
      ))}
    </div>
  );
}
