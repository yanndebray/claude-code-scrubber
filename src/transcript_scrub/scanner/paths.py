"""Filesystem path detection — redact usernames from home directory paths."""

from __future__ import annotations

import re

from transcript_scrub.allowlists import SAFE_PATHS
from transcript_scrub.models import Confidence, ContentBlock, Finding
from transcript_scrub.scanner.base import BaseDetector

# macOS: /Users/<username>/...
_MACOS_PATH = re.compile(
    r"/Users/([A-Za-z0-9._-]+)(/[^\s\"'`\x00-\x1f]*)?",
)

# Linux: /home/<username>/...
_LINUX_PATH = re.compile(
    r"/home/([A-Za-z0-9._-]+)(/[^\s\"'`\x00-\x1f]*)?",
)

# Windows: C:\Users\<username>\...  (also handles forward slashes)
_WINDOWS_PATH = re.compile(
    r"[A-Z]:\\Users\\([A-Za-z0-9._-]+)(\\[^\s\"'`\x00-\x1f]*)?",
)


def _snippet(text: str, start: int, end: int, margin: int = 30) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    return text[s:e]


class PathDetector(BaseDetector):
    """Detects filesystem paths that contain usernames."""

    @property
    def name(self) -> str:
        return "paths"

    @property
    def category(self) -> str:
        return "FILEPATH"

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

        # macOS paths
        for m in _MACOS_PATH.finditer(text):
            full_path = m.group(0)
            if self._is_safe(full_path):
                continue
            username = m.group(1)
            if not username or username.lower() in ("shared",):
                continue
            findings.append(self._make_finding(
                text, m.start(), m.end(), full_path, username,
                message_index, block_index,
            ))

        # Linux paths
        for m in _LINUX_PATH.finditer(text):
            full_path = m.group(0)
            if self._is_safe(full_path):
                continue
            username = m.group(1)
            if not username:
                continue
            findings.append(self._make_finding(
                text, m.start(), m.end(), full_path, username,
                message_index, block_index,
            ))

        # Windows paths
        for m in _WINDOWS_PATH.finditer(text):
            full_path = m.group(0)
            username = m.group(1)
            if not username or username.lower() in ("public", "default", "all users"):
                continue
            findings.append(self._make_finding(
                text, m.start(), m.end(), full_path, username,
                message_index, block_index,
            ))

        return findings

    def _is_safe(self, path: str) -> bool:
        """Check if path is a known system path that doesn't leak user info."""
        for safe in SAFE_PATHS:
            if path == safe or path.startswith(safe + "/"):
                return True
        return False

    def _make_finding(
        self,
        text: str,
        start: int,
        end: int,
        full_path: str,
        username: str,
        message_index: int,
        block_index: int,
    ) -> Finding:
        return Finding(
            detector_name=self.name,
            category=self.category,
            confidence=Confidence.HIGH,
            matched_text=full_path,
            message_index=message_index,
            block_index=block_index,
            char_start=start,
            char_end=end,
            replacement_template="REDACTED-PATH",
            context_snippet=_snippet(text, start, end),
        )
