import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import GlobalSearch from "@/components/GlobalSearch";
import { useAuth } from "@/hooks/useAuth";
import { useSidebar } from "@/hooks/useSidebar";
import { useTheme } from "@/hooks/useTheme";
import { APP_NAME } from "@/lib/constants";
import { getPageTitle, isNavActive, NAV_ITEMS } from "@/lib/navigation";

function AegisLogo({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <div className="text-[var(--primary)] flex-shrink-0">
        <svg width="26" height="26" viewBox="0 0 28 28" fill="none" aria-hidden>
          <path
            d="M14 2L4 6.5V13.5C4 19.2 8.4 24.5 14 26C19.6 24.5 24 19.2 24 13.5V6.5L14 2Z"
            fill="currentColor"
            fillOpacity="0.12"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <circle cx="14" cy="14" r="3" fill="currentColor" />
          <circle cx="9" cy="11" r="1.5" fill="currentColor" fillOpacity="0.6" />
          <circle cx="19" cy="11" r="1.5" fill="currentColor" fillOpacity="0.6" />
          <circle cx="14" cy="19" r="1.5" fill="currentColor" fillOpacity="0.6" />
          <line x1="14" y1="14" x2="9" y2="11" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
          <line x1="14" y1="14" x2="19" y2="11" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
          <line x1="14" y1="14" x2="14" y2="19" stroke="currentColor" strokeWidth="1" strokeOpacity="0.4" />
        </svg>
      </div>
      <div
        className="overflow-hidden transition-all duration-200"
        style={{ width: collapsed ? 0 : 140, opacity: collapsed ? 0 : 1 }}
      >
        <div className="whitespace-nowrap">
          <div className="text-sm font-semibold text-[var(--foreground)] tracking-tight">{APP_NAME}</div>
          <div className="text-[10px] text-[var(--muted-foreground)] leading-none mt-0.5">
            AI Investigation Platform
          </div>
        </div>
      </div>
    </div>
  );
}

function Tooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);

  return (
    <div
      className="relative"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50 whitespace-nowrap rounded-[var(--radius)] bg-[var(--foreground)] text-[var(--background)] text-xs font-medium px-2.5 py-1.5 shadow-lg"
          role="tooltip"
        >
          {label}
          <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-[var(--foreground)]" />
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const { collapsed, mobileOpen, setMobileOpen, toggleCollapsed, sidebarWidth } = useSidebar();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, setMobileOpen]);

  const pageTitle = getPageTitle(location.pathname);
  const displayName = user?.name ?? "Investigator";
  const initials = user?.initials ?? "IN";

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 bg-black/40 z-20 lg:hidden border-0 cursor-default"
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
        />
      )}

      <aside
        className={`
          fixed lg:relative inset-y-0 left-0 z-30
          flex flex-col
          bg-[var(--card)] border-r border-[var(--border)]
          transition-[width,transform] duration-200 ease-in-out
          lg:translate-x-0
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
          flex-shrink-0 overflow-hidden
        `}
        style={{ width: mobileOpen ? 240 : sidebarWidth }}
        aria-label="Main navigation"
      >
        <div className="flex items-center justify-between px-3 py-3.5 border-b border-[var(--border)] flex-shrink-0">
          <div className={collapsed ? "flex justify-center w-full" : ""}>
            <AegisLogo collapsed={collapsed} />
          </div>
          {!collapsed && (
            <button
              type="button"
              onClick={toggleCollapsed}
              className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors flex-shrink-0 hidden lg:flex"
              aria-label="Collapse sidebar"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
        </div>

        {collapsed && (
          <div className="flex justify-center px-2 pt-2 hidden lg:flex">
            <button
              type="button"
              onClick={toggleCollapsed}
              className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              aria-label="Expand sidebar"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path d="M5 2l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        )}

        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
          {NAV_ITEMS.map((item) => {
            const isActive = isNavActive(location.pathname, item);

            const inner = (
              <NavLink
                to={item.path}
                aria-label={item.label}
                aria-current={isActive ? "page" : undefined}
                className={`
                  flex items-center gap-2.5 rounded-[var(--radius)] text-sm font-medium
                  transition-colors duration-100 outline-none
                  focus-visible:ring-2 focus-visible:ring-[var(--ring)]
                  ${collapsed ? "justify-center px-0 py-2.5 w-full" : "px-3 py-2"}
                  ${
                    isActive
                      ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
                  }
                `}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );

            return collapsed ? (
              <Tooltip key={item.path} label={item.label}>
                {inner}
              </Tooltip>
            ) : (
              <div key={item.path}>{inner}</div>
            );
          })}
        </nav>

        <div className="px-2 py-3 border-t border-[var(--border)] space-y-1 flex-shrink-0">
          {collapsed ? (
            <Tooltip label="System active">
              <div className="flex justify-center py-1.5">
                <span className="w-2 h-2 rounded-full bg-green-500" aria-hidden />
              </div>
            </Tooltip>
          ) : (
            <div className="px-3 py-1.5">
              <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold tracking-widest uppercase text-[var(--muted-foreground)]">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" aria-hidden />
                Active
              </span>
            </div>
          )}

          {collapsed ? (
            <Tooltip label={`${displayName} — Sign out`}>
              <button
                type="button"
                onClick={() => logout()}
                className="w-full flex justify-center py-2 rounded-[var(--radius)] hover:bg-[var(--muted)] transition-colors"
                aria-label="User profile"
              >
                <div className="w-7 h-7 rounded-full bg-[var(--primary)] flex items-center justify-center text-white text-xs font-semibold">
                  {initials}
                </div>
              </button>
            </Tooltip>
          ) : (
            <div className="flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius)] bg-[var(--muted)]">
              <div className="w-7 h-7 rounded-full bg-[var(--primary)] flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-[var(--foreground)] truncate">{displayName}</div>
                <div className="text-[10px] text-[var(--muted-foreground)] truncate">Investigator</div>
              </div>
              <button
                type="button"
                onClick={() => logout()}
                className="p-1 rounded text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--border)] transition-colors flex-shrink-0"
                title="Sign out"
                aria-label="Sign out"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                  <path
                    d="M7.5 4V2.5H2v7h5.5V8M5 6h5.5M8.5 4.5l2 1.5-2 1.5"
                    stroke="currentColor"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center gap-4 px-6 py-3 bg-[var(--card)] border-b border-[var(--border)] flex-shrink-0">
          <button
            type="button"
            className="lg:hidden p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <line x1="2" y1="4.5" x2="16" y2="4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="2" y1="9" x2="16" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="2" y1="13.5" x2="16" y2="13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>

          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-semibold text-[var(--foreground)]">{pageTitle}</h1>
            <div className="text-xs text-[var(--muted-foreground)] mt-0.5 hidden sm:block">
              {APP_NAME} <span className="mx-1 opacity-40">/</span> {pageTitle}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <GlobalSearch />

            <button
              type="button"
              className="relative p-2 rounded-[var(--radius)] text-[var(--muted-foreground)] hover:bg-[var(--muted)] transition-colors"
              aria-label="Notifications"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path
                  d="M8 2a4.5 4.5 0 00-4.5 4.5v2L2 10v1h12v-1l-1.5-1.5v-2A4.5 4.5 0 008 2z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinejoin="round"
                />
                <path d="M6.5 12a1.5 1.5 0 003 0" stroke="currentColor" strokeWidth="1.4" />
              </svg>
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500" aria-hidden />
            </button>

            <button
              type="button"
              onClick={toggle}
              className="p-2 rounded-[var(--radius)] text-[var(--muted-foreground)] hover:bg-[var(--muted)] transition-colors"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? (
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
                  <circle cx="7.5" cy="7.5" r="3.5" stroke="currentColor" strokeWidth="1.3" />
                  <line x1="7.5" y1="1" x2="7.5" y2="2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                  <line x1="7.5" y1="12.5" x2="7.5" y2="14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                  <line x1="1" y1="7.5" x2="2.5" y2="7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                  <line x1="12.5" y1="7.5" x2="14" y2="7.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
                  <path
                    d="M12.5 9.5A5.5 5.5 0 015.5 2.5a5.5 5.5 0 000 10 5.5 5.5 0 007-3z"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
