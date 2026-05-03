import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useEditMode } from "./useEditMode";

describe("useEditMode", () => {
  it("enables editing with a seed draft", () => {
    const { result } = renderHook(() =>
      useEditMode({ title: "Saved recipe", servings: 4 }),
    );

    expect(result.current.isEditing).toBe(false);
    expect(result.current.draft).toEqual({ title: "Saved recipe", servings: 4 });

    act(() => {
      result.current.enable({ title: "Draft recipe", servings: 6 });
    });

    expect(result.current.isEditing).toBe(true);
    expect(result.current.draft).toEqual({ title: "Draft recipe", servings: 6 });
  });

  it("mutates, resets, and disables draft state", () => {
    const { result } = renderHook(() =>
      useEditMode({ ingredients: ["sugar"], notes: "" }),
    );

    act(() => {
      result.current.enable({ ingredients: ["flour"], notes: "draft" });
      result.current.setDraft({ ingredients: ["flour", "salt"], notes: "draft" });
    });

    expect(result.current.draft).toEqual({
      ingredients: ["flour", "salt"],
      notes: "draft",
    });

    act(() => {
      result.current.reset({ ingredients: ["butter"], notes: "reset" });
    });

    expect(result.current.isEditing).toBe(true);
    expect(result.current.draft).toEqual({
      ingredients: ["butter"],
      notes: "reset",
    });

    act(() => {
      result.current.disable();
    });

    expect(result.current.isEditing).toBe(false);
    expect(result.current.draft).toEqual({ ingredients: ["sugar"], notes: "" });
  });
});
