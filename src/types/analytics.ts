export interface TimeSeriesPoint {
  date: string;
  total: number;
  resolved: number;
  high?: number;
}

export interface DistributionItem {
  name: string;
  value: number;
  color?: string;
}

export interface DashboardKpi {
  label: string;
  value: number | string;
  trend: string;
  trendUp: boolean | null;
}

export interface StatTile {
  label: string;
  value: string;
  sub: string;
}
