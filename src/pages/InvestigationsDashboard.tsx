import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import RiskBadge, {
  DecisionBadge,
  getRiskLevel,
  RecommendationBadge,
  StatusBadge,
} from "@/components/RiskBadge";
import { useInvestigations } from "@/hooks/useInvestigations";
import { caseRegistry } from "@/services/caseRegistry";
import type { InvestigationCategory, InvestigationStatus, RiskLevel, StoredCase } from "@/types";
import { categoryLabel, formatCurrency, formatDate } from "@/utils/labels";

function liveStatusBadge(c: StoredCase) {
  const status = c.lastStatus ?? "processing";
  if (status === "completed") {
    const fraud = c.humanDecision === "FRAUD" || c.decision === "FRAUD";
    return (
      <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
        fraud
          ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400"
          : "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400"
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${fraud ? "bg-red-500" : "bg-green-500"}`} />
        {c.humanDecision ?? c.decision ?? "Completed"}
      </span>
    );
  }
  if (status === "pending_human_review") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        Human Review
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
        Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400">
      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
      Processing
    </span>
  );
}

function LiveCasesSection() {
  const navigate = useNavigate();
  const liveCases = useMemo(() => caseRegistry.list(), []);

  if (liveCases.length === 0) return null;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden mb-5">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">
          Live Cases — Real Backend
        </div>
        <span className="text-xs text-[var(--muted-foreground)]">
          {liveCases.length} {liveCases.length === 1 ? "case" : "cases"}
        </span>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {liveCases.map((c) => (
          <button
            key={c.caseId}
            type="button"
            onClick={() => navigate(`/investigations/${c.caseId}`)}
            className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-[var(--muted)] transition-colors"
          >
            <span className="font-mono text-xs font-semibold text-[var(--primary)] flex-shrink-0">
              {c.caseId}
            </span>
            <span className="text-xs text-[var(--muted-foreground)] truncate flex-1 min-w-0">
              {c.message}
            </span>
            <span className="hidden sm:block text-[10px] text-[var(--muted-foreground)] whitespace-nowrap">
              {formatDate(c.submittedAt, "short")}
            </span>
            {liveStatusBadge(c)}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function InvestigationsDashboard() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filterRisk, setFilterRisk] = useState<RiskLevel | "all">("all");
  const [filterStatus, setFilterStatus] = useState<InvestigationStatus | "all">("all");
  const [filterCategory, setFilterCategory] = useState<InvestigationCategory | "all">("all");

  const filters = useMemo(
    () => ({
      search,
      riskLevel: filterRisk,
      status: filterStatus,
      category: filterCategory,
    }),
    [search, filterRisk, filterStatus, filterCategory],
  );

  const { investigations, loading } = useInvestigations(filters);

  return (
    <div className="px-6 py-6 max-w-[1400px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-7">
        <div>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Investigations</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
            Review and analyze return claims using AI-powered evidence.
          </p>
        </div>
        <Link
          to="/investigations/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-[var(--radius)] hover:opacity-90 transition-opacity flex-shrink-0"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <line x1="6" y1="1" x2="6" y2="11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            <line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          New Investigation
        </Link>
      </div>

      <LiveCasesSection />

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-[var(--border)]">
          <div className="flex items-center gap-2 flex-1 min-w-[160px] max-w-xs bg-[var(--muted)] rounded-[var(--radius)] px-3 py-1.5">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="text-[var(--muted-foreground)] flex-shrink-0" aria-hidden>
              <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3" />
              <line x1="8.5" y1="8.5" x2="11.5" y2="11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              placeholder="Search claims…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search investigations"
              className="bg-transparent text-sm text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none w-full"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <select
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value as RiskLevel | "all")}
              aria-label="Filter by risk"
              className="text-xs bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] rounded-[var(--radius)] px-2.5 py-1.5 outline-none cursor-pointer focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="all">All Risk</option>
              <option value="low">Low</option>
              <option value="elevated">Elevated</option>
              <option value="high">High</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as InvestigationStatus | "all")}
              aria-label="Filter by status"
              className="text-xs bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] rounded-[var(--radius)] px-2.5 py-1.5 outline-none cursor-pointer focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="in_review">In Review</option>
              <option value="resolved">Resolved</option>
              <option value="escalated">Escalated</option>
            </select>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value as InvestigationCategory | "all")}
              aria-label="Filter by category"
              className="text-xs bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] rounded-[var(--radius)] px-2.5 py-1.5 outline-none cursor-pointer focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="all">All Categories</option>
              <option value="electronics">Electronics</option>
              <option value="clothing">Clothing</option>
              <option value="sporting">Sporting</option>
            </select>
          </div>

          <div className="ml-auto text-xs text-[var(--muted-foreground)]">
            {investigations.length} {investigations.length === 1 ? "result" : "results"}
          </div>
        </div>

        {loading ? (
          <LoadingState label="Loading investigations…" />
        ) : investigations.length === 0 ? (
          <EmptyState
            title="No investigations found"
            description="Try adjusting your filters or create a new investigation."
            action={
              <Link
                to="/investigations/new"
                className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white text-sm font-medium rounded-[var(--radius)]"
              >
                Create Investigation
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium text-[var(--muted-foreground)] border-b border-[var(--border)]">
                  <th className="px-4 py-3 whitespace-nowrap">Claim ID</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3 hidden md:table-cell">Category</th>
                  <th className="px-4 py-3 whitespace-nowrap">Date</th>
                  <th className="px-4 py-3">Risk Score</th>
                  <th className="px-4 py-3 hidden lg:table-cell">AI Recommendation</th>
                  <th className="px-4 py-3 hidden lg:table-cell">Human Decision</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 hidden xl:table-cell whitespace-nowrap">Last Updated</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {investigations.map((inv, i) => (
                  <tr
                    key={inv.id}
                    className={`border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)] cursor-pointer transition-colors ${
                      i % 2 !== 0 ? "bg-[var(--muted)]/20" : ""
                    }`}
                    onClick={() => navigate(`/investigations/${inv.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-[var(--primary)]">
                      {inv.claimId}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-[var(--foreground)]">{inv.product}</div>
                      <div className="text-xs text-[var(--muted-foreground)] mt-0.5">
                        {formatCurrency(inv.orderValue)}
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-xs text-[var(--muted-foreground)]">
                      {categoryLabel(inv.category)}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--muted-foreground)] whitespace-nowrap">
                      {formatDate(inv.submitted)}
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge score={inv.riskScore} level={getRiskLevel(inv.riskScore)} />
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      <RecommendationBadge rec={inv.recommendation} />
                    </td>
                    <td className="px-4 py-3 hidden lg:table-cell">
                      <DecisionBadge decision={inv.humanDecision} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={inv.status} />
                    </td>
                    <td className="px-4 py-3 hidden xl:table-cell text-xs text-[var(--muted-foreground)] whitespace-nowrap">
                      {formatDate(inv.submitted, "short")}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="text-xs font-medium text-[var(--primary)] hover:underline whitespace-nowrap"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/investigations/${inv.id}`);
                        }}
                      >
                        Review →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
