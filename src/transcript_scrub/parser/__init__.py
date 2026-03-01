"""Transcript parsers for different input formats."""

from __future__ import annotations

from pathlib import Path

from transcript_scrub.models import TranscriptSession
from transcript_scrub.parser.base import BaseParser
from transcript_scrub.parser.jsonl import JSONLParser
from transcript_scrub.parser.json_web import JSONWebParser

# Registry of parsers in priority order
_PARSERS = [
    JSONLParser(),
    JSONWebParser(),
]


def detect_and_parse(path: str | Path) -> TranscriptSession:
    """Auto-detect the transcript format and parse the file.

    Tries each registered parser in order. Returns the result of
    the first parser that reports it can handle the file.

    Raises:
        ValueError: If no parser can handle the file.
        FileNotFoundError: If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")

    for parser in _PARSERS:
        if parser.can_parse(path):
            return parser.parse(path)

    raise ValueError(
        f"Unable to detect transcript format for: {path}. "
        f"Supported formats: JSONL (local Claude Code), JSON (web sessions)."
    )


# Convenience aliases used by integration tests and CLI
parse_transcript = detect_and_parse


def get_parser_for_file(path: str | Path) -> BaseParser:
    """Return the parser instance that can handle the given file.

    Raises:
        ValueError: If no parser can handle the file.
        FileNotFoundError: If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")

    for parser in _PARSERS:
        if parser.can_parse(path):
            return parser

    raise ValueError(
        f"Unable to detect transcript format for: {path}. "
        f"Supported formats: JSONL (local Claude Code), JSON (web sessions)."
    )


def reconstruct_transcript(session: TranscriptSession) -> str:
    """Reconstruct a transcript session back to its original format.

    Uses the source_format metadata to determine which parser to use.
    """
    format_to_parser: dict[str, BaseParser] = {
        "jsonl": JSONLParser(),
        "json_web": JSONWebParser(),
    }
    parser = format_to_parser.get(session.source_format)
    if parser is None:
        raise ValueError(f"Unknown source format: {session.source_format!r}")
    return parser.reconstruct(session)
