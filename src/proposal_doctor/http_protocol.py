"""Modern HTTP envelope compatibility for the existing legacy MCP tool runtime."""

import json
import re

from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from starlette.responses import JSONResponse

from proposal_doctor import __version__

MODERN_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [MODERN_VERSION, *reversed(SUPPORTED_PROTOCOL_VERSIONS)]
SERVER_INFO = {"name": "proposal-doctor", "version": __version__}
VERSION_META = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_META = "io.modelcontextprotocol/clientCapabilities"


def complete_result(result, *, cacheable=False):
    return {**result, **({"cacheScope": "private", "ttlMs": 0} if cacheable else {}),
        "resultType": "complete", "_meta": {
        **result.get("_meta", {}), "io.modelcontextprotocol/serverInfo": SERVER_INFO,
    }}


def rpc_error(payload, code, message, status=400, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": payload.get("id"), "error": error}, status)


def validate_modern_request(payload, headers):
    """Return (modern, error). Preserve legacy initialize and version handling."""
    params = payload.get("params", {})
    meta = params.get("_meta", {}) if isinstance(params, dict) else {}
    header_version = headers.get("mcp-protocol-version")
    requested = meta.get(VERSION_META) if isinstance(meta, dict) else None
    modern = (payload.get("method") == "server/discover" or requested is not None
              or header_version == MODERN_VERSION)
    if not modern:
        return False, None
    if "id" not in payload or "method" not in payload:
        return True, rpc_error(payload, -32600, "Modern HTTP requires a request")
    # Sites discovery probes may send params={} before selecting a version.
    # shortcut: bare discover only, remove when the platform always supplies metadata.
    if (payload["method"] == "server/discover" and params == {}
            and header_version in (None, MODERN_VERSION)):
        if headers.get("mcp-method") not in (None, "server/discover"):
            return True, rpc_error(payload, -32020, "Header mismatch")
        return True, None
    if (not isinstance(meta, dict) or not isinstance(requested, str)
            or not isinstance(meta.get(CAPABILITIES_META), dict)):
        return True, rpc_error(payload, -32602, "Required per-request metadata is missing or invalid")
    client_info = meta.get("io.modelcontextprotocol/clientInfo")
    if client_info is not None and (not isinstance(client_info, dict)
            or not all(isinstance(client_info.get(key), str) for key in ("name", "version"))):
        return True, rpc_error(payload, -32602, "Invalid clientInfo")
    if header_version != requested or headers.get("mcp-method") != payload["method"]:
        return True, rpc_error(payload, -32020, "Header mismatch")
    if requested != MODERN_VERSION:
        return True, rpc_error(payload, -32022, "Unsupported protocol version", data={
            "supported": SUPPORTED_VERSIONS, "requested": requested,
        })
    if payload["method"] == "tools/call":
        name = headers.get("mcp-name", "")
        if name.startswith("=?base64?") and name.endswith("?="):
            import base64

            try:
                name = base64.b64decode(name[9:-2], validate=True).decode("utf-8")
            except (ValueError, UnicodeError):
                return True, rpc_error(payload, -32020, "Malformed Mcp-Name")
        if not isinstance(params.get("name"), str) or name != params["name"]:
            return True, rpc_error(payload, -32020, "Header mismatch")
    if payload["method"] not in {"server/discover", "tools/list", "tools/call", "ping"}:
        return True, rpc_error(payload, -32601, "Method not found", status=404)
    return True, None


def modern_response_sender(send, *, cacheable=False):
    """Adapt real SDK JSON/SSE responses, flushing each event and retaining heartbeats."""
    content_type = ""
    pending = b""

    def envelope(raw):
        payload = json.loads(raw)
        if isinstance(payload.get("result"), dict):
            payload["result"] = complete_result(payload["result"], cacheable=cacheable)
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    async def adapted_send(message):
        nonlocal content_type, pending
        if message["type"] == "http.response.start":
            headers = [(key, value) for key, value in message["headers"]
                       if key.lower() not in {b"content-length", b"mcp-session-id"}]
            content_type = dict(headers).get(b"content-type", b"").decode()
            return await send({**message, "headers": headers})
        if message["type"] != "http.response.body":
            return await send(message)
        pending += message.get("body", b"")
        output = b""
        if content_type.startswith("text/event-stream"):
            while delimiter := re.search(rb"\r?\n\r?\n", pending):
                frame, pending = pending[:delimiter.start()], pending[delimiter.end():]
                lines = frame.splitlines()
                data = b"\n".join(line[5:].lstrip(b" ") for line in lines
                                  if line.startswith(b"data:"))
                if data:
                    lines = [line for line in lines if not line.startswith(b"data:")]
                    lines.append(b"data: " + envelope(data))
                output += b"\n".join(lines) + b"\n\n"
        elif not message.get("more_body") and pending:
            output = envelope(pending) if content_type.startswith("application/json") else pending
            pending = b""
        if not message.get("more_body"):
            output += pending
            pending = b""
        await send({**message, "body": output})

    return adapted_send
