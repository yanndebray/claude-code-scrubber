"""
CLI interface for claude-code-scrubber.

Usage:
    claude-code-scrubber scan session.jsonl          # dry-run: report what would be scrubbed
    claude-code-scrubber scrub session.jsonl          # scrub and write to session.scrubbed.jsonl
    claude-code-scrubber scrub session.jsonl -o out/  # scrub into output directory
    claude-code-scrubber scrub *.html --in-place      # scrub HTML files in place
    claude-code-scrubber init                         # create a starter config file
"""

import os
import sys
from pathlib import Path

import click

from . import __version__
from .config import Config, load_config
from .scrubber import Scrubber


SEVERITY_COLORS = {
    "high": "red",
    "medium": "yellow",
    "low": "blue",
}

SEVERITY_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🔵",
}


def _build_scrubber(config: Config, username: str | None, severity: tuple[str, ...]) -> Scrubber:
    """Build a Scrubber from CLI args + config."""
    effective_username = username or config.username or os.environ.get("USER")
    effective_severity = set(severity) if severity else config.severity
    return Scrubber(
        username=effective_username,
        extra_patterns=config.extra_patterns or None,
        severity_filter=effective_severity,
        allowlist=config.allowlist,
    )


@click.group()
@click.version_option(version=__version__)
def main():
    """🧼 Scrub secrets and PII from Claude Code transcripts.

    Supports JSONL (local sessions), JSON (web sessions), and
    HTML (claude-code-transcripts output).
    """
    pass


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--username", "-u", help="OS username to scrub from file paths")
@click.option(
    "--severity", "-s",
    type=click.Choice(["high", "medium", "low"]),
    multiple=True,
    help="Filter by severity (can specify multiple). Default: all.",
)
@click.option("--config", "-c", "config_path", type=click.Path(exists=True),
              help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Show every individual match")
def scan(files, username, severity, config_path, verbose):
    """Dry-run: show what would be scrubbed without modifying files."""
    config = load_config(Path(config_path) if config_path else None)
    scrubber = _build_scrubber(config, username, severity)

    from .scrubber import ScrubReport
    combined = ScrubReport()

    for filepath in files:
        path = Path(filepath)
        click.echo(f"\n📄 Scanning {click.style(str(path), bold=True)} ...")
        _, report = scrubber.scrub_file(path)
        combined.matches.extend(report.matches)
        combined.files_processed += 1

        if verbose and report.matches:
            for m in report.matches:
                icon = SEVERITY_ICONS.get(m.severity, "⚪")
                click.echo(
                    f"  {icon} [{m.severity.upper()}] {m.pattern_name}"
                    f"  at {m.location}"
                    f"  → {click.style(m.original, fg=SEVERITY_COLORS.get(m.severity, 'white'))}"
                )
        elif report.matches:
            click.echo(f"  Found {len(report.matches)} item(s)")
        else:
            click.echo("  ✅ Clean")

    click.echo()
    click.echo(combined.summary())

    if combined.total > 0:
        click.echo()
        click.echo("Run with " + click.style("scrub", bold=True) + " to redact these findings.")
        sys.exit(1)  # non-zero = findings exist (useful for CI)
    sys.exit(0)


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--username", "-u", help="OS username to scrub from file paths")
@click.option(
    "--severity", "-s",
    type=click.Choice(["high", "medium", "low"]),
    multiple=True,
    help="Filter by severity (can specify multiple). Default: all.",
)
@click.option("--output", "-o", "output_dir", type=click.Path(),
              help="Output directory (default: write next to original with suffix)")
@click.option("--suffix", default=None,
              help="Suffix for output files (default: .scrubbed)")
@click.option("--in-place", is_flag=True,
              help="⚠️  Overwrite original files (no suffix, no copy)")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True),
              help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Show every individual match")
def scrub(files, username, severity, output_dir, suffix, in_place, config_path, verbose):
    """Scrub secrets and PII from transcript files."""
    config = load_config(Path(config_path) if config_path else None)
    scrubber = _build_scrubber(config, username, severity)
    effective_suffix = suffix or config.output_suffix

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    from .scrubber import ScrubReport
    combined = ScrubReport()

    for filepath in files:
        path = Path(filepath)
        click.echo(f"\n🧼 Scrubbing {click.style(str(path), bold=True)} ...")
        scrubbed_content, report = scrubber.scrub_file(path)
        combined.matches.extend(report.matches)
        combined.files_processed += 1

        # Apply config-level string replacements
        for old, new in config.string_replacements.items():
            scrubbed_content = scrubbed_content.replace(old, new)

        # Determine output path
        if in_place:
            dest = path
        elif output_dir:
            dest = Path(output_dir) / path.name
        else:
            stem = path.stem
            dest = path.with_stem(stem + effective_suffix)

        dest.write_text(scrubbed_content, encoding="utf-8")

        if verbose and report.matches:
            for m in report.matches:
                icon = SEVERITY_ICONS.get(m.severity, "⚪")
                click.echo(
                    f"  {icon} {m.pattern_name} at {m.location}"
                )

        n = len(report.matches)
        if n:
            click.echo(f"  Redacted {n} item(s) → {click.style(str(dest), fg='green')}")
        else:
            click.echo(f"  ✅ Clean → {click.style(str(dest), fg='green')}")

    click.echo()
    click.echo(combined.summary())


@main.command()
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "toml"]),
              default="json", help="Config file format")
def init(fmt):
    """Create a starter .transcript-scrub config file in the current directory."""
    if fmt == "json":
        filename = ".transcript-scrub.json"
        content = """\
{
    "username": null,
    "severity": ["high", "medium", "low"],
    "output_suffix": ".scrubbed",
    "allowlist": [
        "example@test.com",
        "sk-ant-this-is-a-dummy-key"
    ],
    "string_replacements": {
        "MyCompanyName": "ACME",
        "my-secret-project": "project-x"
    },
    "patterns": [
        {
            "name": "Internal project ID",
            "regex": "PROJ-[0-9]{4,}",
            "replacement": "PROJ-XXXX",
            "severity": "medium"
        }
    ]
}
"""
    else:
        filename = ".transcript-scrub.toml"
        content = """\
# transcript-scrub configuration

# Your OS username — used to redact /Users/<name>/ and /home/<name>/ paths
# username = "yann"

# Which severity levels to scrub (default: all)
severity = ["high", "medium", "low"]

# Output file suffix (default: ".scrubbed")
output_suffix = ".scrubbed"

# Strings that should never be redacted (false positive prevention)
allowlist = [
    "example@test.com",
    "sk-ant-this-is-a-dummy-key",
]

# Exact string replacements (applied after regex patterns)
[string_replacements]
# "MyCompanyName" = "ACME"
# "my-secret-project" = "project-x"

# Extra custom regex patterns
[[patterns]]
name = "Internal project ID"
regex = "PROJ-[0-9]{4,}"
replacement = "PROJ-XXXX"
severity = "medium"
"""

    dest = Path.cwd() / filename
    if dest.exists():
        click.confirm(f"{filename} already exists. Overwrite?", abort=True)

    dest.write_text(content)
    click.echo(f"✅ Created {click.style(filename, bold=True)}")
    click.echo(f"   Edit it to add your username, custom patterns, and allowlists.")


if __name__ == "__main__":
    main()
