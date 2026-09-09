import { beforeEach, expect, it, vi } from "vitest";
import { apiRequest } from "./apiClient";
import { advanceImportJob, extractRecipe } from "./extractService";

vi.mock("./apiClient", () => ({ apiRequest: vi.fn().mockResolvedValue({}) }));
beforeEach(() => vi.clearAllMocks());

it("uses the same private session for submission and job advancement", async () => {
  await extractRecipe("https://example.com/recipe");
  await advanceImportJob("job-1");
  const calls = vi.mocked(apiRequest).mock.calls;
  const submissionHeaders = new Headers(calls[0][1]?.headers);
  const advanceHeaders = new Headers(calls[1][1]?.headers);
  const session = submissionHeaders.get("X-Parser-Session");
  expect(session).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(advanceHeaders.get("X-Parser-Session")).toBe(session);
});
