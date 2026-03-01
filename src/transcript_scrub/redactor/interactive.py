"""Interactive review mode for scan findings.

Lets users iterate through medium/low confidence findings,
confirm or skip redactions, and add items to the allowlist.
"""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt

from transcript_scrub.config import ScrubConfig, write_default_config
from transcript_scrub.models import Finding, TranscriptSession
from transcript_scrub.redactor.formatter import print_finding_context

# Path for writing updated allowlist entries
from transcript_scrub.config import PROJECT_CONFIG_NAME

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w


def interactive_review(
    session: TranscriptSession,
    findings: list[Finding],
    config: ScrubConfig,
    console: Console | None = None,
) -> list[Finding]:
    """Interactively review findings, letting user confirm or skip each.

    Args:
        session: The parsed transcript session (for context text).
        findings: List of findings to review.
        config: Current scrub config (may be updated if user adds to allowlist).
        console: Rich console for output.

    Returns:
        Filtered list of confirmed findings.
    """
    console = console or Console()
    confirmed: list[Finding] = []

    # Only review medium and low confidence findings interactively
    auto_confirm = [f for f in findings if f.confidence.value == "high"]
    to_review = [f for f in findings if f.confidence.value != "high"]

    confirmed.extend(auto_confirm)

    if not to_review:
        console.print("[green]All findings are high confidence — nothing to review.[/green]")
        return confirmed

    console.print(
        f"\n[bold]Interactive Review[/bold] — {len(to_review)} findings to review "
        f"({len(auto_confirm)} auto-confirmed as high confidence)\n"
    )

    for i, finding in enumerate(to_review, 1):
        console.print(f"[dim]({i}/{len(to_review)})[/dim]")

        # Get block text for context
        block_text = _get_block_text(session, finding)
        print_finding_context(finding, block_text, console)

        choice = Prompt.ask(
            "[bold]Action[/bold]",
            choices=["y", "n", "a", "q"],
            default="y",
            console=console,
        )

        if choice == "y":
            confirmed.append(finding)
        elif choice == "n":
            console.print("[dim]  Skipped.[/dim]")
        elif choice == "a":
            console.print(f"[dim]  Added to allowlist: {finding.matched_text}[/dim]")
            _add_to_allowlist(finding.matched_text, config)
        elif choice == "q":
            console.print("[dim]  Quitting review — remaining findings skipped.[/dim]")
            break

    console.print(f"\n[bold]Confirmed {len(confirmed)} of {len(findings)} findings.[/bold]")
    return confirmed


def _get_block_text(session: TranscriptSession, finding: Finding) -> str:
    """Get the text of the content block containing a finding."""
    if finding.message_index < len(session.messages):
        msg = session.messages[finding.message_index]
        if finding.block_index < len(msg.content_blocks):
            return msg.content_blocks[finding.block_index].text
    return ""


def _add_to_allowlist(value: str, config: ScrubConfig) -> None:
    """Add a value to the config's allowlist and update the config file."""
    if value not in config.allowlist:
        config.allowlist.append(value)

    # Try to update the project config file
    config_path = Path.cwd() / PROJECT_CONFIG_NAME
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        section = data.setdefault("scrubber", {})
        existing = section.get("allowlist", [])
        if value not in existing:
            existing.append(value)
            section["allowlist"] = existing
        with open(config_path, "wb") as f:
            tomli_w.dump(data, f)
    else:
        write_default_config(config_path)
        # Re-open and add the allowlist entry
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        data.setdefault("scrubber", {}).setdefault("allowlist", []).append(value)
        with open(config_path, "wb") as f:
            tomli_w.dump(data, f)
