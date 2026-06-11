import {
  Badge,
  Card,
  CardBody,
  Heading,
  HStack,
  Stack,
  Text,
} from "@chakra-ui/react";
import { motion } from "framer-motion";

import { useNavigationLink } from "../../hooks/useNavigationLink";
import { useToggleFavorite } from "../../hooks/useToggleFavorite";
import type { RecipeCardItem } from "../../types/recipe";
import { FavoriteToggleButton } from "../FavoriteToggleButton/FavoriteToggleButton";
import { CardImage } from "../RecipeCard/CardImage";
import "./RecipeItemLayout.scss";

type RecipeItemLayoutProps = {
  item: RecipeCardItem;
  variant: "recent-tile" | "favorite-row" | "recipe-card";
  canToggleFavorite?: boolean;
  span?: boolean;
  entranceIndex?: number;
};

const entranceFade = (index: number) => ({
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  transition: { delay: index * 0.06, duration: 0.35, ease: "easeOut" as const },
});

export function RecipeItemLayout({
  item,
  variant,
  canToggleFavorite = true,
  span = false,
  entranceIndex = 0,
}: RecipeItemLayoutProps) {
  const toggleFavorite = useToggleFavorite(item.id);
  const navigationLink = useNavigationLink(`/recipes/${item.id}`);
  const toggleFavoriteButton = () => {
    void toggleFavorite.mutateAsync();
  };

  if (variant === "recent-tile") {
    const cuisine = item.primaryRecipe?.recipeCuisine?.[0] ?? null;

    return (
      <motion.article
        {...entranceFade(entranceIndex)}
        className={`recentTile${span ? " recentTile--span" : ""}`}
        onClick={navigationLink.onClick}
        role="link"
        tabIndex={0}
        onKeyDown={navigationLink.onKeyDown}
      >
        <div className="recentTile__imageWrap">
          {item.imageUrl ? (
            <img
              src={item.imageUrl}
              alt={item.title}
              className="recentTile__image"
              loading="lazy"
              decoding="async"
            />
          ) : null}
          {canToggleFavorite ? (
            <FavoriteToggleButton
              title={item.title}
              isFavorite={item.isFavorite}
              isTogglingFavorite={toggleFavorite.isPending}
              onToggleFavorite={toggleFavoriteButton}
              className="recentTile__heart"
              activeClassName="recentTile__heart--active"
            />
          ) : null}
          {cuisine && (
            <div className="recentTile__cuisinePill">{cuisine}</div>
          )}
        </div>
        <div className="recentTile__body">
          <h3 className="recentTile__title">{item.title}</h3>
          <div className="recentTile__meta">
            <span>Cooked {item.timesCooked}×</span>
            <span>{item.createdAtLabel}</span>
          </div>
        </div>
      </motion.article>
    );
  }

  if (variant === "favorite-row") {
    const cuisine = item.primaryRecipe?.recipeCuisine?.join(", ") ?? null;

    return (
      <motion.div
        {...entranceFade(entranceIndex)}
        className="favoriteRow"
        onClick={navigationLink.onClick}
        role="link"
        tabIndex={0}
        onKeyDown={navigationLink.onKeyDown}
      >
        <div className="favoriteRow__thumb">
          {item.imageUrl ? (
            <img
              src={item.imageUrl}
              alt={item.title}
              className="favoriteRow__thumbImage"
              loading="lazy"
              decoding="async"
            />
          ) : null}
        </div>
        <div className="favoriteRow__info">
          <div className="favoriteRow__title">{item.title}</div>
          <div className="favoriteRow__meta">
            {cuisine ? `${cuisine} · ` : ""}cooked {item.timesCooked}×
          </div>
        </div>
        {canToggleFavorite ? (
          <FavoriteToggleButton
            title={item.title}
            isFavorite={item.isFavorite}
            isTogglingFavorite={toggleFavorite.isPending}
            onToggleFavorite={toggleFavoriteButton}
            className="favoriteRow__heart"
            activeClassName="favoriteRow__heart--active"
          />
        ) : null}
      </motion.div>
    );
  }

  const cardCuisine = item.primaryRecipe?.recipeCuisine?.[0] ?? null;

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, rotate: -0.5, scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 20,
        delay: entranceIndex * 0.06,
      }}
      className="recipeCard"
      role="link"
      tabIndex={0}
      onClick={navigationLink.onClick}
      onKeyDown={navigationLink.onKeyDown}
    >
      <Card h="100%" overflow="hidden" className="recipeCard__card">
        <CardImage
          imageUrl={item.imageUrl}
          title={item.title}
          isFavorite={item.isFavorite}
          isTogglingFavorite={toggleFavorite.isPending}
          onToggleFavorite={canToggleFavorite ? toggleFavoriteButton : undefined}
        />
        <CardBody>
          <Stack spacing={4}>
            <Stack spacing={2}>
              <Heading size="md" noOfLines={2}>
                {item.title}
              </Heading>
            </Stack>

            <HStack justify="space-between" align="center" minH="1.5rem">
              <HStack spacing={2}>
                {item.timesCooked > 0 ? (
                  <Badge
                    bg="brand.500"
                    color="white"
                    borderRadius="full"
                    px={3}
                    py={0.5}
                  >
                    Cooked {item.timesCooked}x
                  </Badge>
                ) : null}
                {cardCuisine ? (
                  <Badge
                    bg="brand.100"
                    color="brand.700"
                    borderRadius="full"
                    px={3}
                    py={0.5}
                  >
                    {cardCuisine}
                  </Badge>
                ) : null}
                {item.timesCooked === 0 && !cardCuisine ? <span /> : null}
              </HStack>
              <Text fontSize="sm" color="gray.600">
                {item.createdAtLabel}
              </Text>
            </HStack>
          </Stack>
        </CardBody>
      </Card>
    </motion.article>
  );
}
