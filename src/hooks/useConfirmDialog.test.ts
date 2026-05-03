import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useConfirmDialog } from "./useConfirmDialog";

describe("useConfirmDialog", () => {
  it("opens, confirms async work, and closes on success", async () => {
    let resolveConfirm: (value: string) => void = () => {};
    const asyncFn = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          resolveConfirm = resolve;
        }),
    );
    const { result } = renderHook(() => useConfirmDialog());

    act(() => {
      result.current.open();
    });

    expect(result.current.isOpen).toBe(true);

    let confirmPromise: Promise<string> = Promise.resolve("");
    act(() => {
      confirmPromise = result.current.confirm(asyncFn);
    });

    expect(result.current.isProcessing).toBe(true);

    await act(async () => {
      resolveConfirm("deleted");
      await expect(confirmPromise).resolves.toBe("deleted");
    });

    expect(asyncFn).toHaveBeenCalledTimes(1);
    expect(result.current.isProcessing).toBe(false);
    expect(result.current.isOpen).toBe(false);
  });

  it("keeps dialog open and rethrows when confirm fails", async () => {
    const error = new Error("delete failed");
    const asyncFn = vi.fn().mockRejectedValue(error);
    const { result } = renderHook(() => useConfirmDialog());

    act(() => {
      result.current.open();
    });

    await act(async () => {
      await expect(result.current.confirm(asyncFn)).rejects.toThrow("delete failed");
    });

    expect(result.current.isProcessing).toBe(false);
    expect(result.current.isOpen).toBe(true);
  });

  it("does not close while processing", async () => {
    let resolveConfirm: () => void = () => {};
    const asyncFn = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveConfirm = resolve;
        }),
    );
    const { result } = renderHook(() => useConfirmDialog());

    act(() => {
      result.current.open();
    });

    let confirmPromise: Promise<void>;
    await act(async () => {
      confirmPromise = result.current.confirm(asyncFn);
    });

    act(() => {
      result.current.close();
    });

    expect(result.current.isOpen).toBe(true);

    await act(async () => {
      resolveConfirm();
      await confirmPromise;
    });

    expect(result.current.isOpen).toBe(false);
  });
});
