import type { RecipeRowOverrides, RecipeTextOverrides } from "../types/recipe";

export type DiffSegment = {
  text: string;
  changed: boolean;
};

export function getRecipeTextOverrides(
  overrides?: Partial<RecipeTextOverrides> | null,
): RecipeTextOverrides {
  return {
    ingredients: { ...(overrides?.ingredients ?? {}) },
    instructions: { ...(overrides?.instructions ?? {}) },
  };
}

export function applyRowOverrides(
  rows: string[],
  overrides: RecipeRowOverrides = {},
): string[] {
  return rows.map((row, index) => overrides[String(index)] ?? row);
}

export function buildRowOverrides(
  originalRows: string[],
  editedRows: string[],
): RecipeRowOverrides {
  const nextOverrides: RecipeRowOverrides = {};

  originalRows.forEach((originalRow, index) => {
    const editedRow = editedRows[index] ?? "";
    if (editedRow !== originalRow) {
      nextOverrides[String(index)] = editedRow;
    }
  });

  return nextOverrides;
}

export function areRowsEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

function mergeSegments(segments: DiffSegment[]): DiffSegment[] {
  return segments.reduce<DiffSegment[]>((merged, segment) => {
    if (!segment.text) {
      return merged;
    }

    const previousSegment = merged[merged.length - 1];
    if (previousSegment && previousSegment.changed === segment.changed) {
      previousSegment.text += segment.text;
      return merged;
    }

    merged.push({ ...segment });
    return merged;
  }, []);
}

function tokenizeDiffValue(value: string): string[] {
  const tokens = value.match(
    /(\s+|\d+(?:[./]\d+)*|[A-Za-z]+(?:['’-][A-Za-z]+)*|[^\sA-Za-z\d]+)/g,
  );
  return tokens ?? [];
}

function buildTokenDiffSegments(
  originalTokens: string[],
  editedTokens: string[],
): DiffSegment[] {
  const originalLength = originalTokens.length;
  const editedLength = editedTokens.length;
  const lcsMatrix = Array.from({ length: originalLength + 1 }, () =>
    Array<number>(editedLength + 1).fill(0),
  );

  for (
    let originalIndex = 1;
    originalIndex <= originalLength;
    originalIndex += 1
  ) {
    for (let editedIndex = 1; editedIndex <= editedLength; editedIndex += 1) {
      if (originalTokens[originalIndex - 1] === editedTokens[editedIndex - 1]) {
        lcsMatrix[originalIndex][editedIndex] =
          lcsMatrix[originalIndex - 1][editedIndex - 1] + 1;
      } else {
        lcsMatrix[originalIndex][editedIndex] = Math.max(
          lcsMatrix[originalIndex - 1][editedIndex],
          lcsMatrix[originalIndex][editedIndex - 1],
        );
      }
    }
  }

  const reversedSegments: DiffSegment[] = [];
  let originalIndex = originalLength;
  let editedIndex = editedLength;

  while (originalIndex > 0 && editedIndex > 0) {
    if (originalTokens[originalIndex - 1] === editedTokens[editedIndex - 1]) {
      reversedSegments.push({
        text: editedTokens[editedIndex - 1],
        changed: false,
      });
      originalIndex -= 1;
      editedIndex -= 1;
      continue;
    }

    if (
      lcsMatrix[originalIndex][editedIndex - 1] >=
      lcsMatrix[originalIndex - 1][editedIndex]
    ) {
      reversedSegments.push({
        text: editedTokens[editedIndex - 1],
        changed: true,
      });
      editedIndex -= 1;
    } else {
      originalIndex -= 1;
    }
  }

  while (editedIndex > 0) {
    reversedSegments.push({
      text: editedTokens[editedIndex - 1],
      changed: true,
    });
    editedIndex -= 1;
  }

  return mergeSegments(reversedSegments.reverse());
}

export function buildDiffSegments(
  originalValue: string,
  editedValue: string,
): DiffSegment[] {
  if (originalValue === editedValue) {
    return editedValue ? [{ text: editedValue, changed: false }] : [];
  }

  return buildTokenDiffSegments(
    tokenizeDiffValue(originalValue),
    tokenizeDiffValue(editedValue),
  );
}
