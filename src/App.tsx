import { lazy, Suspense } from "react";
import { Spinner, Stack } from "@chakra-ui/react";
import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAdmin } from "./components/RequireAdmin/RequireAdmin";
import { MainLayout } from "./layouts/MainLayout/MainLayout";
import { HomePage } from "./pages/HomePage/HomePage";
import "./App.scss";

const AuthCallbackPage = lazy(() =>
  import("./pages/AuthCallbackPage/AuthCallbackPage").then((m) => ({ default: m.AuthCallbackPage })),
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const RecipeCreatePage = lazy(() =>
  import("./pages/RecipeCreatePage/RecipeCreatePage").then((m) => ({ default: m.RecipeCreatePage })),
);
const RecipeListPage = lazy(() =>
  import("./pages/RecipeListPage/RecipeListPage").then((m) => ({ default: m.RecipeListPage })),
);
const RecipePage = lazy(() =>
  import("./pages/RecipePage/RecipePage").then((m) => ({ default: m.RecipePage })),
);

function RouteFallback() {
  return (
    <Stack align="center" py={8}>
      <Spinner color="brand.600" />
    </Stack>
  );
}

function App() {
  return (
    <div className="appShell">
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route
              path="/recipes/create"
              element={
                <RequireAdmin>
                  <RecipeCreatePage />
                </RequireAdmin>
              }
            />
            <Route path="/recipes" element={<RecipeListPage />} />
            <Route path="/recipes/:recipeImportId" element={<RecipePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;
