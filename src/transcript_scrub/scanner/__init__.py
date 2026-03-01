"""Sensitive information detection engine."""

from __future__ import annotations

from transcript_scrub.models import Finding, TranscriptSession
from transcript_scrub.scanner.registry import DetectorRegistry, build_default_registry


class ScannerRegistry:
    """High-level scanner that wraps DetectorRegistry and scans full sessions."""

    def __init__(self, registry: DetectorRegistry | None = None) -> None:
        self._registry = registry or build_default_registry()

    def scan_session(self, session: TranscriptSession) -> list[Finding]:
        """Scan all content blocks in a transcript session."""
        return scan_session(session, registry=self._registry)


def scan_session(
    session: TranscriptSession,
    registry: DetectorRegistry | None = None,
) -> list[Finding]:
    """Scan all content blocks in a transcript session for sensitive information.

    Args:
        session: The parsed transcript session.
        registry: Optional detector registry. Uses default if not provided.

    Returns:
        List of all findings across the session.
    """
    if registry is None:
        registry = build_default_registry()

    findings: list[Finding] = []
    for message in session.messages:
        for blk_idx, block in enumerate(message.content_blocks):
            if not block.text:
                continue
            block_findings = registry.scan_all(
                block.text,
                message_index=message.index,
                block_index=blk_idx,
                content_block=block,
            )
            findings.extend(block_findings)
    return findings
