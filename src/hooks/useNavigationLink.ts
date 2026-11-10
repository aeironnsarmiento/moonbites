import { useCallback, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";

export function useNavigationLink(path: string) {
  const navigate = useNavigate();

  const onClick = useCallback(() => {
    navigate(path);
  }, [navigate, path]);

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      // Keys pressed on a nested control (the favorite button) bubble up
      // here; let that control handle them instead of navigating away.
      if (event.target !== event.currentTarget) {
        return;
      }

      event.preventDefault();
      navigate(path);
    },
    [navigate, path],
  );

  return {
    onClick,
    onKeyDown,
  };
}
