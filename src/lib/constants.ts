export const STORAGE_KEYS = {
  theme: "aegis-theme",
  sidebarCollapsed: "aegis-sidebar-collapsed",
  recentSearches: "aegis-recent-searches",
  authSession: "aegis-auth-session",
  liveCases: "aegis-live-cases",
} as const;

export const APP_NAME = "Aegis Swarm";

/**
 * S3 bucket the Agent API reads evidence from. POST /analyze validates that
 * s3_url points at this bucket (not a secret — it is part of the API
 * contract, see backend/src/remote.py).
 */
export const AGENT_EVIDENCE_BUCKET = "aws-s3-877791042657-us-east-1-an";

/** Poll interval for GET /analyze/{case_id} while a case is processing. */
export const CASE_POLL_INTERVAL_MS = 2000;

export const MAX_RECENT_SEARCHES = 5;
