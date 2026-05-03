import { Button, ChakraProvider, Stack } from "@chakra-ui/react";
import { render, screen, fireEvent } from "@testing-library/react";
import { useEffect, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { RecipeIngredientsDisplay } from "./RecipeIngredientsDisplay";

describe("RecipeIngredientsDisplay", () => {
  it("does not remount when a parent rerenders", () => {
    const onMount = vi.fn();

    function TrackedIngredients() {
      useEffect(() => {
        onMount();
      }, []);

      return (
        <RecipeIngredientsDisplay
          originalRows={["1 cup sugar", "2 cups flour"]}
          scaledVisibleIngredients={["1 cup brown sugar", "2 cups flour"]}
          visibleIngredientSections={[
            {
              title: "Batter",
              items: ["1 cup brown sugar", "2 cups flour"],
            },
          ]}
          originalIngredientSections={[
            {
              title: "Batter",
              items: ["1 cup sugar", "2 cups flour"],
            },
          ]}
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
