import type { RiskLevel } from "@/types";
import { getRiskLevel } from "@/utils/risk";

export { getRiskLevel };

interface Props {
  score?: number;
  level: RiskLevel;
  size?: "sm" | "md";
}

const CONFIG: Record<
  RiskLevel,
  { label: string; dot: string; bg: string; text: string; border: string }
> = {
  low: {
    label: "Low Risk",
    dot: "bg-green-500",
    bg: "bg-green-50 dark:bg-green-950/40",
    text: "text-green-700 dark:text-green-400",
    border: "border-green-200 dark:border-green-800",
  },
  elevated: {
    label: "Elevated",
    dot: "bg-amber-500",
    bg: "bg-amber-50 dark:bg-amber-950/40",
    text: "text-amber-700 dark:text-amber-400",
    border: "border-amber-200 dark:border-amber-800",
  },
  high: {
    label: "High Risk",
    dot: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-950/40",
    text: "text-red-700 dark:text-red-400",
    border: "border-red-200 dark:border-red-800",
  },
  insufficient: {
    label: "Insufficient Data",
    dot: "bg-slate-400",
    bg: "bg-slate-50 dark:bg-slate-800/40",
    text: "text-slate-600 dark:text-slate-400",
    border: "border-slate-200 dark:border-slate-700",
  },
};

export default function RiskBadge({ score, level, size = "sm" }: Props) {
  const c = CONFIG[level];
  return (
    <span
      className={`inline-flex items-center gap-1.5 border rounded-full font-medium ${c.bg} ${c.text} ${c.border} ${
        size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1"
      }`}
      aria-label={`Risk level: ${c.label}${score !== undefined ? `, score ${score}` : ""}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.dot}`} aria-hidden />
      {score !== undefined ? (
        <>
          <span className="font-mono font-medium">{score}</span>
          <span className="opacity-60">/100</span>
        </>
      ) : (
        c.label
      )}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; bg: string; text: string }> = {
    pending: {
      label: "Pending",
      bg: "bg-amber-50 dark:bg-amber-950/30",
      text: "text-amber-700 dark:text-amber-400",
    },
    resolved: {
      label: "Resolved",
      bg: "bg-green-50 dark:bg-green-950/30",
      text: "text-green-700 dark:text-green-400",
    },
    escalated: {
      label: "Escalated",
      bg: "bg-red-50 dark:bg-red-950/30",
      text: "text-red-700 dark:text-red-400",
    },
    in_review: {
      label: "In Review",
      bg: "bg-blue-50 dark:bg-blue-950/30",
      text: "text-blue-700 dark:text-blue-400",
    },
  };
  const c = config[status] ?? { label: status, bg: "bg-slate-50", text: "text-slate-600" };
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

export function RecommendationBadge({ rec }: { rec: string }) {
  const config: Record<string, { label: string; style: string }> = {
    approve: {
      label: "Approve",
      style: "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400",
    },
    manual_review: {
      label: "Manual Review",
      style: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400",
    },
    escalate: {
      label: "Escalate",
      style: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400",
    },
  };
  const c = config[rec] ?? { label: rec, style: "bg-slate-50 text-slate-600" };
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${c.style}`}>
      {c.label}
    </span>
  );
}

export function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) return <span className="text-xs text-[var(--muted-foreground)] italic">—</span>;
  const config: Record<string, { label: string; style: string }> = {
    approved: { label: "Approved", style: "text-green-600 dark:text-green-400" },
    rejected: { label: "Rejected", style: "text-red-600 dark:text-red-400" },
    manual_review: { label: "Manual Review", style: "text-amber-600 dark:text-amber-400" },
  };
  const c = config[decision] ?? { label: decision, style: "text-[var(--muted-foreground)]" };
  return <span className={`text-xs font-medium ${c.style}`}>{c.label}</span>;
}
