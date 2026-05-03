import { Stack, Text, Textarea } from "@chakra-ui/react";

type RecipeTextEditorRowsProps = {
  section: "ingredients" | "instructions";
  rows: string[];
  originals: string[];
  onChangeRows: (rows: string[]) => void;
};

export function RecipeTextEditorRows({
  section,
  rows,
  originals,
  onChangeRows,
}: RecipeTextEditorRowsProps) {
  return (
    <Stack spacing={3}>
      {rows.map((row, rowIndex) => {
        const changed = row !== originals[rowIndex];

        return (
          <Stack
            key={`${section}-${rowIndex}`}
            spacing={2}
            className={`recipeDetailCard__editorRow${changed ? " recipeDetailCard__editorRow--changed" : ""}`}
          >
            <Text
              fontSize="sm"
              fontWeight="600"
              color={changed ? "orange.600" : "gray.500"}
            >
              {section === "ingredients" ? "Ingredient" : "Step"} {rowIndex + 1}
            </Text>
            <Textarea
              value={row}
              onChange={(event) => {
                const nextRows = [...rows];
                nextRows[rowIndex] = event.target.value;
                onChangeRows(nextRows);
              }}
              className="recipeDetailCard__editor"
              minH="unset"
              resize="vertical"
            />
          </Stack>
        );
      })}
    </Stack>
  );
}
