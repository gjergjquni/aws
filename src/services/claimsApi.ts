import {
  API_TIMEOUT_MS,
  BACKEND_BASE,
  CLAIMS_TIMEOUT_MS,
  UPLOAD_TIMEOUT_MS,
} from "@/lib/constants";
import type {
  AnalyzeSubmitResponse,
  CaseStatusResponse,
  CreateCaseInput,
  PendingReviewsResponse,
  ReviewCase,
  ReviewDecision,
  ReviewDecisionResponse,
  UploadTicket,
} from "@/types";
import { validateEvidenceFile } from "@/utils/evidence";

// Evidence PUTs go through /api/evidence so browser CORS does not block S3.
const EVIDENCE_PROXY_BASE = "/api/evidence";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const err = (payload as { error?: unknown }).error;
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const message = (err as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  const message = (payload as { message?: unknown }).message;
  return typeof message === "string" ? message : null;
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

function mergeAbortSignals(
  timeoutMs: number,
  userSignal?: AbortSignal,
): { signal: AbortSignal; cancelTimeout: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const onUserAbort = () => controller.abort();
  if (userSignal) {
    if (userSignal.aborted) controller.abort();
    else userSignal.addEventListener("abort", onUserAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cancelTimeout: () => {
      clearTimeout(timer);
      userSignal?.removeEventListener("abort", onUserAbort);
    },
  };
}

async function request<T>(
  url: string,
  init?: RequestInit,
  timeoutMs: number = API_TIMEOUT_MS,
): Promise<T> {
  const { signal, cancelTimeout } = mergeAbortSignals(
    timeoutMs,
    init?.signal ?? undefined,
  );
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal });
  } catch (err) {
    if (isAbortError(err)) {
      throw new ApiError(
        init?.signal?.aborted
          ? "Submission cancelled."
          : "Request timed out. The backend did not respond.",
        0,
      );
    }
    throw new ApiError("Network error — could not reach the backend.", 0);
  } finally {
    cancelTimeout();
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    if (response.ok) {
      throw new ApiError("Invalid response from the backend.", response.status);
    }
  }

  if (!response.ok) {
    const message =
      extractErrorMessage(payload) ??
      `Request failed with status ${response.status}.`;
    throw new ApiError(message, response.status);
  }

  return payload as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function pickString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return undefined;
}

function pickNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return undefined;
}

/**
 * Map a DynamoDB claim record (GET /claims/{id}) into the shape the
 * live case UI expects from GET /analyze/{id}.
 */
function mapClaimRecordToStatus(
  item: Record<string, unknown>,
  fallbackId: string,
): CaseStatusResponse {
  const orch = asRecord(item.orchestrator_result);
  const orchStatus = pickString(orch.status);
  const storedStatus = pickString(item.status);
  const decision = pickString(item.decision, orch.decision);

  let status: string;
  if (
    orchStatus === "processing" ||
    orchStatus === "completed" ||
    orchStatus === "pending_human_review" ||
    orchStatus === "failed"
  ) {
    status = orchStatus;
  } else if (storedStatus === "pending" || item.requires_human_review === true) {
    status = "pending_human_review";
  } else if (
    storedStatus === "approved" ||
    storedStatus === "rejected" ||
    decision === "FRAUD" ||
    decision === "NOT_FRAUD"
  ) {
    status = "completed";
  } else {
    status = "processing";
  }

  return {
    status,
    case_id:
      pickString(item.case_id, item.claim_id, orch.case_id) ?? fallbackId,
    decision,
    confidence: pickNumber(item.confidence, orch.confidence),
    reason: pickString(item.explanation, orch.reason, orch.message),
    requires_human_review: Boolean(item.requires_human_review),
    human_decision:
      pickString(item.human_decision, orch.human_decision) ?? null,
    message: pickString(orch.message, item.explanation),
  };
}

function mapClaimRecordToReview(item: Record<string, unknown>): ReviewCase {
  const orch = asRecord(item.orchestrator_result);
  return {
    case_id: pickString(item.case_id, item.claim_id) ?? "",
    status: pickString(item.status, orch.status),
    message: pickString(item.explanation, orch.message, orch.reason),
    s3_url: pickString(item.s3_url),
    confidence: pickNumber(item.confidence, orch.confidence),
    reason: pickString(item.explanation, orch.reason),
    created_at: pickString(item.created_at),
    human_decision: pickString(item.human_decision) ?? null,
    agent_6_result: Object.keys(orch).length
      ? (orch as ReviewCase["agent_6_result"])
      : null,
  };
}

export const claimsApi = {
  /**
   * Ask the SAM backend for a presigned S3 upload URL.
   * The backend generates the canonical object key and s3_url once.
   */
  async requestUploadUrl(
    input: {
      claimId: string;
      file: File;
    },
    signal?: AbortSignal,
  ): Promise<UploadTicket> {
    const validated = validateEvidenceFile(input.file);
    return request<UploadTicket>(
      `${BACKEND_BASE}/uploads`,
      {
        ...jsonInit("POST", {
          claim_id: input.claimId,
          content_type: validated.contentType,
          filename: input.file.name,
          content_length: input.file.size,
        }),
        signal,
      },
    );
  },

  /**
   * Upload the evidence image directly to S3 via the presigned URL.
   * The URL is routed through the local proxy so browser CORS rules
   * do not block the PUT. The PUT Content-Type must match the type
   * that was signed (ticket.content_type).
   */
  async uploadEvidenceImage(
    ticket: UploadTicket,
    file: File,
    signal?: AbortSignal,
  ): Promise<void> {
    validateEvidenceFile(file);
    const url = new URL(ticket.upload_url);
    const proxiedUrl = `${EVIDENCE_PROXY_BASE}${url.pathname}${url.search}`;
    const { signal: merged, cancelTimeout } = mergeAbortSignals(
      UPLOAD_TIMEOUT_MS,
      signal,
    );

    let response: Response;
    try {
      response = await fetch(proxiedUrl, {
        method: "PUT",
        headers: { "Content-Type": ticket.content_type },
        body: file,
        signal: merged,
      });
    } catch (err) {
      if (isAbortError(err)) {
        throw new ApiError(
          signal?.aborted
            ? "Submission cancelled."
            : "Image upload timed out.",
          0,
        );
      }
      throw new ApiError("Network error — image upload failed.", 0);
    } finally {
      cancelTimeout();
    }

    if (!response.ok) {
      throw new ApiError(
        `Image upload to S3 failed with status ${response.status}.`,
        response.status,
      );
    }
  },

  /**
   * Submit the claim to the SAM backend, which verifies the S3 object
   * and POSTs the exact ticket s3_url to Aegis. The frontend never
   * invents or rewrites the S3 location.
   */
  async createCase(
    input: CreateCaseInput,
    signal?: AbortSignal,
  ): Promise<AnalyzeSubmitResponse> {
    if (!input.s3Url) {
      throw new ApiError("An evidence image is required.", 400);
    }
    const body: Record<string, unknown> = {
      claim_id: input.claimId,
      customer_text: input.message,
      message: input.message,
      s3_url: input.s3Url,
      s3_key: input.s3Key,
    };
    if (input.productCategory) body.product_category = input.productCategory;
    if (input.orderValueUsd !== undefined) {
      body.order_value_usd = input.orderValueUsd;
    }

    return request<AnalyzeSubmitResponse>(
      `${BACKEND_BASE}/claims`,
      { ...jsonInit("POST", body), signal },
      CLAIMS_TIMEOUT_MS,
    );
  },

  /**
   * Poll the current status of a case via the SAM backend.
   * GET /analyze is preferred (live Agent API). If that 404s, fall back
   * to the DynamoDB claim record so a just-submitted case still loads.
   */
  async getCaseStatus(
    caseId: string,
    extraIds: string[] = [],
  ): Promise<CaseStatusResponse> {
    const ids = [...new Set([caseId, ...extraIds.filter(Boolean)])];
    let analyzeError: unknown;

    for (const id of ids) {
      try {
        return await request<CaseStatusResponse>(
          `${BACKEND_BASE}/analyze/${encodeURIComponent(id)}`,
        );
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) throw err;
        analyzeError = err;
      }
    }

    for (const id of ids) {
      try {
        const claim = await request<Record<string, unknown>>(
          `${BACKEND_BASE}/claims/${encodeURIComponent(id)}`,
        );
        return mapClaimRecordToStatus(claim, caseId);
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) throw err;
      }
    }

    throw analyzeError instanceof ApiError
      ? analyzeError
      : new ApiError("Case not found on the backend.", 404);
  },

  /**
   * List cases waiting for human review (Admin page).
   */
  async getPendingReviews(): Promise<ReviewCase[]> {
    try {
      const data = await request<PendingReviewsResponse>(
        `${BACKEND_BASE}/reviews/pending`,
      );
      if (data.cases?.length) return data.cases;
    } catch {
      // Agent proxy may 404; DynamoDB pending claims still show in Admin.
    }

    const fallback = await request<{ claims?: Record<string, unknown>[] }>(
      `${BACKEND_BASE}/claims/pending`,
    );
    return (fallback.claims ?? [])
      .map(mapClaimRecordToReview)
      .filter((item) => item.case_id);
  },

  /**
   * Submit the human decision for a case. The Agent API accepts
   * "FRAUD" (reject the claim) or "NOT_FRAUD" (approve the claim).
   */
  async submitReviewDecision(
    caseId: string,
    decision: ReviewDecision,
  ): Promise<ReviewDecisionResponse> {
    return request<ReviewDecisionResponse>(
      `${BACKEND_BASE}/reviews/${encodeURIComponent(caseId)}/decision`,
      jsonInit("POST", { decision }),
    );
  },
};
