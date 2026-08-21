import { advanceImportJob, extractRecipe } from "../services/extractService";
import type { ExtractResponse, ImportJobErrorCode } from "../types/api";

export const MIN_RETRY_AFTER_MS = 7000;

export type ImportAction =
  | "none"
  | "resume"
  | "edit-or-view"
  | "try-again"
  | "try-again-later";

export type ImportInteractionState = {
  headline: string;
  body: string;
  action: ImportAction;
};

export const PENDING_INTERACTION_STATE: ImportInteractionState = {
  headline: "Importing Reel…",
  body: "Moonbites is checking the Reel and any public recipe link.",
  action: "none",
};

export const INTERRUPTED_INTERACTION_STATE: ImportInteractionState = {
  headline: "Import paused",
  body: "The connection was interrupted. Your import can continue safely.",
  action: "resume",
};

export const NOT_RECIPE_INTERACTION_STATE: ImportInteractionState = {
  headline: "No recipe found",
  body: "Moonbites could not find one complete, confidently matching recipe.",
  action: "edit-or-view",
};

const ERROR_CODE_INTERACTION_STATE: Record<ImportJobErrorCode, ImportInteractionState> = {
  instagram_unavailable: {
    headline: "Reel unavailable",
    body: "The Reel may be private, deleted, or no longer public.",
    action: "edit-or-view",
  },
  provider_unavailable: {
    headline: "Instagram import temporarily unavailable",
    body: "The Instagram data provider cannot complete this import right now.",
    action: "try-again-later",
  },
  provider_invalid_response: {
    headline: "Instagram import temporarily unavailable",
    body: "The Instagram data provider cannot complete this import right now.",
    action: "try-again-later",
  },
  provider_timeout: {
    headline: "Import timed out",
    body: "The Reel or linked recipe took too long to resolve.",
    action: "try-again",
  },
  resolution_timeout: {
    headline: "Import timed out",
    body: "The Reel or linked recipe took too long to resolve.",
    action: "try-again",
  },
  ambiguous_external_operation: {
    headline: "Import could not be resumed safely",
    body: "Moonbites stopped rather than risk running the external operation twice.",
    action: "try-again",
  },
  job_stalled: {
    headline: "Import expired",
    body: "This import did not finish in time.",
    action: "try-again",
  },
  save_failed: {
    headline: "Recipe could not be saved",
    body: "The recipe was found but could not be saved safely.",
    action: "try-again",
  },
};

export function interactionStateForErrorCode(
  errorCode: ImportJobErrorCode,
): ImportInteractionState {
  return ERROR_CODE_INTERACTION_STATE[errorCode];
}

export function retryAfterMsFloor(value: number): number {
  return Math.max(MIN_RETRY_AFTER_MS, value);
}

export { advanceImportJob };

// type DownloadPayload = unknown[] | Record<string, unknown> | null;
//
// function buildFilename(url: string) {
//   try {
//     const hostname = new URL(url).hostname.replace(/[^a-z0-9.-]+/gi, "-");
//     return `${hostname || "ldparser"}-recipe.json`;
//   } catch {
//     return "ldparser-result.json";
//   }
// }
//
// const downloadJsonFile = (data: DownloadPayload, url: string) => {
//   const blob = new Blob([JSON.stringify(data, null, 2)], {
//     type: "application/json",
//   });
//   const downloadUrl = URL.createObjectURL(blob);
//   const link = document.createElement("a");
//
//   link.href = downloadUrl;
//   link.download = buildFilename(url);
//   document.body.appendChild(link);
//   link.click();
//   link.remove();
//   URL.revokeObjectURL(downloadUrl);
// };

export function buildExtractStatus(response: ExtractResponse) {
  const recipeTotal = response.recipes.length;
  const noRecipeMessage =
    response.parse_reason ??
    "No Recipe objects were found on that page, so nothing was saved.";
  const importMessage =
    recipeTotal > 0
      ? `Found ${recipeTotal} unique recipe${recipeTotal === 1 ? "" : "s"}.`
      : noRecipeMessage;

  const rawDatabaseMessage =
    response.database_saved &&
    response.database_message?.includes("Supabase table")
      ? "Recipe saved to your collection."
      : response.database_message;

  const databaseMessage = response.database_message
    ? ` ${rawDatabaseMessage}`
    : "";

  return `${importMessage}${databaseMessage}`;
}

export async function submitRecipeImport(url: string) {
  return extractRecipe(url);
}
