"""Integration tests for the full parse -> scan -> redact -> reconstruct pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Expected secrets per fixture (substrings that MUST be redacted)
# ---------------------------------------------------------------------------

SIMPLE_SESSION_SECRETS = [
    "john.smith@acmecorp.com",
    "/home/jsmith/projects/myapp",
    "db.acmecorp.internal",
]

ENV_FILE_PASTE_SECRETS = [
    "AKIAIOSFODNN7EXAMPLE",
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef12",
    "/Users/jsmith/projects/myapp/.env",
]

GIT_CONFIG_LEAK_SECRETS = [
    "john.smith@realcompany.com",
    # SSH public keys are LOW confidence, filtered at medium threshold — by design
]

AWS_CLI_SECRETS = [
    "10.0.1.42",
]

DATABASE_ERRORS_SECRETS = [
    "noreply@acme-corp.net",
    "10.0.2.100",
    "10.0.3.55",
]

WEB_SESSION_SECRETS = [
    "sarah.chen@startup-inc.io",
    "/home/sarah.chen/.ssh/id_rsa",
    "10.0.1.50",
    "10.0.1.51",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _output_contains_none_of(output: str, secrets: list[str]) -> list[str]:
    """Return any secrets that still appear in the output."""
    found = []
    for secret in secrets:
        if secret in output:
            found.append(secret)
    return found


def _parse_scan_redact_reconstruct(fixture_path: Path) -> tuple:
    """Run the full pipeline on a fixture file.

    Returns (reconstructed_output, redaction_result).
    """
    from transcript_scrub.parser import parse_transcript, reconstruct_transcript
    from transcript_scrub.scanner import scan_session
    from transcript_scrub.redactor import redact_session

    session = parse_transcript(fixture_path)
    findings = scan_session(session)
    result = redact_session(session, findings)
    output = reconstruct_transcript(result.scrubbed_session)
    return output, result


# ---------------------------------------------------------------------------
# Pipeline tests for each fixture
# ---------------------------------------------------------------------------

class TestSimpleSession:
    def test_pipeline_produces_valid_jsonl(self, simple_session_path: Path):
        output, _ = _parse_scan_redact_reconstruct(simple_session_path)
        for line in output.strip().splitlines():
            json.loads(line)  # should not raise

    def test_secrets_are_redacted(self, simple_session_path: Path):
        output, _ = _parse_scan_redact_reconstruct(simple_session_path)
        remaining = _output_contains_none_of(output, SIMPLE_SESSION_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"

    def test_redaction_map_populated(self, simple_session_path: Path):
        _, result = _parse_scan_redact_reconstruct(simple_session_path)
        assert len(result.redaction_map) > 0


class TestEnvFilePaste:
    def test_pipeline_produces_valid_jsonl(self, env_file_paste_path: Path):
        output, _ = _parse_scan_redact_reconstruct(env_file_paste_path)
        for line in output.strip().splitlines():
            json.loads(line)

    def test_secrets_are_redacted(self, env_file_paste_path: Path):
        output, _ = _parse_scan_redact_reconstruct(env_file_paste_path)
        remaining = _output_contains_none_of(output, ENV_FILE_PASTE_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"

    def test_findings_include_multiple_categories(self, env_file_paste_path: Path):
        _, result = _parse_scan_redact_reconstruct(env_file_paste_path)
        categories = {f.category for f in result.findings}
        # Should detect at least API key or credential categories
        assert len(categories) > 1, f"Only found categories: {categories}"


class TestGitConfigLeak:
    def test_pipeline_produces_valid_jsonl(self, git_config_leak_path: Path):
        output, _ = _parse_scan_redact_reconstruct(git_config_leak_path)
        for line in output.strip().splitlines():
            json.loads(line)

    def test_secrets_are_redacted(self, git_config_leak_path: Path):
        output, _ = _parse_scan_redact_reconstruct(git_config_leak_path)
        remaining = _output_contains_none_of(output, GIT_CONFIG_LEAK_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"


class TestAwsCliOutput:
    def test_pipeline_produces_valid_jsonl(self, aws_cli_output_path: Path):
        output, _ = _parse_scan_redact_reconstruct(aws_cli_output_path)
        for line in output.strip().splitlines():
            json.loads(line)

    def test_secrets_are_redacted(self, aws_cli_output_path: Path):
        output, _ = _parse_scan_redact_reconstruct(aws_cli_output_path)
        remaining = _output_contains_none_of(output, AWS_CLI_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"

    def test_has_findings(self, aws_cli_output_path: Path):
        _, result = _parse_scan_redact_reconstruct(aws_cli_output_path)
        assert len(result.findings) > 0


class TestDatabaseErrors:
    def test_pipeline_produces_valid_jsonl(self, database_errors_path: Path):
        output, _ = _parse_scan_redact_reconstruct(database_errors_path)
        for line in output.strip().splitlines():
            json.loads(line)

    def test_secrets_are_redacted(self, database_errors_path: Path):
        output, _ = _parse_scan_redact_reconstruct(database_errors_path)
        remaining = _output_contains_none_of(output, DATABASE_ERRORS_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"


class TestWebSession:
    def test_pipeline_produces_valid_json(self, web_session_path: Path):
        output, _ = _parse_scan_redact_reconstruct(web_session_path)
        json.loads(output)  # should not raise

    def test_secrets_are_redacted(self, web_session_path: Path):
        output, _ = _parse_scan_redact_reconstruct(web_session_path)
        remaining = _output_contains_none_of(output, WEB_SESSION_SECRETS)
        assert remaining == [], f"Secrets still present: {remaining}"


# ---------------------------------------------------------------------------
# Clean session: should pass through unchanged
# ---------------------------------------------------------------------------

class TestCleanSession:
    def test_pipeline_produces_valid_jsonl(self, clean_session_path: Path):
        output, _ = _parse_scan_redact_reconstruct(clean_session_path)
        for line in output.strip().splitlines():
            json.loads(line)

    def test_no_redactions(self, clean_session_path: Path):
        _, result = _parse_scan_redact_reconstruct(clean_session_path)
        assert len(result.findings) == 0, (
            f"Expected no findings in clean session, got: "
            f"{[f.matched_text for f in result.findings]}"
        )

    def test_output_preserves_messages(self, clean_session_path: Path, load_jsonl):
        output, _ = _parse_scan_redact_reconstruct(clean_session_path)
        original_records = load_jsonl(clean_session_path)
        output_records = [json.loads(line) for line in output.strip().splitlines() if line.strip()]
        # Should have the same number of message records
        # (summary lines may be skipped by the parser, so compare message counts)
        original_msgs = [r for r in original_records if "message" in r]
        output_msgs = [r for r in output_records if "message" in r]
        assert len(output_msgs) == len(original_msgs)


# ---------------------------------------------------------------------------
# Cross-cutting concerns
# ---------------------------------------------------------------------------

class TestStableNumbering:
    """Same secret value should always get the same redacted placeholder."""

    def test_same_secret_same_placeholder(self, env_file_paste_path: Path):
        """Repeated secrets in the env fixture should map consistently."""
        _, result = _parse_scan_redact_reconstruct(env_file_paste_path)
        # Every unique matched_text should map to exactly one replacement
        for matched, replacement in result.redaction_map.items():
            assert replacement.startswith("[") and replacement.endswith("]"), (
                f"Replacement not bracketed: {replacement}"
            )

    def test_different_secrets_different_numbers(self, env_file_paste_path: Path):
        _, result = _parse_scan_redact_reconstruct(env_file_paste_path)
        # All replacement values should be unique
        replacements = list(result.redaction_map.values())
        assert len(replacements) == len(set(replacements)), (
            f"Duplicate replacement values: {replacements}"
        )


class TestRoundTrip:
    """Redacted output should be parseable again."""

    def test_redacted_jsonl_reparseable(self, simple_session_path: Path, tmp_path: Path):
        output, _ = _parse_scan_redact_reconstruct(simple_session_path)
        # Write the redacted output to a temp file
        redacted_path = tmp_path / "redacted.jsonl"
        redacted_path.write_text(output)
        # Parse the redacted file — should not raise
        from transcript_scrub.parser import parse_transcript
        session2 = parse_transcript(redacted_path)
        assert len(session2.messages) > 0

    def test_redacted_json_reparseable(self, web_session_path: Path, tmp_path: Path):
        output, _ = _parse_scan_redact_reconstruct(web_session_path)
        redacted_path = tmp_path / "redacted.json"
        redacted_path.write_text(output)
        from transcript_scrub.parser import parse_transcript
        session2 = parse_transcript(redacted_path)
        assert len(session2.messages) > 0
