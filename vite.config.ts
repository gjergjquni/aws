import { defineConfig, loadEnv, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  // Server-side only: these values are read by the dev server process and are
  // NEVER bundled into browser JavaScript (only VITE_-prefixed vars would be).
  const env = loadEnv(mode, rootDir, "");

  const agentApiUrl =
    env.AEGIS_API_URL ||
    "https://xrx4q1jq0k.execute-api.us-east-1.amazonaws.com/prod";
  const agentApiKey = env.AEGIS_API_KEY || "";
  const backendApiUrl =
    env.AEGIS_BACKEND_URL ||
    "https://q7phgdg1m5.execute-api.us-east-1.amazonaws.com/Prod";
  const evidenceBucketUrl =
    env.AEGIS_EVIDENCE_BUCKET_URL ||
    "https://aws-s3-877791042657-us-east-1-an.s3.amazonaws.com";

  if (!agentApiKey) {
    console.warn(
      "[aegis] AEGIS_API_KEY is not set — /api/agent requests will be rejected by the Agent API. Add it to a local .env file (never commit it).",
    );
  }

  // The x-api-key is attached here, on the server side of the proxy.
  const proxy: Record<string, ProxyOptions> = {
    "/api/agent": {
      target: agentApiUrl,
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api\/agent/, ""),
      headers: agentApiKey ? { "x-api-key": agentApiKey } : undefined,
      timeout: 60_000,
      proxyTimeout: 60_000,
    },
    "/api/backend": {
      target: backendApiUrl,
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api\/backend/, ""),
      timeout: 60_000,
      proxyTimeout: 60_000,
    },
    "/api/evidence": {
      target: evidenceBucketUrl,
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api\/evidence/, ""),
      timeout: 60_000,
      proxyTimeout: 60_000,
    },
  };

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(rootDir, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: parseInt(process.env.PORT || "8443"),
      strictPort: true,
      proxy,
    },
    preview: {
      host: "0.0.0.0",
      port: parseInt(process.env.PORT || "8443"),
      proxy,
    },
  };
});
