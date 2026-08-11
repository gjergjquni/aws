import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import RiskBadge, { getRiskLevel, StatusBadge } from "@/components/RiskBadge";
import LoadingState from "@/components/LoadingState";
import { useAuth } from "@/hooks/useAuth";
import { analyticsApi } from "@/services/analyticsApi";
import { investigationsApi } from "@/services/investigationsApi";
import type { DistributionItem, Investigation, TimeSeriesPoint } from "@/types";
import { formatDate } from "@/utils/labels";

const KPI_CONFIG = [
  {
    label: "Total Investigations",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
        <line x1="5" y1="6.5" x2="11" y2="6.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="5" y1="9" x2="9" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
    accentBg: "bg-[var(--accent)]",
    accentText: "text-[var(--primary)]",
  },
  {
    label: "Pending Review",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.4" />
        <path d="M8 5v3.5l2 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    accentBg: "bg-amber-50 dark:bg-amber-950/30",
    accentText: "text-amber-600 dark:text-amber-400",
  },
  {
    label: "High Risk",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path d="M8 1.5L1.5 13.5h13L8 1.5z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
        <line x1="8" y1="6.5" x2="8" y2="9.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="8" cy="11.5" r="0.75" fill="currentColor" />
      </svg>
    ),
    accentBg: "bg-red-50 dark:bg-red-950/30",
    accentText: "text-red-600 dark:text-red-400",
  },
  {
    label: "Reviewed",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.4" />
        <path d="M5.5 8.5L7 10L10.5 6.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    accentBg: "bg-green-50 dark:bg-green-950/30",
    accentText: "text-green-600 dark:text-green-400",
  },
] as const;

const KPI_STYLES = KPI_CONFIG.map(({ accentBg, accentText }) => ({ accentBg, accentText }));

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: "8px",
  fontSize: "12px",
  color: "var(--foreground)",
};

export default function Dashboard() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [recent, setRecent] = useState<Investigation[]>([]);
  const [activity, setActivity] = useState<TimeSeriesPoint[]>([]);
  const [riskDist, setRiskDist] = useState<DistributionItem[]>([]);
  const [kpis, setKpis] = useState<
    readonly {
      label: string;
      value: number;
      trend: string;
      trendUp: boolean | null;
    }[]
  >([]);

  useEffect(() => {
    Promise.all([
      investigationsApi.getRecent(4),
      analyticsApi.getDashboardActivity(),
      analyticsApi.getRiskDistribution(),
      analyticsApi.getDashboardKpis(),
    ])
      .then(([recentData, activityData, riskData, kpiData]) => {
        setRecent(recentData);
        setActivity(activityData);
        setRiskDist(riskData);
        setKpis(kpiData);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingState label="Loading dashboard…" />;
  }

  return (
    <div className="px-6 py-6 max-w-[1400px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-7">
        <div>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Dashboard</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
            Good morning, {user?.name ?? "Investigator"} — here is your investigation workload.
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

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {kpis.map((kpi, index) => {
          const style = KPI_STYLES[index] ?? KPI_STYLES[0];
          const icon = KPI_CONFIG[index]?.icon;
          return (
            <div
              key={kpi.label}
              className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-4"
            >
              <div className="flex items-start justify-between mb-3">
                <p className="text-xs font-medium text-[var(--muted-foreground)]">{kpi.label}</p>
                <div className={`p-1.5 rounded-md ${style.accentBg} ${style.accentText}`}>{icon}</div>
              </div>
              <div className="text-3xl font-bold text-[var(--foreground)] font-mono">{kpi.value}</div>
              <div
                className={`text-xs mt-1.5 font-medium ${
                  kpi.trendUp === true
                    ? "text-green-600 dark:text-green-400"
                    : kpi.trendUp === false
                      ? "text-red-600 dark:text-red-400"
                      : "text-[var(--muted-foreground)]"
                }`}
              >
                {kpi.trend}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-5">
        <div className="lg:col-span-2 bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">Investigation Activity</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={activity} margin={{ left: -20, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="total" stroke="#2563EB" strokeWidth={2} dot={false} name="Total" />
              <Line
                type="monotone"
                dataKey="resolved"
                stroke="#22C55E"
                strokeWidth={2}
                dot={false}
                name="Resolved"
                strokeDasharray="4 2"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5">
          <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">Risk Distribution</h3>
          <div className="flex justify-center mb-3">
            <ResponsiveContainer width={160} height={140}>
              <PieChart>
                <Pie
                  data={riskDist}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={65}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {riskDist.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2">
            {riskDist.map((d) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                  <span className="text-[var(--muted-foreground)]">{d.name}</span>
                </div>
                <span className="font-mono font-medium text-[var(--foreground)]">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h3 className="text-sm font-semibold text-[var(--foreground)]">Recent Investigations</h3>
          <Link to="/investigations" className="text-xs text-[var(--primary)] hover:underline">
            View all →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-medium text-[var(--muted-foreground)] border-b border-[var(--border)]">
                <th className="px-5 py-3">Claim ID</th>
                <th className="px-5 py-3">Product</th>
                <th className="px-5 py-3">Submitted</th>
                <th className="px-5 py-3">Risk</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {recent.map((inv) => (
                <tr
                  key={inv.id}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)] transition-colors"
                >
                  <td className="px-5 py-3 font-mono text-xs font-medium text-[var(--primary)]">
                    {inv.claimId}
                  </td>
                  <td className="px-5 py-3 text-sm font-medium text-[var(--foreground)]">{inv.product}</td>
                  <td className="px-5 py-3 text-sm text-[var(--muted-foreground)]">
                    {formatDate(inv.submitted, "short")}
                  </td>
                  <td className="px-5 py-3">
                    <RiskBadge score={inv.riskScore} level={getRiskLevel(inv.riskScore)} />
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-5 py-3">
                    <Link to={`/investigations/${inv.id}`} className="text-xs text-[var(--primary)] hover:underline">
                      Review →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
