# Proposal Doctor

Proposal Doctor は、提案書ドラフトを複数のビジネス観点からレビューし、
優先度付きの改善レポートを返す CLI / MCP ツールです。

Codex SDK を使って、観点ごとに提案書を並列レビューします。

- `uvx` でローカル実行
- 同じレビュー機能を MCP tool として公開
- Codex SDK による lens 別の並列レビュー
- Markdown または JSON で出力

## インストール

```bash
uvx proposal-doctor --help
```

ローカル開発中:

```bash
uv run proposal-doctor --help
```

## 使い方

提案書ファイルをレビュー:

```bash
proposal-doctor review proposal.md --audience "enterprise CFO"
```

提案書フォルダをレビュー:

```bash
proposal-doctor review ./proposals
```

レポートをファイルへ書き出し:

```bash
proposal-doctor review proposal.md --out review.md
```

日本語レポートをフォルダへ自動ファイル名で書き出し:

```bash
proposal-doctor review proposal.md --language ja --out-dir .work
```

Codex の作業ディレクトリを指定:

```bash
proposal-doctor review proposal.md --repo .
```

Codex-backed review では、顧客価値、決裁者承認、財務根拠、実行リスク、
競合比較、調達要件適合、ステークホルダー定着、技術実現性、商務条件
リスク、ストーリー整合性について詳細な rubric を使います。

JSON で出力:

```bash
proposal-doctor review proposal.md --format json
```

MCP server として起動:

```bash
proposal-doctor-mcp
```

MCP server は、単一ファイル向けの `review_proposal_file`、フォルダ向けの
`review_proposal_folder`、ファイル/フォルダ両対応の `review_proposal_path`
を公開します。各 MCP tool は `language` に `en` または `ja` を指定できます。
フォルダレビューでは `.md`, `.markdown`, `.txt` を再帰的に読み、隠しファイルと
隠しフォルダは無視します。

## 仕様

レビューの流れやデータモデルは [docs/SPEC.md](docs/SPEC.md) を参照してください。

## レビュー観点

デフォルトでは、提案書を次の10観点からレビューします。

- `customer`: 顧客視点で、課題、導入価値、緊急度、信頼性を見る
- `decision_maker`: 決裁者視点で、承認判断、事業価値、意思決定材料を見る
- `finance`: 財務視点で、価格、ROI、予算前提、測定方法を見る
- `execution_risk`: 実行リスク視点で、体制、責任分界、スケジュール、依存関係を見る
- `competitive`: 競合比較視点で、代替案との差別化、比較軸、勝ち筋を見る
- `procurement_compliance`: 調達要件、必須項目、評価基準への対応を見る
- `stakeholder_adoption`: 利用者、運用担当、教育、変更管理、定着指標を見る
- `technical_feasibility`: アーキテクチャ、統合、データ、セキュリティ前提を見る
- `commercial_terms_risk`: スコープ、支払、更新、SLA、受入、責任範囲を見る
- `narrative_coherence`: 論理展開、重複、矛盾、読みやすさ、要約の強さを見る

## 実行モデル

Proposal Doctor は Codex SDK session を開き、各 lens ごとに read-only ephemeral
thread を開始します。提案書本文を prompt に埋め込むのではなく、レビュー対象の
ファイルまたはフォルダ path を Codex に渡します。

## ステータス

このリポジトリは Codex-backed review を主経路として提供します。レビュー実行には
Codex ログインまたは Codex 認証設定が必要です。
