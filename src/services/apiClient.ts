import type { ApiErrorResponse } from "../types/api";

const DEFAULT_API_BASE_URL = import.meta.env.PROD ? "/_/backend" : "";
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

function buildApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const requestUrl = buildApiUrl(path);
  const response = await fetch(requestUrl, init);
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? ((await response.json().catch(() => null)) as T | ApiErrorResponse | null)
    : null;

  if (!response.ok) {
    const message =
      data && typeof data === "object" && "detail" in data && data.detail
        ? data.detail
        : `API request failed with status ${response.status}.`;
    throw new Error(message);
  }

  if (data == null) {
    throw new Error(
      `API returned an empty or non-JSON response for ${requestUrl}.`,
    );
  }

  return data as T;
}
