export type ParsedQuantity = {
  value: number;
  rest: string;
  /** Upper bound of a range such as "1-2" or "1 to 2". */
  upperValue?: number;
  /** Text between the two ends of a range, e.g. "-" or " to ". */
  rangeSeparator?: string;
  /** Whitespace between the quantity and the rest ("" for "200g"). */
  separator: string;
};

const VULGAR_FRACTIONS: Record<string, number> = {
  "¼": 1 / 4,
  "½": 1 / 2,
  "¾": 3 / 4,
  "⅐": 1 / 7,
  "⅑": 1 / 9,
  "⅒": 1 / 10,
  "⅓": 1 / 3,
  "⅔": 2 / 3,
  "⅕": 1 / 5,
  "⅖": 2 / 5,
  "⅗": 3 / 5,
  "⅘": 4 / 5,
  "⅙": 1 / 6,
  "⅚": 5 / 6,
  "⅛": 1 / 8,
  "⅜": 3 / 8,
  "⅝": 5 / 8,
  "⅞": 7 / 8,
};

const VULGAR_CLASS = `[${Object.keys(VULGAR_FRACTIONS).join("")}]`;

// One quantity, tried in order: whole + vulgar ("1½", "1 ½"), whole + ASCII
// fraction ("1 1/2"), ASCII fraction, lone vulgar, then a plain number with
// optional thousands separators and decimals ("1,000", "1.5", ".5").
const NUMBER_SOURCE = [
  `(\\d+)\\s*(${VULGAR_CLASS})`,
  `(\\d+)\\s+(\\d+)\\s*\\/\\s*(\\d+)`,
  `(\\d+)\\s*\\/\\s*(\\d+)`,
  `(${VULGAR_CLASS})`,
  `(\\d{1,3}(?:,\\d{3})+(?:\\.\\d+)?|\\d+(?:\\.\\d+)?|\\.\\d+)`,
].join("|");

const MAX_RANGE_RATIO = 10;

const LEADING_NUMBER = new RegExp(`^(?:${NUMBER_SOURCE})`, "u");
const RANGE_TAIL = new RegExp(
  `^(\\s*(?:-|–|—|to)\\s*)(?:${NUMBER_SOURCE})`,
  "iu",
);

function valueFromMatch(match: RegExpMatchArray, offset: number): number | null {
  const group = (index: number) => match[offset + index];

  if (group(1) !== undefined) {
    return Number(group(1)) + VULGAR_FRACTIONS[group(2)];
  }
  if (group(3) !== undefined) {
    const denominator = Number(group(5));
    return denominator ? Number(group(3)) + Number(group(4)) / denominator : null;
  }
  if (group(6) !== undefined) {
    const denominator = Number(group(7));
    return denominator ? Number(group(6)) / denominator : null;
  }
  if (group(8) !== undefined) {
    return VULGAR_FRACTIONS[group(8)];
  }
  if (group(9) !== undefined) {
    return Number(group(9).replace(/,/g, ""));
  }
  return null;
}

export function parseQuantity(text: string): ParsedQuantity | null {
  const trimmed = text.trimStart();
  const leading = trimmed.match(LEADING_NUMBER);
  if (!leading) {
    return null;
  }

  const value = valueFromMatch(leading, 0);
  if (value == null) {
    return null;
  }

  let remainder = trimmed.slice(leading[0].length);
  let upperValue: number | undefined;
  let rangeSeparator: string | undefined;

  const range = remainder.match(RANGE_TAIL);
  if (range) {
    const upper = valueFromMatch(range, 1);
    // A real range climbs modestly ("1-2", "10-12"). Anything else is a count
    // followed by a size, e.g. "1 - 400g can": scale the count, not the can.
    if (upper != null && upper > value && upper <= value * MAX_RANGE_RATIO) {
      upperValue = upper;
      rangeSeparator = range[1];
      remainder = remainder.slice(range[0].length);
    }
  }

  // More number straight after the match ("1,5" decimal comma, "1/2/3")
  // means it was not a quantity we understand; leave such lines alone.
  if (/^(?:[\d/]|[.,]\d)/.test(remainder)) {
    return null;
  }

  const separator = remainder.match(/^\s*/)?.[0] ?? "";
  const parsed: ParsedQuantity = {
    value,
    rest: remainder.slice(separator.length),
    separator,
  };
  if (upperValue !== undefined) {
    parsed.upperValue = upperValue;
    parsed.rangeSeparator = rangeSeparator;
  }
  return parsed;
}

export function formatQuantity(value: number): string {
  const sign = value < 0 ? "-" : "";
  const absoluteValue = Math.abs(value);
  const whole = Math.floor(absoluteValue);
  const fraction = absoluteValue - whole;
  const cleanFractions: Array<[number, string]> = [
    [1 / 8, "1/8"],
    [1 / 4, "1/4"],
    [1 / 3, "1/3"],
    [3 / 8, "3/8"],
    [1 / 2, "1/2"],
    [5 / 8, "5/8"],
    [2 / 3, "2/3"],
    [3 / 4, "3/4"],
    [7 / 8, "7/8"],
  ];

  for (const [fractionValue, label] of cleanFractions) {
    if (Math.abs(fraction - fractionValue) <= 0.001) {
      return whole > 0 ? `${sign}${whole} ${label}` : `${sign}${label}`;
    }
  }

  if (Math.abs(fraction) <= 0.001) {
    return `${sign}${whole}`;
  }

  if (Math.abs(fraction - 1) <= 0.001) {
    return `${sign}${whole + 1}`;
  }

  return `${sign}${absoluteValue.toFixed(2).replace(/\.?0+$/, "")}`;
}
