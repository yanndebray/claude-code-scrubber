"""JSONL parser for local Claude Code transcripts.

Claude Code stores transcripts in ~/.claude/projects/ as JSONL files.
Each line is a JSON object representing a message in the conversation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from transcript_scrub.models import (
    ContentBlock,
    ContentType,
    MessageRole,
    TranscriptMessage,
    TranscriptSession,
)
from transcript_scrub.parser.base import BaseParser

logger = logging.getLogger(__name__)

# Mapping from raw role strings to MessageRole enum
_ROLE_MAP = {
    "user": MessageRole.USER,
    "human": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "system": MessageRole.SYSTEM,
}


def _parse_content_block(raw_block: dict[str, Any]) -> ContentBlock:
    """Parse a single content block dict into a ContentBlock."""
    block_type = raw_block.get("type", "text")

    if block_type == "text":
        return ContentBlock(
            content_type=ContentType.TEXT,
            text=raw_block.get("text", ""),
            raw=raw_block,
        )

    if block_type == "tool_use":
        tool_input = raw_block.get("input", {})
        # Serialize the tool input for scanning
        scannable = json.dumps(tool_input, ensure_ascii=False) if tool_input else ""
        return ContentBlock(
            content_type=ContentType.TOOL_USE,
            text=scannable,
            raw=raw_block,
            tool_name=raw_block.get("name"),
            tool_input=tool_input,
        )

    if block_type == "tool_result":
        content = raw_block.get("content", "")
        # tool_result content can be a string, a list of blocks, or other JSON
        if isinstance(content, list):
            # Extract text from nested content blocks
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", json.dumps(item, ensure_ascii=False)))
                else:
                    parts.append(str(item))
            text = "\n".join(parts)
        elif isinstance(content, dict):
            text = json.dumps(content, ensure_ascii=False)
        else:
            text = str(content)
        return ContentBlock(
            content_type=ContentType.TOOL_RESULT,
            text=text,
            raw=raw_block,
            tool_use_id=raw_block.get("tool_use_id"),
        )

    if block_type == "thinking":
        return ContentBlock(
            content_type=ContentType.THINKING,
            text=raw_block.get("thinking", ""),
            raw=raw_block,
        )

    if block_type == "image":
        return ContentBlock(
            content_type=ContentType.IMAGE,
            text="",  # Skip scanning images
            raw=raw_block,
        )

    # Unknown block type — treat as text, preserve raw
    logger.warning("Unknown content block type: %s", block_type)
    return ContentBlock(
        content_type=ContentType.TEXT,
        text=json.dumps(raw_block, ensure_ascii=False),
        raw=raw_block,
    )


def _parse_content(content: Any) -> list[ContentBlock]:
    """Parse the content field of a message, which can be a string or list."""
    if isinstance(content, str):
        return [
            ContentBlock(
                content_type=ContentType.TEXT,
                text=content,
                raw={"type": "text", "text": content},
            )
        ]

    if isinstance(content, list):
        return [_parse_content_block(block) for block in content if isinstance(block, dict)]

    # Fallback: convert to string
    text = str(content)
    return [
        ContentBlock(
            content_type=ContentType.TEXT,
            text=text,
            raw={"type": "text", "text": text},
        )
    ]


class JSONLParser(BaseParser):
    """Parser for JSONL transcript files from local Claude Code sessions."""

    def can_parse(self, path: Path) -> bool:
        """Check if the file looks like a JSONL transcript."""
        if path.suffix.lower() == ".jsonl":
            return True
        # Also try sniffing: read first non-empty line and check structure
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    return isinstance(data, dict) and "message" in data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return False
        return False

    def parse(self, path: Path) -> TranscriptSession:
        """Parse a JSONL transcript file into a TranscriptSession."""
        session = TranscriptSession(
            source_format="jsonl",
            source_path=str(path),
        )

        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed JSON on line %d of %s", line_num, path)
                    continue

                if not isinstance(data, dict):
                    logger.warning("Skipping non-object JSON on line %d of %s", line_num, path)
                    continue

                message = self._parse_line(data, len(session.messages))
                if message is not None:
                    session.messages.append(message)

        return session

    def _parse_line(self, data: dict[str, Any], index: int) -> TranscriptMessage | None:
        """Parse a single JSONL line dict into a TranscriptMessage."""
        msg_data = data.get("message")
        if msg_data is None:
            # Some lines may be metadata or other non-message records
            return None

        if not isinstance(msg_data, dict):
            return None

        # Determine role from either the wrapper type or the message role
        raw_role = msg_data.get("role", data.get("type", "user"))
        role = _ROLE_MAP.get(raw_role, MessageRole.USER)

        content = msg_data.get("content", "")
        blocks = _parse_content(content)

        return TranscriptMessage(
            role=role,
            content_blocks=blocks,
            raw=data,
            index=index,
        )

    def reconstruct(self, session: TranscriptSession) -> str:
        """Reconstruct the session back to JSONL format.

        Uses the raw data stored on each message, with updated content
        blocks reflecting any redactions applied.
        """
        lines = []
        for message in session.messages:
            raw = self._reconstruct_message_raw(message)
            lines.append(json.dumps(raw, ensure_ascii=False))
        return "\n".join(lines) + "\n" if lines else ""

    def _reconstruct_message_raw(self, message: TranscriptMessage) -> dict[str, Any]:
        """Build the raw dict for a message, applying content block updates."""
        import copy

        raw = copy.deepcopy(message.raw)
        msg_data = raw.get("message", {})
        original_content = msg_data.get("content")

        if isinstance(original_content, str):
            # Plain string content — update from first text block
            if message.content_blocks:
                msg_data["content"] = message.content_blocks[0].text
        elif isinstance(original_content, list):
            # Array of content blocks — update each from corresponding block
            for i, block in enumerate(message.content_blocks):
                if i < len(original_content):
                    original_content[i] = self._reconstruct_block_raw(block)
                else:
                    original_content.append(self._reconstruct_block_raw(block))

        raw["message"] = msg_data
        return raw

    def _reconstruct_block_raw(self, block: ContentBlock) -> dict[str, Any]:
        """Build the raw dict for a content block, reflecting redactions."""
        import copy

        raw = copy.deepcopy(block.raw)

        if block.content_type == ContentType.TEXT:
            raw["text"] = block.text
        elif block.content_type == ContentType.THINKING:
            raw["thinking"] = block.text
        elif block.content_type == ContentType.TOOL_USE:
            # The raw dict is already updated by the redaction engine,
            # so we don't overwrite it from block.tool_input (which may
            # still hold the original unredacted value).
            pass
        elif block.content_type == ContentType.TOOL_RESULT:
            # Reconstruct content from the (possibly redacted) text
            original_content = raw.get("content")
            if isinstance(original_content, str):
                raw["content"] = block.text
            elif isinstance(original_content, list):
                # If original was a list, try to preserve structure
                # but fall back to string if structure changed
                raw["content"] = block.text
            else:
                raw["content"] = block.text
        # IMAGE and unknown types: keep raw as-is

        return raw
