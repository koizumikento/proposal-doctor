import asyncio

import pytest

from proposal_doctor.codex_client import _build_prompt
from proposal_doctor.cli import _output_path_for_dir
from proposal_doctor.core import render_markdown, review_proposal
from proposal_doctor.lenses import DEFAULT_LENSES
from proposal_doctor.models import LensReview, ProposalDoctorConfig


def _stub_lens_reviews() -> list[LensReview]:
    return [
        LensReview(
            lens="customer",
            summary="Codex path review.",
            findings=[],
            questions=[],
        )
    ]


def test_review_proposal_accepts_folder(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "proposal"
    folder.mkdir()
    (folder / "overview.md").write_text(
        "Problem: Support costs are rising.\nROI: Reduce support load by 20%.",
        encoding="utf-8",
    )
    (folder / "implementation.txt").write_text(
        "Timeline: Launch in Q3. Owner: Customer success.",
        encoding="utf-8",
    )
    (folder / "notes.csv").write_text("ignored,true", encoding="utf-8")
    captured = {}

    async def fake_review_lenses_with_codex(**kwargs):
        captured.update(kwargs)
        return _stub_lens_reviews()

    monkeypatch.setattr(
        "proposal_doctor.core.review_lenses_with_codex",
        fake_review_lenses_with_codex,
    )

    report = asyncio.run(review_proposal(folder, ProposalDoctorConfig()))

    assert report.source == str(folder)
    assert report.source_type == "folder"
    assert report.sources == [str(folder / "implementation.txt"), str(folder / "overview.md")]
    assert captured["proposal_path"] == folder
    assert captured["source_type"] == "folder"
    assert captured["lenses"] == DEFAULT_LENSES


def test_review_proposal_rejects_folder_without_supported_files(tmp_path) -> None:
    folder = tmp_path / "proposal"
    folder.mkdir()
    (folder / "notes.csv").write_text("ignored,true", encoding="utf-8")

    with pytest.raises(ValueError, match="No proposal files found"):
        asyncio.run(review_proposal(folder, ProposalDoctorConfig()))


def test_folder_report_markdown_lists_reviewed_files(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "proposal"
    folder.mkdir()
    (folder / "proposal.md").write_text("Problem: Expansion is blocked.", encoding="utf-8")

    async def fake_review_lenses_with_codex(**kwargs):
        return _stub_lens_reviews()

    monkeypatch.setattr(
        "proposal_doctor.core.review_lenses_with_codex",
        fake_review_lenses_with_codex,
    )

    report = asyncio.run(review_proposal(folder, ProposalDoctorConfig()))
    rendered = render_markdown(report)

    assert "Source type: folder" in rendered
    assert "## Reviewed Files" in rendered
    assert f"`{folder / 'proposal.md'}`" in rendered


def test_codex_review_does_not_read_proposal_body(tmp_path, monkeypatch) -> None:
    proposal = tmp_path / "proposal.md"
    proposal.write_bytes(b"\xff")
    captured = {}

    async def fake_review_lenses_with_codex(**kwargs):
        captured.update(kwargs)
        return _stub_lens_reviews()

    monkeypatch.setattr(
        "proposal_doctor.core.review_lenses_with_codex",
        fake_review_lenses_with_codex,
    )

    report = asyncio.run(review_proposal(proposal, ProposalDoctorConfig()))

    assert report.source_type == "file"
    assert report.sources == [str(proposal)]
    assert captured["proposal_path"] == proposal
    assert captured["source_type"] == "file"


def test_codex_lens_prompts_are_substantive() -> None:
    expected_terms = {
        "customer": ("customer problem", "cost of inaction", "trust"),
        "decision_maker": ("decision", "risk", "approval"),
        "finance": ("ROI", "payback", "measurement"),
        "execution_risk": ("milestones", "owners", "acceptance criteria"),
        "competitive": ("alternatives", "differentiated", "status quo"),
        "procurement_compliance": ("mandatory", "evaluation criteria", "compliance"),
        "stakeholder_adoption": ("stakeholder", "adoption", "enablement"),
        "technical_feasibility": ("architecture", "integration", "security"),
        "commercial_terms_risk": ("payment", "renewal", "legal advice"),
        "narrative_coherence": ("executive summary", "logical flow", "consistency"),
    }

    assert {lens.name for lens in DEFAULT_LENSES} == set(expected_terms)
    for lens in DEFAULT_LENSES:
        assert len(lens.prompt.splitlines()) >= 15
        for term in expected_terms[lens.name]:
            assert term in lens.prompt


def test_codex_prompt_passes_path_and_review_protocol(tmp_path) -> None:
    proposal = tmp_path / "proposal.md"
    proposal.write_text("This body should not be in the prompt.", encoding="utf-8")
    prompt = _build_prompt(proposal, "file", "enterprise CFO", "en", DEFAULT_LENSES[0])

    assert "Review protocol:" in prompt
    assert "Response language: English" in prompt
    assert f"Proposal path: {proposal}" in prompt
    assert "Resolved proposal path:" in prompt
    assert "This body should not be in the prompt." not in prompt
    assert "Return only JSON matching this schema:" in prompt


def test_codex_prompt_can_request_japanese_output(tmp_path) -> None:
    proposal = tmp_path / "proposal.md"
    proposal.write_text("Draft", encoding="utf-8")
    prompt = _build_prompt(proposal, "file", "enterprise CFO", "ja", DEFAULT_LENSES[0])

    assert "Response language: Japanese" in prompt
    assert "Keep JSON keys and enum values exactly as specified" in prompt


def test_out_dir_builds_language_specific_report_path(tmp_path) -> None:
    proposal = tmp_path / "proposal.md"
    out_dir = tmp_path / "work"

    assert _output_path_for_dir(proposal, out_dir, "markdown", "ja") == (
        out_dir / "proposal.review.ja.md"
    )
