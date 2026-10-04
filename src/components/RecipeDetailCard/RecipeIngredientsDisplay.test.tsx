import { Button, ChakraProvider, Stack } from "@chakra-ui/react";
import { render, screen, fireEvent } from "@testing-library/react";
import { useEffect, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { resolveRows } from "../../utils/recipeOverrides";
import { RecipeIngredientsDisplay } from "./RecipeIngredientsDisplay";

const rows = resolveRows(["1 cup sugar", "2 cups flour"], [
  { source: 0, text: "1 cup brown sugar" },
  { source: 1, text: null },
]);

describe("RecipeIngredientsDisplay", () => {
  it("does not remount when a parent rerenders", () => {
    const onMount = vi.fn();

    function TrackedIngredients() {
      useEffect(() => {
        onMount();
      }, []);

      return (
        <RecipeIngredientsDisplay
          visibleRows={rows}
          visibleSections={[{ title: "Batter", rows }]}
          scaleFactor={1}
        />
      );
    }

    function TestHarness() {
      const [count, setCount] = useState(0);

      return (
        <ChakraProvider theme={chakraTheme}>
          <Stack>
            <Button onClick={() => setCount((value) => value + 1)}>
              Rerender {count}
            </Button>
            <TrackedIngredients />
          </Stack>
        </ChakraProvider>
      );
    }

    render(<TestHarness />);
    fireEvent.click(screen.getByRole("button", { name: /rerender/i }));

    expect(onMount).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Batter")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("1 cup brown sugar");
  });
});
