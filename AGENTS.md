# AGENTS.md

## Repository Purpose

Proposal Doctor is a Python CLI and MCP tool for reviewing proposal drafts
through multiple business lenses. Keep changes focused on that product shape:
proposal review, structured findings, CLI/MCP access, and Codex SDK-backed
review flows.

## Tooling

- Use `uv` for all Python dependency, environment, and command execution.
- Do not use `pip`, `python -m venv`, Poetry, or ad hoc virtualenv commands.
- Prefer these commands:
  - `uv lock`
  - `uv run proposal-doctor review <file>`
  - `uv run proposal-doctor-mcp`
  - `uv run --extra dev pytest`
  - `uv run --extra dev ruff check .`
- Keep `uv.lock` committed when dependency metadata changes.
- This project intentionally allows prerelease dependencies because the Codex
  Python SDK currently depends on prerelease runtime packages.

## Architecture

- Keep the CLI and MCP layers thin.
- Put orchestration and report construction in `src/proposal_doctor/core.py`.
- Put shared data contracts in `src/proposal_doctor/models.py`.
- Keep Codex SDK integration isolated in `src/proposal_doctor/codex_client.py`.
- Keep lens definitions and review rubrics in `src/proposal_doctor/lenses.py`.
- Proposal review is Codex-backed by default and requires Codex authentication.

## Codex SDK Rules

- Start Codex review threads in read-only mode unless a future feature
  explicitly needs writes.
- Treat model output as untrusted. Validate it with Pydantic models and keep a
  fallback for unstructured responses.
- Do not read or print secrets, access tokens, or local Codex auth files.

## CLI And MCP Expectations

- Keep `proposal-doctor review ...` as the primary CLI command.
- Keep `proposal-doctor-mcp` as the MCP server entry point.
- When adding CLI options, mirror them in the MCP tool if they affect review
  behavior.
- JSON output should remain compatible with `ProposalReviewReport`.
- Markdown output should stay readable in terminals and issue comments.

## Documentation

- Update `docs/SPEC.md` when behavior, flow, public commands, data models, or
  supported modes change.
- Keep Mermaid diagrams in `docs/SPEC.md` aligned with the implemented flow.
- Update `README.md` when user-facing commands or installation expectations
  change.

## Validation

- Run `uv run --extra dev pytest` before committing code changes.
- Run `uv run proposal-doctor review <sample-file>` when changing CLI behavior,
  report rendering, or review orchestration.
- Run `uv run --extra dev ruff check .` when changing Python code unless the
  dependency environment is unavailable.
- If Codex SDK behavior changes, test path resolution and prompt construction
  separately from live Codex authentication.

## Scope Control

- Do not add `.docx`, PDF, CRM, storage, or web UI support without updating the
  spec first.
- Do not turn this into a general agent runner. Keep the product centered on
  proposal review.
- Avoid broad framework changes unless they reduce complexity in the current
  CLI/MCP package.
