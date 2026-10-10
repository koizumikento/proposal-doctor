// Invoked by pytest against its owned loopback backend with synthetic inference.
import assert from "node:assert/strict";
import worker from "../worker/index.js";

const transportFetch = globalThis.fetch;
const endpoint = process.argv[2];
assert.match(endpoint, /^http:\/\/127\.0\.0\.1:\d+\/mcp$/);
globalThis.fetch = (url, options) => {
  assert.equal(String(url), "https://fixture.invalid/mcp");
  return transportFetch(endpoint, options);
};
const env = {
  PROPOSAL_DOCTOR_BACKEND_URL: "https://fixture.invalid/mcp",
  PROPOSAL_DOCTOR_BACKEND_TOKEN: "fixture-token-" + "x".repeat(32),
  PROPOSAL_DOCTOR_ALLOWED_USER_IDS: '["alice"]',
};

async function call(method, params = {}) {
  const payload = { jsonrpc: "2.0", id: "modern-flow", method, params: { ...params, _meta: {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": { name: "worker-flow", version: "1" },
  } } };
  const headers = {
    "oai-authenticated-user-id": "alice", "Content-Type": "application/json",
    Accept: "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": method,
  };
  if (params.name) headers["Mcp-Name"] = params.name;
  const response = await worker.fetch(new Request("https://site.example/mcp", {
    method: "POST", headers, body: JSON.stringify(payload),
  }), env);
  assert.equal(response.status, 200);
  const text = await response.text();
  const data = response.headers.get("Content-Type").startsWith("text/event-stream")
    ? text.split(/\r?\n/).find(line => line.startsWith("data: ")).slice(6) : text;
  const envelope = JSON.parse(data);
  assert.equal(envelope.id, "modern-flow");
  assert.equal(envelope.result.resultType, "complete");
  assert.equal(envelope.result._meta["io.modelcontextprotocol/serverInfo"].name, "proposal-doctor");
  return envelope.result;
}

const discovery = await call("server/discover");
assert.ok(discovery.supportedVersions.includes("2026-07-28"));
assert.deepEqual(discovery.capabilities, { tools: {} });
assert.equal((await call("tools/list")).tools.length, 3);
for (const [name, path] of [["review_proposal_file", "draft"],
                           ["review_proposal_folder", "folder"],
                           ["review_proposal_path", "folder"]]) {
  const result = await call("tools/call", { name, arguments: { path, language: "ja" } });
  assert.ok(!result.isError);
  const report = JSON.parse(result.content[0].text);
  assert.equal(report.lens_reviews.length, 10);
  assert.equal(report.language, "ja");
}
console.log("Modern Worker/backend discovery and all three tool calls passed");
