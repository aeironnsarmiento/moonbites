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
};

export function RecipeItemLayout({
  item,
  variant,
  canToggleFavorite = true,
  span = false,
}: RecipeItemLayoutProps) {
  const toggleFavorite = useToggleFavorite(item.id);
  const navigationLink = useNavigationLink(`/recipes/${item.id}`);
  const toggleFavoriteButton = () => {
    void toggleFavorite.mutateAsync();
  };

  if (variant === "recent-tile") {
    const cuisine = item.primaryRecipe?.recipeCuisine?.[0] ?? null;

    return (
      <article
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
      </article>
    );
  }

  if (variant === "favorite-row") {
    const cuisine = item.primaryRecipe?.recipeCuisine?.join(", ") ?? null;

    return (
      <div
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
      </div>
    );
  }

  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
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
              {item.timesCooked > 0 ? (
                <Badge colorScheme="brand">Cooked {item.timesCooked}x</Badge>
              ) : (
                <span />
              )}
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
