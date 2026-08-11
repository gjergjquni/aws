import { analysisStages } from "@/data/agents";
import type { AIRecommendation, CreateInvestigationInput } from "@/types";

export interface AnalysisResult {
  riskScore: number;
  recommendation: AIRecommendation;
  summary: string;
  visualEvidenceScore: number;
  visualEvidenceConfidence: number;
  claimIntelligenceScore: number;
  claimIntelligenceConfidence: number;
  visualEvidenceFindings: string[];
  claimIntelligenceFindings: string[];
}

const STAGE_DURATION_MS = 1400;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildAnalysis(input: CreateInvestigationInput): AnalysisResult {
  const hasImage = Boolean(input.imageUrl);
  const visualScore = hasImage ? 55 + Math.floor(Math.random() * 30) : 0;
  const claimScore = 40 + Math.floor(Math.random() * 35);
  const riskScore = hasImage
    ? Math.round(visualScore * 0.5 + claimScore * 0.5)
    : claimScore;

  let recommendation: AIRecommendation = "manual_review";
  if (riskScore < 35) recommendation = "approve";
  if (riskScore >= 75) recommendation = "escalate";

  return {
    riskScore,
    recommendation,
    summary: hasImage
      ? "AI analysis identified potential risk signals across visual and textual evidence. Human review is recommended before making a final determination."
      : "No image was submitted. Claim intelligence analysis completed with limited visual evidence. Manual review recommended.",
    visualEvidenceScore: visualScore,
    visualEvidenceConfidence: hasImage ? 78 + Math.floor(Math.random() * 15) : 0,
    claimIntelligenceScore: claimScore,
    claimIntelligenceConfidence: 72 + Math.floor(Math.random() * 18),
    visualEvidenceFindings: hasImage
      ? ["Metadata reviewed", "Damage pattern analyzed", "Editing indicators checked"]
      : [],
    claimIntelligenceFindings: [
      "Language pattern analyzed",
      "Timeline consistency checked",
      "Fraud pattern similarity assessed",
    ],
  };
}

export const analysisApi = {
  stages: analysisStages,

  async runAnalysis(
    input: CreateInvestigationInput,
    onStageComplete?: (stageIndex: number) => void,
  ): Promise<AnalysisResult> {
    for (let i = 0; i < analysisStages.length; i++) {
      await delay(STAGE_DURATION_MS);
      onStageComplete?.(i);
    }

    return buildAnalysis(input);
  },
};
