import type {
  AIRecommendation,
  HumanDecision,
  InvestigationCategory,
  InvestigationStatus,
} from "@/types";

export const CATEGORY_LABELS: Record<InvestigationCategory, string> = {
  electronics: "Electronics",
  clothing: "Clothing",
  home: "Home",
  sporting: "Sporting",
  books: "Books",
};

export const STATUS_LABELS: Record<InvestigationStatus, string> = {
  pending: "Pending",
  in_review: "In Review",
  resolved: "Resolved",
  escalated: "Escalated",
};

export const RECOMMENDATION_LABELS: Record<AIRecommendation, string> = {
  approve: "Approve",
  manual_review: "Manual Review",
  escalate: "Escalate",
};

export const DECISION_LABELS: Record<Exclude<HumanDecision, null>, string> = {
  approved: "Approved",
  rejected: "Rejected",
  manual_review: "Manual Review",
};

export function formatDate(
  date: string,
  style: "short" | "medium" | "long" = "medium",
): string {
  const options: Intl.DateTimeFormatOptions =
    style === "short"
      ? { day: "numeric", month: "short" }
      : style === "long"
        ? { day: "numeric", month: "long", year: "numeric" }
        : { day: "numeric", month: "short", year: "numeric" };

  return new Date(date).toLocaleDateString("en-GB", options);
}

export function formatCurrency(value: number): string {
  return `$${value.toLocaleString()}`;
}

export function categoryLabel(category: InvestigationCategory | string): string {
  return CATEGORY_LABELS[category as InvestigationCategory] ?? category;
}
