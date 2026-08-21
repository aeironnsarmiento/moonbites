import { apiRequest } from "./apiClient";
import type { ExtractApiResponse, ImportJobResponse } from "../types/api";

export function extractRecipe(url: string): Promise<ExtractApiResponse> {
  return apiRequest<ExtractApiResponse>("/api/extract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });
}

export function advanceImportJob(jobId: string): Promise<ImportJobResponse> {
  return apiRequest<ImportJobResponse>(
    `/api/extract/jobs/${encodeURIComponent(jobId)}/advance`,
    { method: "POST" },
  );
}
