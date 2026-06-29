# Proposal Doctor

Proposal Doctor is a focused CLI and MCP tool that reviews proposal drafts from
multiple business perspectives, then returns a practical improvement brief.

It is designed as a thin flow layer around Codex SDK:

- run locally with `uvx`
- expose the same flow as an MCP tool
- optionally ask Codex SDK to review each lens in parallel
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

- customer: 顧客視点で、課題、導入価値、緊急度、信頼性を見る
- decision_maker: 決裁者視点で、承認判断、事業価値、意思決定材料を見る
- finance: 財務視点で、価格、ROI、予算前提、測定方法を見る
- execution_risk: 実行リスク視点で、体制、責任分界、スケジュール、依存関係を見る
- competitive: 競合比較視点で、代替案との差別化、比較軸、勝ち筋を見る

## Status

This repository starts with a safe local heuristic reviewer and a Codex-backed
path behind `--use-codex`. The heuristic path keeps the tool usable without
model credentials while the Codex flow is refined.
