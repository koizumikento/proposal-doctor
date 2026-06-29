from __future__ import annotations

from pathlib import Path

from proposal_doctor.codex_client import review_lenses_with_codex
from proposal_doctor.lenses import DEFAULT_LENSES, LENS_LABELS
from proposal_doctor.models import (
    LensReview,
    ProposalDoctorConfig,
    ProposalReviewReport,
    SourceType,
)

SUPPORTED_PROPOSAL_EXTENSIONS = {".md", ".markdown", ".txt"}


async def review_proposal(path: Path, config: ProposalDoctorConfig) -> ProposalReviewReport:
    source_type, sources = _resolve_proposal_sources(path)
    lens_reviews = await review_lenses_with_codex(
        proposal_path=path,
        source_type=source_type,
        audience=config.audience,
        lenses=DEFAULT_LENSES,
        repo=config.repo,
        max_parallel=config.max_parallel,
    )

    priority_fixes = _priority_fixes(lens_reviews)

    return ProposalReviewReport(
        source=str(path),
        source_type=source_type,
        sources=[str(source) for source in sources],
        audience=config.audience,
        overall_assessment=_overall_assessment(lens_reviews),
        lens_reviews=list(lens_reviews),
        priority_fixes=priority_fixes,
        decision_maker_summary=_decision_maker_summary(priority_fixes),
    )


def _resolve_proposal_sources(path: Path) -> tuple[SourceType, list[Path]]:
    if path.is_file():
        return "file", [path]
    if path.is_dir():
        files = _proposal_files_in_folder(path)
        if not files:
            supported = ", ".join(sorted(SUPPORTED_PROPOSAL_EXTENSIONS))
            raise ValueError(f"No proposal files found in {path}. Supported extensions: {supported}")
        return "folder", files
    raise FileNotFoundError(f"Proposal path does not exist: {path}")


def _proposal_files_in_folder(path: Path) -> list[Path]:
    return sorted(
        file
        for file in path.rglob("*")
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_PROPOSAL_EXTENSIONS
        and not any(part.startswith(".") for part in file.relative_to(path).parts)
    )


def render_markdown(report: ProposalReviewReport) -> str:
    lines = [
        "# Proposal Doctor Review",
        "",
        f"Source: `{report.source}`",
        f"Source type: {report.source_type}",
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

    if report.source_type == "folder" and report.sources:
        lines.extend(["", "## Reviewed Files", ""])
        lines.extend(f"- `{source}`" for source in report.sources)

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
        return ["No medium or high priority fixes were returned by the Codex review."]
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
        "financial proof, execution risk, competitive positioning, procurement compliance, "
        "adoption, technical feasibility, commercial terms, and narrative clarity before it is "
        "used in a high-stakes sales motion. Start with the "
        f"top fix: {priority_fixes[0]}"
    )
