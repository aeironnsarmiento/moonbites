import type { RecipeCardItem } from "../../types/recipe";
import { useAuth } from "../../hooks/useAuth";
import { RecipeCard } from "../RecipeCard/RecipeCard";
import "./RecipeCardGrid.scss";

type RecipeCardGridProps = {
  items: RecipeCardItem[];
};

export function RecipeCardGrid({ items }: RecipeCardGridProps) {
  const { isAdmin } = useAuth();

  return (
    <div className="recipeCardGrid">
      {items.map((item) => (
        <RecipeCard key={item.id} item={item} canToggleFavorite={isAdmin} />
      ))}
    </div>
  );
}
