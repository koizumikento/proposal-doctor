# Proposal Doctor

Proposal Doctor is a focused CLI and MCP tool that reviews proposal drafts from
multiple business perspectives, then returns a practical improvement brief.

It is designed as a thin flow layer around Codex SDK:

- run locally with `uvx`
- expose the same flow as an MCP tool
- optionally ask Codex to review each lens in parallel
- emit Markdown or JSON that can be pasted into a proposal workflow

## Install

```bash
uvx proposal-doctor --help
```

During local development:

```bash
uv run proposal-doctor --help
```

## Usage

Review a proposal draft:

```bash
proposal-doctor review proposal.md --audience "enterprise CFO"
```

Write the report to a file:

```bash
proposal-doctor review proposal.md --out review.md
```

Ask Codex to perform the lens reviews:

```bash
proposal-doctor review proposal.md --use-codex --repo .
```

Emit JSON:

```bash
proposal-doctor review proposal.md --format json
```

Run as an MCP server:

```bash
proposal-doctor-mcp
```

## Specification

See [docs/SPEC.md](docs/SPEC.md) for the tool specification, including the
review flow diagrams.

## Review Lenses

The default flow reviews the proposal through five lenses:

- buyer: whether the proposal is clear and compelling to the customer
- executive: whether the decision case is crisp enough for approval
- finance: whether ROI, pricing, and assumptions are defensible
- legal: whether commitments, scope, and risk language need tightening
- delivery: whether implementation, ownership, and timeline are credible

## Status

This repository starts with a safe local heuristic reviewer and a Codex-backed
path behind `--use-codex`. The heuristic path keeps the tool usable without
model credentials while the Codex flow is refined.
