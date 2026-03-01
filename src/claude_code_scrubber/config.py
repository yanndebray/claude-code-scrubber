"""
Configuration file support.

Users can create a .transcript-scrub.toml or .transcript-scrub.json file
to customize scrubbing behavior: extra patterns, allowlists, username, etc.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .patterns import ScrubPattern, pattern_from_string

CONFIG_FILENAMES = [
    ".transcript-scrub.toml",
    ".transcript-scrub.json",
]


@dataclass
class Config:
    """Loaded configuration."""
    username: str | None = None
    severity: set[str] = field(default_factory=lambda: {"high", "medium", "low"})
    allowlist: set[str] = field(default_factory=set)
    extra_patterns: list[ScrubPattern] = field(default_factory=list)
    output_suffix: str = ".scrubbed"
    # Custom replacements for specific strings (exact match)
    string_replacements: dict[str, str] = field(default_factory=dict)


def find_config(start: Path | None = None) -> Path | None:
    """Walk up from `start` (or cwd) looking for a config file."""
    search = start or Path.cwd()
    for directory in [search, *search.parents]:
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return None


def load_config(path: Path | None = None) -> Config:
    """Load config from a file, or return defaults."""
    if path is None:
        path = find_config()
    if path is None:
        return Config()

    if path.suffix == ".toml":
        return _load_toml(path)
    elif path.suffix == ".json":
        return _load_json(path)
    else:
        return Config()


def _load_json(path: Path) -> Config:
    data = json.loads(path.read_text())
    return _parse_config_dict(data)


def _load_toml(path: Path) -> Config:
    # Use tomllib (Python 3.11+) or tomli as fallback
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            raise ImportError(
                "TOML config requires Python 3.11+ or `pip install tomli`"
            )
    data = tomllib.loads(path.read_text())
    return _parse_config_dict(data)


def _parse_config_dict(data: dict) -> Config:
    config = Config()

    if "username" in data:
        config.username = data["username"]

    if "severity" in data:
        config.severity = set(data["severity"])

    if "allowlist" in data:
        config.allowlist = set(data["allowlist"])

    if "output_suffix" in data:
        config.output_suffix = data["output_suffix"]

    if "string_replacements" in data:
        config.string_replacements = dict(data["string_replacements"])

    if "patterns" in data:
        for p in data["patterns"]:
            config.extra_patterns.append(pattern_from_string(
                name=p.get("name", "custom"),
                regex_str=p["regex"],
                replacement=p.get("replacement", "***REDACTED***"),
                severity=p.get("severity", "high"),
            ))

    return config
