from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


LensName = Literal[
    "customer",
    "decision_maker",
    "finance",
    "execution_risk",
    "competitive",
    "procurement_compliance",
    "stakeholder_adoption",
    "technical_feasibility",
    "commercial_terms_risk",
    "narrative_coherence",
]
Severity = Literal["low", "medium", "high"]
SourceType = Literal["file", "folder"]


class ReviewLens(BaseModel):
    name: LensName
    prompt: str


class ReviewFinding(BaseModel):
    lens: LensName
    severity: Severity
    title: str
    rationale: str
    recommendation: str


class LensReview(BaseModel):
    lens: LensName
    summary: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class ProposalReviewReport(BaseModel):
    source: str
    source_type: SourceType = "file"
    sources: list[str] = Field(default_factory=list)
    audience: str
    overall_assessment: str
    lens_reviews: list[LensReview]
    priority_fixes: list[str]
    decision_maker_summary: str


class ProposalDoctorConfig(BaseModel):
    audience: str = "enterprise buyer"
    repo: str = "."
    max_parallel: int = 5
