"""Core data models shared across parser, scanner, and redactor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Confidence(Enum):
    """Confidence level for a detection finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentType(Enum):
    """Type of content block within a transcript message."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    IMAGE = "image"
    SYSTEM = "system"


class MessageRole(Enum):
    """Role of a message in the transcript."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ContentBlock:
    """A single content block within a message.

    Represents one piece of content: text, tool call, tool result, etc.
    The `text` field holds the scannable string content.
    The `raw` field preserves the original parsed dict for reconstruction.
    """

    content_type: ContentType
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    # For tool_use blocks
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    # For tool_result blocks
    tool_use_id: str | None = None


@dataclass
class TranscriptMessage:
    """A single message in a transcript session.

    Contains the role, one or more content blocks, and the original
    raw data for faithful reconstruction after redaction.
    """

    role: MessageRole
    content_blocks: list[ContentBlock] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    # Index of this message in the session (for location tracking)
    index: int = 0


@dataclass
class TranscriptSession:
    """A complete transcript session containing multiple messages.

    This is the normalized representation that parsers produce
    and that the scanner/redactor consume.
    """

    messages: list[TranscriptMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_format: str = ""  # "jsonl" or "json_web"
    source_path: str = ""


@dataclass
class Finding:
    """A single detected sensitive item.

    Produced by scanners, consumed by the redactor.
    """

    detector_name: str
    category: str  # e.g. "API_KEY", "EMAIL", "FILEPATH"
    confidence: Confidence
    matched_text: str
    # Location within the transcript
    message_index: int
    block_index: int
    char_start: int
    char_end: int
    # What to replace it with (before numbering is applied)
    replacement_template: str  # e.g. "REDACTED-API-KEY"
    # Context for review
    context_snippet: str = ""  # surrounding text for review display


@dataclass
class RedactionResult:
    """Result of applying redactions to a transcript."""

    scrubbed_session: TranscriptSession
    findings: list[Finding] = field(default_factory=list)
    # Maps matched_text → stable replacement like "[REDACTED-API-KEY-1]"
    redaction_map: dict[str, str] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)  # category → count
