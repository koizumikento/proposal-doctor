from __future__ import annotations

from proposal_doctor.models import LensName, LensReview, ReviewFinding, ReviewLens


LENS_LABELS: dict[LensName, str] = {
    "customer": "顧客視点",
    "decision_maker": "決裁者視点",
    "finance": "財務視点",
    "execution_risk": "実行リスク視点",
    "competitive": "競合比較視点",
}


def review_with_heuristics(text: str, audience: str, lens: ReviewLens) -> LensReview:
    findings: list[ReviewFinding] = []
    lower = text.lower()

    if lens.name in {"customer", "decision_maker"} and not any(
        marker in lower for marker in ("problem", "challenge", "pain", "goal")
    ):
        findings.append(
            _finding(
                lens.name,
                "high",
                "Customer problem is not explicit",
                "The draft does not clearly anchor the proposal in the customer's problem.",
                "Open with the customer's current pain, desired outcome, and cost of inaction.",
            )
        )

    if lens.name == "finance" and not any(
        marker in lower for marker in ("roi", "cost", "price", "budget", "revenue")
    ):
        findings.append(
            _finding(
                lens.name,
                "medium",
                "Commercial case needs evidence",
                "A financial buyer will likely need quantified assumptions before approving.",
                "Add pricing, expected impact, ROI logic, and the measurement window.",
            )
        )

    if lens.name == "execution_risk" and not any(
        marker in lower for marker in ("timeline", "milestone", "owner", "implementation")
    ):
        findings.append(
            _finding(
                lens.name,
                "high",
                "Delivery plan is underspecified",
                "The proposal does not make implementation ownership and milestones obvious.",
                "Add phases, owners, dependencies, acceptance criteria, and a launch checkpoint.",
            )
        )

    if lens.name == "competitive" and not any(
        marker in lower for marker in ("competitor", "alternative", "different", "compare", "versus")
    ):
        findings.append(
            _finding(
                lens.name,
                "medium",
                "Competitive positioning is unclear",
                "The proposal does not explain why this option should win against alternatives.",
                "Add the customer's likely alternatives, comparison criteria, and specific differentiators.",
            )
        )

    if not findings:
        findings.append(
            _finding(
                lens.name,
                "low",
                "No obvious blocker found by heuristic review",
                f"The draft has enough surface detail for a first-pass {LENS_LABELS[lens.name]} review.",
                "Use Codex review for deeper document-specific critique before sending.",
            )
        )

    return LensReview(
        lens=lens.name,
        summary=f"{LENS_LABELS[lens.name]}レビュー for {audience}.",
        findings=findings,
        questions=_questions_for_lens(lens.name),
    )


def _finding(
    lens: LensName,
    severity: str,
    title: str,
    rationale: str,
    recommendation: str,
) -> ReviewFinding:
    return ReviewFinding(
        lens=lens,
        severity=severity,  # type: ignore[arg-type]
        title=title,
        rationale=rationale,
        recommendation=recommendation,
    )


def _questions_for_lens(lens: LensName) -> list[str]:
    return {
        "customer": ["Why should this customer act now?", "What customer pain is most urgent?"],
        "decision_maker": ["What one metric justifies approval?", "What decision is being requested?"],
        "finance": ["Which assumptions drive the business case?", "How will impact be measured?"],
        "execution_risk": ["Who owns each milestone?", "What dependencies could delay delivery?"],
        "competitive": [
            "Which alternatives will the customer compare against?",
            "What is the clearest reason to choose this proposal?",
        ],
    }[lens]
