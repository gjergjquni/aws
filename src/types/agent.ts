export interface AgentResult {
  name: string;
  accuracy: number;
  avgScore: number;
  avgConfidence: number;
}

export interface AgentDefinition {
  id: string;
  name: string;
  description: string;
  status: "active" | "roadmap";
}

export interface AnalysisStage {
  key: string;
  label: string;
  description: string;
}
