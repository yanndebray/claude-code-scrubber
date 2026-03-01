"""Click CLI for claude-code-scrubber.

Entry point: claude-code-scrubber (defined in pyproject.toml).
Commands: scan, scrub, config.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress

from transcript_scrub.config import (
    PROJECT_CONFIG_NAME,
    ScrubConfig,
    load_config,
    write_default_config,
)
from transcript_scrub.models import Confidence

console = Console()


def _load_cfg(config_path: str | None, confidence: str | None) -> ScrubConfig:
    """Load config, optionally overriding confidence threshold."""
    cfg = load_config(
        config_path=Path(config_path) if config_path else None,
    )
    if confidence:
        cfg.confidence_threshold = confidence
    return cfg


def _run_pipeline(file_path: Path, cfg: ScrubConfig):
    """Run the parse -> scan -> redact pipeline on a single file.

    Returns (original_session, redaction_result) or raises click.ClickException.
    """
    try:
        from transcript_scrub.parser import detect_and_parse
    except ImportError:
        raise click.ClickException(
            "Parser module not available. Ensure transcript_scrub.parser is installed."
        )

    try:
        from transcript_scrub.scanner import ScannerRegistry
    except ImportError:
        raise click.ClickException(
            "Scanner module not available. Ensure transcript_scrub.scanner is installed."
        )

    from transcript_scrub.redactor.engine import RedactionEngine

    # Parse
    try:
        session = detect_and_parse(file_path)
    except Exception as e:
        raise click.ClickException(f"Failed to parse {file_path}: {e}")

    # Scan
    registry = ScannerRegistry()
    findings = registry.scan_session(session)

    # Redact
    import copy
    original = copy.deepcopy(session)
    engine = RedactionEngine(config=cfg)
    result = engine.redact(session, findings)

    return original, result


@click.group()
@click.version_option(package_name="claude-code-scrubber")
def cli() -> None:
    """Claude Code Scrubber — scrub sensitive information from transcripts."""


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--interactive", "-i", is_flag=True, help="Interactively review findings.")
@click.option(
    "--confidence",
    type=click.Choice(["high", "medium", "low"]),
    help="Override confidence threshold.",
)
@click.option("--config", "config_path", type=click.Path(), help="Path to config file.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress detailed output.")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output.")
def scan(
    file_path: Path,
    interactive: bool,
    confidence: str | None,
    config_path: str | None,
    quiet: bool,
    verbose: bool,
) -> None:
    """Scan a transcript file for sensitive information (dry run).

    Shows a colored diff of what would be redacted without modifying the file.
    """
    cfg = _load_cfg(config_path, confidence)

    if file_path.is_dir():
        _scan_directory(file_path, cfg, interactive, quiet, verbose)
        return

    original, result = _run_pipeline(file_path, cfg)

    if interactive:
        from transcript_scrub.redactor.interactive import interactive_review

        confirmed = interactive_review(
            original, result.findings, cfg, console=console
        )
        # Re-run engine with only confirmed findings
        from transcript_scrub.redactor.engine import RedactionEngine

        engine = RedactionEngine(config=cfg)
        result = engine.redact(original, confirmed)

    from transcript_scrub.redactor.formatter import (
        print_redaction_map,
        print_scan_diff,
        print_summary_table,
    )

    if not quiet:
        print_scan_diff(original, result, console=console)

    if verbose:
        print_redaction_map(result, console=console)

    print_summary_table(result, console=console)

    if result.findings:
        console.print(
            f"[bold yellow]Found {len(result.findings)} items to redact.[/bold yellow]"
        )
    else:
        console.print("[bold green]No sensitive information found.[/bold green]")


def _scan_directory(
    dir_path: Path,
    cfg: ScrubConfig,
    interactive: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    """Scan all transcript files in a directory."""
    files = list(dir_path.glob("**/*.jsonl")) + list(dir_path.glob("**/*.json"))
    if not files:
        console.print(f"[yellow]No .jsonl or .json files found in {dir_path}[/yellow]")
        return

    total_findings = 0
    for fp in sorted(files):
        console.print(f"\n[bold]{fp}[/bold]")
        try:
            original, result = _run_pipeline(fp, cfg)
            total_findings += len(result.findings)
            if not quiet:
                from transcript_scrub.redactor.formatter import print_summary_table
                print_summary_table(result, console=console)
        except click.ClickException as e:
            console.print(f"[red]  Error: {e.message}[/red]")

    console.print(f"\n[bold]Total: {total_findings} findings across {len(files)} files.[/bold]")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path.")
@click.option("--in-place", is_flag=True, help="Scrub the file in place.")
@click.option(
    "--confidence",
    type=click.Choice(["high", "medium", "low"]),
    help="Override confidence threshold.",
)
@click.option("--config", "config_path", type=click.Path(), help="Path to config file.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress detailed output.")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output.")
def scrub(
    file_path: Path,
    output: Path | None,
    in_place: bool,
    confidence: str | None,
    config_path: str | None,
    quiet: bool,
    verbose: bool,
) -> None:
    """Scrub sensitive information from a transcript file.

    Writes the redacted output to a new file or in place.
    """
    cfg = _load_cfg(config_path, confidence)

    if file_path.is_dir():
        _scrub_directory(file_path, cfg, output, quiet, verbose)
        return

    if not output and not in_place:
        # Default: write to <name>.scrubbed.<ext>
        output = file_path.with_suffix(f".scrubbed{file_path.suffix}")

    original, result = _run_pipeline(file_path, cfg)

    # Reconstruct the scrubbed output
    try:
        from transcript_scrub.parser import detect_and_parse
        from transcript_scrub.parser.base import BaseParser
    except ImportError:
        raise click.ClickException("Parser module not available.")

    # Use the parser to reconstruct
    from transcript_scrub.parser import get_parser_for_file
    parser = get_parser_for_file(file_path)
    scrubbed_text = parser.reconstruct(result.scrubbed_session)

    # Write output
    out_path = file_path if in_place else output
    out_path.write_text(scrubbed_text, encoding="utf-8")

    if not quiet:
        from transcript_scrub.redactor.formatter import print_summary_table
        print_summary_table(result, console=console)
        console.print(f"[green]Scrubbed output written to {out_path}[/green]")


def _scrub_directory(
    dir_path: Path,
    cfg: ScrubConfig,
    output_dir: Path | None,
    quiet: bool,
    verbose: bool,
) -> None:
    """Scrub all transcript files in a directory."""
    files = list(dir_path.glob("**/*.jsonl")) + list(dir_path.glob("**/*.json"))
    if not files:
        console.print(f"[yellow]No .jsonl or .json files found in {dir_path}[/yellow]")
        return

    with Progress(console=console) as progress:
        task = progress.add_task("Scrubbing files...", total=len(files))
        for fp in sorted(files):
            try:
                original, result = _run_pipeline(fp, cfg)

                from transcript_scrub.parser import get_parser_for_file
                parser = get_parser_for_file(fp)
                scrubbed_text = parser.reconstruct(result.scrubbed_session)

                if output_dir:
                    out_path = output_dir / fp.relative_to(dir_path)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    out_path = fp.with_suffix(f".scrubbed{fp.suffix}")

                out_path.write_text(scrubbed_text, encoding="utf-8")

                if not quiet:
                    console.print(f"  [green]{fp} -> {out_path}[/green]")
            except (click.ClickException, Exception) as e:
                console.print(f"  [red]Error processing {fp}: {e}[/red]")
            progress.advance(task)


@cli.command("config")
@click.option("--init", is_flag=True, help="Create a default config file in the current directory.")
@click.option("--path", "config_path", type=click.Path(), help="Path to config file to display.")
def config_cmd(init: bool, config_path: str | None) -> None:
    """Show or initialize the scrubber configuration."""
    if init:
        target = Path.cwd() / PROJECT_CONFIG_NAME
        if target.exists():
            console.print(f"[yellow]Config file already exists: {target}[/yellow]")
            return
        write_default_config(target)
        console.print(f"[green]Created config file: {target}[/green]")
        return

    cfg = load_config(config_path=Path(config_path) if config_path else None)

    from rich.table import Table

    table = Table(title="Current Configuration", show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("confidence_threshold", cfg.confidence_threshold)
    table.add_row("redact_paths", str(cfg.redact_paths))
    table.add_row("keep_example_ips", str(cfg.keep_example_ips))
    table.add_row("allowlist", ", ".join(cfg.allowlist) if cfg.allowlist else "(empty)")
    table.add_row("denylist", ", ".join(cfg.denylist) if cfg.denylist else "(empty)")

    console.print(table)
