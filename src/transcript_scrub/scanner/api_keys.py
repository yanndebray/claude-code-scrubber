"""API key detection — OpenAI, Anthropic, AWS, GitHub, HuggingFace, Slack, Stripe, generic."""

from __future__ import annotations

import re

from transcript_scrub.allowlists import SAFE_API_KEY_PATTERNS, SAFE_PLACEHOLDER_VALUES
from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# Specific provider patterns: (name, pattern, confidence, skip_allowlist)
# skip_allowlist=True for Stripe test keys since they match SAFE_API_KEY_PATTERNS
# but we still want to flag them at LOW confidence.
_PATTERNS: list[tuple[str, re.Pattern[str], Confidence, bool]] = [
    # Anthropic must come before OpenAI since sk-ant- starts with sk-
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), Confidence.HIGH, False),
    # OpenAI: sk- followed by 20-100 alphanumeric/dash, but NOT sk-ant- and NOT sk_test_ / sk-test-
    ("openai", re.compile(r"sk-(?!ant-|test[-_])[A-Za-z0-9_-]{20,100}"), Confidence.HIGH, False),
    # AWS Access Key IDs
    ("aws", re.compile(r"AKIA[0-9A-Z]{16}"), Confidence.HIGH, False),
    # GitHub tokens
    ("github", re.compile(r"(?:ghp_|gho_|ghs_|ghr_)[A-Za-z0-9_]{36,}"), Confidence.HIGH, False),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), Confidence.HIGH, False),
    # Hugging Face
    ("huggingface", re.compile(r"hf_[A-Za-z0-9]{20,}"), Confidence.HIGH, False),
    # Slack
    ("slack", re.compile(r"xox[bpsa]-[A-Za-z0-9-]{20,}"), Confidence.HIGH, False),
    # Stripe live keys
    ("stripe_live", re.compile(r"[sr]k_live_[A-Za-z0-9]{20,}"), Confidence.HIGH, False),
    ("stripe_pub_live", re.compile(r"pk_live_[A-Za-z0-9]{20,}"), Confidence.HIGH, False),
    # Stripe test keys (LOW confidence — intentionally test data, skip allowlist)
    ("stripe_test", re.compile(r"[sr]k_test_[A-Za-z0-9]{20,}"), Confidence.LOW, True),
    ("stripe_pub_test", re.compile(r"pk_test_[A-Za-z0-9]{20,}"), Confidence.LOW, True),
]

# Generic high-entropy patterns in secret-like contexts
_GENERIC_HEX = re.compile(r"(?<=[=:\"'\s])[0-9a-f]{40,}(?=[\"'\s,;}\]\)]|$)", re.MULTILINE)
_GENERIC_SECRET_CONTEXT = re.compile(
    r"(?:secret|token|api[_-]?key|auth|credential|password)[\s]*[=:]\s*[\"']?([A-Za-z0-9+/=_-]{40,})[\"']?",
    re.IGNORECASE,
)


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


def _is_safe_key(value: str) -> bool:
    lower = value.lower()
    if lower in SAFE_PLACEHOLDER_VALUES:
        return True
    for prefix in SAFE_API_KEY_PATTERNS:
        if lower.startswith(prefix):
            return True
    return False


class APIKeyDetector(BaseDetector):
    """Detects API keys from various providers."""

    @property
    def name(self) -> str:
        return "api_keys"

    @property
    def category(self) -> str:
        return "API-KEY"

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

        # Provider-specific patterns
        for provider, pattern, confidence, skip_allowlist in _PATTERNS:
            for m in pattern.finditer(text):
                span = (m.start(), m.end())
                if span in seen_spans:
                    continue
                matched = m.group(0)
                if not skip_allowlist and _is_safe_key(matched):
                    continue
                seen_spans.add(span)
                findings.append(
                    Finding(
                        detector_name=self.name,
                        category=self.category,
                        confidence=confidence,
                        matched_text=matched,
                        message_index=message_index,
                        block_index=block_index,
                        char_start=m.start(),
                        char_end=m.end(),
                        replacement_template="REDACTED-API-KEY",
                        context_snippet=_snippet(text, m.start(), m.end()),
                    )
                )

        # Generic secret-context pattern
        for m in _GENERIC_SECRET_CONTEXT.finditer(text):
            val_start = m.start(1)
            val_end = m.end(1)
            span = (val_start, val_end)
            # Skip if already covered by a specific pattern
            if any(s[0] <= val_start and val_end <= s[1] for s in seen_spans):
                continue
            matched = m.group(1)
            if _is_safe_key(matched):
                continue
            seen_spans.add(span)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category=self.category,
                    confidence=Confidence.MEDIUM,
                    matched_text=matched,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=val_start,
                    char_end=val_end,
                    replacement_template="REDACTED-API-KEY",
                    context_snippet=_snippet(text, val_start, val_end),
                )
            )

        return findings
