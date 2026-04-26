import { beforeEach, describe, expect, it, vi } from "vitest";

import { getCurrentAccessToken } from "./supabaseClient";
import { apiRequest } from "./apiClient";

vi.mock("./supabaseClient", () => ({
  getCurrentAccessToken: vi.fn(),
}));

const mockedGetCurrentAccessToken = vi.mocked(getCurrentAccessToken);

describe("apiRequest", () => {
  beforeEach(() => {
    mockedGetCurrentAccessToken.mockResolvedValue(null);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ ok: true }),
      }),
    );
  });

  it("adds bearer token when Supabase session exists", async () => {
    mockedGetCurrentAccessToken.mockResolvedValue("session-token");

    await apiRequest<{ ok: boolean }>("/api/test");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = new Headers(init?.headers);

    expect(headers.get("Authorization")).toBe("Bearer session-token");
  });
});
