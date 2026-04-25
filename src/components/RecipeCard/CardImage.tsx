import { Icon, IconButton, Tooltip } from "@chakra-ui/react";
import { motion } from "framer-motion";

import "./CardImage.scss";

type CardImageProps = {
  imageUrl: string | null;
  title: string;
  isFavorite: boolean;
  onToggleFavorite?: () => void;
  isTogglingFavorite?: boolean;
};

function HeartIcon({ filled }: { filled: boolean }) {
  return (
    <Icon viewBox="0 0 24 24" boxSize={5}>
      <path
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78Z"
      />
    </Icon>
  );
}

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
        <img className="cardImage__image" src={imageUrl} alt="" loading="lazy" />
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
        <Tooltip label={isFavorite ? "Remove favorite" : "Add favorite"} hasArrow>
          <IconButton
            as={motion.button}
            whileTap={{ scale: 1.3 }}
            type="button"
            aria-label={`${isFavorite ? "Remove" : "Add"} ${title} favorite`}
            icon={<HeartIcon filled={isFavorite} />}
            className="cardImage__favorite"
            color={isFavorite ? "red.500" : "whiteAlpha.900"}
            isLoading={isTogglingFavorite}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onToggleFavorite();
            }}
          />
        </Tooltip>
      ) : null}
    </div>
  );
}
