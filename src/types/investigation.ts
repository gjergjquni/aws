export type RiskLevel = "low" | "elevated" | "high" | "insufficient";

export type InvestigationStatus = "pending" | "resolved" | "escalated" | "in_review";

export type AIRecommendation = "approve" | "manual_review" | "escalate";

export type HumanDecision = "approved" | "rejected" | "manual_review" | null;

export type InvestigationCategory =
  | "electronics"
  | "clothing"
  | "home"
  | "sporting"
  | "books";

export interface ImageMetadata {
  fileType: string;
  dimensions: string;
  exif: string;
  editingSoftware: string;
}

export interface AuditEvent {
  time: string;
  component: string;
  event: string;
  status: "success" | "info" | "warning";
  model?: string;
}

export interface Investigation {
  id: string;
  claimId: string;
  product: string;
  category: InvestigationCategory;
  orderValue: number;
  submitted: string;
  riskScore: number;
  riskLevel: RiskLevel;
  recommendation: AIRecommendation;
  status: InvestigationStatus;
  investigator: string | null;
  humanDecision: HumanDecision;
  customerExplanation: string;
  visualEvidenceScore: number;
  visualEvidenceConfidence: number;
  claimIntelligenceScore: number;
  claimIntelligenceConfidence: number;
  imageUrl: string | null;
  summary: string;
  notes: string;
  auditTrail: AuditEvent[];
  visualEvidenceFindings: string[];
  claimIntelligenceFindings: string[];
  imageMetadata: ImageMetadata;
}

export interface InvestigationFilters {
  search?: string;
  riskLevel?: RiskLevel | "all";
  status?: InvestigationStatus | "all";
  category?: InvestigationCategory | "all";
}

export interface CreateInvestigationInput {
  product: string;
  category: InvestigationCategory;
  orderValue: number;
  customerExplanation: string;
  imageUrl: string | null;
}

export interface UpdateDecisionInput {
  decision: HumanDecision;
  notes: string;
  investigator: string;
}
