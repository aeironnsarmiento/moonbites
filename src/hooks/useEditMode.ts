import { useCallback, useState } from "react";

export function useEditMode<T>(initialDraft: T) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<T>(initialDraft);

  const reset = useCallback(
    (seed: T = initialDraft) => {
      setDraft(seed);
    },
    [initialDraft],
  );

  const enable = useCallback(
    (seed: T = initialDraft) => {
      setDraft(seed);
      setIsEditing(true);
    },
    [initialDraft],
  );

  const disable = useCallback(() => {
    setDraft(initialDraft);
    setIsEditing(false);
  }, [initialDraft]);

  return {
    isEditing,
    draft,
    setDraft,
    enable,
    disable,
    reset,
  };
}
