"""Tests for claude-code-scrubber."""

import json
from pathlib import Path

import pytest

from claude_code_scrubber.patterns import build_patterns
from claude_code_scrubber.scrubber import Scrubber

FIXTURES = Path(__file__).parent / "fixtures"


class TestPatternDetection:
    """Test that individual patterns catch what they should."""

    def setup_method(self):
        self.scrubber = Scrubber(username="yannick")

    def test_anthropic_key(self):
        text = "key: sk-ant-api03-abc123def456ghi789jkl012mno345pqr678stu901vwx234"
        scrubbed, matches = self.scrubber.scrub_text(text)
        assert "sk-ant-api03-abc123" not in scrubbed
        assert "REDACTED" in scrubbed
        assert any(m.pattern_name == "Anthropic API key" for m in matches)

    def test_openai_key(self):
        text = "OPENAI_API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "sk-1234567890" not in scrubbed

    def test_github_token(self):
        text = "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn"
        scrubbed, matches = self.scrubber.scrub_text(text)
        assert "ghp_ABCDEF" not in scrubbed
        assert any("GitHub" in m.pattern_name for m in matches)

    def test_github_fine_grained_pat(self):
        text = "github_pat_11AAAAAA0abcdefghijklm_BbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTt"
        scrubbed, matches = self.scrubber.scrub_text(text)
        assert "github_pat_11AAAAAA" not in scrubbed

    def test_aws_access_key(self):
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed

    def test_aws_secret_key(self):
        text = "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "wJalrXUtnFEMI" not in scrubbed

    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abc123def"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "eyJhbGci" not in scrubbed

    def test_jwt(self):
        text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        scrubbed, matches = self.scrubber.scrub_text(text)
        assert "JWT_REDACTED" in scrubbed

    def test_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Z3\n-----END RSA PRIVATE KEY-----"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "MIIEowIBAAK" not in scrubbed
        assert "PRIVATE KEY REDACTED" in scrubbed

    def test_database_url(self):
        text = "postgres://admin:secret@db.example.com:5432/mydb"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "admin:secret" not in scrubbed
        assert "DB_CONNECTION_REDACTED" in scrubbed

    def test_email(self):
        text = "Contact me at yann.dupont@company.com for details"
        scrubbed, matches = self.scrubber.scrub_text(text)
        assert "yann.dupont@company.com" not in scrubbed
        assert any(m.pattern_name == "Email address" for m in matches)

    def test_private_ip_10(self):
        text = "Server at 10.0.1.55"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "10.0.1.55" not in scrubbed
        assert "10.x.x.x" in scrubbed

    def test_private_ip_192(self):
        text = "Router: 192.168.1.100"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "192.168.1.100" not in scrubbed

    def test_home_path_macos(self):
        text = "File at /Users/yannick/projects/app/main.py"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "/Users/yannick/" not in scrubbed
        assert "/Users/REDACTED_USER/" in scrubbed

    def test_home_path_linux(self):
        text = "Config: /home/yannick/code/config.yml"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "/home/yannick/" not in scrubbed
        assert "/home/REDACTED_USER/" in scrubbed

    def test_encoded_claude_project_path(self):
        text = "-Users-yannick-projects-my-app"
        scrubber = Scrubber(username="yannick")
        scrubbed, _ = scrubber.scrub_text(text)
        assert "-Users-yannick-" not in scrubbed

    def test_shell_prompt(self):
        text = "alice@macbook-pro.local:~$"
        scrubber = Scrubber()
        scrubbed, _ = scrubber.scrub_text(text)
        assert "user@host.local" in scrubbed

    def test_sendgrid_key(self):
        text = "SG.abc123def456ghi789jklm.lmno012pqr345stu678vwx901yz234abc567def890gh"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "SG.abc123" not in scrubbed

    def test_stripe_key(self):
        text = "sk_test_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "sk_test_A1b2C3" not in scrubbed

    def test_hf_token(self):
        text = "hf_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "hf_ABCDEF" not in scrubbed

    def test_generic_secret(self):
        text = "MY_SECRET_TOKEN=super-secret-value-12345"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "super-secret-value" not in scrubbed

    def test_mongodb_connection(self):
        text = "mongodb+srv://admin:password123@cluster0.abc123.mongodb.net/mydb"
        scrubbed, _ = self.scrubber.scrub_text(text)
        assert "admin:password123" not in scrubbed

    def test_no_false_positive_on_short_sk(self):
        """Ensure 'sk-' prefix alone doesn't trigger on short strings."""
        text = "Using sk-2 as the sort key"
        scrubbed, matches = self.scrubber.scrub_text(text)
        # Should NOT be flagged (too short)
        assert scrubbed == text


class TestAllowlist:
    def test_allowlisted_string_not_scrubbed(self):
        scrubber = Scrubber(allowlist={"sk-ant-api03-this-is-a-test-key-for-docs"})
        text = "Use key sk-ant-api03-this-is-a-test-key-for-docs in examples"
        scrubbed, matches = scrubber.scrub_text(text)
        # The allowlisted key should remain
        assert "sk-ant-api03-this-is-a-test-key-for-docs" in scrubbed


class TestSeverityFilter:
    def test_high_only(self):
        scrubber = Scrubber(username="yannick", severity_filter={"high"})
        text = "key=sk-ant-api03-abc123def456ghi789jkl012 email=a@b.com path=/Users/yannick/x"
        scrubbed, matches = scrubber.scrub_text(text)
        # API key should be scrubbed
        assert "sk-ant-api03" not in scrubbed
        # Email and path should remain (medium/low)
        assert "a@b.com" in scrubbed
        assert "/Users/yannick/" in scrubbed

    def test_medium_and_above(self):
        scrubber = Scrubber(username="yannick", severity_filter={"high", "medium"})
        text = "email=a@b.com path=/Users/yannick/x"
        scrubbed, _ = scrubber.scrub_text(text)
        assert "a@b.com" not in scrubbed
        assert "/Users/yannick/" in scrubbed  # low, not included


class TestJSONLScrubbing:
    def test_scrub_sample_jsonl(self):
        path = FIXTURES / "sample_session.jsonl"
        scrubber = Scrubber(username="yannick")
        scrubbed, report = scrubber.scrub_jsonl(path.read_text())

        # Verify secrets are gone
        assert "sk-ant-api03-abc123" not in scrubbed
        assert "sk-1234567890" not in scrubbed
        assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
        assert "ghp_ABCDEF" not in scrubbed
        assert "yann.dupont@company.com" not in scrubbed
        assert "/Users/yannick/" not in scrubbed

        # Verify it's still valid JSONL
        for line in scrubbed.splitlines():
            if line.strip():
                json.loads(line)  # should not raise

        # Verify report has findings
        assert report.total > 0
        assert report.by_severity["high"] > 0


class TestHTMLScrubbing:
    def test_scrub_sample_html(self):
        path = FIXTURES / "sample_transcript.html"
        scrubber = Scrubber(username="yannick")
        scrubbed, report = scrubber.scrub_html(path.read_text())

        assert "sk-ant-api03-abc123" not in scrubbed
        assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
        assert "yann.dupont@company.com" not in scrubbed
        assert "/Users/yannick/" not in scrubbed
        assert "192.168.1.100" not in scrubbed

        # HTML structure should be preserved
        assert "<html>" in scrubbed
        assert "</body>" in scrubbed
        assert '<div class="message user">' in scrubbed

        assert report.total > 0


class TestScrubReport:
    def test_summary_clean(self):
        from claude-code-scrubber.scrubber import ScrubReport
        r = ScrubReport()
        assert "No secrets" in r.summary()

    def test_summary_with_findings(self):
        from claude-code-scrubber.scrubber import ScrubReport, Match
        r = ScrubReport(matches=[
            Match("test", "high", "xxx", "line 1", "***"),
            Match("test2", "medium", "yyy", "line 2", "***"),
        ], files_processed=1)
        summary = r.summary()
        assert "2 item(s)" in summary
        assert "High" in summary
        assert "Medium" in summary
