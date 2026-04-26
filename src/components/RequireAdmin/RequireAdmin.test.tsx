import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "../../hooks/useAuth";
import { RequireAdmin } from "./RequireAdmin";

vi.mock("../../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function renderProtectedRoute() {
  render(
    <MemoryRouter initialEntries={["/recipes/create"]}>
      <Routes>
        <Route
          path="/recipes/create"
          element={
            <RequireAdmin>
              <div>Protected create page</div>
            </RequireAdmin>
          }
        />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAdmin", () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      userEmail: null,
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
    });
  });

  it("redirects guests to login", () => {
    renderProtectedRoute();

    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Protected create page")).not.toBeInTheDocument();
  });

  it("renders children for admins", () => {
    mockedUseAuth.mockReturnValue({
      isAdmin: true,
      isLoading: false,
      userEmail: "admin@example.com",
      signInWithGoogle: vi.fn(),
      signOut: vi.fn(),
    });

    renderProtectedRoute();

    expect(screen.getByText("Protected create page")).toBeInTheDocument();
  });
});
