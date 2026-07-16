import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("start", 300));

    expect(result.current).toBe("start");
  });

  it("updates only after the delay elapses", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: "a" } },
    );

    rerender({ value: "ab" });

    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("ab");
  });

  it("collapses rapid changes into the last value", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: "c" } },
    );

    rerender({ value: "cu" });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "cur" });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    rerender({ value: "curry" });

    expect(result.current).toBe("c");

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(result.current).toBe("curry");
  });
});
