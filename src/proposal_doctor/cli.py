from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from proposal_doctor.core import render_markdown, review_proposal
from proposal_doctor.models import OutputLanguage, ProposalDoctorConfig, WebSearchSetting

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
    language: Annotated[OutputLanguage, typer.Option("--language", "-l")] = "en",
    web_search: Annotated[WebSearchSetting, typer.Option("--web-search")] = "lens",
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    output_format: Annotated[Literal["markdown", "json"], typer.Option("--format")] = "markdown",
    repo: Annotated[Path, typer.Option("--repo")] = Path("."),
    max_parallel: Annotated[int, typer.Option("--max-parallel")] = 10,
    codex_config: Annotated[
        list[str] | None,
        typer.Option(
            "--codex-config",
            help="Codex runtime override in TOML key=value form. Can be passed multiple times.",
        ),
    ] = None,
) -> None:
    """Review a proposal file or folder and print a prioritized improvement report."""
    if out and out_dir:
        raise typer.BadParameter("Use either --out or --out-dir, not both.", param_hint="out")

    config = ProposalDoctorConfig(
        audience=audience,
        language=language,
        web_search=web_search,
        repo=str(repo),
        max_parallel=max_parallel,
        codex_config_overrides=tuple(codex_config or ()),
    )
    try:
        report = asyncio.run(review_proposal(proposal, config))
    except (FileNotFoundError, UnicodeDecodeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="proposal") from exc
    rendered = (
        report.model_dump_json(indent=2) if output_format == "json" else render_markdown(report)
    )

    output_path = out or _output_path_for_dir(proposal, out_dir, output_format, language)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    elif output_format == "json":
        console.out(rendered)
    else:
        console.print(rendered, markup=False)


def _output_path_for_dir(
    proposal: Path,
    out_dir: Path | None,
    output_format: Literal["markdown", "json"],
    language: OutputLanguage,
) -> Path | None:
    if out_dir is None:
        return None

    extension = "json" if output_format == "json" else "md"
    return out_dir / f"{proposal.stem}.review.{language}.{extension}"
