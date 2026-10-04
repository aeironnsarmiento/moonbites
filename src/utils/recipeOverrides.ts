import type { RecipeRowLayout, RecipeTextOverrides } from "../types/recipe";

export type DiffSegment = {
  text: string;
  changed: boolean;
};

// A row as shown or edited, with the parsed text it came from ("" when added).
export type RecipeRow = {
  key: string;
  source: number | null;
  text: string;
  original: string;
};

let addedRowCounter = 0;

export function getRecipeTextOverrides(
  overrides?: Partial<RecipeTextOverrides> | null,
): RecipeTextOverrides {
  return {
    ingredients: overrides?.ingredients ?? null,
    instructions: overrides?.instructions ?? null,
  };
}

export function createAddedRow(text = ""): RecipeRow {
  addedRowCounter += 1;
  return { key: `new-${addedRowCounter}`, source: null, text, original: "" };
}

export function resolveRows(
  rows: string[],
  layout: RecipeRowLayout = null,
): RecipeRow[] {
  if (!layout) {
    return rows.map((text, index) => ({
      key: `s${index}`,
      source: index,
      text,
      original: text,
    }));
  }

  return layout.map((entry, position) => {
    const original = entry.source === null ? "" : (rows[entry.source] ?? "");
    return {
      key: entry.source === null ? `a${position}` : `s${entry.source}`,
      source: entry.source,
      text: entry.text ?? original,
      original,
    };
  });
}

export function buildRowLayout(
  originalRows: string[],
  editedRows: RecipeRow[],
): RecipeRowLayout {
  const layout = editedRows
    .filter((row) => row.text.trim())
    .map((row) => ({
      source: row.source,
      text:
        row.source !== null && row.text === originalRows[row.source]
          ? null
          : row.text,
    }));

  const isIdentity =
    layout.length === originalRows.length &&
    layout.every((entry, index) => entry.source === index && entry.text === null);

  return isIdentity ? null : layout;
}

export function areRowsEqual(left: RecipeRow[], right: RecipeRow[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every(
    (row, index) =>
      row.source === right[index].source && row.text === right[index].text,
  );
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
