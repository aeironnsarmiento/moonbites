import { Icon } from "@chakra-ui/react";

import { FavoriteToggleButton } from "../FavoriteToggleButton/FavoriteToggleButton";
import "./CardImage.scss";

type CardImageProps = {
  imageUrl: string | null;
  title: string;
  isFavorite: boolean;
  onToggleFavorite?: () => void;
  isTogglingFavorite?: boolean;
};

export function CardImage({
  imageUrl,
  title,
  isFavorite,
  onToggleFavorite,
  isTogglingFavorite = false,
}: CardImageProps) {
  return (
    <div className="cardImage">
      {imageUrl ? (
        <img className="cardImage__image" src={imageUrl} alt={title} loading="lazy" />
      ) : (
        <div className="cardImage__placeholder" aria-hidden="true">
          <Icon viewBox="0 0 24 24" boxSize={12}>
            <path
              fill="currentColor"
              d="M7 2a1 1 0 0 1 1 1v7a3 3 0 0 1-2 2.83V21a1 1 0 1 1-2 0v-8.17A3 3 0 0 1 2 10V3a1 1 0 0 1 2 0v7a1 1 0 1 0 2 0V3a1 1 0 0 1 1-1Zm8 0c2.21 0 4 2.69 4 6v4a1 1 0 0 1-1 1h-1v8a1 1 0 1 1-2 0V2Z"
            />
          </Icon>
        </div>
      )}

      {onToggleFavorite ? (
        <FavoriteToggleButton
          title={title}
          isFavorite={isFavorite}
          isTogglingFavorite={isTogglingFavorite}
          onToggleFavorite={onToggleFavorite}
          className="cardImage__favorite"
          activeClassName="cardImage__favorite--active"
        />
      ) : null}
    </div>
  );
}
