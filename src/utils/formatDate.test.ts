import { describe, expect, it } from "vitest";

import { formatDate } from "./formatDate";

describe("formatDate", () => {
  it("formats dates with the recipe card date style", () => {
    const value = "2026-04-24T00:00:00.000Z";
    const expected = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(value));

    expect(formatDate(value)).toBe(expected);
  });
});
