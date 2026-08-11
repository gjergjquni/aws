import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import LoadingState from "@/components/LoadingState";
import { analyticsApi } from "@/services/analyticsApi";
import type { AgentResult, DistributionItem, StatTile, TimeSeriesPoint } from "@/types";

const tooltipStyle = {
  backgroundColor: "var(--card)",
  border: "1px solid var(--border)",
  borderRadius: "8px",
  fontSize: "12px",
  color: "var(--foreground)",
};

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-lg)] p-5 ${className}`}>
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: string }) {
  return <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">{children}</h3>;
}

export default function Analytics() {
  const [loading, setLoading] = useState(true);
  const [dateFilter, setDateFilter] = useState("7d");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [overTime, setOverTime] = useState<TimeSeriesPoint[]>([]);
  const [riskDist, setRiskDist] = useState<DistributionItem[]>([]);
  const [recDist, setRecDist] = useState<DistributionItem[]>([]);
  const [decisionDist, setDecisionDist] = useState<DistributionItem[]>([]);
  const [agentPerf, setAgentPerf] = useState<AgentResult[]>([]);
  const [statTiles, setStatTiles] = useState<StatTile[]>([]);

  useEffect(() => {
    Promise.all([
      analyticsApi.getInvestigationsOverTime(),
      analyticsApi.getRiskDistribution(),
      analyticsApi.getRecommendationDistribution(),
      analyticsApi.getDecisionDistribution(),
      analyticsApi.getAgentPerformance(),
      analyticsApi.getStatTiles(),
    ])
      .then(([time, risk, rec, decision, agents, tiles]) => {
        setOverTime(time);
        setRiskDist(risk);
        setRecDist(rec);
        setDecisionDist(decision);
        setAgentPerf(agents);
        setStatTiles(tiles);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingState label="Loading analytics…" />;
  }

  return (
    <div className="px-6 py-6 max-w-[1400px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-[var(--foreground)]">Analytics</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
            Investigation patterns and AI performance insights.
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            aria-label="Date range"
            className="text-xs bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] rounded-[var(--radius)] px-2.5 py-1.5 outline-none"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Category filter"
            className="text-xs bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] rounded-[var(--radius)] px-2.5 py-1.5 outline-none"
          >
            <option value="all">All Categories</option>
            <option value="electronics">Electronics</option>
            <option value="clothing">Clothing</option>
          </select>
          <Link
            to="/reports"
            className="inline-flex items-center px-3 py-1.5 border border-[var(--border)] text-xs font-medium text-[var(--foreground)] rounded-[var(--radius)] hover:bg-[var(--muted)]"
          >
            View Reports
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {statTiles.map((t) => (
          <Card key={t.label}>
            <div className="text-2xl font-bold font-mono text-[var(--foreground)]">{t.value}</div>
            <div className="text-xs font-medium text-[var(--foreground)] mt-1">{t.label}</div>
            <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{t.sub}</div>
          </Card>
        ))}
      </div>

      <Card className="mb-5">
        <SectionTitle>Investigations Over Time</SectionTitle>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={overTime} margin={{ left: -10, right: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="total" stroke="#2563EB" strokeWidth={2} dot={false} name="Total" />
            <Line type="monotone" dataKey="resolved" stroke="#22C55E" strokeWidth={2} dot={false} name="Resolved" />
            <Line type="monotone" dataKey="high" stroke="#EF4444" strokeWidth={2} dot={false} name="High Risk" strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        <Card>
          <SectionTitle>Risk Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={riskDist} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                {riskDist.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <SectionTitle>AI Recommendation Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={recDist} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="#2563EB" radius={[3, 3, 0, 0]} name="Count" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <SectionTitle>Human Decision Distribution</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={decisionDist} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="#8B5CF6" radius={[3, 3, 0, 0]} name="Count" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card>
        <SectionTitle>Agent Performance</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--muted-foreground)] border-b border-[var(--border)]">
                <th className="pb-3 font-medium">Agent</th>
                <th className="pb-3 font-medium">Agreement Rate</th>
                <th className="pb-3 font-medium">Avg Risk Score</th>
                <th className="pb-3 font-medium">Avg Confidence</th>
              </tr>
            </thead>
            <tbody>
              {agentPerf.map((a) => (
                <tr key={a.name} className="border-b border-[var(--border)] last:border-0">
                  <td className="py-3 font-medium text-[var(--foreground)]">{a.name}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 max-w-[80px] h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
                        <div className="h-full bg-[var(--primary)] rounded-full" style={{ width: `${a.accuracy}%` }} />
                      </div>
                      <span className="text-xs font-mono text-[var(--foreground)]">{a.accuracy}%</span>
                    </div>
                  </td>
                  <td className="py-3 font-mono text-sm text-[var(--foreground)]">{a.avgScore}</td>
                  <td className="py-3 font-mono text-sm text-[var(--foreground)]">{a.avgConfidence}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
