"""Configuration system for claude-code-scrubber.

Loads config from .claude-code-scrubber.toml in CWD or
~/.config/claude-code-scrubber/config.toml, with project-level
overriding user-level settings.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w


PROJECT_CONFIG_NAME = ".claude-code-scrubber.toml"
USER_CONFIG_DIR = Path.home() / ".config" / "claude-code-scrubber"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.toml"


@dataclass
class ScrubConfig:
    """Configuration for the scrubber."""

    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    confidence_threshold: str = "medium"  # "high", "medium", "low"
    redact_paths: bool = True
    keep_example_ips: bool = True

    def __post_init__(self) -> None:
        valid = {"high", "medium", "low"}
        if self.confidence_threshold not in valid:
            raise ValueError(
                f"confidence_threshold must be one of {valid}, "
                f"got {self.confidence_threshold!r}"
            )


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dict."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two config dicts. override wins for scalar values; lists are replaced."""
    merged = dict(base)
    for key, value in override.items():
        merged[key] = value
    return merged


def load_config(
    config_path: Path | None = None,
    project_dir: Path | None = None,
) -> ScrubConfig:
    """Load configuration, merging user-level and project-level configs.

    Priority: explicit config_path > project-level > user-level > defaults.
    """
    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        data = _load_toml(config_path)
        return _config_from_dict(data)

    # Start with defaults
    merged: dict[str, Any] = {}

    # Load user-level config
    if USER_CONFIG_PATH.exists():
        user_data = _load_toml(USER_CONFIG_PATH)
        merged = _merge_dicts(merged, user_data.get("scrubber", user_data))

    # Load project-level config (overrides user)
    if project_dir is None:
        project_dir = Path.cwd()
    project_config = project_dir / PROJECT_CONFIG_NAME
    if project_config.exists():
        project_data = _load_toml(project_config)
        merged = _merge_dicts(merged, project_data.get("scrubber", project_data))

    return _config_from_dict(merged)


def _config_from_dict(data: dict[str, Any]) -> ScrubConfig:
    """Create a ScrubConfig from a dict, using only known fields."""
    # Extract the scrubber section if present
    if "scrubber" in data:
        data = data["scrubber"]

    known_fields = {f.name for f in ScrubConfig.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return ScrubConfig(**filtered)


def write_default_config(path: Path) -> None:
    """Write a default config file to the given path."""
    default = {
        "scrubber": {
            "confidence_threshold": "medium",
            "redact_paths": True,
            "keep_example_ips": True,
            "allowlist": [],
            "denylist": [],
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(default, f)


def confidence_meets_threshold(
    confidence: str, threshold: str
) -> bool:
    """Check if a confidence level meets or exceeds the threshold.

    Ordering: high > medium > low.
    A threshold of "low" passes everything.
    A threshold of "high" only passes "high".
    """
    levels = {"low": 0, "medium": 1, "high": 2}
    return levels.get(confidence, 0) >= levels.get(threshold, 1)
