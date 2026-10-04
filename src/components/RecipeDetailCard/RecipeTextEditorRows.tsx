import {
  Button,
  CloseButton,
  HStack,
  IconButton,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";

import {
  createAddedRow,
  type RecipeRow,
} from "../../utils/recipeOverrides";

type RecipeTextEditorRowsProps = {
  section: "ingredients" | "instructions";
  rows: RecipeRow[];
  originals: string[];
  onChangeRows: (rows: RecipeRow[]) => void;
};

function moveRow(rows: RecipeRow[], from: number, to: number): RecipeRow[] {
  const nextRows = [...rows];
  const [row] = nextRows.splice(from, 1);
  nextRows.splice(to, 0, row);
  return nextRows;
}

// Put a restored parsed row back after the last kept row parsed before it.
function restoreRow(rows: RecipeRow[], source: number, text: string) {
  const insertAt = rows.reduce(
    (position, row, index) =>
      row.source !== null && row.source < source ? index + 1 : position,
    0,
  );
  const nextRows = [...rows];
  nextRows.splice(insertAt, 0, {
    key: `s${source}`,
    source,
    text,
    original: text,
  });
  return nextRows;
}

export function RecipeTextEditorRows({
  section,
  rows,
  originals,
  onChangeRows,
}: RecipeTextEditorRowsProps) {
  const rowNoun = section === "ingredients" ? "Ingredient" : "Step";
  const lowerNoun = rowNoun.toLowerCase();
  const keptSources = new Set(rows.map((row) => row.source));
  const removedSources = originals
    .map((_, source) => source)
    .filter((source) => !keptSources.has(source));

  return (
    <Stack spacing={3}>
      {rows.map((row, rowIndex) => {
        const isAdded = row.source === null;
        const changed = isAdded || row.text !== row.original;
        const position = rowIndex + 1;
        const label = `${rowNoun} ${position}`;

        return (
          <Stack
            key={row.key}
            spacing={2}
            className={`recipeDetailCard__editorRow${changed ? " recipeDetailCard__editorRow--changed" : ""}`}
          >
            <HStack justify="space-between" minH="24px">
              <Text
                fontSize="sm"
                fontWeight="600"
                color={changed ? "orange.600" : "gray.500"}
              >
                {label}
                {isAdded ? " (new)" : ""}
              </Text>
              <HStack spacing={1}>
                <IconButton
                  size="xs"
                  variant="ghost"
                  aria-label={`Move ${lowerNoun} ${position} up`}
                  icon={<span aria-hidden="true">↑</span>}
                  isDisabled={rowIndex === 0}
                  onClick={() => onChangeRows(moveRow(rows, rowIndex, rowIndex - 1))}
                />
                <IconButton
                  size="xs"
                  variant="ghost"
                  aria-label={`Move ${lowerNoun} ${position} down`}
                  icon={<span aria-hidden="true">↓</span>}
                  isDisabled={rowIndex === rows.length - 1}
                  onClick={() => onChangeRows(moveRow(rows, rowIndex, rowIndex + 1))}
                />
                <CloseButton
                  size="sm"
                  aria-label={`Remove ${lowerNoun} ${position}`}
                  onClick={() =>
                    onChangeRows(rows.filter((_, index) => index !== rowIndex))
                  }
                />
              </HStack>
            </HStack>
            <Textarea
              value={row.text}
              aria-label={label}
              autoFocus={isAdded && rowIndex === rows.length - 1 && !row.text}
              onChange={(event) => {
                const nextRows = [...rows];
                nextRows[rowIndex] = { ...row, text: event.target.value };
                onChangeRows(nextRows);
              }}
              className="recipeDetailCard__editor"
              minH="unset"
              resize="vertical"
            />
          </Stack>
        );
      })}
      <Button
        variant="outline"
        size="sm"
        alignSelf="flex-start"
        onClick={() => onChangeRows([...rows, createAddedRow()])}
      >
        Add {lowerNoun}
      </Button>
      {removedSources.length > 0 ? (
        <Stack spacing={1} pt={1}>
          <Text fontSize="sm" fontWeight="600" color="gray.500">
            Removed
          </Text>
          {removedSources.map((source) => (
            <HStack key={`removed-${source}`} justify="space-between" spacing={3}>
              <Text fontSize="sm" color="gray.500" textDecoration="line-through">
                {originals[source]}
              </Text>
              <Button
                size="xs"
                variant="ghost"
                aria-label={`Restore ${lowerNoun}: ${originals[source]}`}
                onClick={() =>
                  onChangeRows(restoreRow(rows, source, originals[source]))
                }
              >
                Restore
              </Button>
            </HStack>
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
