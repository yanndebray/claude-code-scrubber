"""JSON parser for Claude Code web session exports.

Web session exports are a single JSON file containing the full conversation.
"""

from __future__ import annotations

import copy
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
from transcript_scrub.parser.jsonl import _parse_content

logger = logging.getLogger(__name__)

_ROLE_MAP = {
    "user": MessageRole.USER,
    "human": MessageRole.USER,
    "assistant": MessageRole.ASSISTANT,
    "system": MessageRole.SYSTEM,
}


class JSONWebParser(BaseParser):
    """Parser for JSON web session exports."""

    def can_parse(self, path: Path) -> bool:
        """Check if the file looks like a web session JSON export."""
        if path.suffix.lower() != ".json":
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # Web sessions have a top-level object with a conversation array
            if isinstance(data, dict):
                return "conversation" in data or "messages" in data or "chat_messages" in data
            return False
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return False

    def parse(self, path: Path) -> TranscriptSession:
        """Parse a web session JSON file into a TranscriptSession."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        session = TranscriptSession(
            source_format="json_web",
            source_path=str(path),
            metadata={k: v for k, v in data.items() if k not in ("conversation", "messages", "chat_messages")},
        )
        # Store the full raw structure for reconstruction
        session.metadata["_raw_wrapper"] = data

        # Find the messages array — try common keys
        messages_raw = data.get("conversation") or data.get("messages") or data.get("chat_messages") or []

        for idx, msg_raw in enumerate(messages_raw):
            if not isinstance(msg_raw, dict):
                logger.warning("Skipping non-object message at index %d in %s", idx, path)
                continue
            message = self._parse_message(msg_raw, idx)
            session.messages.append(message)

        return session

    def _parse_message(self, msg_raw: dict[str, Any], index: int) -> TranscriptMessage:
        """Parse a single message dict from the web session."""
        raw_role = msg_raw.get("role", msg_raw.get("sender", "user"))
        role = _ROLE_MAP.get(raw_role, MessageRole.USER)

        content = msg_raw.get("content", "")
        blocks = _parse_content(content)

        return TranscriptMessage(
            role=role,
            content_blocks=blocks,
            raw=msg_raw,
            index=index,
        )

    def reconstruct(self, session: TranscriptSession) -> str:
        """Reconstruct the session back to its original JSON format."""
        raw_wrapper = session.metadata.get("_raw_wrapper")
        if raw_wrapper is None:
            # Fallback: build a minimal structure
            raw_wrapper = {"conversation": []}

        output = copy.deepcopy(raw_wrapper)

        # Find which key holds the messages array
        messages_key = "conversation"
        for key in ("conversation", "messages", "chat_messages"):
            if key in output:
                messages_key = key
                break

        # Rebuild the messages array from session messages
        reconstructed = []
        for message in session.messages:
            reconstructed.append(self._reconstruct_message_raw(message))
        output[messages_key] = reconstructed

        return json.dumps(output, indent=2, ensure_ascii=False) + "\n"

    def _reconstruct_message_raw(self, message: TranscriptMessage) -> dict[str, Any]:
        """Build the raw dict for a message, applying content block updates."""
        raw = copy.deepcopy(message.raw)
        original_content = raw.get("content")

        if isinstance(original_content, str):
            if message.content_blocks:
                raw["content"] = message.content_blocks[0].text
        elif isinstance(original_content, list):
            updated = []
            for i, block in enumerate(message.content_blocks):
                updated.append(self._reconstruct_block_raw(block))
            raw["content"] = updated

        return raw

    def _reconstruct_block_raw(self, block: ContentBlock) -> dict[str, Any]:
        """Build the raw dict for a content block, reflecting redactions."""
        raw = copy.deepcopy(block.raw)

        if block.content_type == ContentType.TEXT:
            raw["text"] = block.text
        elif block.content_type == ContentType.THINKING:
            raw["thinking"] = block.text
        elif block.content_type == ContentType.TOOL_USE:
            # The raw dict is already updated by the redaction engine,
            # so we don't overwrite it from block.tool_input.
            pass
        elif block.content_type == ContentType.TOOL_RESULT:
            original_content = raw.get("content")
            if isinstance(original_content, str):
                raw["content"] = block.text
            else:
                raw["content"] = block.text

        return raw
