import { proxyTo } from "../_lib/proxy.js";

export const config = {
  runtime: "edge",
  maxDuration: 60,
};

const DEFAULT_AGENT_API =
  "https://xrx4q1jq0k.execute-api.us-east-1.amazonaws.com/prod";

export default function handler(request) {
  const apiKey = process.env.AEGIS_API_KEY || "";
  if (!apiKey) {
    return new Response(
      JSON.stringify({
        error:
          "AEGIS_API_KEY is not set. Add it in the Vercel project environment variables.",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  return proxyTo(request, {
    prefix: "/api/agent",
    targetBase: process.env.AEGIS_API_URL || DEFAULT_AGENT_API,
    extraHeaders: { "x-api-key": apiKey },
  });
}
