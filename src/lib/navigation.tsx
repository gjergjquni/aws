export interface NavItem {
  path: string;
  label: string;
  matchPaths?: string[];
  icon: React.ReactNode;
}

export const NAV_ITEMS: NavItem[] = [
  {
    path: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
        <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
        <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
        <rect x="9" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      </svg>
    ),
  },
  {
    path: "/investigations",
    label: "Investigations",
    matchPaths: ["/investigations"],
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
        <line x1="4.5" y1="6" x2="11.5" y2="6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="4.5" y1="9" x2="8.5" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    path: "/analytics",
    label: "Analytics & Reports",
    matchPaths: ["/analytics", "/reports"],
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="1.5" y="8.5" width="3" height="6" rx="1" fill="currentColor" fillOpacity="0.55" />
        <rect x="6.5" y="5" width="3" height="9.5" rx="1" fill="currentColor" fillOpacity="0.75" />
        <rect x="11.5" y="1.5" width="3" height="13" rx="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    path: "/settings",
    label: "Settings",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path
          d="M6.5 2h3l.5 1.5a4.5 4.5 0 011.1.65l1.5-.4 1.5 2.6-1.15 1.05a4.6 4.6 0 010 1.2L14.1 9.75l-1.5 2.6-1.5-.4A4.5 4.5 0 019.5 12.5L9 14H6l-.5-1.5a4.5 4.5 0 01-1.1-.65l-1.5.4-1.5-2.6 1.15-1.05a4.6 4.6 0 010-1.2L1.9 6.25l1.5-2.6 1.5.4A4.5 4.5 0 016.5 3.5L6.5 2z"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.25" />
      </svg>
    ),
  },
];

export function getPageTitle(pathname: string): string {
  if (pathname === "/dashboard") return "Dashboard";
  if (pathname === "/analytics") return "Analytics";
  if (pathname === "/reports") return "Reports";
  if (pathname === "/settings") return "Settings";
  if (pathname === "/investigations/new") return "New Investigation";
  if (pathname.startsWith("/investigations/")) return "Investigation Detail";
  if (pathname === "/investigations") return "Investigations";
  return "Aegis Swarm";
}

export function isNavActive(pathname: string, item: NavItem): boolean {
  const paths = item.matchPaths ?? [item.path];
  if (item.path === "/investigations") {
    return pathname.startsWith("/investigations");
  }
  return paths.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}
