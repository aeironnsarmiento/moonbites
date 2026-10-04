import { describe, expect, it } from "vitest";

import {
  buildRowLayout,
  createAddedRow,
  resolveRows,
  type RecipeRow,
} from "./recipeOverrides";

const ROWS = ["a", "b", "c"];

function texts(rows: RecipeRow[]) {
  return rows.map((row) => row.text);
}

describe("resolveRows", () => {
  it("shows parsed rows when there is no layout", () => {
    expect(resolveRows(ROWS, null)).toEqual([
      { key: "s0", source: 0, text: "a", original: "a" },
      { key: "s1", source: 1, text: "b", original: "b" },
      { key: "s2", source: 2, text: "c", original: "c" },
    ]);
  });

  it("applies edits, deletes, reorders and additions", () => {
    const rows = resolveRows(ROWS, [
      { source: 2, text: null },
      { source: null, text: "new" },
      { source: 0, text: "A" },
    ]);

    expect(texts(rows)).toEqual(["c", "new", "A"]);
    expect(rows.map((row) => row.original)).toEqual(["c", "", "a"]);
  });
});

describe("buildRowLayout", () => {
  it("returns null when rows match the parsed recipe", () => {
    expect(buildRowLayout(ROWS, resolveRows(ROWS))).toBeNull();
  });

  it("records edits, deletes, reorders and additions", () => {
    const [a, , c] = resolveRows(ROWS);

    expect(
      buildRowLayout(ROWS, [
        c,
        { ...a, text: "A" },
        { ...createAddedRow(), text: "new" },
      ]),
    ).toEqual([
      { source: 2, text: null },
      { source: 0, text: "A" },
      { source: null, text: "new" },
    ]);
  });

  it("drops blank rows", () => {
    const [a, b, c] = resolveRows(ROWS);

    expect(
      buildRowLayout(ROWS, [a, { ...b, text: " " }, c, createAddedRow()]),
    ).toEqual([
      { source: 0, text: null },
      { source: 2, text: null },
    ]);
  });
});
