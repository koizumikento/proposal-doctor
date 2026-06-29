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
    repo: str = ".",
    max_parallel: int = 5,
) -> dict:
    """Review a local proposal file through business lenses."""
    if not Path(path).is_file():
        raise ValueError(f"Proposal path is not a file: {path}")
    return await _review_path(path, audience, repo, max_parallel)


@mcp.tool()
async def review_proposal_path(
    path: str,
    audience: str = "enterprise buyer",
    repo: str = ".",
    max_parallel: int = 5,
) -> dict:
    """Review a local proposal file or folder through business lenses."""
    return await _review_path(path, audience, repo, max_parallel)


@mcp.tool()
async def review_proposal_folder(
    path: str,
    audience: str = "enterprise buyer",
    repo: str = ".",
    max_parallel: int = 5,
) -> dict:
    """Review a local folder of proposal files through business lenses."""
    if not Path(path).is_dir():
        raise ValueError(f"Proposal path is not a folder: {path}")
    return await _review_path(path, audience, repo, max_parallel)


async def _review_path(
    path: str,
    audience: str,
    repo: str,
    max_parallel: int,
) -> dict:
    report = await review_proposal(
        Path(path),
        ProposalDoctorConfig(
            audience=audience,
            repo=repo,
            max_parallel=max_parallel,
        ),
    )
    return report.model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
