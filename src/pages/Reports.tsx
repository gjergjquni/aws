import { useEffect, useState } from "react";
import { Link } from "react-router";
import RiskBadge, { getRiskLevel } from "@/components/RiskBadge";
import LoadingState from "@/components/LoadingState";
import { investigationsApi } from "@/services/investigationsApi";
import type { Investigation } from "@/types";
import { DECISION_LABELS, formatDate, RECOMMENDATION_LABELS } from "@/utils/labels";

type ExportFormat = "pdf" | "json";

function exportReport(inv: Investigation, format: ExportFormat) {
  if (format === "json") {
    const blob = new Blob([JSON.stringify(inv, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${inv.claimId}-report.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    return;
  }

  window.print();
}

export default function Reports() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    investigationsApi
      .getResolved()
      .then(setInvestigations)
      .finally(() => setLoading(false));
  }, []);

  const selectedInv = investigations.find((inv) => inv.id === selected);

  if (loading) {
    return <LoadingState label="Loading reports…" />;
  }

  return (
    <div className="px-6 py-6 max-w-[1400px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Reports</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
            Summaries of completed investigations for record-keeping and review.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/analytics"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] text-xs font-medium text-[var(--foreground)] rounded-[var(--radius)] hover:bg-[var(--muted)] transition-colors"
          >
            View Analytics
          </Link>
          <button
            type="button"
            onClick={() => investigations.forEach((inv) => exportReport(inv, "json"))}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border)] text-xs font-medium text-[var(--foreground)] rounded-[var(--radius)] hover:bg-[var(--muted)] transition-colors"
          >
            Export All (JSON)
          </button>
        </div>
      </div>

      <div className={`grid gap-5 ${selectedInv ? "grid-cols-1 lg:grid-cols-5" : "grid-cols-1"}`}>
        <div className={selectedInv ? "lg:col-span-2" : ""}>
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-medium text-[var(--muted-foreground)] border-b border-[var(--border)]">
                    <th className="px-4 py-3">Claim ID</th>
                    <th className="px-4 py-3">Risk</th>
                    <th className="px-4 py-3 hidden sm:table-cell">AI Rec.</th>
                    <th className="px-4 py-3">Decision</th>
                    <th className="px-4 py-3 hidden md:table-cell">Date</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {investigations.map((inv) => (
                    <tr
                      key={inv.id}
                      onClick={() => setSelected(selected === inv.id ? null : inv.id)}
                      className={`border-b border-[var(--border)] last:border-0 cursor-pointer transition-colors ${
                        selected === inv.id ? "bg-[var(--accent)]" : "hover:bg-[var(--muted)]"
                      }`}
                    >
                      <td className="px-4 py-3 font-mono text-xs font-semibold text-[var(--primary)]">
                        {inv.claimId}
                      </td>
                      <td className="px-4 py-3">
                        <RiskBadge score={inv.riskScore} level={getRiskLevel(inv.riskScore)} />
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-xs text-[var(--muted-foreground)]">
                        {RECOMMENDATION_LABELS[inv.recommendation]}
                      </td>
                      <td className="px-4 py-3">
                        {inv.humanDecision ? (
                          <span
                            className={`text-xs font-medium ${
                              inv.humanDecision === "approved"
                                ? "text-green-600 dark:text-green-400"
                                : inv.humanDecision === "rejected"
                                  ? "text-red-600 dark:text-red-400"
                                  : "text-amber-600 dark:text-amber-400"
                            }`}
                          >
                            {DECISION_LABELS[inv.humanDecision]}
                          </span>
                        ) : (
                          <span className="text-xs text-[var(--muted-foreground)] italic">Pending</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-xs text-[var(--muted-foreground)]">
                        {formatDate(inv.submitted, "short")}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/investigations/${inv.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-[10px] text-[var(--primary)] hover:underline"
                          >
                            View
                          </Link>
                          {(["pdf", "json"] as ExportFormat[]).map((fmt) => (
                            <button
                              key={fmt}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                exportReport(inv, fmt);
                              }}
                              className="text-[10px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] uppercase font-mono"
                            >
                              {fmt}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {selectedInv && (
          <div className="lg:col-span-3">
            <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
              <div className="flex items-start justify-between mb-5">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-[var(--foreground)]">
                      Report — {selectedInv.claimId}
                    </h3>
                    <RiskBadge
                      score={selectedInv.riskScore}
                      level={getRiskLevel(selectedInv.riskScore)}
                    />
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {selectedInv.product} · {formatDate(selectedInv.submitted, "long")}
                  </p>
                </div>
                <div className="flex gap-1.5">
                  {(["pdf", "json"] as ExportFormat[]).map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() => exportReport(selectedInv, fmt)}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs border border-[var(--border)] rounded-[var(--radius)] text-[var(--muted-foreground)] hover:bg-[var(--muted)] transition-colors"
                    >
                      {fmt.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mb-4">
                <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-2">
                  Investigation Summary
                </div>
                <p className="text-sm text-[var(--foreground)] leading-relaxed">{selectedInv.summary}</p>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-[var(--border)] pt-4">
                <div>
                  <div className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Overall Risk</div>
                  <div className="text-xl font-bold font-mono text-[var(--foreground)]">
                    {selectedInv.riskScore}
                    <span className="text-xs text-[var(--muted-foreground)] font-normal">/100</span>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-[var(--muted-foreground)] mb-0.5">AI Recommendation</div>
                  <div className="text-sm font-semibold text-[var(--foreground)]">
                    {RECOMMENDATION_LABELS[selectedInv.recommendation]}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
