import { investigations as seedInvestigations } from "@/data/investigations";
import { getRiskLevel } from "@/utils/risk";
import type {
  CreateInvestigationInput,
  Investigation,
  InvestigationFilters,
  UpdateDecisionInput,
} from "@/types";

let store: Investigation[] = seedInvestigations.map((inv) => ({ ...inv }));

function delay(ms = 120): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function matchesFilters(inv: Investigation, filters: InvestigationFilters): boolean {
  const { search, riskLevel, status, category } = filters;

  if (search?.trim()) {
    const q = search.toLowerCase();
    const matches =
      inv.claimId.toLowerCase().includes(q) ||
      inv.product.toLowerCase().includes(q) ||
      inv.category.toLowerCase().includes(q) ||
      inv.status.toLowerCase().includes(q);
    if (!matches) return false;
  }

  if (riskLevel && riskLevel !== "all" && inv.riskLevel !== riskLevel) return false;
  if (status && status !== "all" && inv.status !== status) return false;
  if (category && category !== "all" && inv.category !== category) return false;

  return true;
}

function nextClaimId(): string {
  const max = store.reduce((acc, inv) => {
    const num = parseInt(inv.claimId.replace("CLM-", ""), 10);
    return Number.isNaN(num) ? acc : Math.max(acc, num);
  }, 0);
  return `CLM-${String(max + 1).padStart(3, "0")}`;
}

export const investigationsApi = {
  async getAll(): Promise<Investigation[]> {
    await delay();
    return store.map((inv) => ({ ...inv }));
  },

  async getById(id: string): Promise<Investigation | null> {
    await delay();
    const inv = store.find((item) => item.id === id);
    return inv ? { ...inv } : null;
  },

  async search(query: string): Promise<Investigation[]> {
    return investigationsApi.filter({ search: query });
  },

  async filter(filters: InvestigationFilters): Promise<Investigation[]> {
    await delay();
    return store.filter((inv) => matchesFilters(inv, filters)).map((inv) => ({ ...inv }));
  },

  async getRecent(limit = 4): Promise<Investigation[]> {
    await delay();
    return [...store]
      .sort((a, b) => new Date(b.submitted).getTime() - new Date(a.submitted).getTime())
      .slice(0, limit)
      .map((inv) => ({ ...inv }));
  },

  async getResolved(): Promise<Investigation[]> {
    await delay();
    return store
      .filter((inv) => inv.status === "resolved" || inv.humanDecision !== null)
      .map((inv) => ({ ...inv }));
  },

  async updateDecision(id: string, input: UpdateDecisionInput): Promise<Investigation> {
    await delay(200);
    const index = store.findIndex((inv) => inv.id === id);
    if (index === -1) throw new Error("Investigation not found");

    const updated: Investigation = {
      ...store[index],
      humanDecision: input.decision,
      notes: input.notes,
      investigator: input.investigator,
      status: input.decision === "manual_review" ? "in_review" : "resolved",
      auditTrail: [
        ...store[index].auditTrail,
        {
          time: new Date().toLocaleTimeString("en-GB", { hour12: false }),
          component: "Investigator",
          event: `Human decision recorded: ${input.decision?.replace("_", " ")}`,
          status: "success",
        },
      ],
    };

    store[index] = updated;
    return { ...updated };
  },

  async create(input: CreateInvestigationInput, analysis: {
    riskScore: number;
    recommendation: Investigation["recommendation"];
    summary: string;
    visualEvidenceScore: number;
    visualEvidenceConfidence: number;
    claimIntelligenceScore: number;
    claimIntelligenceConfidence: number;
    visualEvidenceFindings: string[];
    claimIntelligenceFindings: string[];
  }): Promise<Investigation> {
    await delay(100);

    const id = String(Date.now());
    const claimId = nextClaimId();
    const riskLevel = getRiskLevel(analysis.riskScore);

    const investigation: Investigation = {
      id,
      claimId,
      product: input.product,
      category: input.category,
      orderValue: input.orderValue,
      submitted: new Date().toISOString().slice(0, 10),
      riskScore: analysis.riskScore,
      riskLevel,
      recommendation: analysis.recommendation,
      status: "pending",
      investigator: null,
      humanDecision: null,
      customerExplanation: input.customerExplanation,
      visualEvidenceScore: analysis.visualEvidenceScore,
      visualEvidenceConfidence: analysis.visualEvidenceConfidence,
      claimIntelligenceScore: analysis.claimIntelligenceScore,
      claimIntelligenceConfidence: analysis.claimIntelligenceConfidence,
      imageUrl: input.imageUrl,
      summary: analysis.summary,
      notes: "",
      visualEvidenceFindings: analysis.visualEvidenceFindings,
      claimIntelligenceFindings: analysis.claimIntelligenceFindings,
      imageMetadata: input.imageUrl
        ? {
            fileType: "JPEG",
            dimensions: "2048 × 1536",
            exif: "Present",
            editingSoftware: "Not detected",
          }
        : {
            fileType: "—",
            dimensions: "—",
            exif: "—",
            editingSoftware: "—",
          },
      auditTrail: [
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "System", event: "Claim submitted", status: "info" },
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "Privacy Guard", event: "PII removed before AI processing", status: "success" },
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "Visual Evidence Agent", event: input.imageUrl ? "Image analysis completed" : "Skipped — no image provided", status: input.imageUrl ? "success" : "warning", model: "Amazon Nova Pro v1.0" },
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "Claim Intelligence Agent", event: "Text analysis completed", status: "success", model: "Amazon Nova Pro v1.0" },
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "Orchestrator", event: "Evidence combination completed", status: "success", model: "Amazon Nova Pro v1.0" },
        { time: new Date().toLocaleTimeString("en-GB", { hour12: false }), component: "System", event: `AI recommendation generated: ${analysis.recommendation.replace("_", " ")}`, status: "info" },
      ],
    };

    store = [investigation, ...store];
    return { ...investigation };
  },
};
