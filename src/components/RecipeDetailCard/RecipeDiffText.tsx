import { Text, Tooltip } from "@chakra-ui/react";

import { buildDiffSegments } from "../../utils/recipeOverrides";

type RecipeDiffTextProps = {
  originalValue: string;
  editedValue: string;
  keyPrefix: string;
};

export function RecipeDiffText({
  originalValue,
  editedValue,
  keyPrefix,
}: RecipeDiffTextProps) {
  const diffSegments = buildDiffSegments(originalValue, editedValue);

  if (originalValue === editedValue) {
    return <>{editedValue}</>;
  }

  if (diffSegments.length === 0) {
    return (
      <Tooltip label={`Original: ${originalValue}`} hasArrow>
        <Text
          as="span"
          tabIndex={0}
          className="recipeDetailCard__diff recipeDetailCard__diff--changed"
        >
          (empty)
        </Text>
      </Tooltip>
    );
  }

  return (
    <>
      {diffSegments.map((segment, index) => {
        if (!segment.changed) {
          return (
            <Text as="span" key={`${keyPrefix}-${index}`}>
              {segment.text}
            </Text>
          );
        }

        return (
          <Tooltip
            key={`${keyPrefix}-${index}`}
            label={`Original: ${originalValue}`}
            hasArrow
          >
            <Text
              as="span"
              tabIndex={0}
              className="recipeDetailCard__diff recipeDetailCard__diff--changed"
            >
              {segment.text}
            </Text>
          </Tooltip>
        );
      })}
    </>
  );
}
