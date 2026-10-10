import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";

const root = new URL("../", import.meta.url);
assert.deepEqual((await readdir(new URL("dist/", root))).sort(), [".openai", "server"]);
assert.deepEqual(await readdir(new URL("dist/server/", root)), ["index.js"]);
assert.deepEqual(await readdir(new URL("dist/.openai/", root)), ["hosting.json"]);
const manifest = JSON.parse(await readFile(new URL("dist/.openai/hosting.json", root), "utf8"));
assert.ok(manifest.capabilities.includes("mcp"));
assert.ok(!manifest.static);
const source = await readFile(new URL("dist/server/index.js", root), "utf8");
const worker = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
assert.equal(typeof worker.default?.fetch, "function");
console.log("Valid Sites Worker ESM artifact with MCP capability");
