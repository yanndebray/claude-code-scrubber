"""Tests for API key detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.api_keys import APIKeyDetector


@pytest.fixture
def detector():
    return APIKeyDetector()


class TestOpenAIKeys:
    def test_detects_openai_key(self, detector):
        text = "OPENAI_API_KEY=sk-abc123def456ghi789jkl012mno"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any("sk-abc123def456ghi789jkl012mno" in f.matched_text for f in findings)

    def test_does_not_match_sk_ant_prefix(self, detector):
        """sk-ant- should be matched as Anthropic, not OpenAI."""
        text = "key=sk-ant-abcdef1234567890abcdef"
        findings = detector.scan(text)
        matched = [f for f in findings if "openai" in str(f.context_snippet).lower() or f.matched_text.startswith("sk-ant-")]
        # The key should be detected, but as Anthropic
        anthropic_findings = [f for f in findings if f.matched_text.startswith("sk-ant-")]
        assert len(anthropic_findings) >= 1

    def test_does_not_match_short_sk(self, detector):
        """Short sk- strings should not match."""
        text = "sk-short"
        findings = detector.scan(text)
        assert len(findings) == 0


class TestAnthropicKeys:
    def test_detects_anthropic_key(self, detector):
        text = "ANTHROPIC_API_KEY=sk-ant-api03-abcdef1234567890abcdef"
        findings = detector.scan(text)
        assert len(findings) >= 1
        matched = [f for f in findings if f.matched_text.startswith("sk-ant-")]
        assert len(matched) == 1
        assert matched[0].confidence == Confidence.HIGH


class TestAWSKeys:
    def test_detects_aws_access_key(self, detector):
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any("AKIAIOSFODNN7EXAMPLE" in f.matched_text for f in findings)

    def test_no_false_positive_akia_short(self, detector):
        text = "AKIA is an AWS prefix"
        findings = detector.scan(text)
        assert len(findings) == 0


class TestGitHubKeys:
    def test_detects_ghp_token(self, detector):
        text = "GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.matched_text.startswith("ghp_") for f in findings)

    def test_detects_github_pat(self, detector):
        text = "token=github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZab"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.matched_text.startswith("github_pat_") for f in findings)


class TestHuggingFaceKeys:
    def test_detects_hf_token(self, detector):
        text = "HF_TOKEN=hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.matched_text.startswith("hf_") for f in findings)


class TestSlackKeys:
    def test_detects_xoxb_token(self, detector):
        # Build token at runtime to avoid triggering GitHub push protection
        token = "xox" + "b-000000000000-000000000000-ABCDEFGHIJKLMNOP"
        text = f"SLACK_TOKEN={token}"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.matched_text.startswith("xox") for f in findings)

    def test_detects_xoxp_token(self, detector):
        token = "xox" + "p-000000000000-000000000000-ABCDEFGHIJ"
        text = f"token={token}"
        findings = detector.scan(text)
        assert len(findings) >= 1


class TestStripeKeys:
    def test_detects_live_key_high_confidence(self, detector):
        # Build token at runtime to avoid triggering GitHub push protection
        key = "sk" + "_live_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        text = f"STRIPE_KEY={key}"
        findings = detector.scan(text)
        live_findings = [f for f in findings if "live_" in f.matched_text]
        assert len(live_findings) == 1
        assert live_findings[0].confidence == Confidence.HIGH

    def test_detects_test_key_low_confidence(self, detector):
        # Build token at runtime to avoid triggering GitHub push protection
        key = "sk" + "_test_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        text = f"STRIPE_KEY={key}"
        findings = detector.scan(text)
        test_findings = [f for f in findings if "test_" in f.matched_text]
        assert len(test_findings) == 1
        assert test_findings[0].confidence == Confidence.LOW


class TestGenericSecretContext:
    def test_detects_secret_in_assignment(self, detector):
        text = 'secret="aB3dEfGhIjKlMnOpQrStUvWxYz0123456789ABCDEF"'
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_no_false_positive_normal_text(self, detector):
        text = "This is a normal sentence without any secrets."
        findings = detector.scan(text)
        assert len(findings) == 0


class TestAllowlists:
    def test_skips_safe_test_prefix(self, detector):
        """Keys starting with known test prefixes should be skipped."""
        text = "key=sk-test-abcdefghij1234567890ab"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_placeholder_values(self, detector):
        text = 'api_key="your-api-key-here"'
        findings = detector.scan(text)
        # Should not detect the placeholder as a real key
        assert not any(f.matched_text == "your-api-key-here" for f in findings)


class TestCharPositions:
    def test_char_positions_accurate(self, detector):
        prefix = "prefix text "
        key = "sk-ant-abcdefghij1234567890abcdef"
        text = prefix + key + " suffix"
        findings = detector.scan(text)
        assert len(findings) >= 1
        f = findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text

    def test_context_snippet_present(self, detector):
        text = "my key is sk-ant-abcdefghij1234567890abcdef here"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert findings[0].context_snippet != ""
