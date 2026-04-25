import { useEffect, useState } from "react";

function storageKey(recipeImportId: string) {
  return `moonbites:servings:${recipeImportId}`;
}

export function useServingsScale(
  recipeImportId: string,
  defaultServings: number | null,
) {
  const originalServings = defaultServings && defaultServings > 0 ? defaultServings : 1;

  const [currentServings, setCurrentServings] = useState(() => {
    const stored = window.localStorage.getItem(storageKey(recipeImportId));
    const parsed = stored ? Number(stored) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : originalServings;
  });

  useEffect(() => {
    window.localStorage.setItem(
      storageKey(recipeImportId),
      String(currentServings),
    );
  }, [currentServings, recipeImportId]);

  return {
    currentServings,
    originalServings,
    scaleFactor: currentServings / originalServings,
    decrement: () => setCurrentServings((current) => Math.max(1, current - 1)),
    increment: () => setCurrentServings((current) => current + 1),
    setCurrentServings,
  };
}
