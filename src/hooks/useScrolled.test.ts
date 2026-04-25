import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useScrolled } from "./useScrolled";

describe("useScrolled", () => {
  it("updates when scroll passes the threshold", () => {
    const addEventListener = vi.spyOn(window, "addEventListener");
    const removeEventListener = vi.spyOn(window, "removeEventListener");
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 1;
    });

    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
    const { result, unmount } = renderHook(() => useScrolled(8));
    expect(result.current).toBe(false);

    Object.defineProperty(window, "scrollY", { value: 12, configurable: true });
    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current).toBe(true);
    unmount();
    expect(addEventListener).toHaveBeenCalledWith(
      "scroll",
      expect.any(Function),
      { passive: true },
    );
    expect(removeEventListener).toHaveBeenCalledWith(
      "scroll",
      expect.any(Function),
    );
  });
});
