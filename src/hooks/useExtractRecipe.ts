import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  buildExtractStatus,
  submitRecipeImport,
} from "../controllers/extractController";

export function useExtractRecipe() {
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  const submitRecipe = useCallback(
    async (url: string) => {
      setIsLoading(true);
      setError("");
      setStatus("");

      try {
        const response = await submitRecipeImport(url);

        if (response.database_saved && response.recipe_count > 0) {
          await queryClient.invalidateQueries({ queryKey: ["recipe-list"] });
        }

        setStatus(buildExtractStatus(response));
        return response;
      } catch (submitError) {
        const message =
          submitError instanceof Error
            ? submitError.message
            : "Something went wrong while contacting the backend.";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [queryClient],
  );

  return {
    isLoading,
    error,
    status,
    submitRecipe,
  };
}
