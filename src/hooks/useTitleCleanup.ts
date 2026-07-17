import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  applyTitleCleanup,
  getTitleCleanupPreview,
} from "../controllers/titleCleanupController";
import { invalidateRecipeQueries } from "./recipeQueryKeys";
import type { ApplyTitleItem } from "../types/recipe";

/**
 * Both calls are mutations rather than queries: each spends Gemini quota, so
 * they must fire only on an explicit click, never on mount or a refocus.
 */
export function useTitleCleanup() {
  const queryClient = useQueryClient();

  const previewMutation = useMutation({
    mutationFn: (cursor: string | null) => getTitleCleanupPreview(cursor),
  });

  const applyMutation = useMutation({
    mutationFn: (items: ApplyTitleItem[]) => applyTitleCleanup(items),
    onSuccess: async () => {
      await invalidateRecipeQueries(queryClient);
    },
  });

  return {
    preview: previewMutation.data ?? null,
    isPreviewing: previewMutation.isPending,
    previewError: previewMutation.error,
    loadPreview: (cursor: string | null = null) =>
      previewMutation.mutateAsync(cursor),

    isApplying: applyMutation.isPending,
    applyError: applyMutation.error,
    applyTitles: (items: ApplyTitleItem[]) => applyMutation.mutateAsync(items),
  };
}
