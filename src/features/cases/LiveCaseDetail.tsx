import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import LoadingState from "@/components/LoadingState";
import { useCaseStatus } from "@/hooks/useCaseStatus";
import { caseRegistry } from "@/services/caseRegistry";
import { claimsApi } from "@/services/claimsApi";
import type { CaseStatusResponse, ReviewCase, StoredCase } from "@/types";
import { categoryLabel, formatCurrency } from "@/utils/labels";

// ── workflow timeline ────────────────────────────────────────────────────
//
// Every step state below is derived from real data only:
//   - client-observed events (this app performed the upload / submit)
//   - the latest real response of GET /analyze/{case_id}
// Nothing is simulated with timers; while the backend only reports
// "processing" the intermediate agent steps stay in a waiting state.

type StepState = "done" | "active" | "waiting" | "error" | "review" | "skipped";

interface WorkflowStep {
  key: string;
  label: string;
  description: string;
  state: StepState;
  timestamp?: string | null;
}

function formatTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

function buildWorkflowSteps(
  stored: StoredCase | null,
  status: CaseStatusResponse | null,
  pollError: string | null,
): WorkflowStep[] {
  const s = status?.status;
  const processing = s === "processing";
  const terminal = Boolean(s) && !processing;
  const failed = s === "failed";
  const pendingReview = s === "pending_human_review";
  const humanDecided = Boolean(status?.human_decision);
  const completed = s === "completed";

  const steps: WorkflowStep[] = [];

  steps.push({
    key: "submitted",
    label: "Case submitted",
    description: stored
      ? "Claim accepted by the backend (POST /analyze, HTTP 202)"
      : "Claim registered by the backend",
    state: "done",
    timestamp: stored?.submittedAt,
  });

  if (stored) {
    steps.push(
      stored.s3Key
        ? {
            key: "s3",
            label: "Evidence uploaded to S3",
            description: `Stored as ${stored.s3Key}`,
            state: "done",
            timestamp: stored.uploadCompletedAt,
          }
        : {
            key: "s3",
            label: "Evidence upload",
            description: "No image was submitted with this claim",
            state: "skipped",
          },
    );
  }

  steps.push({
    key: "agents",
    label: "Agent 1 + Agent 3 analysis",
    description: processing
      ? status?.message ??
        "Visual evidence and claim intelligence agents are running in parallel"
      : terminal && !failed
      ? "Agent analysis finished"
      : failed
      ? "Analysis failed"
      : "Waiting for backend status…",
    state: failed ? "error" : terminal ? "done" : processing ? "active" : "waiting",
  });

  steps.push({
    key: "agent6",
    label: "Agent 6 — final decision",
    description:
      terminal && !failed
        ? status?.decision
          ? `Orchestrator decision: ${status.decision}`
          : "Orchestrator decision generated"
        : "Orchestrator combines agent results into a decision",
    state: failed ? "error" : terminal ? "done" : "waiting",
  });

  if (pendingReview || humanDecided) {
    steps.push({
      key: "human",
      label: "Human review",
      description: humanDecided
        ? `Human decision recorded: ${status?.human_decision}`
        : status?.message ?? "This case requires human review",
      state: humanDecided ? "done" : "review",
    });
  }

  steps.push({
    key: "complete",
    label: "Workflow completed",
    description: completed
      ? "Case closed with a final decision"
      : failed
      ? "Workflow ended with a failure"
      : "Pending",
    state: completed ? "done" : failed ? "error" : "waiting",
  });

  if (pollError) {
    steps.push({
      key: "poll-error",
      label: "Status updates interrupted",
      description: pollError,
      state: "error",
    });
  }

  return steps;
}

function StepIndicator({ state }: { state: StepState }) {
  if (state === "done") {
    return (
      <span className="w-6 h-6 rounded-full bg-green-500 text-white flex items-center justify-center flex-shrink-0">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
    );
  }
  if (state === "active") {
    return (
      <span className="w-6 h-6 rounded-full bg-[var(--primary)] text-white flex items-center justify-center flex-shrink-0">
        <svg className="animate-spin" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.6" strokeDasharray="18 10" />
        </svg>
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center flex-shrink-0 text-[10px] font-bold">✕</span>
    );
  }
  if (state === "review") {
    return (
      <span className="w-6 h-6 rounded-full bg-amber-500 text-white flex items-center justify-center flex-shrink-0 text-[10px] font-bold animate-pulse">!</span>
    );
  }
  if (state === "skipped") {
    return (
      <span className="w-6 h-6 rounded-full bg-[var(--muted)] text-[var(--muted-foreground)] flex items-center justify-center flex-shrink-0 text-[10px]">—</span>
    );
  }
  return (
    <span className="w-6 h-6 rounded-full border-2 border-[var(--border)] bg-[var(--card)] flex items-center justify-center flex-shrink-0">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--border)]" />
    </span>
  );
}

function WorkflowTimeline({ steps }: { steps: WorkflowStep[] }) {
  return (
    <div className="relative">
      <div className="absolute left-3 top-2 bottom-2 w-px bg-[var(--border)]" />
      <div className="space-y-5">
        {steps.map((step) => {
          const time = formatTime(step.timestamp);
          return (
            <div key={step.key} className="flex items-start gap-4">
              <div className="relative z-10">
                <StepIndicator state={step.state} />
              </div>
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-center gap-3 flex-wrap">
                  <span
                    className={`text-sm font-medium ${
                      step.state === "waiting" || step.state === "skipped"
                        ? "text-[var(--muted-foreground)]"
                        : step.state === "error"
                        ? "text-red-600 dark:text-red-400"
                        : step.state === "review"
                        ? "text-amber-700 dark:text-amber-400"
                        : "text-[var(--foreground)]"
                    }`}
                  >
                    {step.label}
                  </span>
                  {time && (
                    <span className="font-mono text-[10px] text-[var(--muted-foreground)]">{time}</span>
                  )}
                </div>
                <div className="text-xs text-[var(--muted-foreground)] mt-0.5 break-words">
                  {step.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── final result ─────────────────────────────────────────────────────────

function ResultCard({
  status,
  onRefresh,
}: {
  status: CaseStatusResponse | null;
  onRefresh: () => void;
}) {
  const s = status?.status;

  if (!status || s === "processing") {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
        <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">Final Result</div>
        <div className="flex items-center gap-3">
          <svg className="animate-spin text-[var(--primary)] flex-shrink-0" width="20" height="20" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" strokeDasharray="40 20" />
          </svg>
          <div>
            <div className="text-sm font-medium text-[var(--foreground)]">Analysis in progress</div>
            <div className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Polling the backend every 2 seconds for the real case status.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const confidencePct =
    typeof status.confidence === "number"
      ? `${Math.round(status.confidence * 100)}%`
      : null;

  if (s === "pending_human_review") {
    return (
      <div className="bg-[var(--card)] border border-amber-300 dark:border-amber-700 rounded-[var(--radius-lg)] p-5">
        <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Final Result</div>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400 text-sm font-bold tracking-wide mb-3">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          HUMAN REVIEW REQUIRED
        </div>
        {confidencePct && (
          <div className="flex justify-between text-xs mb-2">
            <span className="text-[var(--muted-foreground)]">AI confidence</span>
            <span className="font-mono font-semibold text-[var(--foreground)]">{confidencePct}</span>
          </div>
        )}
        {status.reason && (
          <p className="text-xs text-[var(--muted-foreground)] leading-relaxed border-t border-[var(--border)] pt-3 mt-1">
            {status.reason}
          </p>
        )}
        <div className="flex items-center gap-2 mt-4">
          <Link
            to="/admin"
            className="px-3 py-1.5 text-xs font-semibold rounded-[var(--radius)] bg-[var(--primary)] text-white hover:opacity-90"
          >
            Open Admin Review →
          </Link>
          <button
            type="button"
            onClick={onRefresh}
            className="px-3 py-1.5 text-xs font-medium rounded-[var(--radius)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          >
            Refresh status
          </button>
        </div>
      </div>
    );
  }

  if (s === "completed") {
    const fraud = status.decision === "FRAUD";
    return (
      <div className={`bg-[var(--card)] border rounded-[var(--radius-lg)] p-5 ${fraud ? "border-red-300 dark:border-red-800" : "border-green-300 dark:border-green-800"}`}>
        <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Final Result</div>
        <div
          className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-bold tracking-wide mb-3 ${
            fraud
              ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400"
              : "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${fraud ? "bg-red-500" : "bg-green-500"}`} />
          {status.decision ?? "—"}
        </div>
        <div className="space-y-2 text-xs">
          {confidencePct && (
            <div className="flex justify-between">
              <span className="text-[var(--muted-foreground)]">Confidence</span>
              <span className="font-mono font-semibold text-[var(--foreground)]">{confidencePct}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-[var(--muted-foreground)]">Status</span>
            <span className="font-medium text-green-600 dark:text-green-400">Completed</span>
          </div>
          {status.human_decision && (
            <div className="flex justify-between">
              <span className="text-[var(--muted-foreground)]">Human decision</span>
              <span className="font-mono font-semibold text-[var(--foreground)]">{status.human_decision}</span>
            </div>
          )}
        </div>
        {status.reason && (
          <p className="text-xs text-[var(--muted-foreground)] leading-relaxed border-t border-[var(--border)] pt-3 mt-3">
            {status.reason}
          </p>
        )}
      </div>
    );
  }

  // failed or an unknown terminal state
  return (
    <div className="bg-[var(--card)] border border-red-300 dark:border-red-800 rounded-[var(--radius-lg)] p-5">
      <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Final Result</div>
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 text-sm font-bold tracking-wide mb-3">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        {s === "failed" ? "FAILED" : (s ?? "UNKNOWN").toUpperCase()}
      </div>
      <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
        {status.reason ?? status.message ?? "The workflow did not complete successfully."}
      </p>
      <button
        type="button"
        onClick={onRefresh}
        className="mt-4 px-3 py-1.5 text-xs font-medium rounded-[var(--radius)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
      >
        Refresh status
      </button>
    </div>
  );
}

// ── agent results (real data from the pending-review record) ────────────

function AgentResults({ review }: { review: ReviewCase }) {
  const a1 = review.agent_1_result;
  const a3 = review.agent_3_result;
  const a6 = review.agent_6_result;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
      <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">
        Agent Results
      </div>
      <div className="divide-y divide-[var(--border)]">
        <div className="pb-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-[var(--foreground)]">Agent 1 — Visual Evidence</div>
            {a1?.status === "ok" ? (
              <span className="text-xs font-mono text-green-600 dark:text-green-400">ok</span>
            ) : (
              <span className="text-xs font-mono text-red-600 dark:text-red-400">{a1?.status ?? "n/a"}</span>
            )}
          </div>
          {a1?.error && (
            <p className="text-xs text-[var(--muted-foreground)] mt-1">{a1.error}</p>
          )}
          {a1?.result?.explanation && (
            <p className="text-xs text-[var(--muted-foreground)] mt-1 leading-relaxed">{a1.result.explanation}</p>
          )}
        </div>

        <div className="py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-[var(--foreground)]">Agent 3 — Claim Intelligence</div>
            {typeof a3?.result?.risk_score === "number" && (
              <span className="text-xs font-mono font-semibold text-[var(--foreground)]">
                risk {a3.result.risk_score}/100
              </span>
            )}
          </div>
          {a3?.result?.explanation && (
            <p className="text-xs text-[var(--muted-foreground)] mt-1 leading-relaxed">{a3.result.explanation}</p>
          )}
          {(a3?.result?.findings ?? []).length > 0 && (
            <div className="mt-2 space-y-1.5">
              {(a3?.result?.findings ?? []).map((f, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[9px]">!</span>
                  <span className="text-xs text-[var(--foreground)]">
                    {f.description}
                    {f.evidence && (
                      <span className="text-[var(--muted-foreground)]"> — {f.evidence}</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pt-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-[var(--foreground)]">Agent 6 — Orchestrator</div>
            {typeof a6?.final_score === "number" && (
              <span className="text-xs font-mono font-semibold text-[var(--foreground)]">
                score {a6.final_score}
              </span>
            )}
          </div>
          {a6?.score_breakdown?.formula && (
            <div className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">
              {a6.score_breakdown.formula}
            </div>
          )}
          {a6?.explanation && (
            <p className="text-xs text-[var(--muted-foreground)] mt-1 leading-relaxed">{a6.explanation}</p>
          )}
          {(a6?.audit ?? []).length > 0 && (
            <div className="mt-3 border-t border-[var(--border)] pt-2">
              <div className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-1.5">
                Backend audit events
              </div>
              <div className="space-y-1">
                {(a6?.audit ?? []).map((ev, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                    <span className="text-[var(--muted-foreground)]">{formatTime(ev.timestamp) ?? "—"}</span>
                    <span className="text-[var(--foreground)]">{ev.event}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── main view ────────────────────────────────────────────────────────────

export default function LiveCaseDetail({ caseId }: { caseId: string }) {
  const navigate = useNavigate();
  const { status, loading, isProcessing, notFound, error, refresh } =
    useCaseStatus(caseId);
  const [stored, setStored] = useState<StoredCase | null>(() =>
    caseRegistry.get(caseId),
  );
  const [review, setReview] = useState<ReviewCase | null>(null);

  // Refresh the local record after each poll writes to it.
  useEffect(() => {
    setStored(caseRegistry.get(caseId));
  }, [caseId, status]);

  // When the case waits for human review, fetch the real agent results
  // from the pending-reviews record.
  useEffect(() => {
    if (status?.status !== "pending_human_review") return;
    let cancelled = false;
    claimsApi
      .getPendingReviews()
      .then((cases) => {
        if (cancelled) return;
        setReview(cases.find((c) => c.case_id === caseId) ?? null);
      })
      .catch(() => {
        // Agent detail enrichment is optional; the core status is shown anyway.
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, status?.status]);

  if (loading) {
    return <LoadingState label="Loading case…" />;
  }

  if (notFound) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-24 text-center">
        <p className="text-sm font-medium text-[var(--foreground)] mb-2">Case not found on the backend</p>
        <p className="text-xs text-[var(--muted-foreground)] mb-4 font-mono">{caseId}</p>
        <Link to="/investigations" className="text-sm text-[var(--primary)] hover:underline">← Back to investigations</Link>
      </div>
    );
  }

  if (!status && error) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-24 text-center px-6">
        <p className="text-sm font-medium text-[var(--foreground)] mb-2">Could not load case status</p>
        <p className="text-xs text-[var(--muted-foreground)] mb-4 max-w-sm">{error}</p>
        <button
          type="button"
          onClick={refresh}
          className="px-4 py-2 text-sm font-semibold rounded-[var(--radius)] bg-[var(--primary)] text-white hover:opacity-90"
        >
          Retry
        </button>
      </div>
    );
  }

  const steps = buildWorkflowSteps(stored, status, error);

  return (
    <div className="px-6 py-6 max-w-[1200px] mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] mb-4">
        <button onClick={() => navigate('/investigations')} className="hover:text-[var(--foreground)] transition-colors">Investigations</button>
        <span>/</span>
        <span className="font-mono text-[var(--foreground)]">{caseId}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h2 className="text-xl font-semibold text-[var(--foreground)]">Investigation</h2>
            <span className="font-mono text-xl font-semibold text-[var(--primary)]">{caseId}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)] flex-wrap">
            {stored?.category && (
              <>
                <span className="capitalize">{categoryLabel(stored.category)}</span>
                <span className="opacity-40">·</span>
              </>
            )}
            {typeof stored?.orderValueUsd === "number" && (
              <>
                <span className="font-mono">{formatCurrency(stored.orderValueUsd)}</span>
                <span className="opacity-40">·</span>
              </>
            )}
            <span>Live backend case</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isProcessing ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              Processing
            </span>
          ) : status?.status === "pending_human_review" ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Pending Human Review
            </span>
          ) : status?.status === "completed" ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              Completed
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              {status?.status ?? "Unknown"}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left column — workflow */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
            <div className="flex items-center justify-between mb-5">
              <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">
                Workflow Progress
              </div>
              {isProcessing && (
                <span className="text-[10px] text-[var(--muted-foreground)] font-mono">
                  polling every 2s
                </span>
              )}
            </div>
            <WorkflowTimeline steps={steps} />
          </div>

          {review && <AgentResults review={review} />}
        </div>

        {/* Right column — result + claim info */}
        <div className="space-y-4">
          <ResultCard status={status} onRefresh={refresh} />

          {stored && (
            <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
              <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Claim Details</div>
              <div className="space-y-2 text-xs mb-3">
                {stored.category && (
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Category</span>
                    <span className="font-medium text-[var(--foreground)]">{categoryLabel(stored.category)}</span>
                  </div>
                )}
                {typeof stored.orderValueUsd === "number" && (
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Order value</span>
                    <span className="font-mono font-medium text-[var(--foreground)]">{formatCurrency(stored.orderValueUsd)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-[var(--muted-foreground)]">Evidence image</span>
                  <span className="font-mono font-medium text-[var(--foreground)] truncate max-w-[55%]" title={stored.imageName ?? undefined}>
                    {stored.imageName ?? "None"}
                  </span>
                </div>
              </div>
              <div className="p-3 bg-[var(--muted)] rounded-[var(--radius)] border-l-2 border-[var(--primary)]">
                <div className="text-[10px] text-[var(--muted-foreground)] mb-1">Customer explanation</div>
                <p className="text-xs text-[var(--foreground)] italic leading-relaxed">"{stored.message}"</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
