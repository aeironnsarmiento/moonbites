import { ChakraProvider } from "@chakra-ui/react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { NutritionFactsPanel } from "./NutritionFactsPanel";

function renderPanel(
  props: Partial<React.ComponentProps<typeof NutritionFactsPanel>> = {},
) {
  const defaultProps: React.ComponentProps<typeof NutritionFactsPanel> = {
    nutrition: {
      calories: "320 kcal",
      protein: "12 g",
      sodium: "480 mg",
    },
    recordServings: 4,
    currentServings: 4,
  };

  render(
    <ChakraProvider theme={chakraTheme}>
      <NutritionFactsPanel {...defaultProps} {...props} />
    </ChakraProvider>,
  );
}

describe("NutritionFactsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows an honest empty state when the source provided no nutrition", () => {
    renderPanel({ nutrition: null });

    expect(
      screen.getByText("The source did not provide nutrition information."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nutrition" })).toBeInTheDocument();
  });

  it("renders canonical nutrients in order with normalized units", () => {
    renderPanel();

    const terms = screen
      .getAllByRole("term")
      .map((element) => element.textContent);
    expect(terms).toEqual(["Calories", "Protein", "Sodium"]);
    expect(screen.getByText("320 kcal")).toBeInTheDocument();
    expect(screen.getByText("12 g")).toBeInTheDocument();
    expect(screen.getByText("480 mg")).toBeInTheDocument();
    expect(screen.getByText("Per serving")).toBeInTheDocument();
  });

  it("shows calculated batch totals for the selected serving count while per-serving values stay fixed", () => {
    renderPanel({ currentServings: 8 });

    fireEvent.click(
      screen.getByRole("button", { name: /batch totals for 8 servings/i }),
    );

    expect(screen.getByText("2560 kcal")).toBeInTheDocument();
    expect(screen.getByText("96 g")).toBeInTheDocument();
    expect(screen.getByText("3840 mg")).toBeInTheDocument();
    expect(screen.getByText("320 kcal")).toBeInTheDocument();
    expect(screen.getByText(/calculated from per-serving values/i)).toBeInTheDocument();
  });

  it("renders unparseable values verbatim and keeps them out of batch totals", () => {
    renderPanel({
      nutrition: { calories: "320 kcal", sodium: "a pinch of sodium" },
      currentServings: 8,
    });

    expect(screen.getByText("a pinch of sodium")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /batch totals for 8 servings/i }),
    );

    expect(screen.getByText("2560 kcal")).toBeInTheDocument();
    expect(screen.getAllByText(/sodium/i)).toHaveLength(2);
  });

  it("labels values as provided and hides the batch view without a per-serving basis", () => {
    renderPanel({ recordServings: null });

    expect(screen.getByText("As provided by the source")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /batch totals/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the serving size when the source provides one", () => {
    renderPanel({
      nutrition: { calories: "320 kcal", servingSize: "1 slice" },
      recordServings: null,
    });

    expect(screen.getByText("Serving size: 1 slice")).toBeInTheDocument();
    expect(screen.getByText("Per serving")).toBeInTheDocument();
  });
});
