import type { RecipeVideo } from "../../utils/videoEmbed";
import { FavoriteToggleButton } from "../FavoriteToggleButton/FavoriteToggleButton";
import { CardImage } from "../RecipeCard/CardImage";
import { VideoEmbed } from "../VideoEmbed/VideoEmbed";

type RecipeDetailHeroProps = {
  imageUrl: string | null;
  title: string;
  isFavorite: boolean;
  isTogglingFavorite: boolean;
  onToggleFavorite?: () => void;
  video?: RecipeVideo | null;
};

export function RecipeDetailHero({
  imageUrl,
  title,
  isFavorite,
  isTogglingFavorite,
  onToggleFavorite,
  video,
}: RecipeDetailHeroProps) {
  return (
    <div className="recipeDetailCard__hero">
      {video ? (
        <VideoEmbed
          embed={video.embed}
          watchUrl={video.watchUrl}
          thumbnailUrl={imageUrl}
          title={title}
          isFallback={video.isFallback}
          overlay={
            onToggleFavorite ? (
              <FavoriteToggleButton
                title={title}
                isFavorite={isFavorite}
                isTogglingFavorite={isTogglingFavorite}
                onToggleFavorite={onToggleFavorite}
                className="videoEmbed__favorite"
                activeClassName="videoEmbed__favorite--active"
              />
            ) : null
          }
        />
      ) : (
        <CardImage
          imageUrl={imageUrl}
          title={title}
          isFavorite={isFavorite}
          isTogglingFavorite={isTogglingFavorite}
          onToggleFavorite={onToggleFavorite}
        />
      )}
    </div>
  );
}
