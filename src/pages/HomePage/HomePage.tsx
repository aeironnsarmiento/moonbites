import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { HomeFavoritesList } from "../../components/HomeFavoritesList/HomeFavoritesList";
import { HomeHero } from "../../components/HomeHero/HomeHero";
import { HomeRecentGrid } from "../../components/HomeRecentGrid/HomeRecentGrid";
import { HomeSectionHeader } from "../../components/HomeSectionHeader/HomeSectionHeader";
import {
  HomeFavoritesListSkeleton,
  HomeRecentGridSkeleton,
} from "../../components/HomeSkeletons/HomeSkeletons";
import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useAuth } from "../../hooks/useAuth";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import { useHighlightedRecipes } from "../../hooks/useHighlightedRecipes";
import "./HomePage.scss";

export function HomePage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { data, error, isLoading } = useHighlightedRecipes();
  const [url, setUrl] = useState("");
  const onSaved = useCallback(() => setUrl(""), []);
  const {
    submitRecipe,
    isLoading: isSubmitting,
    error: submitError,
    status: submitStatus,
    isPending,
    isInterrupted,
    isResuming,
    resume,
  } = useExtractRecipe({ onSaved });

  return (
    <div className="homePage">
      <HomeHero
        isAdmin={isAdmin}
        totalCount={data.totalCount}
        favoriteCount={data.favoriteCount}
        isLoadingCounts={isLoading}
        url={url}
        onUrlChange={setUrl}
        onSubmit={submitRecipe}
        isSubmitting={isSubmitting}
        submitError={submitError}
        submitStatus={submitStatus}
        isPending={isPending}
        isInterrupted={isInterrupted}
        isResuming={isResuming}
        onResume={resume}
      />

      {!isLoading && <StatusBanner error={error} />}

      <section className="homePage__recent">
        <HomeSectionHeader
          eyebrow="Latest"
          title="Recently added"
          count={isLoading ? undefined : data.recent.length}
          action="Browse all"
          onAction={() => navigate("/recipes")}
        />
        {isLoading ? (
          <HomeRecentGridSkeleton />
        ) : (
          <HomeRecentGrid items={data.recent} canToggleFavorite={isAdmin} />
        )}
      </section>

      <section className="homePage__favorites">
        <HomeSectionHeader
          eyebrow="Pinned"
          title="Favorites"
          count={isLoading ? undefined : data.favorites.length}
          action="See all favorites"
          onAction={() => navigate("/recipes?favorite=true")}
        />
        {isLoading ? (
          <HomeFavoritesListSkeleton />
        ) : (
          <HomeFavoritesList
            items={data.favorites}
            canToggleFavorite={isAdmin}
          />
        )}
      </section>
    </div>
  );
}
