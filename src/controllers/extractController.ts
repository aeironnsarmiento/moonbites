import { extractRecipe } from "../services/extractService";
import type { ExtractResponse } from "../types/api";

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
  const importMessage =
    recipeTotal > 0
      ? `Found ${recipeTotal} unique recipe${recipeTotal === 1 ? "" : "s"}.`
      : "No Recipe objects were found on that page, so nothing was saved.";

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
