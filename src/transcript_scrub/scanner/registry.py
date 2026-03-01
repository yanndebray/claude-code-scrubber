"""Detector registry — holds all detector instances and provides scan-all."""

from __future__ import annotations

from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector


class DetectorRegistry:
    """Registry that holds detector instances and scans text through all of them."""

    def __init__(self) -> None:
        self._detectors: list[BaseDetector] = []

    def register(self, detector: BaseDetector) -> None:
        """Register a detector instance."""
        self._detectors.append(detector)

    @property
    def detectors(self) -> list[BaseDetector]:
        return list(self._detectors)

    def scan_all(
        self,
        text: str,
        *,
        message_index: int = 0,
        block_index: int = 0,
        content_block: ContentBlock | None = None,
    ) -> list[Finding]:
        """Run all registered detectors against the text."""
        findings: list[Finding] = []
        for detector in self._detectors:
            findings.extend(
                detector.scan(
                    text,
                    message_index=message_index,
                    block_index=block_index,
                    content_block=content_block,
                )
            )
        return findings

    def scan_all_filtered(
        self,
        text: str,
        *,
        min_confidence: Confidence = Confidence.LOW,
        message_index: int = 0,
        block_index: int = 0,
        content_block: ContentBlock | None = None,
    ) -> list[Finding]:
        """Scan and filter results by minimum confidence level."""
        confidence_order = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
        min_level = confidence_order[min_confidence]
        return [
            f
            for f in self.scan_all(
                text,
                message_index=message_index,
                block_index=block_index,
                content_block=content_block,
            )
            if confidence_order[f.confidence] >= min_level
        ]


def build_default_registry() -> DetectorRegistry:
    """Create a registry with all built-in detectors registered."""
    from transcript_scrub.scanner.api_keys import APIKeyDetector
    from transcript_scrub.scanner.credentials import CredentialsDetector
    from transcript_scrub.scanner.crypto import CryptoDetector
    from transcript_scrub.scanner.network import NetworkDetector
    from transcript_scrub.scanner.paths import PathDetector
    from transcript_scrub.scanner.pii import PIIDetector

    registry = DetectorRegistry()
    registry.register(APIKeyDetector())
    registry.register(CredentialsDetector())
    registry.register(PIIDetector())
    registry.register(PathDetector())
    registry.register(NetworkDetector())
    registry.register(CryptoDetector())
    return registry
