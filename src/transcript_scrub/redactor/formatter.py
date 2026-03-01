"""Rich-based output formatting for scan and scrub results.

Provides colored diff views, summary tables, and finding lists
for terminal display.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from transcript_scrub.models import Finding, RedactionResult, TranscriptSession


def print_scan_diff(
    original: TranscriptSession,
    result: RedactionResult,
    console: Console | None = None,
) -> None:
    """Print a colored diff showing original vs redacted text.

    Highlights redacted portions in red/yellow in the original,
    and shows the replacement in green.
    """
    console = console or Console()
    redaction_map = result.redaction_map

    if not redaction_map:
        console.print("[green]No sensitive information detected.[/green]")
        return

    console.print()
    console.print(
        Panel("[bold]Scan Results — Detected Redactions[/bold]", style="blue")
    )

    # Group findings by message
    findings_by_msg: dict[int, list[Finding]] = {}
    for f in result.findings:
        findings_by_msg.setdefault(f.message_index, []).append(f)

    for msg_idx in sorted(findings_by_msg.keys()):
        msg_findings = findings_by_msg[msg_idx]
        if msg_idx < len(original.messages):
            role = original.messages[msg_idx].role.value
        else:
            role = "unknown"

        console.print(f"\n[bold cyan]Message {msg_idx} ({role}):[/bold cyan]")

        for f in sorted(msg_findings, key=lambda x: (x.block_index, x.char_start)):
            replacement = redaction_map.get(f.matched_text, "[REDACTED]")

            line = Text()
            line.append("  - ", style="dim")
            line.append(f.matched_text, style="bold red strikethrough")
            line.append(" -> ", style="dim")
            line.append(replacement, style="bold green")
            line.append(f"  ({f.category}, {f.confidence.value})", style="dim")
            console.print(line)

    console.print()


def print_summary_table(
    result: RedactionResult,
    console: Console | None = None,
) -> None:
    """Print a summary table of redaction counts by category."""
    console = console or Console()

    if not result.stats:
        return

    table = Table(title="Redaction Summary", show_header=True, header_style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")

    total = 0
    for category, count in sorted(result.stats.items()):
        table.add_row(category, str(count))
        total += count

    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(table)
    console.print()


def print_redaction_map(
    result: RedactionResult,
    console: Console | None = None,
) -> None:
    """Print the unique redacted values and their replacements."""
    console = console or Console()

    if not result.redaction_map:
        return

    table = Table(
        title="Redaction Map",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Original", style="red")
    table.add_column("Replacement", style="green")

    for original, replacement in sorted(
        result.redaction_map.items(), key=lambda x: x[1]
    ):
        # Truncate long values for display
        display_original = original if len(original) <= 60 else original[:57] + "..."
        table.add_row(display_original, replacement)

    console.print(table)
    console.print()


def print_finding_context(
    finding: Finding,
    block_text: str,
    console: Console | None = None,
) -> None:
    """Print a single finding with surrounding context for interactive review."""
    console = console or Console()

    # Extract context around the finding
    ctx_start = max(0, finding.char_start - 40)
    ctx_end = min(len(block_text), finding.char_end + 40)

    text = Text()
    if ctx_start > 0:
        text.append("...", style="dim")
    text.append(block_text[ctx_start : finding.char_start], style="dim")
    text.append(block_text[finding.char_start : finding.char_end], style="bold red")
    text.append(block_text[finding.char_end : ctx_end], style="dim")
    if ctx_end < len(block_text):
        text.append("...", style="dim")

    panel = Panel(
        text,
        title=f"[bold]{finding.category}[/bold] ({finding.confidence.value} confidence)",
        subtitle=f"Message {finding.message_index}, Block {finding.block_index}",
        border_style="yellow",
    )
    console.print(panel)
