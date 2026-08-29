// Types for the real fraud-analysis backend (Agent API + SAM backend).
// Shapes verified against live API responses — do not add fields the
// backend does not actually return.

/** Case lifecycle states returned by GET /analyze/{case_id}. */
export type CaseStatus =
  | "processing"
  | "completed"
  | "pending_human_review"
  | "failed";

/** Final decision values produced by the backend. */
export type CaseDecision = "FRAUD" | "NOT_FRAUD" | "HUMAN_REVIEW";

/** Admin review decision accepted by POST /reviews/{case_id}/decision. */
export type ReviewDecision = "FRAUD" | "NOT_FRAUD";

/** Response of POST /analyze (HTTP 202). */
export interface AnalyzeSubmitResponse {
  status: string;
  case_id: string;
  poll_url?: string;
  message?: string;
}

/** Response of GET /analyze/{case_id} (processing and terminal states). */
export interface CaseStatusResponse {
  status: CaseStatus | string;
  case_id: string;
  decision?: CaseDecision | string;
  confidence?: number;
  reason?: string;
  requires_human_review?: boolean;
  human_decision?: string | null;
  message?: string;
  poll_url?: string;
}

/** Response of POST /uploads on the SAM backend. */
export interface UploadTicket {
  upload_url: string;
  s3_key: string;
}

/** A single finding reported by the Claim Intelligence agent. */
export interface AgentFinding {
  severity?: string;
  description?: string;
  category?: string;
  evidence?: string;
  source?: string;
}

/** Agent 1 / Agent 3 result envelope inside a pending review case. */
export interface AgentResultEnvelope {
  agent?: string;
  status?: string;
  error?: string | null;
  result?: {
    risk_score?: number;
    confidence_score?: number;
    explanation?: string;
    risk_level?: string;
    recommendation?: string;
    findings?: AgentFinding[];
  } | null;
}

/** Real, timestamped audit event recorded by the Agent 6 orchestrator. */
export interface OrchestratorAuditEvent {
  event?: string;
  timestamp?: string;
  formula?: string;
  decision?: string;
  final_score?: number;
  model_id?: string;
}

/** Agent 6 (orchestrator) result inside a pending review case. */
export interface OrchestratorResult {
  decision?: string;
  confidence?: number;
  final_score?: number;
  fraud_probability?: number;
  explanation?: string;
  reason?: string;
  recommendation?: string;
  requires_human_review?: boolean;
  individual_scores?: {
    visual_evidence?: number;
    claim_intelligence?: number;
  };
  score_breakdown?: {
    formula?: string;
    visual_weight?: number;
    claim_weight?: number;
    visual_evidence_score?: number;
    claim_intelligence_score?: number;
  };
  audit?: OrchestratorAuditEvent[];
  created_at?: string;
}

/** A case awaiting human review, from GET /reviews/pending. */
export interface ReviewCase {
  case_id: string;
  status?: string;
  message?: string;
  s3_url?: string;
  confidence?: number;
  reason?: string;
  created_at?: string;
  human_decision?: string | null;
  reviewed_at?: string | null;
  agent_1_result?: AgentResultEnvelope | null;
  agent_3_result?: AgentResultEnvelope | null;
  agent_6_result?: OrchestratorResult | null;
}

/** Response of GET /reviews/pending. */
export interface PendingReviewsResponse {
  status: string;
  count: number;
  cases: ReviewCase[];
}

/** Response of POST /reviews/{case_id}/decision. */
export interface ReviewDecisionResponse {
  status: string;
  case_id: string;
  decision: string;
  review_status?: string;
  reviewed_at?: string;
  reason?: string;
}

/** Input for creating a new case via POST /analyze. */
export interface CreateCaseInput {
  message: string;
  s3Key: string | null;
  productCategory?: string;
  orderValueUsd?: number;
}

/**
 * Client-side record of a case submitted from this browser. Only contains
 * real, client-observed events (timestamps of operations this app actually
 * performed) plus the latest real backend status.
 */
export interface StoredCase {
  caseId: string;
  message: string;
  category?: string;
  orderValueUsd?: number;
  s3Key: string | null;
  imageName: string | null;
  /** When the image PUT to S3 succeeded (real client event). */
  uploadCompletedAt: string | null;
  /** When POST /analyze returned 202 (real client event). */
  submittedAt: string;
  /** Latest status observed from GET /analyze/{case_id}. */
  lastStatus?: string;
  decision?: string;
  confidence?: number;
  reason?: string;
  humanDecision?: string | null;
  /** When a terminal status was first observed by this client. */
  completedAt?: string | null;
}
