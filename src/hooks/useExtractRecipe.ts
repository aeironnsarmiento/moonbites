import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  INTERRUPTED_INTERACTION_STATE,
  NOT_RECIPE_INTERACTION_STATE,
  PENDING_INTERACTION_STATE,
  advanceImportJob,
  buildExtractStatus,
  interactionStateForErrorCode,
  retryAfterMsFloor,
  submitRecipeImport,
} from "../controllers/extractController";
import { invalidateRecipeQueries } from "./recipeQueryKeys";
import { isImportJobResponse } from "../types/api";
import type { ExtractResponse } from "../types/api";

export type ExtractPhase = "idle" | "pending" | "interrupted" | "done";

function combinedMessage(state: { headline: string; body: string }): string {
  return `${state.headline} ${state.body}`;
}

export function useExtractRecipe(options: { onSaved?: () => void } = {}) {
  const { onSaved } = options;
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [phase, setPhase] = useState<ExtractPhase>("idle");
  const [isResuming, setIsResuming] = useState(false);

  const jobIdRef = useRef<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const runAdvanceRef = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const finishWithSuccess = useCallback(
    async (result: ExtractResponse) => {
      const saved = result.database_saved && result.recipes.length > 0;
      if (saved) {
        await invalidateRecipeQueries(queryClient);
      }
      if (!mountedRef.current) return;
      setStatus(buildExtractStatus(result));
      setError("");
      setPhase("done");
      jobIdRef.current = null;
      if (saved) {
        onSaved?.();
      }
    },
    [queryClient, onSaved],
  );

  const finishWithFailure = useCallback((message: string) => {
    setError(message);
    setStatus("");
    setPhase("done");
    jobIdRef.current = null;
  }, []);

  const finishWithNotRecipe = useCallback(() => {
    setError(combinedMessage(NOT_RECIPE_INTERACTION_STATE));
    setStatus("");
    setPhase("done");
    jobIdRef.current = null;
  }, []);

  const scheduleNextAdvance = useCallback(
    (delayMs: number) => {
      clearTimer();
      timerRef.current = setTimeout(() => {
        void runAdvanceRef.current();
      }, retryAfterMsFloor(delayMs));
    },
    [clearTimer],
  );

  const runAdvance = useCallback(async () => {
    const jobId = jobIdRef.current;
    if (!jobId || inFlightRef.current) {
      return;
    }
    inFlightRef.current = true;
    try {
      const response = await advanceImportJob(jobId);
      if (!mountedRef.current) return;

      if (response.kind === "pending") {
        setPhase("pending");
        setStatus(PENDING_INTERACTION_STATE.body);
        setError("");
        scheduleNextAdvance(response.retry_after_ms);
        return;
      }

      if (response.kind === "result") {
        if (response.result.parse_status === "not_recipe") {
          finishWithNotRecipe();
          return;
        }
        await finishWithSuccess(response.result);
        return;
      }

      finishWithFailure(combinedMessage(interactionStateForErrorCode(response.error_code)));
    } catch {
      if (!mountedRef.current) return;
      setPhase("interrupted");
      setStatus("");
      setError(combinedMessage(INTERRUPTED_INTERACTION_STATE));
    } finally {
      inFlightRef.current = false;
    }
  }, [finishWithNotRecipe, finishWithSuccess, finishWithFailure, scheduleNextAdvance]);

  useEffect(() => {
    runAdvanceRef.current = runAdvance;
  }, [runAdvance]);

  const resume = useCallback(async () => {
    if (!jobIdRef.current || phase !== "interrupted") {
      return;
    }
    setIsResuming(true);
    setPhase("pending");
    setStatus(PENDING_INTERACTION_STATE.body);
    setError("");
    try {
      await runAdvance();
    } finally {
      if (mountedRef.current) {
        setIsResuming(false);
      }
    }
  }, [phase, runAdvance]);

  const submitRecipe = useCallback(
    async (url: string) => {
      setIsLoading(true);
      setError("");
      setStatus("");
      setPhase("idle");
      clearTimer();
      jobIdRef.current = null;

      try {
        const response = await submitRecipeImport(url);

        if (isImportJobResponse(response)) {
          if (response.kind === "pending") {
            jobIdRef.current = response.job_id;
            setPhase("pending");
            setStatus(PENDING_INTERACTION_STATE.body);
            scheduleNextAdvance(response.retry_after_ms);
            return undefined;
          }

          if (response.kind === "result") {
            if (response.result.parse_status === "not_recipe") {
              finishWithNotRecipe();
              return undefined;
            }
            await finishWithSuccess(response.result);
            return response.result;
          }

          finishWithFailure(
            combinedMessage(interactionStateForErrorCode(response.error_code)),
          );
          return undefined;
        }

        if (response.database_saved && response.recipes.length > 0) {
          await invalidateRecipeQueries(queryClient);
          onSaved?.();
        }
        setStatus(buildExtractStatus(response));
        setPhase("done");
        return response;
      } catch (submitError) {
        const message =
          submitError instanceof Error
            ? submitError.message
            : "Something went wrong while contacting the backend.";
        setError(message);
        setPhase("done");
        return undefined;
      } finally {
        setIsLoading(false);
      }
    },
    [
      queryClient,
      clearTimer,
      scheduleNextAdvance,
      finishWithSuccess,
      finishWithFailure,
      finishWithNotRecipe,
      onSaved,
    ],
  );

  return {
    isLoading,
    error,
    status,
    phase,
    isPending: phase === "pending",
    isInterrupted: phase === "interrupted",
    isResuming,
    resume,
    submitRecipe,
  };
}
