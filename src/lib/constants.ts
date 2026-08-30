export const STORAGE_KEYS = {
  theme: "aegis-theme",
  sidebarCollapsed: "aegis-sidebar-collapsed",
  recentSearches: "aegis-recent-searches",
  authSession: "aegis-auth-session",
  liveCases: "aegis-live-cases",
} as const;

export const APP_NAME = "Aegis Swarm";

/** SAM API Gateway. Production builds call this directly so every Vercel URL works. */
export const AWS_BACKEND_URL =
  "https://q7phgdg1m5.execute-api.us-east-1.amazonaws.com/Prod";

/**
 * Local Vite proxies /api/backend. Hosted builds (any *.vercel.app, including
 * preview URLs) talk to API Gateway — Vite catch-all API routes 404 on Vercel.
 */
export const BACKEND_BASE = import.meta.env.DEV
  ? "/api/backend"
  : AWS_BACKEND_URL;

/** Poll interval for GET /analyze/{case_id} while a case is processing. */
export const CASE_POLL_INTERVAL_MS = 2000;

/** Abort JSON API calls if the backend does not answer in time. */
export const API_TIMEOUT_MS = 25_000;

/** Evidence PUT can be slower than JSON calls. */
export const UPLOAD_TIMEOUT_MS = 60_000;

/** POST /claims waits on S3 verify + Aegis accept. */
export const CLAIMS_TIMEOUT_MS = 55_000;

export const MAX_RECENT_SEARCHES = 5;
