import { useCallback, useEffect, useRef, useState } from "react";
import { CASE_POLL_INTERVAL_MS } from "@/lib/constants";
import { caseRegistry } from "@/services/caseRegistry";
import { ApiError, claimsApi } from "@/services/claimsApi";
import type { CaseStatusResponse } from "@/types";

const MAX_CONSECUTIVE_ERRORS = 5;

interface UseCaseStatusResult {
  /** Latest real backend response for this case. */
  status: CaseStatusResponse | null;
  /** True while the initial fetch has not completed yet. */
  loading: boolean;
  /** True while the backend still reports "processing" (polling active). */
  isProcessing: boolean;
  /** Set when the case does not exist on the backend. */
  notFound: boolean;
  /** Set when polling had to stop because of repeated failures. */
  error: string | null;
  /** Manually re-fetch the case status (e.g. after an admin decision). */
  refresh: () => void;
}

/**
 * Polls GET /analyze/{case_id} every ~2 seconds while the case is
 * processing. Uses a setTimeout chain so requests never overlap, runs a
 * single loop per case id, stops as soon as the backend reports a
 * non-"processing" status and cleans up on unmount.
 */
export function useCaseStatus(caseId: string | undefined): UseCaseStatusResult {
  const [status, setStatus] = useState<CaseStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollGeneration, setPollGeneration] = useState(0);

  // Guards against starting a second loop for the same case (e.g. React
  // StrictMode double-invocation) — the previous effect's cleanup runs
  // first and cancels its loop.
  const activeRef = useRef<symbol | null>(null);

  const refresh = useCallback(() => {
    setError(null);
    setPollGeneration((g) => g + 1);
  }, []);

  useEffect(() => {
    if (!caseId) {
      setLoading(false);
      return;
    }

    const loopId = Symbol(caseId);
    activeRef.current = loopId;
    let timer: number | undefined;
    let consecutiveErrors = 0;

    const cancelled = () => activeRef.current !== loopId;

    const recordStatus = (res: CaseStatusResponse) => {
      const isTerminal = res.status !== "processing";
      caseRegistry.update(caseId, {
        lastStatus: res.status,
        decision: res.decision,
        confidence: res.confidence,
        reason: res.reason,
        humanDecision: res.human_decision ?? undefined,
        ...(isTerminal && !caseRegistry.get(caseId)?.completedAt
          ? { completedAt: new Date().toISOString() }
          : {}),
      });
    };

    const tick = async () => {
      try {
        const res = await claimsApi.getCaseStatus(caseId);
        if (cancelled()) return;
        consecutiveErrors = 0;
        setStatus(res);
        setError(null);
        setLoading(false);
        recordStatus(res);
        if (res.status === "processing") {
          timer = window.setTimeout(tick, CASE_POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled()) return;
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
          setLoading(false);
          return;
        }
        consecutiveErrors += 1;
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to fetch case status.",
          );
          setLoading(false);
          return;
        }
        // Transient failure — keep polling.
        timer = window.setTimeout(tick, CASE_POLL_INTERVAL_MS);
      }
    };

    setNotFound(false);
    tick();

    return () => {
      if (activeRef.current === loopId) activeRef.current = null;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [caseId, pollGeneration]);

  return {
    status,
    loading,
    isProcessing: status?.status === "processing",
    notFound,
    error,
    refresh,
  };
}
