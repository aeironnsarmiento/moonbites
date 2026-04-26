import { ChakraProvider } from "@chakra-ui/react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { useAuth } from "../../hooks/useAuth";
import { useScrolled } from "../../hooks/useScrolled";
import { HeaderBar } from "./HeaderBar";

vi.mock("../../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../../hooks/useScrolled", () => ({
  useScrolled: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseScrolled = vi.mocked(useScrolled);

function renderHeader() {
  render(
    <ChakraProvider theme={chakraTheme}>
      <MemoryRouter>
        <HeaderBar />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

describe("HeaderBar", () => {
  beforeEach(() => {
    mockedUseScrolled.mockReturnValue(false);
    mockedUseAuth.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      userEmail: null,
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
    });
  });

  it("uses the page background before scrolling", () => {
    renderHeader();

    expect(document.querySelector(".headerBar")).toHaveStyle({
      backgroundColor: "var(--chakra-colors-surface-page, #f0f4e2)",
    });
  });

  it("renders the subtle fixed dot-grid texture", () => {
    renderHeader();

    const style = document.querySelector(".headerBar")?.getAttribute("style") ?? "";

    expect(style).toContain("radial-gradient(1100px 420px at 50% -160px");
    expect(style).toContain("rgba(73, 85, 54, 0.1)");
    expect(style).toContain("background-size: auto, 22px 22px");
    expect(style).toContain("background-attachment: fixed");
  });

  it("hides create recipe link for guests", () => {
    renderHeader();

    expect(screen.queryByRole("link", { name: /create recipe/i })).not.toBeInTheDocument();
  });

  it("shows create recipe link for admins", () => {
    mockedUseAuth.mockReturnValue({
      isAdmin: true,
      isLoading: false,
      userEmail: "admin@example.com",
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
    });

    renderHeader();

    expect(screen.getByRole("link", { name: /create recipe/i })).toBeInTheDocument();
  });
});
