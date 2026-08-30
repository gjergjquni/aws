export const STORAGE_KEYS = {
  theme: "aegis-theme",
  sidebarCollapsed: "aegis-sidebar-collapsed",
  recentSearches: "aegis-recent-searches",
  authSession: "aegis-auth-session",
  liveCases: "aegis-live-cases",
} as const;

export const APP_NAME = "Aegis Swarm";

/**
 * Same-origin proxy. Locally Vite forwards this; on Vercel, vercel.json
 * rewrites it to API Gateway. Calling API Gateway from the browser fails
 * CORS preflight (OPTIONS /uploads is 403).
 */
export const BACKEND_BASE = "/api/backend";

/** Poll interval for GET /analyze/{case_id} while a case is processing. */
export const CASE_POLL_INTERVAL_MS = 2000;

/** Abort JSON API calls if the backend does not answer in time. */
export const API_TIMEOUT_MS = 25_000;

/** Evidence PUT can be slower than JSON calls. */
export const UPLOAD_TIMEOUT_MS = 60_000;

/** POST /claims waits on S3 verify + Aegis accept. */
export const CLAIMS_TIMEOUT_MS = 55_000;

export const MAX_RECENT_SEARCHES = 5;
