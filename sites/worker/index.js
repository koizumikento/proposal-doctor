const MAX_REQUEST_BYTES = 16384;
const failure = (status, error, headers = {}) => Response.json(
  { error }, { status, headers: { "Cache-Control": "no-store", ...headers } },
);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/mcp") return failure(404, "Not found");
    // Only Sites dispatch supplies this identity. Service access is not a user grant.
    const user = request.headers.get("oai-authenticated-user-id");
    if (!user) return failure(401, "Sign in with ChatGPT");
    let backend;
    let allowed;
    try {
      backend = new URL(env.PROPOSAL_DOCTOR_BACKEND_URL);
      allowed = JSON.parse(env.PROPOSAL_DOCTOR_ALLOWED_USER_IDS);
      if (backend.protocol !== "https:" || backend.pathname !== "/mcp" ||
          backend.username || backend.password || backend.search || backend.hash ||
          !Array.isArray(allowed) || !allowed.length ||
          !allowed.every(id => typeof id === "string" && id.length > 0) ||
          typeof env.PROPOSAL_DOCTOR_BACKEND_TOKEN !== "string" ||
          !/^[\x21-\x7e]{32,}$/.test(env.PROPOSAL_DOCTOR_BACKEND_TOKEN)) {
        throw new Error("Invalid configuration");
      }
    } catch {
      return failure(503, "Backend is not configured");
    }
    if (!allowed.includes(user)) return failure(403, "User is not authorized");
    const origin = request.headers.get("Origin");
    if (origin && origin !== url.origin) return failure(403, "Invalid Origin");
    if (request.method !== "POST") return failure(405, "Use POST", { Allow: "POST" });
    if (request.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
      return failure(415, "Use application/json");
    }
    const headers = new Headers({
      "Authorization": `Bearer ${env.PROPOSAL_DOCTOR_BACKEND_TOKEN}`,
      "X-Proposal-User-Id": user,
      "Content-Type": "application/json",
      "Accept": request.headers.get("Accept") || "",
    });
    const version = request.headers.get("MCP-Protocol-Version");
    if (version) headers.set("MCP-Protocol-Version", version);
    for (const name of ["Mcp-Method", "Mcp-Name"]) {
      const value = request.headers.get(name);
      if (value !== null) headers.set(name, value);
    }
    try {
      const reader = request.body?.getReader();
      const chunks = [];
      let size = 0;
      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > MAX_REQUEST_BYTES) {
            await reader.cancel();
            return failure(413, "Request too large");
          }
          chunks.push(value);
        }
      }
      const body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
      const response = await fetch(backend, { method: "POST", headers, body, redirect: "manual" });
      if (response.status >= 300 && response.status < 400 || response.status >= 500) {
        await response.body?.cancel();
        return failure(502, "Backend unavailable");
      }
      // Stream SSE heartbeats/results without buffering a potentially long Codex review.
      return new Response(response.body, {
        status: response.status,
        headers: {
          "Content-Type": response.headers.get("Content-Type") || "application/json",
          "Cache-Control": "no-store",
          "X-Accel-Buffering": "no",
        },
      });
    } catch {
      return failure(502, "Backend unavailable");
    }
  },
};
