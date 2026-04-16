import {
  Badge,
  Card,
  CardBody,
  Heading,
  HStack,
  LinkBox,
  LinkOverlay,
  Stack,
  Text,
} from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";

import type { RecipeCardItem } from "../../types/recipe";
import "./RecipeCard.scss";

type RecipeCardProps = {
  item: RecipeCardItem;
};

export function RecipeCard({ item }: RecipeCardProps) {
  return (
    <LinkBox as="article" className="recipeCard">
      <Card h="100%">
        <CardBody>
          <Stack spacing={4}>
            <HStack justify="space-between" align="start">
              {item.timesCooked > 0 ? (
                <Badge colorScheme="brand">Cooked {item.timesCooked}x</Badge>
              ) : (
                <span />
              )}
              <Text fontSize="sm" color="gray.500">
                {item.createdAtLabel}
              </Text>
            </HStack>

            <Stack spacing={2}>
              <Heading size="md">
                <LinkOverlay as={RouterLink} to={`/recipes/${item.id}`}>
                  {item.title}
                </LinkOverlay>
              </Heading>
            </Stack>

            <Text noOfLines={2} color="gray.500" fontSize="sm">
              {item.pageTitle ?? item.submittedUrl}
            </Text>
          </Stack>
        </CardBody>
      </Card>
    </LinkBox>
  );
}
