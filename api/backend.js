import { proxyTo } from "./_lib/proxy.js";

export const config = {
  runtime: "edge",
  maxDuration: 60,
};

const DEFAULT_BACKEND_API =
  "https://q7phgdg1m5.execute-api.us-east-1.amazonaws.com/Prod";

export default function handler(request) {
  return proxyTo(request, {
    prefix: "/api/backend",
    targetBase: process.env.AEGIS_BACKEND_URL || DEFAULT_BACKEND_API,
  });
}
