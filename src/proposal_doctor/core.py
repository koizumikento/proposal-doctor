from __future__ import annotations

import asyncio
from pathlib import Path

from proposal_doctor.codex_client import review_with_codex
from proposal_doctor.heuristic import LENS_LABELS, review_with_heuristics
from proposal_doctor.lenses import DEFAULT_LENSES
from proposal_doctor.models import LensReview, ProposalDoctorConfig, ProposalReviewReport, ReviewLens


async def review_proposal(path: Path, config: ProposalDoctorConfig) -> ProposalReviewReport:
    text = path.read_text(encoding="utf-8")
    semaphore = asyncio.Semaphore(config.max_parallel)

    async def run_lens(lens: ReviewLens) -> LensReview:
        async with semaphore:
            if config.use_codex:
                return await review_with_codex(text, config.audience, lens, config.repo)
            return review_with_heuristics(text, config.audience, lens)

    lens_reviews = await asyncio.gather(*(run_lens(lens) for lens in DEFAULT_LENSES))
    priority_fixes = _priority_fixes(lens_reviews)

    return ProposalReviewReport(
        source=str(path),
        audience=config.audience,
        overall_assessment=_overall_assessment(lens_reviews),
        lens_reviews=list(lens_reviews),
        priority_fixes=priority_fixes,
        decision_maker_summary=_decision_maker_summary(priority_fixes),
    )


def render_markdown(report: ProposalReviewReport) -> str:
    lines = [
        "# Proposal Doctor Review",
        "",
        f"Source: `{report.source}`",
        f"Audience: {report.audience}",
        "",
        "## Overall Assessment",
        "",
        report.overall_assessment,
        "",
        "## Priority Fixes",
        "",
    ]
    lines.extend(f"- {fix}" for fix in report.priority_fixes)

    for lens in report.lens_reviews:
        lines.extend(["", f"## {LENS_LABELS[lens.lens]}", "", lens.summary, ""])
        for finding in lens.findings:
            lines.extend(
                [
                    f"### [{finding.severity.upper()}] {finding.title}",
                    "",
                    f"Why it matters: {finding.rationale}",
                    "",
                    f"Recommendation: {finding.recommendation}",
                    "",
                ]
            )
        if lens.questions:
            lines.extend(["Questions to answer:", ""])
            lines.extend(f"- {question}" for question in lens.questions)

    lines.extend(["", "## Decision-Maker Summary", "", report.decision_maker_summary, ""])
    return "\n".join(lines)


def _priority_fixes(lens_reviews: list[LensReview]) -> list[str]:
    findings = [
        finding
        for review in lens_reviews
        for finding in review.findings
        if finding.severity in {"high", "medium"}
    ]
    if not findings:
        return ["Run a deeper Codex-backed review before sending the final proposal."]
    return [f"{finding.title}: {finding.recommendation}" for finding in findings[:5]]


def _overall_assessment(lens_reviews: list[LensReview]) -> str:
    high_count = sum(
        1 for review in lens_reviews for finding in review.findings if finding.severity == "high"
    )
    if high_count:
        return f"Needs revision before sending. Found {high_count} high-priority issue(s)."
    return "Ready for a deeper human review. No high-priority issue was found in the first pass."


def _decision_maker_summary(priority_fixes: list[str]) -> str:
    return (
        "The proposal should be tightened around customer value, decision-maker approval logic, "
        "financial proof, execution risk, and competitive positioning before it is used in a "
        "high-stakes sales motion. Start with the "
        f"top fix: {priority_fixes[0]}"
    )
