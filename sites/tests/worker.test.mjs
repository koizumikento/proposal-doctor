import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import worker from "../worker/index.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const env = {
  PROPOSAL_DOCTOR_BACKEND_URL: "https://backend.example.com/mcp",
  PROPOSAL_DOCTOR_BACKEND_TOKEN: "fixture-token-" + "x".repeat(32),
  PROPOSAL_DOCTOR_ALLOWED_USER_IDS: '["alice"]',
};
const headers = {
  "oai-authenticated-user-id": "alice", "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25",
};
const request = (extra = {}) => new Request("https://site.example/mcp", {
  method: "POST", headers, body: '{"jsonrpc":"2.0","id":1,"method":"tools/list"}', ...extra,
});

test("identity, membership, origin, method and body limits fail before forwarding", async () => {
  globalThis.fetch = () => { throw new Error("Must not forward"); };
  for (const [req, status] of [
    [request({ headers: { ...headers, "oai-authenticated-user-id": "" } }), 401],
    [request({ headers: { ...headers, "oai-authenticated-user-id": "mallory" } }), 403],
    [request({ headers: { ...headers, Origin: "https://evil.example" } }), 403],
    [request({ method: "GET", body: undefined }), 405],
    [request({ headers: { ...headers, "Content-Type": "text/plain" } }), 415],
    [request({ body: "x".repeat(16385) }), 413],
  ]) assert.equal((await worker.fetch(req, env)).status, status);
});

test("only server credentials and Sites identity reach the fixed backend", async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(String(url), env.PROPOSAL_DOCTOR_BACKEND_URL);
    assert.equal(options.redirect, "manual");
    assert.equal(options.headers.get("Authorization"), `Bearer ${env.PROPOSAL_DOCTOR_BACKEND_TOKEN}`);
    assert.equal(options.headers.get("X-Proposal-User-Id"), "alice");
    assert.equal(options.headers.get("Origin"), null);
    assert.equal(options.headers.get("Cookie"), null);
    assert.equal(options.headers.get("OAI-Sites-Authorization"), null);
    assert.equal(options.headers.get("MCP-Protocol-Version"), "2025-11-25");
    assert.equal(new TextDecoder().decode(options.body), await request().text());
    return new Response('data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n', {
      headers: { "Content-Type": "text/event-stream", "Set-Cookie": "private" },
    });
  };
  const response = await worker.fetch(request({ headers: {
    ...headers, Authorization: "Bearer untrusted", "X-Proposal-User-Id": "mallory",
    Cookie: "private", "OAI-Sites-Authorization": "Bearer private",
  } }), env);
  assert.equal(response.headers.get("Set-Cookie"), null);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.ok((await response.text()).startsWith("data: "));
});

test("forwarding preserves streamed chunks instead of buffering", async () => {
  let controller;
  globalThis.fetch = async () => new Response(new ReadableStream({ start(c) { controller = c; } }), {
    headers: { "Content-Type": "text/event-stream" },
  });
  const response = await worker.fetch(request(), env);
  const reader = response.body.getReader();
  controller.enqueue(new TextEncoder().encode(": heartbeat\n\n"));
  assert.equal(new TextDecoder().decode((await reader.read()).value), ": heartbeat\n\n");
  controller.enqueue(new TextEncoder().encode('data: {"result":{}}\n\n'));
  controller.close();
  assert.ok(new TextDecoder().decode((await reader.read()).value).includes("result"));
});

test("missing settings, redirects and upstream exceptions disclose no secrets", async () => {
  assert.equal((await worker.fetch(request(), {})).status, 503);
  assert.equal((await worker.fetch(request(), { ...env,
    PROPOSAL_DOCTOR_BACKEND_URL: "http://localhost:8765/mcp" })).status, 503);
  for (const response of [new Response("private", { status: 302 }),
                          new Response(env.PROPOSAL_DOCTOR_BACKEND_TOKEN, { status: 500 })]) {
    globalThis.fetch = async () => response;
    const result = await worker.fetch(request(), env);
    assert.equal(result.status, 502);
    assert.ok(!(await result.text()).includes(env.PROPOSAL_DOCTOR_BACKEND_TOKEN));
  }
  globalThis.fetch = async () => { throw new Error(env.PROPOSAL_DOCTOR_BACKEND_TOKEN); };
  assert.deepEqual(await (await worker.fetch(request(), env)).json(), { error: "Backend unavailable" });
});

test("modern discovery metadata and routing headers reach the real backend boundary", async () => {
  const payload = { jsonrpc: "2.0", id: "modern", method: "server/discover", params: { _meta: {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
  } } };
  globalThis.fetch = async (_, options) => {
    assert.equal(options.headers.get("Mcp-Method"), "server/discover");
    assert.equal(options.headers.get("MCP-Protocol-Version"), "2026-07-28");
    assert.deepEqual(JSON.parse(new TextDecoder().decode(options.body)), payload);
    return Response.json({ jsonrpc: "2.0", id: "modern", result: {
      resultType: "complete", supportedVersions: ["2026-07-28", "2025-11-25"],
      capabilities: { tools: {} },
      _meta: { "io.modelcontextprotocol/serverInfo": { name: "proposal-doctor", version: "0.1.0" } },
    } });
  };
  const response = await worker.fetch(request({ headers: { ...headers,
    "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover" },
    body: JSON.stringify(payload) }), env);
  assert.deepEqual((await response.json()).result.supportedVersions, ["2026-07-28", "2025-11-25"]);
});
