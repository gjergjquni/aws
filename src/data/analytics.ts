import type {
  AgentResult,
  DistributionItem,
  StatTile,
  TimeSeriesPoint,
} from "@/types";

export const investigationsOverTime: TimeSeriesPoint[] = [
  { date: "Aug 4", total: 14, resolved: 11, high: 2 },
  { date: "Aug 5", total: 18, resolved: 14, high: 3 },
  { date: "Aug 6", total: 12, resolved: 10, high: 1 },
  { date: "Aug 7", total: 22, resolved: 18, high: 4 },
  { date: "Aug 8", total: 19, resolved: 15, high: 3 },
  { date: "Aug 9", total: 21, resolved: 16, high: 5 },
  { date: "Aug 10", total: 18, resolved: 10, high: 4 },
];

export const dashboardActivity: TimeSeriesPoint[] = investigationsOverTime.map(
  ({ date, total, resolved }) => ({ date, total, resolved }),
);

export const riskDistribution: DistributionItem[] = [
  { name: "Low Risk", value: 51, color: "#22C55E" },
  { name: "Elevated", value: 42, color: "#F59E0B" },
  { name: "High Risk", value: 19, color: "#EF4444" },
  { name: "Insufficient", value: 12, color: "#94A3B8" },
];

export const recommendationDistribution: DistributionItem[] = [
  { name: "Approve", value: 48 },
  { name: "Manual Review", value: 58 },
  { name: "Escalate", value: 18 },
];

export const decisionDistribution: DistributionItem[] = [
  { name: "Approved", value: 52 },
  { name: "Rejected", value: 28 },
  { name: "Pending", value: 44 },
];

export const agentPerformance: AgentResult[] = [
  { name: "Visual Evidence", accuracy: 87, avgScore: 64, avgConfidence: 84 },
  { name: "Claim Intel", accuracy: 82, avgScore: 58, avgConfidence: 81 },
  { name: "Orchestrator", accuracy: 85, avgScore: 61, avgConfidence: 83 },
];

export const analyticsStatTiles: StatTile[] = [
  { label: "Avg Risk Score", value: "61", sub: "across all investigations" },
  { label: "AI Accuracy", value: "85%", sub: "vs human decisions" },
  { label: "Avg Processing", value: "1.2s", sub: "end-to-end analysis" },
  { label: "Agreement Rate", value: "79%", sub: "AI vs investigator" },
];

export const dashboardKpis = [
  {
    label: "Total Investigations",
    value: 124,
    trend: "+8 this week",
    trendUp: true,
  },
  {
    label: "Pending Review",
    value: 18,
    trend: "3 new today",
    trendUp: null,
  },
  {
    label: "High Risk",
    value: 12,
    trend: "↑2 from last week",
    trendUp: false,
  },
  {
    label: "Reviewed",
    value: 94,
    trend: "+12 this week",
    trendUp: true,
  },
] as const;
