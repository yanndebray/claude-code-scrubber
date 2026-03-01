"""Tests for the JSON web session parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from transcript_scrub.models import ContentType, MessageRole
from transcript_scrub.parser.json_web import JSONWebParser

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def parser():
    return JSONWebParser()


# ---------------------------------------------------------------------------
# can_parse
# ---------------------------------------------------------------------------

class TestCanParse:
    def test_accepts_web_session_json(self, parser: JSONWebParser):
        assert parser.can_parse(FIXTURES / "web_session.json") is True

    def test_rejects_jsonl(self, parser: JSONWebParser):
        assert parser.can_parse(FIXTURES / "simple_session.jsonl") is False

    def test_rejects_nonexistent_file(self, parser: JSONWebParser):
        assert parser.can_parse(Path("/nonexistent/file.json")) is False

    def test_rejects_json_without_conversation(self, parser: JSONWebParser, tmp_path: Path):
        f = tmp_path / "other.json"
        f.write_text('{"data": [1, 2, 3]}')
        assert parser.can_parse(f) is False


# ---------------------------------------------------------------------------
# parse — web session
# ---------------------------------------------------------------------------

class TestParseWebSession:
    def test_message_count(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        assert len(session.messages) == 4

    def test_source_format(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        assert session.source_format == "json_web"

    def test_metadata_preserved(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        assert session.metadata.get("uuid") == "session-abc123-def456-789"
        assert session.metadata.get("name") == "Debugging API integration"

    def test_first_message_is_user(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        assert session.messages[0].role == MessageRole.USER

    def test_plain_string_content(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[0]
        assert len(msg.content_blocks) == 1
        assert msg.content_blocks[0].content_type == ContentType.TEXT
        assert "API" in msg.content_blocks[0].text

    def test_assistant_with_thinking_and_text(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[1]
        assert msg.role == MessageRole.ASSISTANT
        types = [b.content_type for b in msg.content_blocks]
        assert ContentType.THINKING in types
        assert ContentType.TEXT in types

    def test_user_with_text_and_tool_result(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[2]
        assert msg.role == MessageRole.USER
        types = [b.content_type for b in msg.content_blocks]
        assert ContentType.TEXT in types
        assert ContentType.TOOL_RESULT in types

    def test_tool_result_content(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert len(tr_blocks) == 1
        assert "403 Forbidden" in tr_blocks[0].text
        assert "sk-mc-prod" in tr_blocks[0].text

    def test_secrets_in_user_message(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[0]
        text = msg.content_blocks[0].text
        assert "sk-mc-prod-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" in text
        assert "cs_live_Xk9mP2nQ4rS6tU8vW0xY1zA3bC5dE7fG" in text

    def test_ip_address_in_error(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        msg = session.messages[3]
        assert "203.45.67.89" in msg.content_blocks[0].text

    def test_message_indices(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        for i, msg in enumerate(session.messages):
            assert msg.index == i

    def test_raw_preserved_on_messages(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        for msg in session.messages:
            assert isinstance(msg.raw, dict)
            assert "role" in msg.raw


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_conversation(self, parser: JSONWebParser, tmp_path: Path):
        f = tmp_path / "empty.json"
        f.write_text('{"conversation": []}')
        session = parser.parse(f)
        assert len(session.messages) == 0

    def test_messages_key_variant(self, parser: JSONWebParser, tmp_path: Path):
        data = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        }
        f = tmp_path / "messages_key.json"
        f.write_text(json.dumps(data))
        assert parser.can_parse(f) is True
        session = parser.parse(f)
        assert len(session.messages) == 2

    def test_chat_messages_key_variant(self, parser: JSONWebParser, tmp_path: Path):
        data = {
            "chat_messages": [
                {"role": "user", "content": "Hello"},
            ]
        }
        f = tmp_path / "chat_messages.json"
        f.write_text(json.dumps(data))
        assert parser.can_parse(f) is True
        session = parser.parse(f)
        assert len(session.messages) == 1


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_web_session_round_trip(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        reconstructed = parser.reconstruct(session)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(reconstructed)
            f.flush()
            session2 = parser.parse(Path(f.name))

        assert len(session2.messages) == len(session.messages)
        for m1, m2 in zip(session.messages, session2.messages):
            assert m1.role == m2.role
            assert len(m1.content_blocks) == len(m2.content_blocks)
            for b1, b2 in zip(m1.content_blocks, m2.content_blocks):
                assert b1.content_type == b2.content_type
                assert b1.text == b2.text

    def test_reconstructed_is_valid_json(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        reconstructed = parser.reconstruct(session)
        data = json.loads(reconstructed)
        assert isinstance(data, dict)
        assert "conversation" in data

    def test_metadata_preserved_in_reconstruction(self, parser: JSONWebParser):
        session = parser.parse(FIXTURES / "web_session.json")
        reconstructed = parser.reconstruct(session)
        data = json.loads(reconstructed)
        assert data["uuid"] == "session-abc123-def456-789"
        assert data["name"] == "Debugging API integration"


# ---------------------------------------------------------------------------
# detect_and_parse integration
# ---------------------------------------------------------------------------

class TestDetectAndParse:
    def test_detect_jsonl(self):
        from transcript_scrub.parser import detect_and_parse
        session = detect_and_parse(FIXTURES / "simple_session.jsonl")
        assert session.source_format == "jsonl"
        assert len(session.messages) > 0

    def test_detect_json_web(self):
        from transcript_scrub.parser import detect_and_parse
        session = detect_and_parse(FIXTURES / "web_session.json")
        assert session.source_format == "json_web"
        assert len(session.messages) > 0

    def test_detect_nonexistent_raises(self):
        from transcript_scrub.parser import detect_and_parse
        with pytest.raises(FileNotFoundError):
            detect_and_parse("/nonexistent/path.jsonl")

    def test_detect_unsupported_raises(self, tmp_path: Path):
        from transcript_scrub.parser import detect_and_parse
        f = tmp_path / "unknown.txt"
        f.write_text("just some text")
        with pytest.raises(ValueError, match="Unable to detect"):
            detect_and_parse(f)
