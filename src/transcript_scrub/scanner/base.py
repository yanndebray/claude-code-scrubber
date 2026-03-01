"""Base detector protocol for sensitive information scanners."""

from __future__ import annotations

from abc import ABC, abstractmethod

from transcript_scrub.models import Confidence, ContentBlock, Finding


class BaseDetector(ABC):
    """Abstract base class for sensitive information detectors.

    Each detector handles one category of sensitive information
    (API keys, emails, filesystem paths, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this detector, e.g. 'api_keys'."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Category label used in redaction placeholders, e.g. 'API-KEY'."""
        ...

    @property
    @abstractmethod
    def confidence(self) -> Confidence:
        """Default confidence level for findings from this detector."""
        ...

    @abstractmethod
    def scan(
        self,
        text: str,
        *,
        message_index: int = 0,
        block_index: int = 0,
        content_block: ContentBlock | None = None,
    ) -> list[Finding]:
        """Scan text for sensitive information.

        Args:
            text: The text to scan.
            message_index: Index of the parent message in the session.
            block_index: Index of the content block within the message.
            content_block: The full content block for context-aware detection.

        Returns:
            List of findings detected in the text.
        """
        ...
