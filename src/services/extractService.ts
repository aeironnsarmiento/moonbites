import { apiRequest } from "./apiClient";
import type { ExtractResponse } from "../types/api";

export function extractRecipe(url: string): Promise<ExtractResponse> {
  return apiRequest<ExtractResponse>("/api/extract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });
}
