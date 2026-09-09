import { apiRequest } from "./apiClient";
import type { ExtractApiResponse, ImportJobResponse } from "../types/api";

// A per-tab secret keeps public Instagram jobs scoped to their original visitor.
let parserSession: string | undefined;
function parserHeaders(): Record<string, string> {
  parserSession ??= crypto.randomUUID();
  return { "X-Parser-Session": parserSession };
}

export function extractRecipe(url: string): Promise<ExtractApiResponse> {
  return apiRequest<ExtractApiResponse>("/api/extract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...parserHeaders(),
    },
    body: JSON.stringify({ url }),
  });
}

export function advanceImportJob(jobId: string): Promise<ImportJobResponse> {
  return apiRequest<ImportJobResponse>(
    `/api/extract/jobs/${encodeURIComponent(jobId)}/advance`,
    { method: "POST", headers: parserHeaders() },
  );
}
