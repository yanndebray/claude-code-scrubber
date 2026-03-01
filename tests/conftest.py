"""Shared pytest fixtures for claude-code-scrubber tests."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture path helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def simple_session_path() -> Path:
    return FIXTURES_DIR / "simple_session.jsonl"


@pytest.fixture
def env_file_paste_path() -> Path:
    return FIXTURES_DIR / "env_file_paste.jsonl"


@pytest.fixture
def git_config_leak_path() -> Path:
    return FIXTURES_DIR / "git_config_leak.jsonl"


@pytest.fixture
def aws_cli_output_path() -> Path:
    return FIXTURES_DIR / "aws_cli_output.jsonl"


@pytest.fixture
def database_errors_path() -> Path:
    return FIXTURES_DIR / "database_errors.jsonl"


@pytest.fixture
def clean_session_path() -> Path:
    return FIXTURES_DIR / "clean_session.jsonl"


@pytest.fixture
def web_session_path() -> Path:
    return FIXTURES_DIR / "web_session.json"


# ---------------------------------------------------------------------------
# Temporary directory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for test outputs."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for config file tests."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    return cfg


@pytest.fixture
def copy_fixture(tmp_path: Path) -> callable:
    """Return a helper that copies a fixture file into a temp directory.

    Useful for in-place modification tests.
    """
    def _copy(fixture_name: str) -> Path:
        src = FIXTURES_DIR / fixture_name
        dst = tmp_path / fixture_name
        shutil.copy2(src, dst)
        return dst
    return _copy


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def load_jsonl() -> callable:
    """Return a helper that reads a JSONL file into a list of dicts."""
    def _load(path: Path) -> list[dict]:
        records = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    return _load


@pytest.fixture
def load_json() -> callable:
    """Return a helper that reads a JSON file into a dict."""
    def _load(path: Path) -> dict:
        with open(path) as f:
            return json.load(f)
    return _load
