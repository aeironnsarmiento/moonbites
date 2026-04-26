import { Navigate, Route, Routes } from "react-router-dom";

import { RequireAdmin } from "./components/RequireAdmin/RequireAdmin";
import { MainLayout } from "./layouts/MainLayout/MainLayout";
import { AuthCallbackPage } from "./pages/AuthCallbackPage/AuthCallbackPage";
import { HomePage } from "./pages/HomePage/HomePage";
import { LoginPage } from "./pages/LoginPage/LoginPage";
import { RecipeCreatePage } from "./pages/RecipeCreatePage/RecipeCreatePage";
import { RecipeListPage } from "./pages/RecipeListPage/RecipeListPage";
import { RecipePage } from "./pages/RecipePage/RecipePage";
import "./App.scss";

function App() {
  return (
    <div className="appShell">
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
    </div>
  );
}

export default App;
