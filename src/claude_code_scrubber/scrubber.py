"""
Core scrubbing engine.

Walks through transcript content (JSONL, JSON, or HTML) and applies
pattern-based redaction, returning the scrubbed output and a report
of all matches found.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .patterns import ScrubPattern, build_patterns


@dataclass
class Match:
    """A single detected secret / PII match."""
    pattern_name: str
    severity: str
    original: str          # the matched text (truncated for display)
    location: str          # e.g. "line 42" or "message[3].content"
    replacement: str


@dataclass
class ScrubReport:
    """Summary of everything found and redacted."""
    matches: list[Match] = field(default_factory=list)
    files_processed: int = 0

    @property
    def total(self) -> int:
        return len(self.matches)

    @property
    def by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for m in self.matches:
            counts[m.severity] = counts.get(m.severity, 0) + 1
        return counts

    @property
    def by_pattern(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self.matches:
            counts[m.pattern_name] = counts.get(m.pattern_name, 0) + 1
        return counts

    def summary(self) -> str:
        if not self.matches:
            return "✅ No secrets or PII detected."
        lines = [
            f"🧼 Found {self.total} item(s) to scrub across {self.files_processed} file(s):",
            "",
        ]
        sev = self.by_severity
        if sev["high"]:
            lines.append(f"  🔴 High:   {sev['high']}  (API keys, tokens, passwords)")
        if sev["medium"]:
            lines.append(f"  🟡 Medium: {sev['medium']}  (emails, private IPs)")
        if sev["low"]:
            lines.append(f"  🔵 Low:    {sev['low']}  (usernames in paths)")
        lines.append("")
        lines.append("  Breakdown by type:")
        for name, count in sorted(self.by_pattern.items(), key=lambda x: -x[1]):
            lines.append(f"    • {name}: {count}")
        return "\n".join(lines)


def _truncate(s: str, max_len: int = 40) -> str:
    """Truncate a matched string for safe display in reports."""
    if len(s) <= max_len:
        return s
    quarter = max_len // 4
    return s[:quarter] + "…" + s[-quarter:]


class Scrubber:
    """Applies scrub patterns to text content."""

    def __init__(
        self,
        username: str | None = None,
        extra_patterns: list[ScrubPattern] | None = None,
        severity_filter: set[str] | None = None,
        allowlist: set[str] | None = None,
    ):
        self.patterns = build_patterns(username=username)
        if extra_patterns:
            self.patterns.extend(extra_patterns)
        # Only keep enabled patterns at the requested severity
        if severity_filter:
            self.patterns = [
                p for p in self.patterns
                if p.enabled and p.severity in severity_filter
            ]
        else:
            self.patterns = [p for p in self.patterns if p.enabled]
        # Strings to never redact
        self.allowlist = allowlist or set()

    def scrub_text(self, text: str, location: str = "") -> tuple[str, list[Match]]:
        """Apply all patterns to a text string.

        Returns (scrubbed_text, list_of_matches).
        """
        matches: list[Match] = []
        for pat in self.patterns:
            for m in pat.pattern.finditer(text):
                original = m.group(0)
                if original in self.allowlist:
                    continue
                matches.append(Match(
                    pattern_name=pat.name,
                    severity=pat.severity,
                    original=_truncate(original),
                    location=location,
                    replacement=pat.replacement,
                ))
            text = pat.pattern.sub(pat.replacement, text)
        return text, matches

    # ── Format-specific processors ────────────────────────────────────────

    def scrub_jsonl(self, content: str) -> tuple[str, ScrubReport]:
        """Scrub a Claude Code local session JSONL file.

        Each line is a JSON object. We walk all string values recursively
        and apply patterns.
        """
        report = ScrubReport(files_processed=1)
        output_lines: list[str] = []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line:
                output_lines.append("")
                continue
            try:
                obj = json.loads(line)
                scrubbed_obj, line_matches = self._scrub_json_value(
                    obj, location=f"line {line_num}"
                )
                report.matches.extend(line_matches)
                output_lines.append(json.dumps(scrubbed_obj, ensure_ascii=False))
            except json.JSONDecodeError:
                # Not valid JSON — scrub as plain text
                scrubbed, line_matches = self.scrub_text(line, f"line {line_num}")
                report.matches.extend(line_matches)
                output_lines.append(scrubbed)

        return "\n".join(output_lines), report

    def scrub_json(self, content: str) -> tuple[str, ScrubReport]:
        """Scrub a Claude Code for web JSON session file."""
        report = ScrubReport(files_processed=1)
        try:
            data = json.loads(content)
            scrubbed_data, matches = self._scrub_json_value(data, location="root")
            report.matches.extend(matches)
            return json.dumps(scrubbed_data, indent=2, ensure_ascii=False), report
        except json.JSONDecodeError:
            # Fall back to plain text scrubbing
            scrubbed, matches = self.scrub_text(content, "file")
            report.matches.extend(matches)
            return scrubbed, report

    def scrub_html(self, content: str) -> tuple[str, ScrubReport]:
        """Scrub an HTML transcript (e.g. output from claude-code-transcripts).

        We treat it as plain text — regex patterns work across HTML content.
        We're careful not to break HTML tags themselves.
        """
        report = ScrubReport(files_processed=1)

        # Split on HTML tags so we only scrub text nodes & attribute values
        parts = re.split(r'(<[^>]+>)', content)
        scrubbed_parts: list[str] = []

        for i, part in enumerate(parts):
            if part.startswith('<') and part.endswith('>'):
                # It's an HTML tag — scrub attribute values only
                scrubbed, matches = self.scrub_text(part, f"tag@{i}")
                report.matches.extend(matches)
                scrubbed_parts.append(scrubbed)
            else:
                # Text node — scrub fully
                scrubbed, matches = self.scrub_text(part, f"text@{i}")
                report.matches.extend(matches)
                scrubbed_parts.append(scrubbed)

        return "".join(scrubbed_parts), report

    def scrub_file(self, path: Path) -> tuple[str, ScrubReport]:
        """Auto-detect format from extension and scrub."""
        content = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()

        if suffix == ".jsonl":
            return self.scrub_jsonl(content)
        elif suffix == ".json":
            return self.scrub_json(content)
        elif suffix in (".html", ".htm"):
            return self.scrub_html(content)
        else:
            # Default: treat as plain text
            report = ScrubReport(files_processed=1)
            scrubbed, matches = self.scrub_text(content, "file")
            report.matches.extend(matches)
            return scrubbed, report

    # ── Internal helpers ──────────────────────────────────────────────────

    def _scrub_json_value(
        self, value: object, location: str
    ) -> tuple[object, list[Match]]:
        """Recursively walk a parsed JSON value and scrub all strings."""
        all_matches: list[Match] = []

        if isinstance(value, str):
            scrubbed, matches = self.scrub_text(value, location)
            return scrubbed, matches

        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                scrubbed_v, matches = self._scrub_json_value(
                    v, location=f"{location}.{k}"
                )
                result[k] = scrubbed_v
                all_matches.extend(matches)
            return result, all_matches

        elif isinstance(value, list):
            result_list = []
            for i, item in enumerate(value):
                scrubbed_item, matches = self._scrub_json_value(
                    item, location=f"{location}[{i}]"
                )
                result_list.append(scrubbed_item)
                all_matches.extend(matches)
            return result_list, all_matches

        else:
            # int, float, bool, None — pass through
            return value, []
