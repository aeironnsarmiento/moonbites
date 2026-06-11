import {
  Card,
  CardBody,
  HStack,
  Skeleton,
  SkeletonText,
  Stack,
} from "@chakra-ui/react";

const skeletonColors = {
  startColor: "brand.100",
  endColor: "brand.200",
} as const;

export function RecipeCardSkeleton() {
  return (
    <Card h="100%" overflow="hidden">
      <Skeleton sx={{ aspectRatio: "16 / 9" }} {...skeletonColors} />
      <CardBody>
        <Stack spacing={4}>
          <SkeletonText
            noOfLines={2}
            spacing={3}
            skeletonHeight={4}
            {...skeletonColors}
          />
          <HStack justify="space-between" align="center" minH="1.5rem">
            <Skeleton height="20px" width="96px" borderRadius="full" {...skeletonColors} />
            <Skeleton height="14px" width="72px" {...skeletonColors} />
          </HStack>
        </Stack>
      </CardBody>
    </Card>
  );
}
