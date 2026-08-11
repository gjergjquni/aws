import {
  agentPerformance,
  analyticsStatTiles,
  dashboardActivity,
  dashboardKpis,
  decisionDistribution,
  investigationsOverTime,
  recommendationDistribution,
  riskDistribution,
} from "@/data/analytics";

function delay(ms = 80): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const analyticsApi = {
  async getDashboardKpis() {
    await delay();
    return dashboardKpis;
  },

  async getDashboardActivity() {
    await delay();
    return dashboardActivity;
  },

  async getRiskDistribution() {
    await delay();
    return riskDistribution;
  },

  async getInvestigationsOverTime() {
    await delay();
    return investigationsOverTime;
  },

  async getRecommendationDistribution() {
    await delay();
    return recommendationDistribution;
  },

  async getDecisionDistribution() {
    await delay();
    return decisionDistribution;
  },

  async getAgentPerformance() {
    await delay();
    return agentPerformance;
  },

  async getStatTiles() {
    await delay();
    return analyticsStatTiles;
  },
};
