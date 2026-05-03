import { act, renderHook } from "@testing-library/react";
import { type KeyboardEvent } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useNavigationLink } from "./useNavigationLink";

const navigate = vi.fn();

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigate,
}));

function keyEvent(key: string) {
  return {
    key,
    preventDefault: vi.fn(),
  } as unknown as KeyboardEvent<HTMLElement>;
}

describe("useNavigationLink", () => {
  beforeEach(() => {
    navigate.mockClear();
  });

  it("navigates on click", () => {
    const { result } = renderHook(() => useNavigationLink("/recipes/recipe-1"));

    act(() => {
      result.current.onClick();
    });

    expect(navigate).toHaveBeenCalledWith("/recipes/recipe-1");
  });

  it("navigates on Enter and Space key presses", () => {
    const { result } = renderHook(() => useNavigationLink("/recipes/recipe-1"));
    const enterEvent = keyEvent("Enter");
    const spaceEvent = keyEvent(" ");

    act(() => {
      result.current.onKeyDown(enterEvent);
      result.current.onKeyDown(spaceEvent);
    });

    expect(enterEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(spaceEvent.preventDefault).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenNthCalledWith(1, "/recipes/recipe-1");
    expect(navigate).toHaveBeenNthCalledWith(2, "/recipes/recipe-1");
  });

  it("ignores other key presses", () => {
    const { result } = renderHook(() => useNavigationLink("/recipes/recipe-1"));
    const tabEvent = keyEvent("Tab");

    act(() => {
      result.current.onKeyDown(tabEvent);
    });

    expect(tabEvent.preventDefault).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});
