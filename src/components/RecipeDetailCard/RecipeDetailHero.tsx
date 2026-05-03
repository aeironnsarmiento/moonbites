import { CardImage } from "../RecipeCard/CardImage";

type RecipeDetailHeroProps = {
  imageUrl: string | null;
  title: string;
  isFavorite: boolean;
  isTogglingFavorite: boolean;
  onToggleFavorite?: () => void;
};

export function RecipeDetailHero({
  imageUrl,
  title,
  isFavorite,
  isTogglingFavorite,
  onToggleFavorite,
}: RecipeDetailHeroProps) {
  return (
    <div className="recipeDetailCard__hero">
      <CardImage
        imageUrl={imageUrl}
        title={title}
        isFavorite={isFavorite}
        isTogglingFavorite={isTogglingFavorite}
        onToggleFavorite={onToggleFavorite}
      />
    </div>
  );
}
