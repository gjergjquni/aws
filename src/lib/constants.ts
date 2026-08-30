export const STORAGE_KEYS = {
  theme: "aegis-theme",
  sidebarCollapsed: "aegis-sidebar-collapsed",
  recentSearches: "aegis-recent-searches",
  authSession: "aegis-auth-session",
  liveCases: "aegis-live-cases",
} as const;

export const APP_NAME = "Aegis Swarm";

/** Poll interval for GET /analyze/{case_id} while a case is processing. */
export const CASE_POLL_INTERVAL_MS = 2000;

export const MAX_RECENT_SEARCHES = 5;
