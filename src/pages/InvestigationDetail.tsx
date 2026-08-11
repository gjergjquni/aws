import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router";
import LoadingState from "@/components/LoadingState";
import { useAuth } from "@/hooks/useAuth";
import { useInvestigation } from "@/hooks/useInvestigations";
import { investigationsApi } from "@/services/investigationsApi";
import type { HumanDecision, Investigation } from "@/types";
import { getRiskColorScheme } from "@/utils/risk";
import { RECOMMENDATION_LABELS } from "@/utils/labels";

function riskColor(score: number) {
  return getRiskColorScheme(score);
}

const statusConfig: Record<string, { label: string; style: string }> = {
  pending: { label: 'Pending Review', style: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400' },
  in_review: { label: 'In Review', style: 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400' },
  resolved: { label: 'Resolved', style: 'bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400' },
  escalated: { label: 'Escalated', style: 'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400' },
};

const recLabels = RECOMMENDATION_LABELS;

// ── sub-components ─────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const c = riskColor(score);
  const stroke = score >= 70 ? '#EF4444' : score >= 40 ? '#F59E0B' : '#22C55E';
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: 88, height: 88 }}>
      <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
        <circle cx="44" cy="44" r={r} fill="none" stroke="var(--border)" strokeWidth="7" />
        <circle cx="44" cy="44" r={r} fill="none" stroke={stroke} strokeWidth="7"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.7s ease' }} />
      </svg>
      <div className="absolute text-center leading-none">
        <div className={`text-xl font-bold font-mono ${c.text}`}>{score}</div>
        <div className="text-[9px] text-[var(--muted-foreground)] mt-0.5">/ 100</div>
      </div>
    </div>
  );
}

// ── TABS ───────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'evidence' | 'analysis' | 'audit';

function OverviewTab({
  inv,
  onGoToAnalysis,
  onSave,
}: {
  inv: Investigation;
  onGoToAnalysis: () => void;
  onSave: (decision: HumanDecision, notes: string) => Promise<void>;
}) {
  const [decision, setDecision] = useState<HumanDecision>(inv.humanDecision ?? null);
  const [notes, setNotes] = useState(inv.notes ?? '');
  const [saving, setSaving] = useState(false);
  const rc = riskColor(inv.riskScore);

  const findings = [
    ...(inv.visualEvidenceFindings ?? []).slice(0, 2).map((f: string) => ({ icon: '⚠', severity: 'warn', title: f })),
    ...(inv.claimIntelligenceFindings ?? []).slice(0, 2).map((f: string) => ({ icon: '⚠', severity: 'warn', title: f })),
  ].slice(0, 4);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      {/* Left column */}
      <div className="lg:col-span-2 space-y-4">

        {/* Risk + Rec row */}
        <div className="grid sm:grid-cols-2 gap-4">
          {/* Overall Risk */}
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">Overall Risk</div>
            <div className="flex items-center gap-5">
              <ScoreRing score={inv.riskScore} />
              <div>
                <div className={`inline-flex items-center gap-1.5 text-sm font-semibold ${rc.text}`}>
                  <span className={`w-2 h-2 rounded-full ${rc.dot}`} />
                  {rc.label}
                </div>
                <div className="mt-2 text-xs text-[var(--muted-foreground)]">Confidence</div>
                <div className="font-mono font-semibold text-[var(--foreground)]">{Math.round((inv.visualEvidenceConfidence + inv.claimIntelligenceConfidence) / 2)}%</div>
              </div>
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">AI Recommendation</div>
            <div className="text-lg font-bold tracking-wide text-[var(--foreground)] mb-2">
              {recLabels[inv.recommendation]?.toUpperCase()}
            </div>
            <p className="text-xs text-[var(--muted-foreground)] leading-relaxed mb-3">
              Multiple signals require additional investigation. The AI recommendation is based on visual evidence and claim analysis.
            </p>
            <div className="flex items-start gap-2 p-2.5 rounded-[var(--radius)] bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5">
                <path d="M6 1L1 9.5h10L6 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
                <line x1="6" y1="5" x2="6" y2="7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <circle cx="6" cy="8.5" r="0.5" fill="currentColor" />
              </svg>
              <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-relaxed">
                AI provides decision support only. Final decision remains with a human investigator.
              </p>
            </div>
          </div>
        </div>

        {/* Key Findings */}
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">Key Findings</div>
          {findings.length > 0 ? (
            <div className="divide-y divide-[var(--border)]">
              {findings.map((f, i) => (
                <div key={i} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px]">!</span>
                  <div>
                    <div className="text-sm font-medium text-[var(--foreground)]">{f.title}</div>
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5">Flagged by AI analysis — review required</div>
                  </div>
                </div>
              ))}
              {!inv.imageUrl && (
                <div className="flex items-start gap-3 py-3 last:pb-0">
                  <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px]">—</span>
                  <div>
                    <div className="text-sm font-medium text-[var(--muted-foreground)]">Visual analysis unavailable</div>
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5">No image was submitted — insufficient data</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">No significant findings detected.</p>
          )}
        </div>

        {/* Agent Summary */}
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-4">Agent Summary</div>
          <div className="divide-y divide-[var(--border)]">
            {[
              {
                name: 'Visual Evidence Agent',
                score: inv.imageUrl ? inv.visualEvidenceScore : null,
                confidence: inv.imageUrl ? inv.visualEvidenceConfidence : null,
                status: inv.imageUrl ? 'Potential manipulation detected' : 'Insufficient data — no image',
              },
              {
                name: 'Claim Intelligence Agent',
                score: inv.claimIntelligenceScore,
                confidence: inv.claimIntelligenceConfidence,
                status: 'Potential inconsistency detected',
              },
              {
                name: 'Orchestrator',
                score: inv.riskScore,
                confidence: null,
                status: `Recommendation: ${recLabels[inv.recommendation]}`,
              },
            ].map((agent) => {
              const ac = agent.score !== null ? riskColor(agent.score) : null;
              return (
                <div key={agent.name} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-[var(--foreground)]">{agent.name}</div>
                    <div className="text-xs text-[var(--muted-foreground)] mt-0.5 truncate">{agent.status}</div>
                  </div>
                  <div className="flex items-center gap-4 flex-shrink-0">
                    {agent.score !== null && ac ? (
                      <>
                        <div className="text-right">
                          <div className="text-[10px] text-[var(--muted-foreground)]">Risk</div>
                          <div className={`font-mono font-bold text-sm ${ac.text}`}>{agent.score}</div>
                        </div>
                        {agent.confidence !== null && (
                          <div className="text-right">
                            <div className="text-[10px] text-[var(--muted-foreground)]">Conf.</div>
                            <div className="font-mono font-medium text-sm text-[var(--foreground)]">{agent.confidence}%</div>
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-[var(--muted-foreground)] italic">—</span>
                    )}
                    <button onClick={onGoToAnalysis} className="text-[10px] text-[var(--primary)] hover:underline whitespace-nowrap">
                      Details →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Right column — Human Decision */}
      <div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 sticky top-5">
          <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-1">Human Investigator Decision</div>
          <p className="text-xs text-[var(--muted-foreground)] mb-4 leading-relaxed">
            Review all evidence and make the final determination. The AI recommendation is advisory only.
          </p>

          <div className="mb-4 pb-4 border-b border-[var(--border)]">
            <div className="text-[10px] text-[var(--muted-foreground)] mb-1">AI Recommendation</div>
            <div className="text-sm font-bold tracking-wide text-[var(--foreground)]">
              {recLabels[inv.recommendation]?.toUpperCase()}
            </div>
          </div>

          <div className="space-y-2 mb-4">
            {[
              { key: 'approved', label: 'Approve Refund', activeStyle: 'ring-2 ring-green-400 border-green-400 bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400', baseStyle: 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]' },
              { key: 'manual_review', label: 'Manual Review', activeStyle: 'ring-2 ring-amber-400 border-amber-400 bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400', baseStyle: 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]' },
              { key: 'rejected', label: 'Reject Refund', activeStyle: 'ring-2 ring-red-400 border-red-400 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400', baseStyle: 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]' },
            ].map((opt) => (
              <button
                key={opt.key}
                onClick={() => setDecision(opt.key as HumanDecision)}
                className={`w-full py-2.5 px-3 text-sm font-medium text-left rounded-[var(--radius)] border transition-all ${decision === opt.key ? opt.activeStyle : opt.baseStyle}`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="space-y-3 mb-4 text-xs">
            <div className="flex justify-between">
              <span className="text-[var(--muted-foreground)]">Decision</span>
              <span className={`font-medium ${decision ? 'text-[var(--foreground)]' : 'text-[var(--muted-foreground)] italic'}`}>
                {decision ? decision.replace('_', ' ') : 'Not decided'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--muted-foreground)]">Investigator</span>
              <span className="font-medium text-[var(--foreground)]">A. Johnson</span>
            </div>
          </div>

          <label className="block text-xs font-medium text-[var(--foreground)] mb-1.5">Investigator Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add reasoning for your decision…"
            rows={4}
            className="w-full text-xs bg-[var(--muted)] border border-[var(--border)] rounded-[var(--radius)] px-3 py-2 text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none resize-none focus:ring-2 focus:ring-[var(--ring)] mb-3"
          />

          <button
            type="button"
            disabled={!decision || saving}
            onClick={async () => {
              if (!decision) return;
              setSaving(true);
              try {
                await onSave(decision, notes);
              } finally {
                setSaving(false);
              }
            }}
            className="w-full py-2.5 text-sm font-semibold rounded-[var(--radius)] transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-[var(--primary)] text-white hover:opacity-90"
          >
            {saving ? "Saving…" : "Save Decision"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EvidenceTab({ inv }: { inv: Investigation }) {
  if (!inv.imageUrl) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-12 text-center">
        <div className="w-10 h-10 rounded-full bg-[var(--muted)] flex items-center justify-center mx-auto mb-4 text-[var(--muted-foreground)]">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="2" y="3" width="14" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
            <circle cx="6" cy="7.5" r="1.5" stroke="currentColor" strokeWidth="1.2" />
            <path d="M2 12.5l4-3.5 3 2.5 2.5-2 4.5 3.5" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="text-xs font-semibold tracking-widest uppercase text-[var(--muted-foreground)] mb-2">Insufficient Data</div>
        <p className="text-sm text-[var(--muted-foreground)]">No visual evidence was provided for this investigation.</p>
        <p className="text-xs text-[var(--muted-foreground)] mt-1 opacity-60">Visual analysis could not be completed. This does not indicate low risk.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Image */}
      <div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden">
          <div className="aspect-[4/3] bg-[var(--muted)]">
            <img src={inv.imageUrl} alt="Return evidence" className="w-full h-full object-cover" />
          </div>
          <div className="px-4 py-3 border-t border-[var(--border)]">
            <div className="text-xs font-medium text-[var(--foreground)]">Submitted evidence photo</div>
            <div className="text-[10px] text-[var(--muted-foreground)] mt-0.5">Customer-uploaded at time of claim submission</div>
          </div>
        </div>
      </div>

      {/* Metadata + signals */}
      <div className="space-y-4">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">File Metadata</div>
          <div className="divide-y divide-[var(--border)]">
            {[
              ['File type', inv.imageMetadata.fileType],
              ['Resolution', inv.imageMetadata.dimensions],
              ['EXIF data', inv.imageMetadata.exif],
              ['Editing software', inv.imageMetadata.editingSoftware],
              ['GPS data', 'Not available'],
              ['Timestamp', 'Not available'],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                <span className="text-xs text-[var(--muted-foreground)]">{k}</span>
                <span className={`text-xs font-mono font-medium ${
                  v === 'Missing' || v === 'Detected' || v === 'Stripped'
                    ? 'text-red-600 dark:text-red-400'
                    : v === 'Present'
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-[var(--foreground)]'
                }`}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-3">Detected Evidence Signals</div>
          <div className="space-y-2">
            {inv.visualEvidenceFindings.map((f: string) => (
              <div key={f} className="flex items-start gap-2.5">
                <span className="w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px]">!</span>
                <span className="text-sm text-[var(--foreground)]">{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AnalysisTab({ inv, overallScore }: { inv: Investigation; overallScore: number }) {
  const rc = riskColor(overallScore);

  return (
    <div className="space-y-5">
      {/* Agent 1 */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Agent 1</div>
            <h3 className="text-sm font-semibold text-[var(--foreground)] mt-0.5">Visual Evidence Agent</h3>
          </div>
          {inv.imageUrl ? (
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-[10px] text-[var(--muted-foreground)]">Risk Score</div>
                <div className={`font-mono font-bold text-lg ${riskColor(inv.visualEvidenceScore).text}`}>{inv.visualEvidenceScore}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-[var(--muted-foreground)]">Confidence</div>
                <div className="font-mono font-bold text-lg text-[var(--foreground)]">{inv.visualEvidenceConfidence}%</div>
              </div>
            </div>
          ) : (
            <span className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-500 px-2.5 py-1 rounded-full">Insufficient Data</span>
          )}
        </div>

        {inv.imageUrl ? (
          <>
            <div className="text-xs font-medium text-[var(--foreground)] mb-2">Manipulation Status</div>
            <div className="flex items-center gap-2 mb-4 p-3 bg-amber-50 dark:bg-amber-950/20 rounded-[var(--radius)] border border-amber-200 dark:border-amber-800">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-400">Potential manipulation detected</span>
            </div>
            <div className="text-xs font-medium text-[var(--foreground)] mb-3">Metadata Findings &amp; Evidence Signals</div>
            <div className="grid sm:grid-cols-2 gap-2">
              {inv.visualEvidenceFindings.map((f: string) => (
                <div key={f} className="flex items-start gap-2 p-2.5 bg-[var(--muted)] rounded-[var(--radius)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0 mt-1.5" />
                  <span className="text-xs text-[var(--foreground)]">{f}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-[var(--border)]">
              <div className="text-xs font-medium text-[var(--foreground)] mb-1">Agent Explanation</div>
              <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                Image analysis identified indicators of potential post-processing. The absence of EXIF metadata and detected editing software artifacts are inconsistent with an unmodified device photo.
              </p>
            </div>
          </>
        ) : (
          <div className="p-4 bg-[var(--muted)] rounded-[var(--radius)] text-center">
            <p className="text-sm font-medium text-[var(--muted-foreground)]">Analysis unavailable</p>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">No image was submitted. Visual analysis could not be completed.</p>
          </div>
        )}
      </div>

      {/* Agent 3 */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Agent 3</div>
            <h3 className="text-sm font-semibold text-[var(--foreground)] mt-0.5">Claim Intelligence Agent</h3>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-[10px] text-[var(--muted-foreground)]">Risk Score</div>
              <div className={`font-mono font-bold text-lg ${riskColor(inv.claimIntelligenceScore).text}`}>{inv.claimIntelligenceScore}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-[var(--muted-foreground)]">Confidence</div>
              <div className="font-mono font-bold text-lg text-[var(--foreground)]">{inv.claimIntelligenceConfidence}%</div>
            </div>
          </div>
        </div>

        <div className="mb-4 p-3 bg-[var(--muted)] rounded-[var(--radius)] border-l-2 border-[var(--primary)]">
          <div className="text-[10px] text-[var(--muted-foreground)] mb-1">Customer explanation</div>
          <p className="text-sm text-[var(--foreground)] italic leading-relaxed">"{inv.customerExplanation}"</p>
        </div>

        <div className="text-xs font-medium text-[var(--foreground)] mb-3">Detected Patterns</div>
        <div className="grid sm:grid-cols-2 gap-2 mb-4">
          {inv.claimIntelligenceFindings.map((f: string) => (
            <div key={f} className="flex items-start gap-2 p-2.5 bg-[var(--muted)] rounded-[var(--radius)]">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0 mt-1.5" />
              <span className="text-xs text-[var(--foreground)]">{f}</span>
            </div>
          ))}
        </div>

        <div className="pt-4 border-t border-[var(--border)]">
          <div className="text-xs font-medium text-[var(--foreground)] mb-1">Agent Explanation</div>
          <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
            Linguistic and semantic analysis identified potential inconsistencies in the customer explanation. Language patterns show similarity to previously documented return-fraud scenarios. This is a potential signal only — not a determination of fraudulent intent.
          </p>
        </div>
      </div>

      {/* Agent 6 — Orchestrator */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide">Agent 6</div>
            <h3 className="text-sm font-semibold text-[var(--foreground)] mt-0.5">Orchestrator</h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Synthesizes evidence from all active agents</p>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-[var(--muted-foreground)]">Overall Risk</div>
            <div className={`font-mono font-bold text-lg ${rc.text}`}>{overallScore}</div>
          </div>
        </div>

        {/* Contribution breakdown */}
        <div className="mb-4 bg-[var(--muted)] rounded-[var(--radius)] p-4">
          <div className="text-xs font-medium text-[var(--foreground)] mb-3">Agent Contributions</div>
          {[
            { label: 'Visual Evidence Agent', score: inv.imageUrl ? inv.visualEvidenceScore : null, weight: 50 },
            { label: 'Claim Intelligence Agent', score: inv.claimIntelligenceScore, weight: 50 },
          ].map((a) => (
            <div key={a.label} className="mb-3 last:mb-0">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-[var(--muted-foreground)]">{a.label}</span>
                <span className="text-xs font-mono font-medium text-[var(--foreground)]">
                  {a.score !== null ? `${a.score} × ${a.weight}%` : `— × ${a.weight}%`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${a.score !== null ? (a.score >= 70 ? 'bg-red-500' : a.score >= 40 ? 'bg-amber-500' : 'bg-green-500') : 'bg-slate-300'}`}
                    style={{ width: a.score !== null ? `${a.score}%` : '0%', transition: 'width 0.6s ease' }}
                  />
                </div>
                <span className="text-[10px] font-mono text-[var(--muted-foreground)] w-6 text-right">
                  {a.score !== null ? Math.round(a.score * a.weight / 100) : '—'}
                </span>
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between pt-3 mt-3 border-t border-[var(--border)]">
            <span className="text-xs font-semibold text-[var(--foreground)]">Overall Risk Score</span>
            <span className={`font-mono font-bold ${rc.text}`}>{overallScore}</span>
          </div>
          <p className="text-[10px] text-[var(--muted-foreground)] mt-2">Score calculated using configured equal agent weights (50% / 50%).</p>
        </div>

        <div className="pt-4 border-t border-[var(--border)]">
          <div className="text-xs font-medium text-[var(--foreground)] mb-1">Final Explanation</div>
          <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">{inv.summary}</p>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-[var(--muted-foreground)]">AI Recommendation:</span>
            <span className="text-xs font-bold tracking-wide text-[var(--foreground)]">{recLabels[inv.recommendation]?.toUpperCase()}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AuditTab({ inv }: { inv: Investigation }) {
  const statusIcon = (status: string) => {
    if (status === 'success') return <span className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">✓</span>;
    if (status === 'warning') return <span className="w-6 h-6 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">!</span>;
    return <span className="w-6 h-6 rounded-full bg-[var(--muted)] text-[var(--muted-foreground)] flex items-center justify-center text-[10px] flex-shrink-0">i</span>;
  };

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 max-w-2xl">
      <div className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wide mb-5">Investigation Timeline</div>
      <div className="relative">
        <div className="absolute left-3 top-0 bottom-0 w-px bg-[var(--border)]" />
        <div className="space-y-5">
          {inv.auditTrail.map((ev: { time: string; component: string; event: string; status: string; model?: string }, i: number) => (
            <div key={i} className="flex items-start gap-4 pl-1">
              <div className="relative z-10">{statusIcon(ev.status)}</div>
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-mono text-xs text-[var(--muted-foreground)]">{ev.time}</span>
                  <span className="text-xs font-semibold text-[var(--foreground)]">{ev.component}</span>
                </div>
                <div className="text-sm text-[var(--foreground)] mt-0.5">{ev.event}</div>
                {ev.model && (
                  <div className="font-mono text-[10px] text-[var(--muted-foreground)] mt-0.5 opacity-60">{ev.model}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── main page ──────────────────────────────────────────────────────────────

export default function InvestigationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { investigation: inv, loading, reload } = useInvestigation(id);
  const [tab, setTab] = useState<Tab>("overview");

  const handleSaveDecision = async (decision: HumanDecision, notes: string) => {
    if (!inv || !decision || !user) return;
    await investigationsApi.updateDecision(inv.id, {
      decision,
      notes,
      investigator: user.name,
    });
    await reload();
  };

  if (loading) {
    return <LoadingState label="Loading investigation…" />;
  }

  if (!inv) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-24 text-center">
        <p className="text-sm font-medium text-[var(--foreground)] mb-2">Investigation not found</p>
        <Link to="/investigations" className="text-sm text-[var(--primary)] hover:underline">← Back</Link>
      </div>
    );
  }

  const rc = riskColor(inv.riskScore);
  const status = statusConfig[inv.status] ?? { label: inv.status, style: 'bg-slate-100 text-slate-600' };

  const TABS: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'evidence', label: 'Evidence' },
    { key: 'analysis', label: 'AI Analysis' },
    { key: 'audit', label: 'Audit Trail' },
  ];

  return (
    <div className="px-6 py-6 max-w-[1200px] mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] mb-4">
        <button onClick={() => navigate('/investigations')} className="hover:text-[var(--foreground)] transition-colors">Investigations</button>
        <span>/</span>
        <span className="font-mono text-[var(--foreground)]">{inv.claimId}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h2 className="text-xl font-semibold text-[var(--foreground)]">Investigation</h2>
            <span className="font-mono text-xl font-semibold text-[var(--primary)]">#{inv.claimId}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)] flex-wrap">
            <span>{inv.product}</span>
            <span className="opacity-40">·</span>
            <span className="capitalize">{inv.category}</span>
            <span className="opacity-40">·</span>
            <span className="font-mono">${inv.orderValue.toLocaleString()}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${status.style}`}>{status.label}</span>
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${rc.bg} ${rc.text} ${rc.border}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${rc.dot}`} />
            {rc.label}
          </span>
          <button className="p-1.5 rounded-[var(--radius)] border border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)] transition-colors" aria-label="More actions">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <circle cx="7" cy="3" r="1" fill="currentColor" />
              <circle cx="7" cy="7" r="1" fill="currentColor" />
              <circle cx="7" cy="11" r="1" fill="currentColor" />
            </svg>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border)] mb-6 -mx-6 px-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`pb-3 mr-6 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              tab === t.key
                ? 'border-[var(--primary)] text-[var(--primary)]'
                : 'border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && (
        <OverviewTab inv={inv} onGoToAnalysis={() => setTab("analysis")} onSave={handleSaveDecision} />
      )}
      {tab === 'evidence' && <EvidenceTab inv={inv} />}
      {tab === 'analysis' && <AnalysisTab inv={inv} overallScore={inv.riskScore} />}
      {tab === 'audit' && <AuditTab inv={inv} />}
    </div>
  );
}
