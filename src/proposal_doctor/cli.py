from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from proposal_doctor.core import render_markdown, review_proposal
from proposal_doctor.models import ProposalDoctorConfig

app = typer.Typer(help="Review proposal drafts through multiple business lenses.")
console = Console()


@app.callback()
def main() -> None:
    """Review proposal drafts through multiple business lenses."""


@app.command()
def review(
    proposal: Annotated[
        Path,
        typer.Argument(help="Path to a UTF-8 proposal draft or a folder of proposal drafts."),
    ],
    audience: Annotated[str, typer.Option("--audience", "-a")] = "enterprise buyer",
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    output_format: Annotated[Literal["markdown", "json"], typer.Option("--format")] = "markdown",
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    max_parallel: Annotated[int, typer.Option("--max-parallel")] = 5,
) -> None:
    """Review a proposal file or folder and print a prioritized improvement report."""
    config = ProposalDoctorConfig(
        audience=audience,
        repo=str(repo),
        max_parallel=max_parallel,
    )
    try:
        report = asyncio.run(review_proposal(proposal, config))
    except (FileNotFoundError, UnicodeDecodeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="proposal") from exc
    rendered = (
        report.model_dump_json(indent=2) if output_format == "json" else render_markdown(report)
    )

    if out:
        out.write_text(rendered, encoding="utf-8")
    elif output_format == "json":
        console.out(rendered)
    else:
        console.print(rendered, markup=False)
