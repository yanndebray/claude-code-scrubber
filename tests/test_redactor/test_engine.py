"""Tests for the redaction engine."""

from __future__ import annotations

from transcript_scrub.config import ScrubConfig
from transcript_scrub.models import (
    Confidence,
    ContentBlock,
    ContentType,
    Finding,
    MessageRole,
    TranscriptMessage,
    TranscriptSession,
)
from transcript_scrub.redactor.engine import RedactionEngine


def _make_session(texts: list[str]) -> TranscriptSession:
    """Create a simple session with one message per text string."""
    messages = []
    for i, text in enumerate(texts):
        block = ContentBlock(content_type=ContentType.TEXT, text=text, raw={"text": text})
        msg = TranscriptMessage(
            role=MessageRole.ASSISTANT,
            content_blocks=[block],
            raw={"role": "assistant", "content": [{"type": "text", "text": text}]},
            index=i,
        )
        messages.append(msg)
    return TranscriptSession(messages=messages, source_format="jsonl")


def _make_finding(
    matched_text: str,
    category: str = "API-KEY",
    confidence: Confidence = Confidence.HIGH,
    message_index: int = 0,
    block_index: int = 0,
    char_start: int = 0,
    char_end: int | None = None,
) -> Finding:
    """Create a finding with sensible defaults."""
    if char_end is None:
        char_end = char_start + len(matched_text)
    return Finding(
        detector_name="test",
        category=category,
        confidence=confidence,
        matched_text=matched_text,
        message_index=message_index,
        block_index=block_index,
        char_start=char_start,
        char_end=char_end,
        replacement_template=f"REDACTED-{category}",
    )


class TestStableNumbering:
    """Test that the same matched_text always gets the same replacement."""

    def test_same_text_same_number(self):
        """Same matched text in different locations gets the same replacement."""
        session = _make_session([
            "My key is sk-abc123 and again sk-abc123",
            "Repeated: sk-abc123",
        ])
        findings = [
            _make_finding("sk-abc123", char_start=10, message_index=0),
            _make_finding("sk-abc123", char_start=30, message_index=0),
            _make_finding("sk-abc123", char_start=10, message_index=1),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        # All occurrences should get the same replacement
        assert result.redaction_map["sk-abc123"] == "[REDACTED-API-KEY-1]"
        # Check all messages contain the same replacement
        for msg in result.scrubbed_session.messages:
            assert "sk-abc123" not in msg.content_blocks[0].text
            assert "[REDACTED-API-KEY-1]" in msg.content_blocks[0].text

    def test_different_texts_different_numbers(self):
        """Different matched texts get different numbers."""
        session = _make_session(["Keys: sk-abc123 and sk-xyz789"])
        findings = [
            _make_finding("sk-abc123", char_start=6),
            _make_finding("sk-xyz789", char_start=20),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert result.redaction_map["sk-abc123"] == "[REDACTED-API-KEY-1]"
        assert result.redaction_map["sk-xyz789"] == "[REDACTED-API-KEY-2]"

    def test_different_categories_independent_numbering(self):
        """Different categories have independent numbering."""
        session = _make_session(["Email: test@real.com, Key: sk-abc123"])
        findings = [
            _make_finding("test@real.com", category="EMAIL", char_start=7, char_end=20),
            _make_finding("sk-abc123", category="API-KEY", char_start=27, char_end=36),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert result.redaction_map["test@real.com"] == "[REDACTED-EMAIL-1]"
        assert result.redaction_map["sk-abc123"] == "[REDACTED-API-KEY-1]"


class TestOverlapResolution:
    """Test that overlapping findings are resolved correctly."""

    def test_prefer_higher_confidence(self):
        """When findings overlap, prefer the higher confidence one."""
        session = _make_session(["Sensitive data here"])
        findings = [
            _make_finding(
                "Sensitive data",
                category="PII",
                confidence=Confidence.MEDIUM,
                char_start=0,
                char_end=14,
            ),
            _make_finding(
                "Sensitive data here",
                category="PII",
                confidence=Confidence.HIGH,
                char_start=0,
                char_end=19,
            ),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        # The high confidence one should be kept
        assert len(result.findings) == 1
        assert result.findings[0].confidence == Confidence.HIGH

    def test_prefer_longer_match_at_same_confidence(self):
        """When findings overlap with same confidence, prefer longer match."""
        session = _make_session(["sk-abc123-extended-key"])
        findings = [
            _make_finding("sk-abc123", char_start=0, char_end=9),
            _make_finding("sk-abc123-extended-key", char_start=0, char_end=22),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert len(result.findings) == 1
        assert result.findings[0].matched_text == "sk-abc123-extended-key"

    def test_non_overlapping_kept(self):
        """Non-overlapping findings are all kept."""
        session = _make_session(["key1 and key2"])
        findings = [
            _make_finding("key1", char_start=0, char_end=4),
            _make_finding("key2", char_start=9, char_end=13),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert len(result.findings) == 2


class TestAllowlistDenylist:
    """Test allowlist and denylist filtering."""

    def test_allowlist_literal(self):
        """Literal allowlist entries are excluded."""
        session = _make_session(["Key: sk-safe-key"])
        findings = [
            _make_finding("sk-safe-key", char_start=5),
        ]

        config = ScrubConfig(allowlist=["sk-safe-key"])
        engine = RedactionEngine(config=config)
        result = engine.redact(session, findings)

        assert len(result.findings) == 0

    def test_allowlist_case_insensitive(self):
        """Allowlist matching is case-insensitive for literals."""
        session = _make_session(["Email: Test@Safe.com"])
        findings = [
            _make_finding("Test@Safe.com", category="EMAIL", char_start=7),
        ]

        config = ScrubConfig(allowlist=["test@safe.com"])
        engine = RedactionEngine(config=config)
        result = engine.redact(session, findings)

        assert len(result.findings) == 0

    def test_safe_email_builtin(self):
        """Built-in safe emails are excluded."""
        session = _make_session(["Email: user@example.com"])
        findings = [
            _make_finding("user@example.com", category="EMAIL", char_start=7),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert len(result.findings) == 0

    def test_safe_ip_builtin(self):
        """Built-in safe IPs are excluded."""
        session = _make_session(["IP: 127.0.0.1"])
        findings = [
            _make_finding("127.0.0.1", category="IP-ADDRESS", char_start=4),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert len(result.findings) == 0


class TestConfidenceThreshold:
    """Test confidence threshold filtering."""

    def test_threshold_high_filters_medium_and_low(self):
        """High threshold only keeps high confidence findings."""
        session = _make_session(["data data data"])
        findings = [
            _make_finding("data", confidence=Confidence.HIGH, char_start=0, char_end=4),
            _make_finding("data", confidence=Confidence.MEDIUM, char_start=5, char_end=9),
            _make_finding("data", confidence=Confidence.LOW, char_start=10, char_end=14),
        ]
        # Make them distinct texts so overlap resolution doesn't interfere
        findings[0] = _make_finding("data1", confidence=Confidence.HIGH, char_start=0, char_end=5)
        findings[1] = _make_finding("data2", confidence=Confidence.MEDIUM, char_start=5, char_end=10)
        findings[2] = _make_finding("data3", confidence=Confidence.LOW, char_start=10, char_end=15)

        session = _make_session(["data1data2data3"])
        config = ScrubConfig(confidence_threshold="high")
        engine = RedactionEngine(config=config)
        result = engine.redact(session, findings)

        assert len(result.findings) == 1
        assert result.findings[0].matched_text == "data1"

    def test_threshold_low_keeps_everything(self):
        """Low threshold keeps all findings."""
        session = _make_session(["a b c"])
        findings = [
            _make_finding("a", confidence=Confidence.HIGH, char_start=0, char_end=1),
            _make_finding("b", confidence=Confidence.MEDIUM, char_start=2, char_end=3),
            _make_finding("c", confidence=Confidence.LOW, char_start=4, char_end=5),
        ]

        config = ScrubConfig(confidence_threshold="low")
        engine = RedactionEngine(config=config)
        result = engine.redact(session, findings)

        assert len(result.findings) == 3


class TestRedactionApplication:
    """Test that redactions are correctly applied to text."""

    def test_basic_replacement(self):
        """A simple finding is replaced correctly."""
        session = _make_session(["My API key is sk-secret123 in this text"])
        findings = [
            _make_finding("sk-secret123", char_start=14, char_end=26),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        text = result.scrubbed_session.messages[0].content_blocks[0].text
        assert text == "My API key is [REDACTED-API-KEY-1] in this text"

    def test_multiple_replacements_in_one_block(self):
        """Multiple findings in one block are all replaced."""
        session = _make_session(["key1=sk-aaa key2=sk-bbb"])
        findings = [
            _make_finding("sk-aaa", char_start=5, char_end=11),
            _make_finding("sk-bbb", char_start=17, char_end=23),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        text = result.scrubbed_session.messages[0].content_blocks[0].text
        assert "sk-aaa" not in text
        assert "sk-bbb" not in text
        assert "[REDACTED-API-KEY-1]" in text
        assert "[REDACTED-API-KEY-2]" in text

    def test_raw_dict_updated(self):
        """Raw dict values are also updated with redactions."""
        session = _make_session(["Secret: sk-raw123"])
        findings = [
            _make_finding("sk-raw123", char_start=8, char_end=17),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        raw = result.scrubbed_session.messages[0].content_blocks[0].raw
        assert "sk-raw123" not in str(raw)

    def test_stats_computed(self):
        """Stats dictionary is correctly computed."""
        session = _make_session(["a@b.co sk-123"])
        findings = [
            _make_finding("a@b.co", category="EMAIL", char_start=0, char_end=6),
            _make_finding("sk-123", category="API-KEY", char_start=7, char_end=13),
        ]

        engine = RedactionEngine()
        result = engine.redact(session, findings)

        assert result.stats["EMAIL"] == 1
        assert result.stats["API-KEY"] == 1

    def test_empty_findings(self):
        """No findings produces a clean result."""
        session = _make_session(["Nothing sensitive here."])
        engine = RedactionEngine()
        result = engine.redact(session, [])

        assert len(result.findings) == 0
        assert result.redaction_map == {}
        assert result.stats == {}
        assert (
            result.scrubbed_session.messages[0].content_blocks[0].text
            == "Nothing sensitive here."
        )

    def test_original_session_not_mutated(self):
        """The original session should not be mutated."""
        session = _make_session(["Secret: sk-original"])
        original_text = session.messages[0].content_blocks[0].text
        findings = [
            _make_finding("sk-original", char_start=8, char_end=19),
        ]

        engine = RedactionEngine()
        engine.redact(session, findings)

        # Original should be unchanged
        assert session.messages[0].content_blocks[0].text == original_text
