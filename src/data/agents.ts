import type { AgentDefinition } from "@/types";

export const mvpAgents: AgentDefinition[] = [
  {
    id: "visual-evidence",
    name: "Visual Evidence Agent",
    description:
      "Analyzes uploaded product images for manipulation and authenticity.",
    status: "active",
  },
  {
    id: "claim-intelligence",
    name: "Claim Intelligence Agent",
    description:
      "Analyzes customer explanations for fraud indicators and patterns.",
    status: "active",
  },
  {
    id: "orchestrator",
    name: "Orchestrator Agent",
    description:
      "Combines agent outputs to produce an overall risk assessment.",
    status: "active",
  },
];

export const roadmapAgents: AgentDefinition[] = [
  {
    id: "shipment-verification",
    name: "Shipment Verification Agent",
    description: "Verify carrier tracking data and delivery confirmation.",
    status: "roadmap",
  },
  {
    id: "marketplace-intelligence",
    name: "Marketplace Intelligence Agent",
    description: "Cross-reference marketplace listing history and pricing.",
    status: "roadmap",
  },
  {
    id: "threat-intelligence",
    name: "Threat Intelligence Agent",
    description: "Match against known fraud syndicate patterns.",
    status: "roadmap",
  },
];
