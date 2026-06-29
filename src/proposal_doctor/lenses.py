from __future__ import annotations

from proposal_doctor.models import ReviewLens


DEFAULT_LENSES: tuple[ReviewLens, ...] = (
    ReviewLens(
        name="buyer",
        prompt="Review for customer clarity, urgency, differentiation, and trust.",
    ),
    ReviewLens(
        name="executive",
        prompt="Review for decision-maker fit, concise business case, and approval readiness.",
    ),
    ReviewLens(
        name="finance",
        prompt="Review pricing, ROI, budget assumptions, measurement, and commercial risk.",
    ),
    ReviewLens(
        name="legal",
        prompt="Review scope, commitments, liability-sensitive language, and ambiguity.",
    ),
    ReviewLens(
        name="delivery",
        prompt="Review implementation credibility, ownership, milestones, and operational risk.",
    ),
)
