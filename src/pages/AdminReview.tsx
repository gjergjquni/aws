import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import { claimsApi } from "@/services/claimsApi";
import type { ReviewCase, ReviewDecision } from "@/types";

function formatDateTime(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function ReviewCard({
  reviewCase,
  onDecision,
  submitting,
}: {
  reviewCase: ReviewCase;
  onDecision: (caseId: string, decision: ReviewDecision) => void;
  submitting: ReviewDecision | null;
}) {
  const a6 = reviewCase.agent_6_result;
  const a3 = reviewCase.agent_3_result;
  const confidencePct =
    typeof reviewCase.confidence === "number"
      ? `${Math.round(reviewCase.confidence * 100)}%`
      : null;
  const created = formatDateTime(reviewCase.created_at);
  const busy = submitting !== null;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              to={`/investigations/${reviewCase.case_id}`}
              className="font-mono text-sm font-semibold text-[var(--primary)] hover:underline"
            >
              {reviewCase.case_id}
            </Link>
            <span className="inline-flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Pending Human Review
            </span>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-[var(--muted-foreground)] mt-1 flex-wrap">
            {created && <span>Created {created}</span>}
            {confidencePct && (
              <>
                <span className="opacity-40">·</span>
                <span>AI confidence <span className="font-mono font-semibold">{confidencePct}</span></span>
              </>
            )}
            {typeof a6?.final_score === "number" && (
              <>
                <span className="opacity-40">·</span>
                <span>Risk score <span className="font-mono font-semibold">{a6.final_score}</span></span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecision(reviewCase.case_id, "NOT_FRAUD")}
            className="px-4 py-2 text-xs font-semibold rounded-[var(--radius)] bg-green-600 text-white hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
          >
            {submitting === "NOT_FRAUD" ? (
              <svg className="animate-spin" width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.6" strokeDasharray="18 10" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            )}
            Approve (Not Fraud)
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecision(reviewCase.case_id, "FRAUD")}
            className="px-4 py-2 text-xs font-semibold rounded-[var(--radius)] bg-red-600 text-white hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
          >
            {submitting === "FRAUD" ? (
              <svg className="animate-spin" width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.6" strokeDasharray="18 10" />
              </svg>
            ) : (
              <span className="text-[10px] leading-none">✕</span>
            )}
            Reject (Fraud)
          </button>
        </div>
      </div>

      {reviewCase.message && (
        <div className="p-3 bg-[var(--muted)] rounded-[var(--radius)] border-l-2 border-[var(--primary)] mb-3">
          <div className="text-[10px] text-[var(--muted-foreground)] mb-1">Customer message</div>
          <p className="text-xs text-[var(--foreground)] italic leading-relaxed">"{reviewCase.message}"</p>
        </div>
      )}

      {reviewCase.reason && (
        <div className="flex items-start gap-2 p-2.5 rounded-[var(--radius)] bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 mb-3">
          <span className="w-4 h-4 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[9px] font-bold">!</span>
          <p className="text-[11px] text-amber-700 dark:text-amber-400 leading-relaxed">{reviewCase.reason}</p>
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-2 text-[11px]">
        <div className="p-2.5 bg-[var(--muted)] rounded-[var(--radius)]">
          <div className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Agent 1 — Visual</div>
          {reviewCase.agent_1_result?.status === "ok" ? (
            <span className="font-mono font-semibold text-[var(--foreground)]">
              risk {a6?.individual_scores?.visual_evidence ?? "—"}
            </span>
          ) : (
            <span className="text-red-600 dark:text-red-400">
              {reviewCase.agent_1_result?.error ?? "unavailable"}
            </span>
          )}
        </div>
        <div className="p-2.5 bg-[var(--muted)] rounded-[var(--radius)]">
          <div className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Agent 3 — Claim Intelligence</div>
          <span className="font-mono font-semibold text-[var(--foreground)]">
            risk {a3?.result?.risk_score ?? a6?.individual_scores?.claim_intelligence ?? "—"}
          </span>
        </div>
        <div className="p-2.5 bg-[var(--muted)] rounded-[var(--radius)]">
          <div className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Agent 6 — Combined</div>
          <span className="font-mono font-semibold text-[var(--foreground)]">
            {a6?.score_breakdown?.formula ?? (typeof a6?.final_score === "number" ? `score ${a6.final_score}` : "—")}
          </span>
        </div>
      </div>

      {reviewCase.s3_url && (
        <div className="mt-3 text-[10px] text-[var(--muted-foreground)] font-mono truncate" title={reviewCase.s3_url}>
          Evidence: {reviewCase.s3_url}
        </div>
      )}
    </div>
  );
}

export default function AdminReview() {
  const [cases, setCases] = useState<ReviewCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<{ caseId: string; decision: ReviewDecision } | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pending = await claimsApi.getPendingReviews();
      setCases(pending);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pending reviews.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDecision = async (caseId: string, decision: ReviewDecision) => {
    if (submitting) return; // prevent duplicate clicks across cards
    setSubmitting({ caseId, decision });
    setFeedback(null);
    try {
      const result = await claimsApi.submitReviewDecision(caseId, decision);
      setCases((prev) => prev.filter((c) => c.case_id !== caseId));
      setFeedback({
        kind: "success",
        text: `Case ${caseId} resolved as ${result.decision}${
          result.review_status ? ` (${result.review_status})` : ""
        }.`,
      });
    } catch (err) {
      setFeedback({
        kind: "error",
        text:
          err instanceof Error
            ? `Decision for ${caseId} failed: ${err.message}`
            : `Decision for ${caseId} failed.`,
      });
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="px-6 py-6 max-w-[1000px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-7">
        <div>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Admin Review</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
            These cases require human review. Approve or reject to complete the workflow.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 border border-[var(--border)] text-[var(--foreground)] text-sm font-medium rounded-[var(--radius)] hover:bg-[var(--muted)] transition-colors flex-shrink-0 disabled:opacity-40"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={loading ? "animate-spin" : ""}>
            <path d="M10.5 6a4.5 4.5 0 11-1.32-3.18M10.5 1v2.5H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Refresh
        </button>
      </div>

      {feedback && (
        <div
          className={`mb-5 p-3.5 rounded-[var(--radius-lg)] border text-sm flex items-start gap-2.5 ${
            feedback.kind === "success"
              ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400"
              : "border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400"
          }`}
          role="status"
        >
          <span className="mt-0.5">
            {feedback.kind === "success" ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" /><path d="M4.5 7l1.8 1.8L9.5 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" /><path d="M5 5l4 4M9 5l-4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>
            )}
          </span>
          <span className="leading-relaxed">{feedback.text}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="ml-auto text-xs opacity-60 hover:opacity-100"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading pending reviews…" />
      ) : error ? (
        <div className="bg-[var(--card)] border border-red-300 dark:border-red-800 rounded-[var(--radius-lg)] p-8 text-center">
          <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">Failed to load pending reviews</p>
          <p className="text-xs text-[var(--muted-foreground)] mb-4">{error}</p>
          <button
            type="button"
            onClick={load}
            className="px-4 py-2 text-sm font-semibold rounded-[var(--radius)] bg-[var(--primary)] text-white hover:opacity-90"
          >
            Retry
          </button>
        </div>
      ) : cases.length === 0 ? (
        <EmptyState
          title="No cases waiting for review"
          description="When the AI cannot decide with enough confidence, cases appear here for a human decision."
        />
      ) : (
        <>
          <div className="text-xs text-[var(--muted-foreground)] mb-3">
            {cases.length} {cases.length === 1 ? "case" : "cases"} pending
          </div>
          <div className="space-y-4">
            {cases.map((c) => (
              <ReviewCard
                key={c.case_id}
                reviewCase={c}
                onDecision={handleDecision}
                submitting={
                  submitting?.caseId === c.case_id ? submitting.decision : null
                }
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
