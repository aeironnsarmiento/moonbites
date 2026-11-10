import { render, screen, waitFor } from "@testing-library/react";
import { useContext } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../../auth/authContext";
import { getSupabaseClient } from "../../services/supabaseClient";
import { AuthProvider } from "./AuthProvider";

vi.mock("../../services/supabaseClient", () => ({
  getSupabaseClient: vi.fn(),
}));

const mockedGetSupabaseClient = vi.mocked(getSupabaseClient);

function AuthState() {
  const auth = useContext(AuthContext);
  return (
    <div>
      {auth?.isLoading ? "loading" : "ready"}:{auth?.isAdmin ? "admin" : "guest"}
    </div>
  );
}

function fakeSupabase(getSession: () => Promise<unknown>) {
  return {
    auth: {
      getSession,
      onAuthStateChange: () => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      }),
    },
  } as unknown as ReturnType<typeof getSupabaseClient>;
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    mockedGetSupabaseClient.mockReset();
  });

  it("finishes loading as a guest when the auth check cannot reach the backend", async () => {
    mockedGetSupabaseClient.mockReturnValue(
      fakeSupabase(() =>
        Promise.resolve({ data: { session: { access_token: "token" } } }),
      ),
    );
    vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("ready:guest")).toBeInTheDocument());
  });

  it("finishes loading when reading the stored session fails", async () => {
    mockedGetSupabaseClient.mockReturnValue(
      fakeSupabase(() => Promise.reject(new Error("storage unavailable"))),
    );

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("ready:guest")).toBeInTheDocument());
  });

  it("marks the user as admin when the backend confirms the email", async () => {
    mockedGetSupabaseClient.mockReturnValue(
      fakeSupabase(() =>
        Promise.resolve({ data: { session: { access_token: "token" } } }),
      ),
    );
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ email: "admin@example.com" }), { status: 200 }),
    );

    render(
      <AuthProvider>
        <AuthState />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("ready:admin")).toBeInTheDocument());
  });
});
