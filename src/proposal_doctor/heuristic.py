from __future__ import annotations

from proposal_doctor.models import LensName, LensReview, ReviewFinding, ReviewLens


def review_with_heuristics(text: str, audience: str, lens: ReviewLens) -> LensReview:
    findings: list[ReviewFinding] = []
    lower = text.lower()

    if lens.name in {"buyer", "executive"} and not any(
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

    if lens.name == "legal" and any(marker in lower for marker in ("guarantee", "always", "never")):
        findings.append(
            _finding(
                lens.name,
                "medium",
                "Absolute language may create avoidable risk",
                "Strong guarantees can be hard to defend unless backed by contract terms.",
                "Replace absolute claims with scoped commitments, assumptions, and exclusions.",
            )
        )

    if lens.name == "delivery" and not any(
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

    if not findings:
        findings.append(
            _finding(
                lens.name,
                "low",
                "No obvious blocker found by heuristic review",
                f"The draft has enough surface detail for a first-pass {lens.name} review.",
                "Use Codex review for deeper document-specific critique before sending.",
            )
        )

    return LensReview(
        lens=lens.name,
        summary=f"{lens.name.title()} review for {audience}.",
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
        "buyer": ["Why should this customer act now?", "What alternative are they comparing against?"],
        "executive": ["What one metric justifies approval?", "What decision is being requested?"],
        "finance": ["Which assumptions drive the business case?", "How will impact be measured?"],
        "legal": ["Which commitments need contractual precision?", "What exclusions are missing?"],
        "delivery": ["Who owns each milestone?", "What dependencies could delay delivery?"],
    }[lens]
