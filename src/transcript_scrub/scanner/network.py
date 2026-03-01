"""Network detection — IPs, internal hostnames, AWS account IDs, private registries."""

from __future__ import annotations

import re

from transcript_scrub.allowlists import SAFE_IPV6_PREFIX, is_safe_ipv4
from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# IPv4: standard dotted quad
_IPV4 = re.compile(
    r"(?<![.\d])"
    r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    r"(?![.\d])",
)

# IPv6: simplified — at least two groups with colons, hex digits
_IPV6 = re.compile(
    r"(?<![:\w])"
    r"(?:"
    r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"  # full form
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,7}:"  # trailing ::
    r"|"
    r"::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}"  # leading ::
    r"|"
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"  # :: in middle
    r")"
    r"(?![:\w])",
)

# Internal hostnames
_INTERNAL_HOST = re.compile(
    r"\b(?:[a-z0-9-]+\.)*[a-z0-9-]+\.(?:internal|corp|local|private)\b",
    re.IGNORECASE,
)

# AWS Account IDs in ARN contexts
_AWS_ARN = re.compile(
    r"arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:(\d{12}):",
)

# Private Docker registries — AWS ECR
_ECR_REGISTRY = re.compile(
    r"\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com(?:/[^\s\"']+)?",
)

# Private Docker/container registries (generic non-DockerHub)
_PRIVATE_REGISTRY = re.compile(
    r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?/[a-z0-9._/-]+(?::[a-z0-9._-]+)?",
    re.IGNORECASE,
)

# Known public registries that shouldn't be flagged
_PUBLIC_REGISTRIES = {
    "docker.io",
    "registry.hub.docker.com",
    "ghcr.io",
    "gcr.io",
    "quay.io",
    "registry.k8s.io",
    "public.ecr.aws",
    "mcr.microsoft.com",
    "nvcr.io",
}


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


def _is_safe_ipv6(ip: str) -> bool:
    lower = ip.lower()
    if lower == "::1":
        return True
    if lower.startswith(SAFE_IPV6_PREFIX):
        return True
    # fe80::/10 link-local — might be ok but we flag them as they can be identifiable
    return False


class NetworkDetector(BaseDetector):
    """Detects IP addresses, internal hostnames, AWS account IDs, and private registries."""

    @property
    def name(self) -> str:
        return "network"

    @property
    def category(self) -> str:
        return "NETWORK"

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

        # IPv4
        for m in _IPV4.finditer(text):
            ip = m.group(0)
            if is_safe_ipv4(ip):
                continue
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="IPV4",
                    confidence=Confidence.HIGH,
                    matched_text=ip,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-IP",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # IPv6
        for m in _IPV6.finditer(text):
            ip = m.group(0)
            if _is_safe_ipv6(ip):
                continue
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="IPV6",
                    confidence=Confidence.HIGH,
                    matched_text=ip,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-IP",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # Internal hostnames
        for m in _INTERNAL_HOST.finditer(text):
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="INTERNAL-HOST",
                    confidence=Confidence.MEDIUM,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-HOST",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        # AWS Account IDs in ARNs
        for m in _AWS_ARN.finditer(text):
            account_id = m.group(1)
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="AWS-ACCOUNT-ID",
                    confidence=Confidence.MEDIUM,
                    matched_text=account_id,
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(1),
                    char_end=m.end(1),
                    replacement_template="REDACTED-AWS-ACCOUNT",
                    context_snippet=_snippet(text, m.start(1), m.end(1)),
                )
            )

        # AWS ECR registries
        for m in _ECR_REGISTRY.finditer(text):
            findings.append(
                Finding(
                    detector_name=self.name,
                    category="PRIVATE-REGISTRY",
                    confidence=Confidence.MEDIUM,
                    matched_text=m.group(0),
                    message_index=message_index,
                    block_index=block_index,
                    char_start=m.start(),
                    char_end=m.end(),
                    replacement_template="REDACTED-REGISTRY",
                    context_snippet=_snippet(text, m.start(), m.end()),
                )
            )

        return findings
