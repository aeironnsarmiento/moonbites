import type { ApiErrorResponse } from "../types/api";

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, init);
  const data = (await response.json().catch(() => null)) as
    | T
    | ApiErrorResponse
    | null;

  if (!response.ok) {
    const message =
      data && typeof data === "object" && "detail" in data && data.detail
        ? data.detail
        : "Unexpected API error.";
    throw new Error(message);
  }

  return data as T;
}
