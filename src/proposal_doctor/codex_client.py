from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from proposal_doctor.models import LensReview, ReviewLens, SourceType


REVIEW_PROTOCOL = """Review protocol:
- Inspect the proposal path before judging. Do not rely only on filenames.
- Stay inside the supplied proposal path unless a directly referenced supporting
  file is necessary for context. Do not inspect secrets, credentials, auth files,
  or unrelated private files.
- Treat the draft as a proposal being prepared for a real buyer. Be specific,
  evidence-based, and commercially practical.
- Distinguish what the draft explicitly says from what you infer. If evidence is
  missing, call that out as a gap rather than inventing facts.
- Prioritize issues that could affect approval, trust, commercial value,
  delivery feasibility, or competitive selection.
- Severity calibration:
  - high: likely to block approval, damage credibility, hide material risk, or
    make the proposal hard to defend.
  - medium: weakens the case materially but can be fixed with targeted edits.
  - low: polish, clarity, or completeness issue that is unlikely to change the
    decision by itself.
- In each rationale, include the concrete evidence or absence of evidence that
  supports the finding. If possible, name the relevant file or section.
- Recommendations must be directly actionable edits, not generic advice.
- Prefer 2-4 findings. Return no more than 5 findings for this lens.
- Add questions only when the proposal owner must provide missing information to
  fix the issue.
"""


async def review_lenses_with_codex(
    proposal_path: Path,
    source_type: SourceType,
    audience: str,
    lenses: tuple[ReviewLens, ...],
    repo: str,
    max_parallel: int,
) -> list[LensReview]:
    try:
        from openai_codex import AsyncCodex
    except ImportError as exc:
        raise RuntimeError("openai-codex is required to review proposals") from exc

    semaphore = asyncio.Semaphore(max_parallel)

    async with AsyncCodex() as codex:

        async def run_lens(lens: ReviewLens) -> LensReview:
            async with semaphore:
                return await _review_with_codex_client(
                    codex=codex,
                    proposal_path=proposal_path,
                    source_type=source_type,
                    audience=audience,
                    lens=lens,
                    repo=repo,
                )

        return list(await asyncio.gather(*(run_lens(lens) for lens in lenses)))


async def review_with_codex(
    proposal_path: Path,
    source_type: SourceType,
    audience: str,
    lens: ReviewLens,
    repo: str,
) -> LensReview:
    try:
        from openai_codex import AsyncCodex, Sandbox
    except ImportError as exc:
        raise RuntimeError("openai-codex is required to review proposals") from exc

    async with AsyncCodex() as codex:
        return await _review_with_codex_client(
            codex=codex,
            proposal_path=proposal_path,
            source_type=source_type,
            audience=audience,
            lens=lens,
            repo=repo,
            sandbox_type=Sandbox,
        )


async def _review_with_codex_client(
    codex: Any,
    proposal_path: Path,
    source_type: SourceType,
    audience: str,
    lens: ReviewLens,
    repo: str,
    sandbox_type: Any | None = None,
) -> LensReview:
    if sandbox_type is None:
        from openai_codex import Sandbox as sandbox_type

    prompt = _build_prompt(
        proposal_path=proposal_path,
        source_type=source_type,
        audience=audience,
        lens=lens,
    )
    thread = await codex.thread_start(
        cwd=str(Path(repo).resolve()),
        ephemeral=True,
        sandbox=sandbox_type.read_only,
    )
    result = await thread.run(prompt, output_schema=LensReview.model_json_schema())

    raw = result.final_response.strip()
    try:
        return LensReview.model_validate_json(raw)
    except ValueError:
        return LensReview(
            lens=lens.name,
            summary="Codex returned an unstructured review.",
            findings=[],
            questions=[raw],
        )


def _build_prompt(
    proposal_path: Path,
    source_type: SourceType,
    audience: str,
    lens: ReviewLens,
) -> str:
    schema = json.dumps(LensReview.model_json_schema(), indent=2)
    return f"""Review the proposal draft at this local path for the {lens.name} lens.

Audience: {audience}
{REVIEW_PROTOCOL}

Lens-specific rubric:
{lens.prompt}

Proposal path: {proposal_path}
Resolved proposal path: {proposal_path.resolve()}
Proposal path type: {source_type}

If the proposal path is a folder, inspect supported proposal files recursively:
.md, .markdown, and .txt. Ignore hidden files and files in hidden folders.

Return only JSON matching this schema:
{schema}
"""
