import { ChakraProvider } from "@chakra-ui/react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chakraTheme } from "../../styles/chakraTheme";
import { useAuth } from "../../hooks/useAuth";
import { HeaderBar } from "./HeaderBar";

vi.mock("../../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

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
    mockedUseAuth.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      userEmail: null,
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
    });
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
