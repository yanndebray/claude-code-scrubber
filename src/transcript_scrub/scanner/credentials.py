"""Credentials detection — passwords, database URIs, auth headers, env patterns."""

from __future__ import annotations

import re

from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# PEM private keys
_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+|ENCRYPTED\s+)?PRIVATE\s+KEY-----"
    r"[\s\S]*?"
    r"-----END\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+|ENCRYPTED\s+)?PRIVATE\s+KEY-----",
)

# Password / secret assignment patterns
_PASSWORD_ASSIGN = re.compile(
    r"(?:password|passwd|pass|secret|token|api_key|apikey|api-key)"
    r"\s*[=:]\s*"
    r"""[\"']([^\"'\s]{4,})[\"']""",
    re.IGNORECASE,
)
_PASSWORD_ASSIGN_UNQUOTED = re.compile(
    r"(?:password|passwd|pass|secret|token|api_key|apikey|api-key)"
    r"\s*=\s*"
    r"(\S{4,})",
    re.IGNORECASE,
)
# Quoted key-value pairs (e.g. 'PASSWORD': 'value' or "PASSWORD": "value")
_PASSWORD_QUOTED_KEY = re.compile(
    r"""[\"'](?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|APIKEY)[\"']"""
    r"""\s*[:=]\s*"""
    r"""[\"']([^\"'\s]{4,})[\"']""",
    re.IGNORECASE,
)

# Database URIs with embedded credentials
_DB_URI = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)"
    r"://[^@\s]+@[^\s\"']+",
    re.IGNORECASE,
)

# .env-style KEY=value where KEY looks secret
_ENV_SECRET = re.compile(
    r"^([A-Z_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|AUTH|CREDENTIAL|PRIVATE)[A-Z_]*)"
    r"\s*=\s*"
    r"(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Authorization headers
_AUTH_HEADER = re.compile(
    r"(?:Authorization|authorization)\s*:\s*(?:Bearer|Basic|Token)\s+([A-Za-z0-9+/=._-]{8,})",
)

# Cookie session tokens
_COOKIE_SESSION = re.compile(
    r"(?:Cookie|Set-Cookie|cookie|set-cookie)\s*:\s*([^\n]{8,})",
)

# Connection strings with embedded credentials (generic)
_CONN_STRING = re.compile(
    r"(?:Server|Data\s+Source|Host)\s*=\s*[^;]+;\s*.*?"
    r"(?:Password|Pwd)\s*=\s*([^;\"'\s]+)",
    re.IGNORECASE,
)


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


# Well-known placeholder values that should not trigger findings
_SAFE_VALUES = {
    "changeme", "password", "pass", "secret", "test", "1234",
    "xxxx", "none", "null", "undefined", "placeholder",
    "your-api-key-here", "YOUR_API_KEY", "INSERT_KEY_HERE",
}


def _is_placeholder(value: str) -> bool:
    return value.strip("\"'").lower() in _SAFE_VALUES


class CredentialsDetector(BaseDetector):
    """Detects passwords, database URIs, auth headers, and env-style secrets."""

    @property
    def name(self) -> str:
        return "credentials"

    @property
    def category(self) -> str:
        return "CREDENTIAL"

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
        seen_spans: set[tuple[int, int]] = set()

        def _add(start: int, end: int, matched: str, confidence: Confidence, cat: str = "CREDENTIAL") -> None:
            span = (start, end)
            # Skip if overlapping with an existing finding
            for s in seen_spans:
                if s[0] <= start < s[1] or s[0] < end <= s[1]:
                    return
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category=cat,
                    confidence=confidence,
                    matched_text=matched,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=start,
                    char_end=end,
                    replacement_template=f"REDACTED-{cat}",
                    context_snippet=_snippet(text, start, end),
                )
            )

        # PEM private keys
        for m in _PEM_PRIVATE_KEY.finditer(text):
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "PRIVATE-KEY")

        # Database URIs
        for m in _DB_URI.finditer(text):
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "DB-URI")

        # Auth headers
        for m in _AUTH_HEADER.finditer(text):
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "AUTH-HEADER")

        # Connection strings
        for m in _CONN_STRING.finditer(text):
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "CREDENTIAL")

        # Cookie headers
        for m in _COOKIE_SESSION.finditer(text):
            _add(m.start(), m.end(), m.group(0), Confidence.MEDIUM, "COOKIE")

        # Password assignments (quoted)
        for m in _PASSWORD_ASSIGN.finditer(text):
            value = m.group(1)
            if _is_placeholder(value):
                continue
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "CREDENTIAL")

        # Password assignments (unquoted)
        for m in _PASSWORD_ASSIGN_UNQUOTED.finditer(text):
            value = m.group(1)
            if _is_placeholder(value):
                continue
            # Skip if this span is already covered (e.g., by the quoted pattern)
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "CREDENTIAL")

        # Quoted key-value pairs (dict literals, JSON)
        for m in _PASSWORD_QUOTED_KEY.finditer(text):
            value = m.group(1)
            if _is_placeholder(value):
                continue
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "CREDENTIAL")

        # .env-style secret lines
        for m in _ENV_SECRET.finditer(text):
            value = m.group(2).strip()
            if _is_placeholder(value):
                continue
            _add(m.start(), m.end(), m.group(0), Confidence.HIGH, "ENV-SECRET")

        return findings
