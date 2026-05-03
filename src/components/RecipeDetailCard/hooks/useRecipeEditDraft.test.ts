import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  NormalizedRecipe,
  RecipeTextOverrides,
  UpdateRecipeMetadataPayload,
} from "../../../types/recipe";
import { useRecipeEditDraft } from "./useRecipeEditDraft";

const recipe: NormalizedRecipe = {
  name: "Chocolate Cake",
  recipeYield: "8 servings",
  cookTime: "45 minutes",
  recipeCuisine: ["American"],
  nutrition: null,
  ingredients: ["1 cup sugar", "2 cups flour"],
  ingredientSections: null,
  instructions: ["Mix ingredients.", "Bake until set."],
};

function renderDraft(
  overrides: Partial<Parameters<typeof useRecipeEditDraft>[0]> = {},
) {
  const onSaveMetadata = vi.fn<() => Promise<void>>(() => Promise.resolve());
  const onSaveOverrides = vi.fn<() => Promise<void>>(() => Promise.resolve());
  const result = renderHook(() =>
    useRecipeEditDraft({
      recipe,
      recipeIndex: 3,
      recordTitle: "Saved Chocolate Cake",
      imageUrl: "https://example.com/cake.jpg",
      sourceUrl: "https://example.com/cake",
      visibleIngredients: ["1 cup brown sugar", "2 cups flour"],
      visibleInstructions: ["Mix ingredients.", "Bake until center is set."],
      canEditMetadata: true,
      onSaveMetadata: onSaveMetadata as unknown as (
        metadata: UpdateRecipeMetadataPayload,
      ) => Promise<void>,
      onSaveOverrides: onSaveOverrides as unknown as (
        recipeIndex: number,
        overrides: RecipeTextOverrides,
      ) => Promise<void>,
      ...overrides,
    }),
  );

  return {
    ...result,
    onSaveMetadata,
    onSaveOverrides,
  };
}

describe("useRecipeEditDraft", () => {
  it("seeds drafts from the visible recipe state", () => {
    const { result } = renderDraft();

    expect(result.current.isEditing).toBe(false);
    expect(result.current.draftIngredients).toEqual([
      "1 cup brown sugar",
      "2 cups flour",
    ]);
    expect(result.current.draftInstructions).toEqual([
      "Mix ingredients.",
      "Bake until center is set.",
    ]);
    expect(result.current.draftTitle).toBe("Saved Chocolate Cake");
    expect(result.current.draftYield).toBe("8 servings");
    expect(result.current.draftImageUrl).toBe("https://example.com/cake.jpg");
    expect(result.current.draftSourceUrl).toBe("https://example.com/cake");
  });

  it("starts and cancels editing with fresh seeds", () => {
    const { result } = renderDraft();

    act(() => {
      result.current.setDraftTitle("Stale draft");
      result.current.startEditing();
    });

    expect(result.current.isEditing).toBe(true);
    expect(result.current.draftTitle).toBe("Saved Chocolate Cake");

    act(() => {
      result.current.setDraftTitle("Draft Cake");
      result.current.cancelEditing();
    });

    expect(result.current.isEditing).toBe(false);
    expect(result.current.draftTitle).toBe("Saved Chocolate Cake");
  });

  it("detects metadata and row changes", () => {
    const { result } = renderDraft();

    expect(result.current.hasMetadataChanges).toBe(false);
    expect(result.current.hasUnsavedChanges).toBe(false);

    act(() => {
      result.current.startEditing();
      result.current.setDraftTitle("Better Chocolate Cake");
    });

    expect(result.current.hasMetadataChanges).toBe(true);
    expect(result.current.hasUnsavedChanges).toBe(true);

    act(() => {
      result.current.setDraftTitle("Saved Chocolate Cake");
      result.current.setDraftIngredients(["2 cups brown sugar", "2 cups flour"]);
    });

    expect(result.current.hasMetadataChanges).toBe(false);
    expect(result.current.hasUnsavedChanges).toBe(true);
  });

  it("saves metadata before row overrides", async () => {
    const calls: string[] = [];
    const onSaveMetadata = vi.fn(async () => {
      calls.push("metadata");
    });
    const onSaveOverrides = vi.fn(async () => {
      calls.push("overrides");
    });
    const { result } = renderDraft({
      onSaveMetadata,
      onSaveOverrides,
    });

    act(() => {
      result.current.startEditing();
      result.current.setDraftTitle("Better Chocolate Cake");
      result.current.setDraftYield("10 servings");
      result.current.setDraftImageUrl("https://example.com/new-cake.jpg");
      result.current.setDraftSourceUrl("https://example.com/new-cake");
      result.current.setDraftIngredients(["2 cups brown sugar", "2 cups flour"]);
      result.current.setDraftInstructions([
        "Mix ingredients.",
        "Bake until center is set and cool.",
      ]);
    });

    await act(async () => {
      await result.current.save();
    });

    expect(calls).toEqual(["metadata", "overrides"]);
    expect(onSaveMetadata).toHaveBeenCalledWith({
      title: "Better Chocolate Cake",
      recipeYield: "10 servings",
      imageUrl: "https://example.com/new-cake.jpg",
      sourceUrl: "https://example.com/new-cake",
    });
    expect(onSaveOverrides).toHaveBeenCalledWith(3, {
      ingredients: {
        "0": "2 cups brown sugar",
      },
      instructions: {
        "1": "Bake until center is set and cool.",
      },
    });
    expect(result.current.isEditing).toBe(false);
  });

  it("skips unchanged metadata when saving", async () => {
    const { result, onSaveMetadata, onSaveOverrides } = renderDraft();

    act(() => {
      result.current.startEditing();
    });

    await act(async () => {
      await result.current.save();
    });

    expect(onSaveMetadata).not.toHaveBeenCalled();
    expect(onSaveOverrides).toHaveBeenCalledWith(3, {
      ingredients: {
        "0": "1 cup brown sugar",
      },
      instructions: {
        "1": "Bake until center is set.",
      },
    });
  });

  it("keeps editing active and exposes a fallback error on failed save", async () => {
    const onSaveOverrides = vi.fn(() => Promise.reject("denied"));
    const { result } = renderDraft({ onSaveOverrides });

    act(() => {
      result.current.startEditing();
    });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.isEditing).toBe(true);
    expect(result.current.saveError).toBe("Unable to save recipe edits.");
  });
});
