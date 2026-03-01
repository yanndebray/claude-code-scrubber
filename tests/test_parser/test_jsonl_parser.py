"""Tests for the JSONL transcript parser."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from transcript_scrub.models import ContentType, MessageRole
from transcript_scrub.parser.jsonl import JSONLParser

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def parser():
    return JSONLParser()


# ---------------------------------------------------------------------------
# can_parse
# ---------------------------------------------------------------------------

class TestCanParse:
    def test_accepts_jsonl_extension(self, parser: JSONLParser):
        assert parser.can_parse(FIXTURES / "simple_session.jsonl") is True

    def test_rejects_json_extension(self, parser: JSONLParser):
        assert parser.can_parse(FIXTURES / "web_session.json") is False

    def test_rejects_nonexistent_file(self, parser: JSONLParser):
        assert parser.can_parse(Path("/nonexistent/file.txt")) is False


# ---------------------------------------------------------------------------
# parse — simple session
# ---------------------------------------------------------------------------

class TestParseSimpleSession:
    def test_message_count(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        # simple_session.jsonl has 4 messages (2 user, 2 assistant)
        assert len(session.messages) == 4

    def test_source_format(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        assert session.source_format == "jsonl"

    def test_first_message_is_user(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        assert session.messages[0].role == MessageRole.USER

    def test_first_message_plain_string_content(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        msg = session.messages[0]
        assert len(msg.content_blocks) == 1
        assert msg.content_blocks[0].content_type == ContentType.TEXT
        assert "project" in msg.content_blocks[0].text.lower()

    def test_assistant_with_text_block(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        msg = session.messages[1]
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.content_blocks) >= 1
        types = [b.content_type for b in msg.content_blocks]
        assert ContentType.TEXT in types

    def test_message_indices_are_sequential(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        for i, msg in enumerate(session.messages):
            assert msg.index == i

    def test_raw_preserved_on_messages(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        for msg in session.messages:
            assert isinstance(msg.raw, dict)
            assert "message" in msg.raw

    def test_raw_preserved_on_blocks(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        for msg in session.messages:
            for block in msg.content_blocks:
                assert isinstance(block.raw, dict)

    def test_user_content_with_array_blocks(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        # Message index 2 has content as an array with a text block
        msg = session.messages[2]
        assert msg.role == MessageRole.USER
        assert len(msg.content_blocks) >= 1


# ---------------------------------------------------------------------------
# parse — content block types (using env_file_paste which has all types)
# ---------------------------------------------------------------------------

class TestContentBlockTypes:
    def test_thinking_block_in_env_file(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        # Message index 3 (assistant response) has thinking + text blocks
        msg = session.messages[3]
        thinking_blocks = [
            b for b in msg.content_blocks
            if b.content_type == ContentType.THINKING
        ]
        assert len(thinking_blocks) == 1
        assert "sensitive" in thinking_blocks[0].text.lower() or "secret" in thinking_blocks[0].text.lower()

    def test_tool_result_block_in_env_file(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        # Message index 2 has the .env tool_result
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert len(tr_blocks) == 1
        assert tr_blocks[0].tool_use_id == "toolu_01READ01"

    def test_tool_use_block_in_env_file(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        # Message index 1 is the Read tool_use
        msg = session.messages[1]
        tu_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_USE]
        assert len(tu_blocks) == 1
        assert tu_blocks[0].tool_name == "Read"


# ---------------------------------------------------------------------------
# parse — env file paste (secrets fixture)
# ---------------------------------------------------------------------------

class TestParseEnvFilePaste:
    def test_contains_tool_result_with_secrets(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        # Message index 2 has the .env content as a tool_result
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert len(tr_blocks) == 1
        text = tr_blocks[0].text
        assert "AKIAIOSFODNN7EXAMPLE" in text
        assert "PLACEHOLDER_STRIPE_LIVE_KEY_0123456789abcdef" in text
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ" in text

    def test_tool_use_with_file_path(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        msg = session.messages[1]
        tu_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_USE]
        assert len(tu_blocks) == 1
        assert tu_blocks[0].tool_name == "Read"
        assert "/Users/jsmith" in tu_blocks[0].text


# ---------------------------------------------------------------------------
# parse — git config leak
# ---------------------------------------------------------------------------

class TestParseGitConfigLeak:
    def test_email_in_tool_result(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "git_config_leak.jsonl")
        # The git config output is in message index 2
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("john.smith@realcompany.com" in b.text for b in tr_blocks)

    def test_ssh_key_in_tool_result(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "git_config_leak.jsonl")
        # SSH key output is in message index 6 (7th line: tool_result with ls + cat output)
        msg = session.messages[6]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("ssh-ed25519" in b.text for b in tr_blocks)


# ---------------------------------------------------------------------------
# parse — AWS CLI output
# ---------------------------------------------------------------------------

class TestParseAwsCliOutput:
    def test_aws_account_id_in_output(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "aws_cli_output.jsonl")
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("123456789012" in b.text for b in tr_blocks)

    def test_jwt_token_in_error_logs(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "aws_cli_output.jsonl")
        msg = session.messages[7]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("eyJhbGciOiJIUzI1NiJ9" in b.text for b in tr_blocks)

    def test_security_group_in_output(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "aws_cli_output.jsonl")
        all_text = " ".join(
            b.text for m in session.messages for b in m.content_blocks
        )
        assert "sg-0abc123def456789a" in all_text


# ---------------------------------------------------------------------------
# parse — database errors
# ---------------------------------------------------------------------------

class TestParseDatabaseErrors:
    def test_db_password_in_settings(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "database_errors.jsonl")
        msg = session.messages[2]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("W3bApp_Pr0d!2024" in b.text for b in tr_blocks)

    def test_connection_string_in_error(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "database_errors.jsonl")
        msg = session.messages[5]
        tr_blocks = [b for b in msg.content_blocks if b.content_type == ContentType.TOOL_RESULT]
        assert any("postgresql://webapp_admin:" in b.text for b in tr_blocks)


# ---------------------------------------------------------------------------
# parse — clean session (no secrets)
# ---------------------------------------------------------------------------

class TestParseCleanSession:
    def test_no_secrets_in_clean_session(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "clean_session.jsonl")
        all_text = " ".join(
            b.text for m in session.messages for b in m.content_blocks
        )
        # Should not contain any of the typical secret patterns
        assert "AKIA" not in all_text
        assert "sk_live" not in all_text
        assert "ghp_" not in all_text
        assert "password" not in all_text.lower()

    def test_message_count(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "clean_session.jsonl")
        assert len(session.messages) == 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_file(self, parser: JSONLParser, tmp_path: Path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        session = parser.parse(empty)
        assert len(session.messages) == 0

    def test_malformed_lines_skipped(self, parser: JSONLParser, tmp_path: Path):
        content = (
            '{"type":"human","message":{"role":"user","content":"hello"}}\n'
            "this is not json\n"
            '{"type":"assistant","message":{"role":"assistant","content":"hi"}}\n'
        )
        f = tmp_path / "malformed.jsonl"
        f.write_text(content)
        session = parser.parse(f)
        assert len(session.messages) == 2

    def test_non_object_lines_skipped(self, parser: JSONLParser, tmp_path: Path):
        content = (
            '["this", "is", "an", "array"]\n'
            '{"type":"human","message":{"role":"user","content":"hello"}}\n'
        )
        f = tmp_path / "array_line.jsonl"
        f.write_text(content)
        session = parser.parse(f)
        assert len(session.messages) == 1

    def test_message_without_message_key_skipped(self, parser: JSONLParser, tmp_path: Path):
        content = (
            '{"type":"metadata","version":"1.0"}\n'
            '{"type":"human","message":{"role":"user","content":"hello"}}\n'
        )
        f = tmp_path / "metadata_line.jsonl"
        f.write_text(content)
        session = parser.parse(f)
        assert len(session.messages) == 1

    def test_blank_lines_skipped(self, parser: JSONLParser, tmp_path: Path):
        content = (
            '{"type":"human","message":{"role":"user","content":"hello"}}\n'
            "\n"
            "\n"
            '{"type":"assistant","message":{"role":"assistant","content":"hi"}}\n'
        )
        f = tmp_path / "blanks.jsonl"
        f.write_text(content)
        session = parser.parse(f)
        assert len(session.messages) == 2

    def test_image_block_has_empty_text(self, parser: JSONLParser, tmp_path: Path):
        line = json.dumps({
            "type": "human",
            "message": {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBOR..."}},
                    {"type": "text", "text": "What is in this image?"},
                ],
            },
        })
        f = tmp_path / "image.jsonl"
        f.write_text(line + "\n")
        session = parser.parse(f)
        assert len(session.messages) == 1
        blocks = session.messages[0].content_blocks
        assert blocks[0].content_type == ContentType.IMAGE
        assert blocks[0].text == ""
        assert blocks[1].content_type == ContentType.TEXT
        assert "image" in blocks[1].text

    def test_tool_result_with_list_content(self, parser: JSONLParser, tmp_path: Path):
        line = json.dumps({
            "type": "human",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_test",
                        "content": [
                            {"type": "text", "text": "Part one"},
                            {"type": "text", "text": "Part two"},
                        ],
                    },
                ],
            },
        })
        f = tmp_path / "list_content.jsonl"
        f.write_text(line + "\n")
        session = parser.parse(f)
        block = session.messages[0].content_blocks[0]
        assert block.content_type == ContentType.TOOL_RESULT
        assert "Part one" in block.text
        assert "Part two" in block.text


# ---------------------------------------------------------------------------
# Round-trip (parse → reconstruct → parse)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_simple_session_round_trip(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        reconstructed = parser.reconstruct(session)
        # Parse the reconstructed output
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
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

    def test_env_file_round_trip(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "env_file_paste.jsonl")
        reconstructed = parser.reconstruct(session)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(reconstructed)
            f.flush()
            session2 = parser.parse(Path(f.name))
        assert len(session2.messages) == len(session.messages)

    def test_reconstructed_is_valid_jsonl(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "simple_session.jsonl")
        reconstructed = parser.reconstruct(session)
        for line in reconstructed.strip().split("\n"):
            data = json.loads(line)
            assert isinstance(data, dict)
            assert "message" in data

    def test_clean_session_round_trip(self, parser: JSONLParser):
        session = parser.parse(FIXTURES / "clean_session.jsonl")
        reconstructed = parser.reconstruct(session)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(reconstructed)
            f.flush()
            session2 = parser.parse(Path(f.name))
        assert len(session2.messages) == len(session.messages)
        for m1, m2 in zip(session.messages, session2.messages):
            assert m1.role == m2.role
            for b1, b2 in zip(m1.content_blocks, m2.content_blocks):
                assert b1.text == b2.text
