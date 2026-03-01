"""Redaction engine and output formatting."""

from transcript_scrub.models import Finding, RedactionResult, TranscriptSession
from transcript_scrub.redactor.engine import RedactionEngine

__all__ = ["RedactionEngine", "redact_session"]


def redact_session(
    session: TranscriptSession,
    findings: list[Finding],
) -> RedactionResult:
    """Convenience function to redact a session with default config."""
    engine = RedactionEngine()
    return engine.redact(session, findings)
