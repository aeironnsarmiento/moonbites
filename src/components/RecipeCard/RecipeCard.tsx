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
import { useNavigate } from "react-router-dom";

import { useToggleFavorite } from "../../hooks/useToggleFavorite";
import type { RecipeCardItem } from "../../types/recipe";
import { CardImage } from "./CardImage";
import "./RecipeCard.scss";

type RecipeCardProps = {
  item: RecipeCardItem;
  canToggleFavorite?: boolean;
};

export function RecipeCard({ item, canToggleFavorite = true }: RecipeCardProps) {
  const navigate = useNavigate();
  const toggleFavorite = useToggleFavorite(item.id);
  const recipeUrl = `/recipes/${item.id}`;

  const openRecipe = () => {
    navigate(recipeUrl);
  };

  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="recipeCard"
      role="link"
      tabIndex={0}
      onClick={openRecipe}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openRecipe();
        }
      }}
    >
      <Card h="100%" overflow="hidden" className="recipeCard__card">
        <CardImage
          imageUrl={item.imageUrl}
          title={item.title}
          isFavorite={item.isFavorite}
          isTogglingFavorite={toggleFavorite.isPending}
          onToggleFavorite={
            canToggleFavorite
              ? () => {
                  void toggleFavorite.mutateAsync();
                }
              : undefined
          }
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
