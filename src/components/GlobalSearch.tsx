import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { MAX_RECENT_SEARCHES, STORAGE_KEYS } from "@/lib/constants";
import { investigationsApi } from "@/services/investigationsApi";
import type { Investigation } from "@/types";
import { getRiskLevel } from "@/utils/risk";
import { RECOMMENDATION_LABELS, STATUS_LABELS } from "@/utils/labels";

function getRisk(score: number) {
  const level = getRiskLevel(score);
  if (level === 'high') return { label: 'High Risk', color: 'text-red-600 dark:text-red-400', dot: 'bg-red-500' };
  if (level === 'elevated') return { label: 'Elevated', color: 'text-amber-600 dark:text-amber-400', dot: 'bg-amber-500' };
  if (level === 'low') return { label: 'Low Risk', color: 'text-green-600 dark:text-green-400', dot: 'bg-green-500' };
  return { label: 'Insufficient', color: 'text-slate-500', dot: 'bg-slate-400' };
}

function highlight(text: string, query: string) {
  if (!query.trim()) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-blue-100 dark:bg-blue-900/50 text-[var(--foreground)] rounded-[2px] px-0.5 not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  );
}

function loadRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.recentSearches) ?? "[]");
  } catch {
    return [];
  }
}

function saveRecent(claimId: string) {
  try {
    const prev = loadRecent().filter((id) => id !== claimId);
    localStorage.setItem(
      STORAGE_KEYS.recentSearches,
      JSON.stringify([claimId, ...prev].slice(0, MAX_RECENT_SEARCHES)),
    );
  } catch {
    // ignore storage errors
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────

function SearchModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [recent, setRecent] = useState<string[]>(loadRecent);
  const [results, setResults] = useState<Investigation[]>([]);

  // Focus input on mount
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 30);
  }, []);

  // Simulate async search with brief loading flash
  const [debouncedQuery, setDebouncedQuery] = useState('');
  useEffect(() => {
    if (!query.trim()) { setLoading(false); setDebouncedQuery(''); return; }
    setLoading(true);
    const t = setTimeout(() => { setDebouncedQuery(query); setLoading(false); }, 180);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }
    investigationsApi.search(debouncedQuery).then(setResults);
  }, [debouncedQuery]);

  const [allInvestigations, setAllInvestigations] = useState<Investigation[]>([]);
  useEffect(() => {
    investigationsApi.getAll().then(setAllInvestigations);
  }, []);

  const recentInvs = recent
    .map((id) => allInvestigations.find((inv) => inv.claimId === id))
    .filter((inv): inv is Investigation => Boolean(inv));

  const items = query.trim() ? results : recentInvs;

  // Reset active on results change
  useEffect(() => { setActiveIdx(-1); }, [debouncedQuery]);

  const goTo = useCallback((inv: Investigation) => {
    saveRecent(inv.claimId);
    setRecent(loadRecent());
    onClose();
    navigate(`/investigations/${inv.id}`);
  }, [navigate, onClose]);

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, items.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, -1));
      }
      if (e.key === 'Enter' && activeIdx >= 0 && items[activeIdx]) {
        goTo(items[activeIdx]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeIdx, items, onClose, goTo]);

  // Scroll active item into view
  useEffect(() => {
    if (activeIdx < 0) return;
    const el = listRef.current?.querySelector(`[data-idx="${activeIdx}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />

      {/* Panel */}
      <div
        className="fixed z-50 top-[12%] left-1/2 -translate-x-1/2 w-full max-w-[560px] px-4"
        role="dialog"
        aria-modal
        aria-label="Search investigations"
      >
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl overflow-hidden">

          {/* Input row */}
          <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[var(--border)]">
            {loading ? (
              <svg className="animate-spin flex-shrink-0 text-[var(--primary)]" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.8" strokeDasharray="24 12" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-[var(--muted-foreground)] flex-shrink-0">
                <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.4" />
                <line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            )}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search investigations..."
              className="flex-1 bg-transparent text-sm text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none"
              aria-autocomplete="list"
              aria-expanded={items.length > 0}
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors flex-shrink-0"
                aria-label="Clear search"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            )}
            <kbd className="hidden sm:inline-flex text-[10px] font-medium text-[var(--muted-foreground)] bg-[var(--muted)] border border-[var(--border)] px-1.5 py-0.5 rounded flex-shrink-0">
              esc
            </kbd>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[380px] overflow-y-auto py-1.5" role="listbox">
            {/* Section label */}
            {!loading && items.length > 0 && (
              <div className="px-4 py-2 text-[10px] font-semibold tracking-widest uppercase text-[var(--muted-foreground)]">
                {query.trim() ? `${results.length} result${results.length !== 1 ? 's' : ''}` : 'Recent'}
              </div>
            )}

            {/* Items */}
            {!loading && items.map((inv, idx) => {
              const risk = getRisk(inv.riskScore);
              const isActive = idx === activeIdx;
              return (
                <button
                  key={inv.id}
                  data-idx={idx}
                  role="option"
                  aria-selected={isActive}
                  onClick={() => goTo(inv)}
                  onMouseEnter={() => setActiveIdx(idx)}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors ${
                    isActive ? 'bg-[var(--accent)]' : 'hover:bg-[var(--muted)]'
                  }`}
                >
                  {/* Risk dot */}
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${risk.dot}`} aria-hidden />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-[var(--primary)]">
                        {highlight(inv.claimId, query)}
                      </span>
                      <span className="text-sm font-medium text-[var(--foreground)] truncate">
                        {highlight(inv.product, query)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                      <span className={`text-xs font-medium ${risk.color}`}>{risk.label}</span>
                      <span className="text-[var(--muted-foreground)] text-xs opacity-40">·</span>
                      <span className="text-xs text-[var(--muted-foreground)]">{STATUS_LABELS[inv.status]}</span>
                      <span className="text-[var(--muted-foreground)] text-xs opacity-40">·</span>
                      <span className="text-xs text-[var(--muted-foreground)]">{RECOMMENDATION_LABELS[inv.recommendation]}</span>
                    </div>
                  </div>

                  <span className="text-[10px] text-[var(--muted-foreground)] flex-shrink-0 mt-1 opacity-60">
                    ${inv.orderValue.toLocaleString()}
                  </span>
                </button>
              );
            })}

            {/* Empty state */}
            {!loading && query.trim() && results.length === 0 && debouncedQuery === query && (
              <div className="px-4 py-8 text-center">
                <div className="text-sm font-medium text-[var(--foreground)] mb-1">No investigations found</div>
                <div className="text-xs text-[var(--muted-foreground)]">
                  Try searching by Claim ID, product name, or category
                </div>
              </div>
            )}

            {/* Empty recent */}
            {!loading && !query.trim() && recentInvs.length === 0 && (
              <div className="px-4 py-8 text-center text-xs text-[var(--muted-foreground)]">
                No recent searches yet
              </div>
            )}
          </div>

          {/* Footer hints */}
          <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border)] bg-[var(--muted)]/40">
            {[
              { keys: ['↑', '↓'], label: 'navigate' },
              { keys: ['↵'], label: 'open' },
              { keys: ['esc'], label: 'close' },
            ].map(({ keys, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="flex gap-1">
                  {keys.map((k) => (
                    <kbd key={k} className="text-[10px] font-medium text-[var(--muted-foreground)] bg-[var(--card)] border border-[var(--border)] px-1.5 py-0.5 rounded">
                      {k}
                    </kbd>
                  ))}
                </div>
                <span className="text-[10px] text-[var(--muted-foreground)]">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Trigger bar (shown in topbar) ─────────────────────────────────────────

export default function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);

  // Global keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-[var(--muted)] hover:bg-[var(--border)] border border-[var(--border)] rounded-[var(--radius)] text-sm text-[var(--muted-foreground)] transition-colors min-w-[200px]"
        aria-label="Search investigations"
      >
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="flex-shrink-0">
          <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" />
          <line x1="8.5" y1="8.5" x2="11.5" y2="11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
        <span className="flex-1 text-left text-xs">Search investigations...</span>
        <kbd className="text-[10px] bg-[var(--card)] border border-[var(--border)] px-1.5 py-0.5 rounded font-medium ml-auto">
          {isMac ? '⌘K' : 'Ctrl K'}
        </kbd>
      </button>

      {/* Mobile search icon */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden p-2 rounded-[var(--radius)] text-[var(--muted-foreground)] hover:bg-[var(--muted)] transition-colors"
        aria-label="Search"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.4" />
          <line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      {open && <SearchModal onClose={() => setOpen(false)} />}
    </>
  );
}
