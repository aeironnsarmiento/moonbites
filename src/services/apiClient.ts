import type { ApiErrorResponse } from "../types/api";
import { getCurrentAccessToken } from "./supabaseClient";

const DEFAULT_API_BASE_URL = import.meta.env.PROD ? "/_/backend" : "";
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/$/, "");

/** A failed API call, with the backend's machine-readable `detail.code` when it sent one. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function extractApiErrorCode(detail: unknown): string | null {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const code = (detail as { code?: unknown }).code;
    return typeof code === "string" ? code : null;
  }

  return null;
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

function extractApiErrorMessage(detail: unknown): string | null {
  if (typeof detail === "string") {
    const normalized = detail.trim();
    return normalized || null;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => extractApiErrorMessage(item))
      .filter((message): message is string => Boolean(message));

    return messages.length > 0 ? messages.join(" ") : null;
  }

  if (detail && typeof detail === "object") {
    const record = detail as {
      detail?: unknown;
      loc?: unknown;
      message?: unknown;
      msg?: unknown;
    };

    const nestedMessage = extractApiErrorMessage(record.detail);
    if (nestedMessage) {
      return nestedMessage;
    }

    const baseMessage =
      typeof record.msg === "string"
        ? record.msg.trim()
        : typeof record.message === "string"
          ? record.message.trim()
          : "";

    if (!baseMessage) {
      return null;
    }

    const location = Array.isArray(record.loc)
      ? record.loc
          .filter(
            (part): part is string | number =>
              (typeof part === "string" || typeof part === "number") &&
              part !== "body",
          )
          .join(".")
      : "";

    return location ? `${location}: ${baseMessage}` : baseMessage;
  }

  return null;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const requestUrl = buildApiUrl(path);
  const accessToken = await getCurrentAccessToken();
  const headers = new Headers(init?.headers);

  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(requestUrl, {
    ...init,
    headers,
  });
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json")
    ? ((await response.json().catch(() => null)) as T | ApiErrorResponse | null)
    : null;

  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data ? data.detail : undefined;
    const message =
      extractApiErrorMessage(detail) ??
      `API request failed with status ${response.status}.`;
    throw new ApiError(message, response.status, extractApiErrorCode(detail));
  }

  if (data == null) {
    throw new Error(
      `API returned an empty or non-JSON response for ${requestUrl}.`,
    );
  }

  return data as T;
}
