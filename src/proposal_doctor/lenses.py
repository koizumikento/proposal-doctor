from __future__ import annotations

from proposal_doctor.models import ReviewLens


DEFAULT_LENSES: tuple[ReviewLens, ...] = (
    ReviewLens(
        name="customer",
        prompt="顧客視点で、課題の明確さ、導入価値、信頼性、顧客にとっての緊急度をレビューする。",
    ),
    ReviewLens(
        name="decision_maker",
        prompt="決裁者視点で、承認判断に必要な事業価値、リスク、投資対効果、意思決定材料をレビューする。",
    ),
    ReviewLens(
        name="finance",
        prompt="財務視点で、価格、ROI、予算前提、回収期間、測定方法、商業リスクをレビューする。",
    ),
    ReviewLens(
        name="execution_risk",
        prompt="実行リスク視点で、体制、スケジュール、責任分界、依存関係、導入失敗リスクをレビューする。",
    ),
    ReviewLens(
        name="competitive",
        prompt="競合比較視点で、代替案との差別化、選定理由、比較軸、勝ち筋の明確さをレビューする。",
    ),
)
