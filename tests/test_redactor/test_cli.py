"""Tests for the CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from transcript_scrub.cli import cli
from transcript_scrub.config import write_default_config


class TestConfigCommand:
    """Test the config CLI command."""

    def test_config_init(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test creating a default config file."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--init"])
        assert result.exit_code == 0
        assert "Created config file" in result.output
        assert (tmp_path / ".claude-code-scrubber.toml").exists()

    def test_config_init_already_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test that init warns if config already exists."""
        monkeypatch.chdir(tmp_path)
        write_default_config(tmp_path / ".claude-code-scrubber.toml")
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--init"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_config_show(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test showing the current configuration."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "medium" in result.output  # default threshold


class TestCliHelp:
    """Test that help text is available for all commands."""

    def test_main_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "scrub" in result.output
        assert "scan" in result.output
        assert "config" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--interactive" in result.output
        assert "--confidence" in result.output

    def test_scrub_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["scrub", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--in-place" in result.output

    def test_config_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "--init" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
