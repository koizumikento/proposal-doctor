"""Authenticated Sites backend. The local CLI/stdio contract remains independent."""

from __future__ import annotations

import asyncio
import hmac
import inspect
import json
import os
import re
import tomllib
from functools import wraps
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import JSONRPCMessage, JSONRPCRequest, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from proposal_doctor import mcp_server
from proposal_doctor.models import OutputLanguage, WebSearchSetting

MAX_REQUEST_BYTES = 16384


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    workspace: str
    path: str
    users: list[str] = Field(min_length=1)

    def resolve_path(self) -> tuple[Path, Path]:
        workspace = Path(self.workspace)
        if not workspace.is_absolute() or not workspace.is_dir():
            raise ValueError("Register an absolute, existing workspace directory")
        relative = Path(self.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Register a relative proposal path inside the workspace")
        root = workspace.resolve(strict=True)
        proposal = (root / relative).resolve(strict=True)
        if not proposal.is_relative_to(root):
            raise ValueError("Registered proposal must stay inside its workspace")
        # Reject links even inside folders: Codex sees the folder, not just core's file list.
        entries = [root / relative, *(root / relative).parents]
        if proposal.is_dir():
            entries.extend(proposal.rglob("*"))
        if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in entries):
            raise ValueError("Registered proposal paths must not contain filesystem links")
        if proposal.is_file() and proposal.suffix.lower() not in {".md", ".markdown", ".txt"}:
            raise ValueError("Register a Markdown/text proposal or a folder")
        return root, proposal


class BackendSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    hosts: list[str] = Field(min_length=1)
    targets: dict[str, Target] = Field(min_length=1)
    max_parallel: int = Field(default=10, ge=1, le=10)
    codex_config_overrides: list[str] = Field(default_factory=list)

    def validate_registration(self) -> None:
        # Codex read-only does not isolate reads between tenants on the same host.
        if len({frozenset(t.users) for t in self.targets.values()}) != 1:
            raise ValueError("Use a separate isolated backend for each user access scope")
        for target_id, target in self.targets.items():
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", target_id):
                raise ValueError("Use opaque target IDs, not local paths")
            target.resolve_path()
        for override in self.codex_config_overrides:
            value = tomllib.loads(override)
            timeout = value.get("stream_idle_timeout_ms")
            if (set(value) != {"stream_idle_timeout_ms"} or type(timeout) is not int
                    or not 1000 <= timeout <= 900000):
                raise ValueError("Only a bounded stream_idle_timeout_ms override is supported")


class RemoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=64)
    audience: str = Field(default="enterprise buyer", min_length=1, max_length=1000)
    language: OutputLanguage = "en"
    web_search: WebSearchSetting = "lens"
    repo: str = "."
    max_parallel: int = Field(default=10, ge=1, le=10)
    codex_config_overrides: list[str] | None = None


def create_app(settings: BackendSettings, token: str):
    settings.validate_registration()
    if not re.fullmatch(r"[\x21-\x7e]{32,}", token):
        raise ValueError("Supply a private backend token of at least 32 printable ASCII characters")
    server = FastMCP(
        "proposal-doctor", stateless_http=True, json_response=False, log_level="CRITICAL",
        transport_security=TransportSecuritySettings(allowed_hosts=settings.hosts),
    )
    review_lock = asyncio.Lock()

    def register(local_tool):
        @wraps(local_tool)
        async def remote_tool(**kwargs):
            try:
                args = RemoteInput.model_validate(kwargs)
            except ValueError:
                raise ValueError("Invalid review arguments; follow the tool schema") from None
            if args.repo != "." or args.codex_config_overrides:
                raise ValueError("repo and Codex runtime overrides are backend-controlled")
            user = server.get_context().request_context.request.headers.get("x-proposal-user-id")
            target = settings.targets.get(args.path)
            if target is None or user not in target.users:
                raise ValueError("Target unavailable for this user")
            if args.max_parallel > settings.max_parallel:
                raise ValueError("max_parallel exceeds the backend limit")
            if review_lock.locked():
                raise ValueError("Backend busy; retry after the current review finishes")
            try:
                root, path = target.resolve_path()
                async with review_lock:
                    return await asyncio.wait_for(local_tool(
                        str(path), args.audience, args.language, args.web_search,
                        str(root), args.max_parallel, settings.codex_config_overrides,
                    ), timeout=900)
            except Exception:
                # SDK errors can contain runtime paths or credentials; do not serialize them.
                raise ValueError("Review failed; operator must check backend readiness") from None

        # Resolve postponed annotations in the original module, preserving its public schema.
        remote_tool.__signature__ = inspect.signature(local_tool, eval_str=True)
        server.add_tool(
            remote_tool,
            description=(f"{local_tool.__doc__} On Sites, path is a registered target ID; "
                         "repo must be '.', overrides empty, max_parallel 1..10 within the "
                         "operator limit. Do not pass local paths. Returns ProposalReviewReport."),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        )

    for tool in (mcp_server.review_proposal_file, mcp_server.review_proposal_folder,
                 mcp_server.review_proposal_path):
        register(tool)
    app = server.streamable_http_app()

    async def authenticated_app(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        request = Request(scope)
        headers = request.headers
        status = None
        if not hmac.compare_digest(headers.get("authorization", "").encode(),
                                   f"Bearer {token}".encode()):
            status = 401
        elif not headers.get("x-proposal-user-id") or not any(
            headers["x-proposal-user-id"] in t.users for t in settings.targets.values()
        ):
            status = 403
        elif headers.get("origin"):
            status = 403  # Worker uses server-to-server HTTP without a browser Origin.
        if status:
            return await JSONResponse({"error": "Unauthorized"}, status)(scope, receive, send)
        if request.url.path != "/mcp":
            return await JSONResponse({"error": "Not found"}, 404)(scope, receive, send)
        if request.method != "POST":
            return await JSONResponse({"error": "Use POST"}, 405,
                                      headers={"Allow": "POST"})(scope, receive, send)
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if len(body) > MAX_REQUEST_BYTES:
                return await JSONResponse({"error": "Request too large"}, 413)(scope, receive, send)
            if not message.get("more_body"):
                break
        try:
            payload = json.loads(body)
            message = JSONRPCMessage.model_validate(payload).root
        except (ValueError, UnicodeDecodeError):
            return await JSONResponse({"error": "Expected one JSON-RPC object"}, 400)(
                scope, receive, send)
        if isinstance(message, JSONRPCRequest) and message.method == "tools/call":
            params = payload.get("params")
            arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
            target_id = arguments.get("path") if isinstance(arguments, dict) else None
            target = settings.targets.get(target_id) if isinstance(target_id, str) else None
            if target is None or headers["x-proposal-user-id"] not in target.users:
                return await JSONResponse({"error": "Target unavailable"}, 403)(scope, receive, send)
            # FastMCP ignores extra fields and coerces values. Validate the remote boundary first.
            try:
                RemoteInput.model_validate(arguments)
            except ValueError:
                return await JSONResponse({"jsonrpc": "2.0", "id": payload.get("id"),
                    "result": {"isError": True, "content": [{"type": "text",
                    "text": "Invalid review arguments; follow the tool schema"}]}})(
                        scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await app(scope, replay, send)

    return authenticated_app


def main() -> None:
    import uvicorn

    try:
        # Remove bridge credentials before the SDK launches its child runtime.
        token = os.environ.pop("PROPOSAL_DOCTOR_BACKEND_TOKEN")
        targets_file = os.environ.pop("PROPOSAL_DOCTOR_TARGETS_FILE")
        settings = BackendSettings.model_validate_json(
            Path(targets_file).read_text(encoding="utf-8")
        )
        app = create_app(settings, token)
    except (KeyError, ValueError, OSError):
        raise SystemExit("Invalid backend configuration; check registration and secret names") from None
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False, log_level="critical")
