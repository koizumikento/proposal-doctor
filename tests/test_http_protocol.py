import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from proposal_doctor.http_protocol import (
    CAPABILITIES_META,
    MODERN_VERSION,
    SERVER_INFO,
    SUPPORTED_VERSIONS,
    VERSION_META,
    modern_response_sender,
)
from proposal_doctor.models import ProposalReviewReport
from test_remote import HEADERS, result


def modern_rpc(client, method, params=None, headers=None, meta=None):
    payload = {"jsonrpc": "2.0", "id": "modern-1", "method": method, "params": {
        **(params or {}), "_meta": {
            VERSION_META: MODERN_VERSION, CAPABILITIES_META: {},
            "io.modelcontextprotocol/clientInfo": {"name": "modern-fixture", "version": "1"},
            **(meta or {}),
        },
    }}
    call_headers = {**HEADERS, "MCP-Protocol-Version": MODERN_VERSION, "Mcp-Method": method}
    if method == "tools/call":
        call_headers["Mcp-Name"] = (params or {}).get("name", "")
    return client.post("/mcp", json=payload, headers={**call_headers, **(headers or {})})


def test_unmodified_legacy_sdk_reproduces_discovery_failure():
    sdk = FastMCP("legacy-fixture", stateless_http=True, json_response=True,
                  transport_security=TransportSecuritySettings(allowed_hosts=["testserver"]))
    with TestClient(sdk.streamable_http_app()) as client:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                               "method": "server/discover", "params": {}}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["error"]["code"] == -32602


def test_discovery_then_real_sdk_list_and_tool_call(backend):
    client, _, captured = backend
    discovery = result(modern_rpc(client, "server/discover"))["result"]
    assert discovery["supportedVersions"] == SUPPORTED_VERSIONS
    assert discovery["capabilities"] == {"tools": {}}
    assert discovery["resultType"] == "complete"
    assert discovery["cacheScope"] == "private" and discovery["ttlMs"] == 0
    assert discovery["_meta"]["io.modelcontextprotocol/serverInfo"] == SERVER_INFO
    assert captured == []
    listed = result(modern_rpc(client, "tools/list"))["result"]
    assert len(listed["tools"]) == 3 and listed["resultType"] == "complete"
    assert listed["cacheScope"] == "private" and listed["ttlMs"] == 0
    assert listed["_meta"]["io.modelcontextprotocol/serverInfo"] == SERVER_INFO
    for tool, target in [("review_proposal_file", "draft"),
                         ("review_proposal_folder", "folder"),
                         ("review_proposal_path", "folder")]:
        call = result(modern_rpc(client, "tools/call", {
            "name": tool, "arguments": {"path": target, "language": "ja"},
        }))["result"]
        assert call["resultType"] == "complete" and not call.get("isError")
        assert "cacheScope" not in call and "ttlMs" not in call
        assert call["_meta"]["io.modelcontextprotocol/serverInfo"] == SERVER_INFO
        report = ProposalReviewReport.model_validate_json(call["content"][0]["text"])
        assert len(report.lens_reviews) == 10 and report.language == "ja"
    assert len(captured) == 3


def test_bare_probe_is_discovery_only_and_has_no_private_data(backend):
    client, _, captured = backend
    probe_headers = {key: value for key, value in HEADERS.items()
                     if key != "MCP-Protocol-Version"}
    probe = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
                        "method": "server/discover", "params": {}}, headers=probe_headers)
    assert result(probe)["result"]["supportedVersions"][0] == MODERN_VERSION
    assert "draft.md" not in probe.text
    missing_meta = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1,
        "method": "tools/list", "params": {}}, headers={**HEADERS,
        "MCP-Protocol-Version": MODERN_VERSION, "Mcp-Method": "tools/list"})
    assert missing_meta.status_code == 400 and missing_meta.json()["error"]["code"] == -32602
    assert captured == []


@pytest.mark.parametrize("headers,meta,code", [
    ({"MCP-Protocol-Version": "2025-11-25"}, {}, -32020),
    ({"Mcp-Method": "tools/call"}, {}, -32020),
    ({"Mcp-Method": ""}, {}, -32020),
    ({}, {CAPABILITIES_META: []}, -32602),
    ({}, {"io.modelcontextprotocol/clientInfo": "wrong"}, -32602),
    ({"MCP-Protocol-Version": "2099-01-01"}, {VERSION_META: "2099-01-01"}, -32022),
])
def test_modern_metadata_errors_do_not_execute(backend, headers, meta, code):
    client, _, captured = backend
    response = modern_rpc(client, "tools/list", headers=headers, meta=meta)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    if code == -32022:
        assert response.json()["error"]["data"] == {
            "supported": SUPPORTED_VERSIONS, "requested": "2099-01-01",
        }
    assert captured == []


def test_name_header_and_modern_tool_error_shape(backend):
    import base64

    client, _, captured = backend
    params = {"name": "review_proposal_file", "arguments": {"path": "draft"}}
    for name in ("review_proposal_folder", "", "=?base64?bad?="):
        response = modern_rpc(client, "tools/call", params, headers={"Mcp-Name": name})
        assert response.status_code == 400 and response.json()["error"]["code"] == -32020
    encoded = base64.b64encode(params["name"].encode()).decode()
    assert not result(modern_rpc(client, "tools/call", params,
        headers={"Mcp-Name": f"=?base64?{encoded}?="}))["result"].get("isError")
    call = result(modern_rpc(client, "tools/call", {
        "name": "review_proposal_file", "arguments": {"path": "draft", "max_parallel": 0},
    }))["result"]
    assert call["isError"] and call["resultType"] == "complete"
    assert len(captured) == 1


def test_modern_auth_origin_host_and_unknown_method(backend):
    client, _, captured = backend
    for headers, status in [({"Authorization": "Bearer wrong"}, 401),
                            ({"X-Proposal-User-Id": ""}, 403),
                            ({"Host": "evil.example"}, 421),
                            ({"Origin": "https://evil.example"}, 403)]:
        assert modern_rpc(client, "server/discover", headers=headers).status_code == status
    unknown = modern_rpc(client, "missing/method")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == -32601
    assert captured == []


def test_real_legacy_sdk_initialize_still_works_after_modern_calls(backend):
    from test_remote import rpc

    client, _, _ = backend
    result(modern_rpc(client, "server/discover"))
    legacy = result(rpc(client, "initialize", {"protocolVersion": "2025-11-25",
        "capabilities": {}, "clientInfo": {"name": "legacy", "version": "1"}}))["result"]
    assert legacy["protocolVersion"] == "2025-11-25" and "resultType" not in legacy
    listed = result(rpc(client, "tools/list"))["result"]
    assert not {"resultType", "cacheScope", "ttlMs"}.intersection(listed)


def test_sse_adaptation_handles_split_utf8_frames_and_flushes_heartbeats():
    sent = []

    async def send(message):
        sent.append(message)

    async def exercise():
        adapt = modern_response_sender(send, cacheable=True)
        await adapt({"type": "http.response.start", "status": 200, "headers": [
            (b"content-type", b"text/event-stream"), (b"content-length", b"10"),
            (b"mcp-session-id", b"legacy-session"),
        ]})
        await adapt({"type": "http.response.body", "body": b": heartbeat\r\n\r\n",
                     "more_body": True})
        assert sent[-1]["body"] == b": heartbeat\n\n"
        payload = json.dumps({"jsonrpc": "2.0", "id": "1", "result": {"content": [
            {"type": "text", "text": "日本語"}], "_meta": {"fixture": True}}},
            ensure_ascii=False).encode()
        frame = b"event: message\r\ndata: " + payload + b"\r\n\r\n"
        for byte in frame:
            await adapt({"type": "http.response.body", "body": bytes([byte]), "more_body": True})
        await adapt({"type": "http.response.body", "body": b"", "more_body": False})
        output = b"".join(message.get("body", b"") for message in sent).decode()
        data = next(line[6:] for line in output.splitlines() if line.startswith("data: "))
        shaped = json.loads(data)["result"]
        assert shaped["resultType"] == "complete"
        assert shaped["cacheScope"] == "private" and shaped["ttlMs"] == 0
        assert shaped["content"][0]["text"] == "日本語" and shaped["_meta"]["fixture"]
        assert dict(sent[0]["headers"]) == {b"content-type": b"text/event-stream"}

    asyncio.run(exercise())
