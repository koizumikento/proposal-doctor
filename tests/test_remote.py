import asyncio
import json

import pytest
from starlette.testclient import TestClient

from proposal_doctor.lenses import DEFAULT_LENSES
from proposal_doctor.mcp_server import mcp as local_mcp
from proposal_doctor.models import LensReview, ProposalReviewReport, ReviewSource
from proposal_doctor.remote_server import BackendSettings, create_app

TOKEN = "fixture-token-" + "x" * 32
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "X-Proposal-User-Id": "alice",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


def rpc(client, method, params=None, headers=None):
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params or {}}, headers=headers or HEADERS)
    return response


def result(response):
    assert response.status_code == 200, response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        data = next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        return json.loads(data)
    return response.json()


@pytest.fixture
def backend(tmp_path, monkeypatch):
    (tmp_path / "draft.md").write_text("Synthetic proposal", encoding="utf-8")
    folder = tmp_path / "proposals"
    folder.mkdir()
    (folder / "overview.md").write_text("Synthetic folder proposal", encoding="utf-8")
    (folder / ".hidden.md").write_text("Hidden", encoding="utf-8")
    settings = BackendSettings.model_validate({
        "hosts": ["testserver"], "targets": {
            "draft": {"workspace": str(tmp_path), "path": "draft.md", "users": ["alice"]},
            "folder": {"workspace": str(tmp_path), "path": "proposals", "users": ["alice"]},
        }, "codex_config_overrides": ["stream_idle_timeout_ms=120000"],
    })
    captured = []

    async def fake_review(**kwargs):
        captured.append(kwargs)
        return [LensReview(lens=lens.name, summary="Fixture review", external_sources=[
            ReviewSource(title="Fixture evidence", url="https://example.com/evidence",
                         relevance="Synthetic provenance")]) for lens in kwargs["lenses"]]

    monkeypatch.setattr("proposal_doctor.core.review_lenses_with_codex", fake_review)
    with TestClient(create_app(settings, TOKEN)) as client:
        yield client, settings, captured


def test_sdk_lifecycle_and_schema_match(backend):
    client, _, _ = backend
    initialized = result(rpc(client, "initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "fixture", "version": "1"},
    }))
    assert initialized["result"]["protocolVersion"] == "2025-11-25"
    notified = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                           headers=HEADERS)
    assert notified.status_code == 202 and not notified.content
    tools = result(rpc(client, "tools/list"))["result"]["tools"]
    local = {tool.name: tool for tool in asyncio.run(local_mcp.list_tools())}
    assert {tool["name"] for tool in tools} == set(local)
    for tool in tools:
        assert tool["inputSchema"] == local[tool["name"]].inputSchema
        assert tool.get("outputSchema") == local[tool["name"]].outputSchema
        assert "registered target ID" in tool["description"]
        assert tool["annotations"]["readOnlyHint"] is True
    assert "draft.md" not in json.dumps(tools)


@pytest.mark.parametrize("tool,target,source_type", [
    ("review_proposal_file", "draft", "file"),
    ("review_proposal_folder", "folder", "folder"),
    ("review_proposal_path", "folder", "folder"),
    ("review_proposal_path", "draft", "file"),
])
def test_all_tools_preserve_report_and_ten_lenses(backend, tool, target, source_type):
    client, _, captured = backend
    call = result(rpc(client, "tools/call", {"name": tool, "arguments": {
        "path": target, "language": "ja", "web_search": "disabled", "max_parallel": 3,
    }}))["result"]
    assert not call.get("isError")
    report = ProposalReviewReport.model_validate_json(call["content"][0]["text"])
    assert report.source_type == source_type
    assert len(report.lens_reviews) == 10
    assert report.language == "ja" and report.web_search == "disabled"
    assert all(lens.external_sources for lens in report.lens_reviews)
    assert captured[0]["lenses"] == DEFAULT_LENSES
    assert captured[0]["codex_config_overrides"] == ("stream_idle_timeout_ms=120000",)
    if source_type == "folder":
        assert len(report.sources) == 1 and report.sources[0].endswith("overview.md")


@pytest.mark.parametrize("headers,status", [
    ({"Accept": "application/json, text/event-stream"}, 401),
    ({**HEADERS, "Authorization": "Bearer wrong"}, 401),
    ({**HEADERS, "X-Proposal-User-Id": ""}, 403),
    ({**HEADERS, "X-Proposal-User-Id": "mallory"}, 403),
    ({**HEADERS, "Origin": "https://evil.example"}, 403),
    ({**HEADERS, "Host": "evil.example"}, 421),
])
def test_backend_auth_and_dns_boundary(backend, headers, status):
    client, _, captured = backend
    assert rpc(client, "tools/list", headers=headers).status_code == status
    assert captured == []


@pytest.mark.parametrize("path", ["private", "unknown", "../draft.md", "C:\\auth.json"])
def test_target_authorization_before_execution(backend, path):
    client, _, captured = backend
    assert rpc(client, "tools/call", {"name": "review_proposal_path", "arguments": {
        "path": path}}).status_code == 403
    assert captured == []


@pytest.mark.parametrize("arguments", [
    {"repo": "/etc"}, {"codex_config_overrides": ["sandbox_mode='danger-full-access'"]},
    {"max_parallel": 0}, {"max_parallel": 11}, {"max_parallel": "2"},
    {"shell": "cat /etc/passwd"}, {"language": "fr"}, {"audience": "x" * 1001},
])
def test_remote_rejects_runtime_overrides_and_invalid_inputs(backend, arguments):
    client, _, captured = backend
    call = result(rpc(client, "tools/call", {"name": "review_proposal_path",
                      "arguments": {"path": "draft", **arguments}}))["result"]
    assert call["isError"] is True
    assert captured == []


def test_operational_failure_is_sanitized(backend, monkeypatch):
    client, _, _ = backend

    async def fail(**kwargs):
        raise RuntimeError("secret-provider-value /private/auth.json")

    monkeypatch.setattr("proposal_doctor.core.review_lenses_with_codex", fail)
    response = rpc(client, "tools/call", {"name": "review_proposal_file",
                                         "arguments": {"path": "draft"}})
    assert result(response)["result"]["isError"]
    assert "secret-provider-value" not in response.text and "/private/auth.json" not in response.text


def test_transport_errors(backend):
    client, _, captured = backend
    assert client.get("/mcp", headers=HEADERS).status_code == 405
    assert client.post("/mcp", content="x" * 16385,
                       headers={**HEADERS, "Content-Type": "application/json"}).status_code == 413
    assert client.post("/mcp", json=[], headers=HEADERS).status_code == 400
    assert client.post("/mcp", content="{bad", headers=HEADERS).status_code == 400
    assert rpc(client, "tools/list", headers={**HEADERS,
        "MCP-Protocol-Version": "unknown"}).status_code == 400
    unknown = result(rpc(client, "tools/call", {"name": "missing_tool",
                                              "arguments": {"path": "draft"}}))
    assert unknown["result"]["isError"] is True
    assert captured == []


def test_registration_rejects_escape_and_runtime_config(backend):
    _, settings, _ = backend
    with pytest.raises(ValueError, match="printable ASCII"):
        create_app(settings, "\x00" * 32)
    settings.targets["draft"].path = "../secret.md"
    with pytest.raises(ValueError, match="relative proposal path"):
        create_app(settings, TOKEN)
    settings.targets["draft"].path = "draft.md"
    settings.codex_config_overrides = ["sandbox_mode='danger-full-access'"]
    with pytest.raises(ValueError, match="bounded"):
        create_app(settings, TOKEN)
    settings.codex_config_overrides = []
    settings.targets["folder"].users = ["bob"]
    with pytest.raises(ValueError, match="separate isolated backend"):
        create_app(settings, TOKEN)


def test_registration_rechecks_filesystem_links(backend, tmp_path):
    client, settings, captured = backend
    link = tmp_path / "proposals" / "linked.md"
    try:
        link.symlink_to(tmp_path / "draft.md")
    except OSError:
        pytest.skip("Filesystem symlink privilege unavailable; covered on Linux CI")
    response = rpc(client, "tools/call", {"name": "review_proposal_folder",
                                         "arguments": {"path": "folder"}})
    assert result(response)["result"]["isError"] is True
    assert captured == []
    with pytest.raises(ValueError, match="filesystem links"):
        create_app(settings, TOKEN)


def test_backend_concurrency_is_bounded(backend, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    client, _, _ = backend
    started = Event()
    release = Event()

    async def slow_review(**kwargs):
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return [LensReview(lens=lens.name, summary="Fixture") for lens in DEFAULT_LENSES]

    monkeypatch.setattr("proposal_doctor.core.review_lenses_with_codex", slow_review)
    params = {"name": "review_proposal_file", "arguments": {"path": "draft"}}
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(rpc, client, "tools/call", params)
        try:
            assert started.wait(5)
            rejected = result(rpc(client, "tools/call", params))["result"]
            assert rejected["isError"] and "busy" in rejected["content"][0]["text"]
        finally:
            release.set()
        assert not result(first.result(timeout=5))["result"]["isError"]


def test_backend_entrypoint_removes_bridge_secrets_before_children(backend, tmp_path, monkeypatch):
    from proposal_doctor.remote_server import main

    _, settings, _ = backend
    registry = tmp_path / "registry.json"
    registry.write_text(settings.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("PROPOSAL_DOCTOR_BACKEND_TOKEN", TOKEN)
    monkeypatch.setenv("PROPOSAL_DOCTOR_TARGETS_FILE", str(registry))
    captured = {}

    def fake_run(app, **kwargs):
        import os
        assert "PROPOSAL_DOCTOR_BACKEND_TOKEN" not in os.environ
        assert "PROPOSAL_DOCTOR_TARGETS_FILE" not in os.environ
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    main()
    assert captured["host"] == "127.0.0.1" and captured["port"] == 8765
    assert captured["access_log"] is False


def test_official_mcp_client_over_loopback_http(backend):
    import socket
    import time
    from threading import Thread

    import uvicorn
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    _, settings, _ = backend
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    settings.hosts = [f"127.0.0.1:{port}"]
    server = uvicorn.Server(uvicorn.Config(create_app(settings, TOKEN),
                                         access_log=False, log_level="critical"))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()

    async def exercise():
        import httpx

        async with httpx.AsyncClient(headers=HEADERS) as http:
            async with streamable_http_client(f"http://127.0.0.1:{port}/mcp",
                                              http_client=http) as (read, write, session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    assert session_id() is None
                    discovered = await session.list_tools()
                    assert len(discovered.tools) == 3
                    call = await session.call_tool("review_proposal_folder", {"path": "folder"})
                    assert not call.isError
                    report = ProposalReviewReport.model_validate_json(call.content[0].text)
                    assert len(report.lens_reviews) == 10 and report.source_type == "folder"

    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        asyncio.run(exercise())
        import subprocess
        from pathlib import Path

        flow = Path(__file__).resolve().parents[1] / "sites/tests/backend-flow.mjs"
        node = subprocess.run(["node", str(flow), f"http://127.0.0.1:{port}/mcp"],
                              capture_output=True, text=True, timeout=15, check=True)
        assert "all three tool calls passed" in node.stdout
        modern_flow = Path(__file__).with_name("modern_client.py")
        modern = subprocess.run(["uv", "run", "--offline", "--script", str(modern_flow),
                                 f"http://127.0.0.1:{port}/mcp"],
                                capture_output=True, text=True, timeout=30)
        assert modern.returncode == 0, modern.stdout + modern.stderr
        assert "SDK 2.3 discovery/list/call passed" in modern.stdout
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive(), "Owned loopback test server did not stop"
