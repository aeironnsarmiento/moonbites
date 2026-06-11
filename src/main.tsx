import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient } from "@tanstack/react-query";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./components/AuthProvider/AuthProvider";
import { getHighlightedRecipes } from "./controllers/recipeController";
import { HIGHLIGHTED_RECIPES_KEY } from "./hooks/recipeQueryKeys";
import "./index.css";
import { chakraTheme } from "./styles/chakraTheme";

const CACHE_MAX_AGE_MS = 1000 * 60 * 60 * 24;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      gcTime: CACHE_MAX_AGE_MS,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: "moonbites-query-cache",
});

function prefetchHighlights() {
  void queryClient.prefetchQuery({
    queryKey: HIGHLIGHTED_RECIPES_KEY,
    queryFn: () => getHighlightedRecipes(),
    staleTime: 1000 * 60 * 5,
  });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: CACHE_MAX_AGE_MS,
        buster: "v1",
      }}
      onSuccess={prefetchHighlights}
    >
      <ChakraProvider theme={chakraTheme}>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </ChakraProvider>
    </PersistQueryClientProvider>
  </StrictMode>,
);
