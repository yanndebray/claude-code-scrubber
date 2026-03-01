"""Crypto material detection — PEM certs/keys, SSH keys, JWTs, git credentials."""

from __future__ import annotations

import re

from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# PEM-encoded certificates and keys (all types)
_PEM_BLOCK = re.compile(
    r"-----BEGIN\s+([A-Z0-9 ]+?)-----"
    r"[\s\S]*?"
    r"-----END\s+\1-----",
)

# SSH public keys
_SSH_PUBKEY = re.compile(
    r"(?:ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-nistp(?:256|384|521))\s+"
    r"[A-Za-z0-9+/=]{40,}",
)

# JWT tokens: three dot-separated base64url segments
_JWT = re.compile(
    r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
)

# Git credential store format: https://user:pass@host
_GIT_CREDENTIAL = re.compile(
    r"https?://[^:]+:[^@]+@[^\s]+",
)


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


class CryptoDetector(BaseDetector):
    """Detects PEM blocks, SSH keys, JWTs, and git credential store entries."""

    @property
    def name(self) -> str:
        return "crypto"

    @property
    def category(self) -> str:
        return "CRYPTO"

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

        # PEM blocks
        for m in _PEM_BLOCK.finditer(text):
            block_type = m.group(1).strip()
            is_private = "PRIVATE" in block_type
            confidence = Confidence.HIGH if is_private else Confidence.MEDIUM
            category = "PRIVATE-KEY" if is_private else "CERTIFICATE"
            span = (m.start(), m.end())
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category=category,
                    confidence=confidence,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template=f"REDACTED-{category}",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # SSH public keys (LOW confidence — these are public)
        for m in _SSH_PUBKEY.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="SSH-PUBKEY",
                    confidence=Confidence.LOW,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-SSH-KEY",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # JWTs
        for m in _JWT.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="JWT",
                    confidence=Confidence.HIGH,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-JWT",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # Git credential store entries
        for m in _GIT_CREDENTIAL.finditer(text):
            span = (m.start(), m.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="GIT-CREDENTIAL",
                    confidence=Confidence.HIGH,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-CREDENTIAL",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        return findings
