"""Tests for the configuration system."""

from __future__ import annotations

import pytest
from pathlib import Path

from transcript_scrub.config import (
    ScrubConfig,
    confidence_meets_threshold,
    load_config,
    write_default_config,
    _config_from_dict,
)


class TestScrubConfig:
    """Test ScrubConfig dataclass."""

    def test_defaults(self):
        cfg = ScrubConfig()
        assert cfg.confidence_threshold == "medium"
        assert cfg.redact_paths is True
        assert cfg.keep_example_ips is True
        assert cfg.allowlist == []
        assert cfg.denylist == []

    def test_invalid_confidence_threshold(self):
        with pytest.raises(ValueError, match="confidence_threshold"):
            ScrubConfig(confidence_threshold="invalid")

    def test_custom_values(self):
        cfg = ScrubConfig(
            confidence_threshold="high",
            redact_paths=False,
            allowlist=["safe@test.com"],
            denylist=["secret-pattern"],
        )
        assert cfg.confidence_threshold == "high"
        assert cfg.redact_paths is False
        assert cfg.allowlist == ["safe@test.com"]
        assert cfg.denylist == ["secret-pattern"]


class TestConfidenceMeetsThreshold:
    """Test the confidence level comparison."""

    def test_high_meets_high(self):
        assert confidence_meets_threshold("high", "high") is True

    def test_high_meets_medium(self):
        assert confidence_meets_threshold("high", "medium") is True

    def test_high_meets_low(self):
        assert confidence_meets_threshold("high", "low") is True

    def test_medium_does_not_meet_high(self):
        assert confidence_meets_threshold("medium", "high") is False

    def test_medium_meets_medium(self):
        assert confidence_meets_threshold("medium", "medium") is True

    def test_medium_meets_low(self):
        assert confidence_meets_threshold("medium", "low") is True

    def test_low_does_not_meet_high(self):
        assert confidence_meets_threshold("low", "high") is False

    def test_low_does_not_meet_medium(self):
        assert confidence_meets_threshold("low", "medium") is False

    def test_low_meets_low(self):
        assert confidence_meets_threshold("low", "low") is True


class TestConfigFromDict:
    """Test creating config from a dict."""

    def test_empty_dict(self):
        cfg = _config_from_dict({})
        assert cfg.confidence_threshold == "medium"

    def test_partial_dict(self):
        cfg = _config_from_dict({"confidence_threshold": "high"})
        assert cfg.confidence_threshold == "high"
        assert cfg.redact_paths is True  # default preserved

    def test_nested_scrubber_section(self):
        cfg = _config_from_dict({
            "scrubber": {
                "confidence_threshold": "low",
                "redact_paths": False,
            }
        })
        assert cfg.confidence_threshold == "low"
        assert cfg.redact_paths is False

    def test_unknown_fields_ignored(self):
        cfg = _config_from_dict({
            "confidence_threshold": "high",
            "unknown_field": "value",
        })
        assert cfg.confidence_threshold == "high"


class TestWriteAndLoadConfig:
    """Test writing and loading config files."""

    def test_write_default_config(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        write_default_config(config_path)
        assert config_path.exists()

        cfg = load_config(config_path=config_path)
        assert cfg.confidence_threshold == "medium"
        assert cfg.redact_paths is True

    def test_load_explicit_config(self, tmp_path: Path):
        config_path = tmp_path / "custom.toml"
        write_default_config(config_path)
        cfg = load_config(config_path=config_path)
        assert isinstance(cfg, ScrubConfig)

    def test_load_missing_explicit_config_raises(self, tmp_path: Path):
        config_path = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError):
            load_config(config_path=config_path)

    def test_load_defaults_when_no_files(self, tmp_path: Path):
        """When no config files exist, defaults are used."""
        cfg = load_config(project_dir=tmp_path)
        assert cfg.confidence_threshold == "medium"

    def test_project_config_loaded(self, tmp_path: Path):
        """Project-level config is loaded from .claude-code-scrubber.toml."""
        config_path = tmp_path / ".claude-code-scrubber.toml"
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump({"scrubber": {"confidence_threshold": "high"}}, f)

        cfg = load_config(project_dir=tmp_path)
        assert cfg.confidence_threshold == "high"
