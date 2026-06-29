from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from proposal_doctor.core import review_proposal
from proposal_doctor.models import ProposalDoctorConfig

mcp = FastMCP("proposal-doctor")


@mcp.tool()
async def review_proposal_file(
    path: str,
    audience: str = "enterprise buyer",
    use_codex: bool = False,
    repo: str = ".",
    max_parallel: int = 5,
) -> dict:
    """Review a local proposal file through business lenses."""
    report = await review_proposal(
        Path(path),
        ProposalDoctorConfig(
            audience=audience,
            use_codex=use_codex,
            repo=repo,
            max_parallel=max_parallel,
        ),
    )
    return report.model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
