import { Navigate, Route, Routes } from "react-router-dom";

import { MainLayout } from "./layouts/MainLayout/MainLayout";
import { HomePage } from "./pages/HomePage/HomePage";
import { RecipeListPage } from "./pages/RecipeListPage/RecipeListPage";
import { RecipePage } from "./pages/RecipePage/RecipePage";
import "./App.scss";

function App() {
  return (
    <div className="appShell">
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/recipes" element={<RecipeListPage />} />
          <Route path="/recipes/:recipeImportId" element={<RecipePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </div>
  );
}

export default App;
