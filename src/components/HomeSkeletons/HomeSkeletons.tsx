import { Skeleton, SkeletonText } from "@chakra-ui/react";

import "../HomeRecentGrid/HomeRecentGrid.scss";
import "../HomeFavoritesList/HomeFavoritesList.scss";
import "../RecipeItemLayout/RecipeItemLayout.scss";

const skeletonColors = {
  startColor: "brand.100",
  endColor: "brand.200",
} as const;

export function HomeRecentGridSkeleton({ tiles = 5 }: { tiles?: number }) {
  return (
    <div className="homeRecentGrid">
      {Array.from({ length: tiles }, (_, index) => (
        <div
          key={index}
          className={`recentTile${index === 0 ? " recentTile--span" : ""}`}
        >
          <Skeleton
            className="recentTile__imageWrap"
            borderRadius="0"
            {...skeletonColors}
          />
          <div className="recentTile__body">
            <SkeletonText
              noOfLines={2}
              spacing={2}
              skeletonHeight={3.5}
              {...skeletonColors}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function HomeFavoritesListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="homeFavoritesList">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="favoriteRow">
          <Skeleton
            className="favoriteRow__thumb"
            borderRadius="14px"
            {...skeletonColors}
          />
          <div className="favoriteRow__info">
            <SkeletonText
              noOfLines={2}
              spacing={2}
              skeletonHeight={3.5}
              {...skeletonColors}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
