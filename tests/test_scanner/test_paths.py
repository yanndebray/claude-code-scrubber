"""Tests for filesystem path detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.paths import PathDetector


@pytest.fixture
def detector():
    return PathDetector()


class TestMacOSPaths:
    def test_detects_macos_home(self, detector):
        text = "File at /Users/johndoe/Documents/project/main.py"
        findings = detector.scan(text)
        assert len(findings) == 1
        assert findings[0].matched_text.startswith("/Users/johndoe")
        assert findings[0].confidence == Confidence.HIGH

    def test_detects_macos_short_path(self, detector):
        text = "cd /Users/alice"
        findings = detector.scan(text)
        assert len(findings) == 1

    def test_skips_shared_user(self, detector):
        text = "/Users/Shared/data"
        findings = detector.scan(text)
        # /Users/Shared is a system path, not a user path
        assert len(findings) == 0


class TestLinuxPaths:
    def test_detects_linux_home(self, detector):
        text = "Config at /home/ubuntu/.bashrc"
        findings = detector.scan(text)
        assert len(findings) == 1
        assert findings[0].matched_text.startswith("/home/ubuntu")

    def test_detects_linux_deep_path(self, detector):
        text = "/home/deploy/app/src/main.rs"
        findings = detector.scan(text)
        assert len(findings) == 1


class TestWindowsPaths:
    def test_detects_windows_path(self, detector):
        text = r"C:\Users\JohnDoe\Documents\project\file.txt"
        findings = detector.scan(text)
        assert len(findings) == 1
        assert findings[0].matched_text.startswith(r"C:\Users\JohnDoe")

    def test_skips_public_user(self, detector):
        text = r"C:\Users\Public\Documents"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_default_user(self, detector):
        text = r"C:\Users\Default\NTUSER.DAT"
        findings = detector.scan(text)
        # "Default" is a system profile
        assert len(findings) == 0


class TestSafePaths:
    def test_skips_usr_bin(self, detector):
        text = "/usr/bin/python3"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_etc(self, detector):
        text = "/etc/nginx/nginx.conf"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_tmp(self, detector):
        text = "/tmp/build-output"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_dev_null(self, detector):
        text = "redirect to /dev/null"
        findings = detector.scan(text)
        assert len(findings) == 0

    def test_skips_usr_local_bin(self, detector):
        text = "/usr/local/bin/node"
        findings = detector.scan(text)
        assert len(findings) == 0


class TestEdgeCases:
    def test_multiple_paths_in_text(self, detector):
        text = "Paths: /Users/alice/a.txt and /home/bob/b.txt"
        findings = detector.scan(text)
        assert len(findings) == 2

    def test_path_in_quotes(self, detector):
        text = 'path="/Users/charlie/project"'
        findings = detector.scan(text)
        assert len(findings) == 1

    def test_no_false_positive_user_mention(self, detector):
        text = "The /Users directory contains home directories."
        findings = detector.scan(text)
        # No username component follows /Users
        assert len(findings) == 0


class TestCharPositions:
    def test_positions_accurate(self, detector):
        text = "found at /Users/alice/project/main.py in the repo"
        findings = detector.scan(text)
        assert len(findings) == 1
        f = findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text

    def test_context_snippet_present(self, detector):
        text = "The file /home/bob/.config/app.toml was modified"
        findings = detector.scan(text)
        assert len(findings) == 1
        assert findings[0].context_snippet != ""
