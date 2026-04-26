import { Spinner, Stack } from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";

import { HomeFavoritesList } from "../../components/HomeFavoritesList/HomeFavoritesList";
import { HomeHero } from "../../components/HomeHero/HomeHero";
import { HomeRecentGrid } from "../../components/HomeRecentGrid/HomeRecentGrid";
import { HomeSectionHeader } from "../../components/HomeSectionHeader/HomeSectionHeader";
import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useAuth } from "../../hooks/useAuth";
import { useExtractRecipe } from "../../hooks/useExtractRecipe";
import { useHighlightedRecipes } from "../../hooks/useHighlightedRecipes";
import "./HomePage.scss";

export function HomePage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { data, error, isLoading } = useHighlightedRecipes();
  const { submitRecipe, isLoading: isSubmitting, error: submitError, status: submitStatus } = useExtractRecipe();

  return (
    <div className="homePage">
      <HomeHero
        isAdmin={isAdmin}
        totalCount={data.totalCount}
        favoriteCount={data.favoriteCount}
        isLoadingCounts={isLoading}
        onSubmit={submitRecipe}
        isSubmitting={isSubmitting}
        submitError={submitError}
        submitStatus={submitStatus}
      />

      {isLoading && (
        <Stack align="center" py={8}>
          <Spinner color="brand.600" />
        </Stack>
      )}

      {!isLoading && <StatusBanner error={error} />}

      {!isLoading && (
        <>
          <section className="homePage__recent">
            <HomeSectionHeader
              eyebrow="Latest"
              title="Recently added"
              count={data.recent.length}
              action="Browse all"
              onAction={() => navigate("/recipes")}
            />
            <HomeRecentGrid
              items={data.recent}
              canToggleFavorite={isAdmin}
            />
          </section>

          <section className="homePage__favorites">
            <HomeSectionHeader
              eyebrow="Pinned"
              title="Favorites"
              count={data.favorites.length}
              action="See all favorites"
              onAction={() => navigate("/recipes?favorite=true")}
            />
            <HomeFavoritesList
              items={data.favorites}
              canToggleFavorite={isAdmin}
            />
          </section>
        </>
      )}
    </div>
  );
}
