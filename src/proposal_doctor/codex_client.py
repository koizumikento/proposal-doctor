from __future__ import annotations

import json
from pathlib import Path

from proposal_doctor.models import LensReview, ReviewLens


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

    prompt = _build_prompt(text=text, audience=audience, lens=lens)

    async with AsyncCodex() as codex:
        thread = await codex.thread_start(sandbox=Sandbox.read_only)
        result = await thread.run(prompt, cwd=str(Path(repo).resolve()))

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
