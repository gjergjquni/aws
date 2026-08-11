import type { RiskLevel } from "@/types";

export function getRiskLevel(score: number): RiskLevel {
  if (score === 0) return "insufficient";
  if (score < 40) return "low";
  if (score < 70) return "elevated";
  return "high";
}

export interface RiskColorScheme {
  text: string;
  bg: string;
  border: string;
  dot: string;
  label: string;
  stroke: string;
}

export function getRiskColorScheme(score: number): RiskColorScheme {
  if (score >= 70) {
    return {
      text: "text-red-600 dark:text-red-400",
      bg: "bg-red-50 dark:bg-red-950/30",
      border: "border-red-200 dark:border-red-800",
      dot: "bg-red-500",
      label: "High Risk",
      stroke: "#EF4444",
    };
  }
  if (score >= 40) {
    return {
      text: "text-amber-600 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-950/30",
      border: "border-amber-200 dark:border-amber-800",
      dot: "bg-amber-500",
      label: "Elevated",
      stroke: "#F59E0B",
    };
  }
  return {
    text: "text-green-600 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-950/30",
    border: "border-green-200 dark:border-green-800",
    dot: "bg-green-500",
    label: "Low Risk",
    stroke: "#22C55E",
  };
}

export function getRiskDisplay(score: number) {
  const level = getRiskLevel(score);
  const scheme = getRiskColorScheme(score);
  return { level, ...scheme };
}
