"""PII detection — emails, phone numbers, physical addresses, names in PII contexts."""

from __future__ import annotations

import re

from transcript_scrub.allowlists import is_safe_email
from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# Email pattern (standard RFC 5322 simplified)
_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)

# US phone formats
_PHONE_US = re.compile(
    r"(?<!\d)"  # not preceded by digit
    r"(?:"
    r"\+?1[-.\s]?"  # optional country code
    r")?"
    r"(?:"
    r"\(\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}"  # (xxx) xxx-xxxx
    r"|"
    r"\d{3}[-.\s]\d{3}[-.\s]\d{4}"  # xxx-xxx-xxxx
    r")"
    r"(?!\d)",  # not followed by digit
)

# International phone (+ followed by 7-15 digits with optional separators)
_PHONE_INTL = re.compile(
    r"(?<!\d)\+[1-9]\d[\d\s.-]{5,14}\d(?!\d)",
)

# Physical address heuristic: number + street name + suffix
_STREET_SUFFIXES = (
    r"(?:Avenue|Ave|Boulevard|Blvd|Circle|Cir|Court|Ct|Drive|Dr|"
    r"Highway|Hwy|Lane|Ln|Parkway|Pkwy|Place|Pl|Road|Rd|Street|St|"
    r"Terrace|Ter|Trail|Trl|Way)"
)
_ADDRESS = re.compile(
    r"\d{1,6}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?\s+" + _STREET_SUFFIXES + r"\.?",
)

# Names in PII contexts
_NAME_CONTEXT = re.compile(
    r"(?:user\.?name|author|Author|committer|Committer|name)\s*[:=]\s*"
    r"""[\"']([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)[\"']""",
)
# Git-style author line
_GIT_AUTHOR = re.compile(
    r"(?:Author|Committer):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+<",
)


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


class PIIDetector(BaseDetector):
    """Detects personally identifiable information."""

    @property
    def name(self) -> str:
        return "pii"

    @property
    def category(self) -> str:
        return "PII"

    @property
    def confidence(self) -> Confidence:
        return Confidence.HIGH

    def scan(
        self,
        text: str,
        *,
        message_index: int = 0,
        block_index: int = 0,
        content_block: ContentBlock | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []

        # Emails
        for m in _EMAIL.finditer(text):
            email = m.group(0)
            if is_safe_email(email):
                continue
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="EMAIL",
                    confidence=Confidence.HIGH,
                    matched_text=email,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-EMAIL",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # Phone numbers (US)
        for m in _PHONE_US.finditer(text):
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="PHONE",
                    confidence=Confidence.MEDIUM,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-PHONE",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # International phone numbers
        for m in _PHONE_INTL.finditer(text):
            # Skip if already matched by US pattern
            if any(f.char_start == m.start() and f.char_end == m.end() for f in findings):
                continue
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="PHONE",
                    confidence=Confidence.MEDIUM,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-PHONE",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # Physical addresses
        for m in _ADDRESS.finditer(text):
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="ADDRESS",
                    confidence=Confidence.MEDIUM,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-ADDRESS",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # Names in PII contexts
        for m in _NAME_CONTEXT.finditer(text):
            name_val = m.group(1)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="NAME",
                    confidence=Confidence.MEDIUM,
                    matched_text=name_val,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(1),
                    char_end=m.end(1),
                    replacement_template="REDACTED-NAME",
                    context_snippet=_snippet(text, m.start(1), m.end(1)),
                )
            )

        # Git author lines
        for m in _GIT_AUTHOR.finditer(text):
            name_val = m.group(1)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="NAME",
                    confidence=Confidence.MEDIUM,
                    matched_text=name_val,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(1),
                    char_end=m.end(1),
                    replacement_template="REDACTED-NAME",
                    context_snippet=_snippet(text, m.start(1), m.end(1)),
                )
            )

        return findings
