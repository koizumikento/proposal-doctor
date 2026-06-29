# Proposal Doctor

[日本語版 README](README.ja.md)

Proposal Doctor is a focused CLI and MCP tool that reviews proposal drafts from
multiple business perspectives, then returns a practical improvement brief.

It is designed as a thin flow layer around Codex SDK:

- run locally with `uvx`
- expose the same flow as an MCP tool
- ask Codex SDK to review each lens in parallel
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

Review a folder of proposal drafts:

```bash
proposal-doctor review ./proposals
```

Write the report to a file:

```bash
proposal-doctor review proposal.md --out review.md
```

Set the Codex working directory:

```bash
proposal-doctor review proposal.md --repo .
```

Codex-backed reviews use detailed rubrics for customer value, decision-maker
approval, financial proof, execution risk, competitive positioning, procurement
compliance, stakeholder adoption, technical feasibility, commercial terms risk,
and narrative coherence.

Emit JSON:

```bash
proposal-doctor review proposal.md --format json
```

Run as an MCP server:

```bash
proposal-doctor-mcp
```

The MCP server exposes `review_proposal_file` for single files,
`review_proposal_folder` for folders, and `review_proposal_path` for either.
Folder reviews include `.md`, `.markdown`, and `.txt` files recursively while
ignoring hidden files and hidden folders.

## Specification

See [docs/SPEC.md](docs/SPEC.md) for the tool specification, including the
review flow diagrams.

## Review Lenses

The default flow reviews the proposal through ten lenses:

- customer: 顧客視点で、課題、導入価値、緊急度、信頼性を見る
- decision_maker: 決裁者視点で、承認判断、事業価値、意思決定材料を見る
- finance: 財務視点で、価格、ROI、予算前提、測定方法を見る
- execution_risk: 実行リスク視点で、体制、責任分界、スケジュール、依存関係を見る
- competitive: 競合比較視点で、代替案との差別化、比較軸、勝ち筋を見る
- procurement_compliance: 調達要件、必須項目、評価基準への対応を見る
- stakeholder_adoption: 利用者、運用担当、教育、変更管理、定着指標を見る
- technical_feasibility: アーキテクチャ、統合、データ、セキュリティ前提を見る
- commercial_terms_risk: スコープ、支払、更新、SLA、受入、責任範囲を見る
- narrative_coherence: 論理展開、重複、矛盾、読みやすさ、要約の強さを見る

## Status

This repository uses Codex-backed proposal review as its primary flow. A Codex
login or configured Codex authentication is required to run reviews.
