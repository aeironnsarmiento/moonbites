export type ParsedQuantity = {
  value: number;
  rest: string;
};

const VULGAR_FRACTIONS: Record<string, number> = {
  "¼": 1 / 4,
  "⅓": 1 / 3,
  "½": 1 / 2,
  "⅔": 2 / 3,
  "¾": 3 / 4,
};

function parseAsciiFraction(value: string) {
  const [numerator, denominator] = value.split("/").map(Number);
  if (!denominator) {
    return null;
  }
  return numerator / denominator;
}

export function parseQuantity(text: string): ParsedQuantity | null {
  const trimmed = text.trimStart();
  const mixedVulgar = trimmed.match(/^(\d+)\s+([¼⅓½⅔¾])(.*)$/u);
  if (mixedVulgar) {
    return {
      value: Number(mixedVulgar[1]) + VULGAR_FRACTIONS[mixedVulgar[2]],
      rest: mixedVulgar[3].trimStart(),
    };
  }

  const mixedAscii = trimmed.match(/^(\d+)\s+(\d+\/\d+)\b(.*)$/);
  if (mixedAscii) {
    const fraction = parseAsciiFraction(mixedAscii[2]);
    if (fraction != null) {
      return {
        value: Number(mixedAscii[1]) + fraction,
        rest: mixedAscii[3].trimStart(),
      };
    }
  }

  const vulgar = trimmed.match(/^([¼⅓½⅔¾])(.*)$/u);
  if (vulgar) {
    return {
      value: VULGAR_FRACTIONS[vulgar[1]],
      rest: vulgar[2].trimStart(),
    };
  }

  const ascii = trimmed.match(/^(\d+\/\d+)\b(.*)$/);
  if (ascii) {
    const fraction = parseAsciiFraction(ascii[1]);
    if (fraction != null) {
      return {
        value: fraction,
        rest: ascii[2].trimStart(),
      };
    }
  }

  const decimal = trimmed.match(/^(\d+\.\d+)\b(.*)$/);
  if (decimal) {
    return {
      value: Number(decimal[1]),
      rest: decimal[2].trimStart(),
    };
  }

  const integer = trimmed.match(/^(\d+)\b(.*)$/);
  if (integer) {
    return {
      value: Number(integer[1]),
      rest: integer[2].trimStart(),
    };
  }

  return null;
}

export function formatQuantity(value: number): string {
  const sign = value < 0 ? "-" : "";
  const absoluteValue = Math.abs(value);
  const whole = Math.floor(absoluteValue);
  const fraction = absoluteValue - whole;
  const cleanFractions: Array<[number, string]> = [
    [1 / 4, "1/4"],
    [1 / 3, "1/3"],
    [1 / 2, "1/2"],
    [2 / 3, "2/3"],
    [3 / 4, "3/4"],
  ];

  for (const [fractionValue, label] of cleanFractions) {
    if (Math.abs(fraction - fractionValue) <= 0.001) {
      return whole > 0 ? `${sign}${whole} ${label}` : `${sign}${label}`;
    }
  }

  if (Math.abs(fraction) <= 0.001) {
    return `${sign}${whole}`;
  }

  return `${sign}${absoluteValue.toFixed(2).replace(/\.?0+$/, "")}`;
}
