"""Core redaction engine with stable numbering.

Takes a TranscriptSession and list of Finding objects, applies redactions
with stable numbering so the same matched_text always gets the same
replacement placeholder everywhere in the transcript.
"""

from __future__ import annotations

import copy
import json
import re
from collections import defaultdict

from transcript_scrub.allowlists import is_safe_email, is_safe_ipv4
from transcript_scrub.config import ScrubConfig, confidence_meets_threshold
from transcript_scrub.models import (
    Confidence,
    Finding,
    RedactionResult,
    TranscriptSession,
)


class RedactionEngine:
    """Applies redactions to a transcript session.

    The engine:
    1. Filters findings by confidence threshold and allowlist/denylist
    2. Resolves overlapping findings (prefer higher confidence, then longer match)
    3. Assigns stable numbered replacements per category
    4. Applies replacements in reverse order to maintain position accuracy
    5. Updates both ContentBlock.text and the raw dicts
    """

    def __init__(self, config: ScrubConfig | None = None) -> None:
        self.config = config or ScrubConfig()

    def redact(
        self,
        session: TranscriptSession,
        findings: list[Finding],
    ) -> RedactionResult:
        """Apply redactions to a transcript session.

        Args:
            session: The parsed transcript session.
            findings: All detected findings from scanners.

        Returns:
            RedactionResult with scrubbed session, findings, map, and stats.
        """
        # Deep copy so we don't mutate the original
        scrubbed = copy.deepcopy(session)

        # Step 1: Filter findings
        filtered = self._filter_findings(findings)

        # Step 2: Resolve overlaps
        resolved = self._resolve_overlaps(filtered)

        # Step 3: Build stable redaction map
        redaction_map = self._build_redaction_map(resolved)

        # Step 4: Apply redactions (grouped by message/block, reverse order)
        self._apply_redactions(scrubbed, resolved, redaction_map)

        # Step 5: Compute stats
        stats: dict[str, int] = defaultdict(int)
        for f in resolved:
            stats[f.category] += 1

        return RedactionResult(
            scrubbed_session=scrubbed,
            findings=resolved,
            redaction_map=redaction_map,
            stats=dict(stats),
        )

    def _filter_findings(self, findings: list[Finding]) -> list[Finding]:
        """Filter findings by confidence threshold, allowlist, and denylist."""
        result = []
        allowlist_patterns = [
            re.compile(p, re.IGNORECASE) if _is_regex(p) else None
            for p in self.config.allowlist
        ]
        allowlist_literals = [
            p.lower() for p in self.config.allowlist if not _is_regex(p)
        ]

        for f in findings:
            # Check confidence threshold
            if not confidence_meets_threshold(
                f.confidence.value, self.config.confidence_threshold
            ):
                continue

            matched_lower = f.matched_text.lower()

            # Check allowlist
            if self._matches_allowlist(
                matched_lower, allowlist_patterns, allowlist_literals
            ):
                continue

            # Check built-in safe lists
            if f.category == "EMAIL" and is_safe_email(f.matched_text):
                continue
            if f.category in ("IP-ADDRESS", "IPV4") and is_safe_ipv4(f.matched_text):
                continue

            result.append(f)

        # Check denylist — add synthetic findings for denylist patterns
        # (denylist is handled by scanners typically, but we pass through here)

        return result

    def _matches_allowlist(
        self,
        text_lower: str,
        patterns: list[re.Pattern[str] | None],
        literals: list[str],
    ) -> bool:
        """Check if text matches any allowlist entry."""
        for lit in literals:
            if text_lower == lit:
                return True
        for pat in patterns:
            if pat is not None and pat.search(text_lower):
                return True
        return False

    def _resolve_overlaps(self, findings: list[Finding]) -> list[Finding]:
        """Resolve overlapping findings within the same block.

        When two findings overlap, keep the one with higher confidence,
        or if equal confidence, the longer match.
        """
        # Group by (message_index, block_index)
        groups: dict[tuple[int, int], list[Finding]] = defaultdict(list)
        for f in findings:
            groups[(f.message_index, f.block_index)].append(f)

        resolved: list[Finding] = []
        for _key, group in groups.items():
            # Sort by start position
            group.sort(key=lambda f: (f.char_start, -f.char_end))
            kept: list[Finding] = []
            for f in group:
                # Check if this overlaps with any already kept finding
                overlaps = False
                for k in kept:
                    if f.char_start < k.char_end and f.char_end > k.char_start:
                        # Overlap detected — keep the better one
                        overlaps = True
                        if _finding_priority(f) > _finding_priority(k):
                            kept.remove(k)
                            kept.append(f)
                        break
                if not overlaps:
                    kept.append(f)
            resolved.extend(kept)

        return resolved

    def _build_redaction_map(self, findings: list[Finding]) -> dict[str, str]:
        """Build a stable mapping of matched_text to numbered replacement.

        Same matched_text always gets the same replacement. Numbers are
        assigned per category in order of first appearance.
        """
        # Sort findings by position for deterministic first-appearance ordering
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.message_index, f.block_index, f.char_start),
        )

        redaction_map: dict[str, str] = {}
        category_counters: dict[str, int] = defaultdict(int)

        for f in sorted_findings:
            if f.matched_text not in redaction_map:
                category_counters[f.category] += 1
                n = category_counters[f.category]
                redaction_map[f.matched_text] = f"[REDACTED-{f.category}-{n}]"

        return redaction_map

    def _apply_redactions(
        self,
        session: TranscriptSession,
        findings: list[Finding],
        redaction_map: dict[str, str],
    ) -> None:
        """Apply redactions to the scrubbed session in-place.

        Processes findings in reverse character order within each block
        to maintain position accuracy.
        """
        # Group findings by (message_index, block_index)
        groups: dict[tuple[int, int], list[Finding]] = defaultdict(list)
        for f in findings:
            groups[(f.message_index, f.block_index)].append(f)

        for (msg_idx, blk_idx), group in groups.items():
            if msg_idx >= len(session.messages):
                continue
            msg = session.messages[msg_idx]
            if blk_idx >= len(msg.content_blocks):
                continue
            block = msg.content_blocks[blk_idx]

            # Sort by char_start descending so replacements don't shift positions
            group.sort(key=lambda f: f.char_start, reverse=True)

            text = block.text
            for f in group:
                replacement = redaction_map[f.matched_text]
                text = text[: f.char_start] + replacement + text[f.char_end :]

            block.text = text

            # Update the raw dict as well
            self._update_raw_block(block, redaction_map)
            self._update_raw_message(msg, redaction_map)

    def _update_raw_block(
        self,
        block: "ContentBlock",
        redaction_map: dict[str, str],
    ) -> None:
        """Update the raw dict of a content block with redacted values."""
        if not block.raw:
            return
        raw_str = json.dumps(block.raw, ensure_ascii=False)
        for original, replacement in redaction_map.items():
            raw_str = raw_str.replace(
                _json_escape(original), _json_escape(replacement)
            )
        try:
            block.raw = json.loads(raw_str)
        except json.JSONDecodeError:
            pass  # If JSON reconstruction fails, keep original raw

    def _update_raw_message(
        self,
        message: "TranscriptMessage",
        redaction_map: dict[str, str],
    ) -> None:
        """Update the raw dict of a message with redacted values."""
        if not message.raw:
            return
        raw_str = json.dumps(message.raw, ensure_ascii=False)
        for original, replacement in redaction_map.items():
            raw_str = raw_str.replace(
                _json_escape(original), _json_escape(replacement)
            )
        try:
            message.raw = json.loads(raw_str)
        except json.JSONDecodeError:
            pass


def _finding_priority(f: Finding) -> tuple[int, int]:
    """Return a priority tuple for a finding (higher is better).

    Prefers higher confidence, then longer match.
    """
    confidence_order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
    return (confidence_order.get(f.confidence, 0), f.char_end - f.char_start)


def _is_regex(pattern: str) -> bool:
    """Check if a pattern looks like a regex (contains regex metacharacters)."""
    return any(c in pattern for c in r".*+?[](){}^$|\\")


def _json_escape(s: str) -> str:
    """Escape a string for safe inclusion in a JSON string value.

    Uses json.dumps to get the escaped form, then strips the surrounding quotes.
    """
    return json.dumps(s)[1:-1]
