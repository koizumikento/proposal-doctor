from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from proposal_doctor.models import LensReview, ReviewLens


async def review_lenses_with_codex(
    text: str,
    audience: str,
    lenses: tuple[ReviewLens, ...],
    repo: str,
    max_parallel: int,
) -> list[LensReview]:
    try:
        from openai_codex import AsyncCodex
    except ImportError as exc:
        raise RuntimeError("openai-codex is required for --use-codex") from exc

    semaphore = asyncio.Semaphore(max_parallel)

    async with AsyncCodex() as codex:

        async def run_lens(lens: ReviewLens) -> LensReview:
            async with semaphore:
                return await _review_with_codex_client(codex, text, audience, lens, repo)

        return list(await asyncio.gather(*(run_lens(lens) for lens in lenses)))


async def review_with_codex(
    text: str,
    audience: str,
    lens: ReviewLens,
    repo: str,
) -> LensReview:
    try:
        from openai_codex import AsyncCodex, Sandbox
    except ImportError as exc:
        raise RuntimeError("openai-codex is required for --use-codex") from exc

    async with AsyncCodex() as codex:
        return await _review_with_codex_client(codex, text, audience, lens, repo, Sandbox)


async def _review_with_codex_client(
    codex: Any,
    text: str,
    audience: str,
    lens: ReviewLens,
    repo: str,
    sandbox_type: Any | None = None,
) -> LensReview:
    if sandbox_type is None:
        from openai_codex import Sandbox as sandbox_type

    prompt = _build_prompt(text=text, audience=audience, lens=lens)
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


def _build_prompt(text: str, audience: str, lens: ReviewLens) -> str:
    schema = json.dumps(LensReview.model_json_schema(), indent=2)
    return f"""Review this proposal draft for the {lens.name} lens.

Audience: {audience}
Lens instruction: {lens.prompt}

Return only JSON matching this schema:
{schema}

Proposal:
```text
{text}
```
"""
