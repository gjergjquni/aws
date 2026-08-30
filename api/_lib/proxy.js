const HOP_BY_HOP = [
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
];

function jsonError(status, message) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Forward a browser request to an upstream API. Extra headers (e.g. x-api-key)
 * are attached here so secrets never ship in the frontend bundle.
 */
export async function proxyTo(request, { prefix, targetBase, extraHeaders = {} }) {
  const base = String(targetBase || "").replace(/\/$/, "");
  if (!base) {
    return jsonError(500, "Proxy target is not configured.");
  }

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204 });
  }

  const url = new URL(request.url);
  // Nested /api/backend/* and /api/agent/* are rewritten to the root
  // function with ?__path=/rest because Vite on Vercel does not support
  // catch-all [...path] routes.
  const injectedPath = url.searchParams.get("__path");
  url.searchParams.delete("__path");

  let rest = injectedPath
    ? injectedPath
    : url.pathname.startsWith(prefix)
      ? url.pathname.slice(prefix.length)
      : url.pathname;
  if (!rest.startsWith("/")) rest = `/${rest}`;
  if (rest === "/") rest = "";

  const search = url.searchParams.toString();
  const target = `${base}${rest}${search ? `?${search}` : ""}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") || "application/json");
  headers.set("accept-encoding", "identity");

  for (const [key, value] of Object.entries(extraHeaders)) {
    if (value) headers.set(key, value);
  }

  const method = request.method.toUpperCase();
  const init = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream;
  try {
    upstream = await fetch(target, init);
  } catch {
    return jsonError(502, "Network error — could not reach the upstream API.");
  }

  const outHeaders = new Headers(upstream.headers);
  for (const name of HOP_BY_HOP) outHeaders.delete(name);
  outHeaders.delete("content-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}
