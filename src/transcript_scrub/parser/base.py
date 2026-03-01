"""Base parser protocol for transcript formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from transcript_scrub.models import TranscriptSession


class BaseParser(ABC):
    """Abstract base class for transcript parsers.

    Each parser handles a specific transcript format (JSONL, JSON web, etc.)
    and produces a normalized TranscriptSession.
    """

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file."""
        ...

    @abstractmethod
    def parse(self, path: Path) -> TranscriptSession:
        """Parse a transcript file into a normalized session."""
        ...

    @abstractmethod
    def reconstruct(self, session: TranscriptSession) -> str:
        """Reconstruct the transcript back to its original format.

        The output must be valid in the original format so that
        downstream tools (e.g., claude-code-transcripts) can still process it.
        """
        ...
