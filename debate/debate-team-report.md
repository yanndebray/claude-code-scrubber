# Team Branch Research Report: claude-code-scrubber

## 1. Architecture Overview

The team branch implements a clean **four-layer pipeline architecture**: Parser -> Scanner -> Redactor -> CLI. Each layer is a dedicated Python sub-package under `src/transcript_scrub/`, with clear separation of concerns:

```
src/transcript_scrub/
  models.py          (115 lines) — Shared data models
  config.py          (131 lines) — Configuration system
  allowlists.py      (114 lines) — Built-in safe-value lists
  cli.py             (300 lines) — Click CLI with scan/scrub/config commands
  parser/
    base.py          (35 lines)  — Abstract base class (ABC)
    jsonl.py         (263 lines) — JSONL parser for local Claude Code transcripts
    json_web.py      (150 lines) — JSON parser for web session exports
    __init__.py      (80 lines)  — Auto-detection and registry
  scanner/
    base.py          (55 lines)  — Abstract detector base class
    registry.py      (84 lines)  — Detector registry with scan-all orchestration
    api_keys.py      (138 lines) — API key detection (8+ providers)
    credentials.py   (186 lines) — Password, DB URI, auth header, env secret detection
    pii.py           (197 lines) — Email, phone, address, name-in-context detection
    paths.py         (125 lines) — Filesystem path (macOS/Linux/Windows) detection
    network.py       (202 lines) — IP, internal hostname, AWS account, ECR registry detection
    crypto.py        (152 lines) — PEM, SSH key, JWT, git credential detection
    __init__.py      (48 lines)  — Public API
  redactor/
    engine.py        (284 lines) — Core redaction engine with stable numbering
    formatter.py     (149 lines) — Rich terminal output (diff, summary, map)
    interactive.py   (127 lines) — Interactive review mode for medium/low findings
    __init__.py      (15 lines)  — Public API
```

**Total source code: 2,953 lines across 22 Python files.**

The data flow is strictly unidirectional. Parsers produce `TranscriptSession` objects (normalized from raw JSONL or JSON). Scanners produce `Finding` objects by examining the text in each `ContentBlock`. The `RedactionEngine` consumes findings, filters/resolves overlaps, builds a stable redaction map, and applies replacements. Parsers also provide `reconstruct()` for faithful output.

This architecture embodies the **Strategy pattern** for both parsers and scanners: new formats and detectors can be added by implementing `BaseParser` or `BaseDetector` and registering them, without modifying existing code.

## 2. Implementation Quality

### Type Safety and Modern Python

The codebase uses `from __future__ import annotations` throughout, enabling PEP 604 union types (`str | None`), PEP 585 generics (`list[str]`, `dict[str, Any]`), and forward references. It targets Python 3.10+ and handles the `tomllib` / `tomli` split cleanly:

```python
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
```

### Data Model Design

The `models.py` module defines 6 dataclasses and 3 enums that form the shared vocabulary:

- `Confidence` (HIGH/MEDIUM/LOW) — tri-level confidence with explicit ordering
- `ContentType` (TEXT, TOOL_USE, TOOL_RESULT, THINKING, IMAGE, SYSTEM) — handles all 6 Claude Code content block types
- `MessageRole` (USER, ASSISTANT, SYSTEM)
- `ContentBlock` — carries both scannable `text` and original `raw` dict, plus type-specific fields (`tool_name`, `tool_input`, `tool_use_id`)
- `TranscriptMessage` — role + content blocks + raw + index
- `TranscriptSession` — messages + metadata + source info
- `Finding` — detector_name, category, confidence, matched_text, precise character positions (`char_start`, `char_end`), replacement_template, context_snippet
- `RedactionResult` — scrubbed session + findings + redaction_map + stats

Every `Finding` carries **exact character positions** and a **context snippet**, enabling precise replacement and informative review output. The `raw` dicts on `ContentBlock` and `TranscriptMessage` enable faithful reconstruction after redaction.

### Redaction Engine Sophistication

The `RedactionEngine` (`engine.py`, 284 lines) implements a rigorous 5-step pipeline:

1. **Filter** by confidence threshold + allowlist (literal and regex) + denylist + built-in safe lists
2. **Resolve overlaps** — when two findings overlap within the same content block, prefer higher confidence, then longer match (using `_finding_priority`)
3. **Build stable redaction map** — same `matched_text` always gets the same `[REDACTED-CATEGORY-N]` placeholder, with independent per-category numbering and deterministic first-appearance ordering
4. **Apply replacements** in reverse character order within each block to maintain position accuracy
5. **Update raw dicts** via JSON serialization/deserialization with string replacement for faithful output reconstruction

The overlap resolution logic is particularly well-designed:

```python
def _finding_priority(f: Finding) -> tuple[int, int]:
    confidence_order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
    return (confidence_order.get(f.confidence, 0), f.char_end - f.char_start)
```

### Configuration System

The `config.py` module implements a hierarchical configuration system: explicit path > project-level (`.claude-code-scrubber.toml`) > user-level (`~/.config/claude-code-scrubber/config.toml`) > defaults. It supports:

- Confidence threshold (high/medium/low)
- Path redaction toggle
- Example IP retention toggle
- Allowlist (literal strings or regex patterns)
- Denylist
- Default config generation via `write_default_config()`

The `_config_from_dict` function safely extracts only known dataclass fields, ignoring unknown keys for forward compatibility.

## 3. Detection Coverage

The team branch implements **6 specialized detector modules** covering **25+ distinct detection patterns**:

### API Keys (api_keys.py) — 11 provider-specific patterns + 2 generic patterns:
- **Anthropic** (`sk-ant-...`, 20+ chars) — HIGH confidence
- **OpenAI** (`sk-...`, negative lookahead for `ant-` and `test-`) — HIGH
- **AWS** (`AKIA` + 16 uppercase alphanumeric) — HIGH
- **GitHub Personal** (`ghp_`, `gho_`, `ghs_`, `ghr_` + 36+ chars) — HIGH
- **GitHub PAT** (`github_pat_` + 22+ chars) — HIGH
- **HuggingFace** (`hf_` + 20+ chars) — HIGH
- **Slack** (`xoxb-`, `xoxp-`, `xoxa-`, `xoxs-` + 20+ chars) — HIGH
- **Stripe Live** (`sk_live_`, `rk_live_`, `pk_live_`) — HIGH
- **Stripe Test** (`sk_test_`, `pk_test_`) — LOW (intentionally lower)
- **Generic hex in secret context** (40+ hex chars after `=:`) — MEDIUM
- **Generic secret context** (key-value pairs with secret-like keys, 40+ char values) — MEDIUM

The Anthropic pattern is correctly ordered before OpenAI to prevent `sk-ant-` from matching the OpenAI pattern. Stripe test keys are deliberately LOW confidence to avoid noise.

### Credentials (credentials.py) — 8 patterns:
- **PEM private keys** (RSA, EC, DSA, OPENSSH, ENCRYPTED, generic) — HIGH
- **Password assignments** (quoted and unquoted, with `password|passwd|pass|secret|token|api_key`) — HIGH
- **Quoted key-value pairs** (dict literal style `'PASSWORD': 'value'`) — HIGH
- **Database URIs** (postgres, mysql, mongodb+srv, redis, amqp with `://user:pass@host`) — HIGH
- **Auth headers** (`Authorization: Bearer|Basic|Token`) — HIGH
- **Cookie/session headers** — MEDIUM
- **Connection strings** (`Server=...; Password=...`) — HIGH
- **.env-style secrets** (multiline `KEY=value` where KEY contains SECRET/TOKEN/PASSWORD/etc.) — HIGH

### PII (pii.py) — 5 patterns:
- **Emails** (RFC 5322 simplified, with safe-email allowlist) — HIGH
- **US phone numbers** (xxx-xxx-xxxx, (xxx) xxx-xxxx, +1 prefix) — MEDIUM
- **International phone** (+N followed by 7-15 digits) — MEDIUM
- **Physical addresses** (number + street name + suffix from 19 suffix types) — MEDIUM
- **Names in PII context** (username/author assignments, git author lines) — MEDIUM

### Paths (paths.py) — 3 OS-specific patterns:
- **macOS** (`/Users/<username>/...`) — HIGH
- **Linux** (`/home/<username>/...`) — HIGH
- **Windows** (`C:\Users\<username>\...`) — HIGH
- Correctly skips system users (Shared, Public, Default), safe system paths (/usr/bin, /etc, /tmp, /dev/null, etc.)

### Network (network.py) — 5 patterns:
- **IPv4** (standard dotted quad with boundary assertions) — HIGH
- **IPv6** (full, trailing ::, leading ::, middle ::) — HIGH
- **Internal hostnames** (`*.internal`, `*.corp`, `*.local`, `*.private`) — MEDIUM
- **AWS Account IDs** (12 digits in ARN context only, preventing false positives) — MEDIUM
- **AWS ECR registries** (`<account>.dkr.ecr.<region>.amazonaws.com/...`) — MEDIUM

### Crypto (crypto.py) — 4 patterns:
- **PEM blocks** (generic with backreference `-----BEGIN X-----...-----END X-----`, private=HIGH, cert=MEDIUM) — Uses `\1` backreference for matching
- **SSH public keys** (ssh-rsa, ssh-ed25519, ssh-dss, ecdsa-sha2-nistp*) — LOW (public data)
- **JWT tokens** (three dot-separated base64url segments starting with `eyJ`) — HIGH
- **Git credential store** (`https://user:pass@host`) — HIGH

### False Positive Prevention

The `allowlists.py` module provides 7 categories of safe values:
- RFC 5737 documentation IPs (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
- RFC 3849 documentation IPv6 (2001:db8::)
- RFC 2606 safe domains (example.com/org/net, test.com, localhost)
- 9 known safe email addresses
- 4 safe API key prefixes (sk-test-, sk_test_, pk_test_, test-key-)
- 7 placeholder values (your-api-key-here, YOUR_API_KEY, etc.)
- 7 special/loopback IPs (127.0.0.1, 0.0.0.0, ::1, etc.)
- 8 safe system paths (/usr/local/bin, /dev/null, etc.)

Each detector incorporates its own safe-value checks, and the redaction engine adds a second layer of filtering via built-in safe lists and user-configured allowlists.

## 4. Test Suite

**257 tests, ALL PASSING (100%), in 0.18 seconds.**

**Total test code: 2,594 lines across 20 Python files** (including `__init__.py` and `conftest.py`).

Test-to-source ratio: **0.88:1** (2,594 test lines / 2,953 source lines) — near parity, demonstrating serious investment in testing.

### Test Organization

Tests mirror the source structure exactly:

- `tests/test_scanner/` — 6 test files, one per detector (test_api_keys.py, test_credentials.py, test_pii.py, test_paths.py, test_network.py, test_crypto.py)
- `tests/test_redactor/` — 3 test files (test_engine.py, test_config.py, test_cli.py)
- `tests/test_parser/` — 2 test files (test_jsonl_parser.py, test_json_web_parser.py)
- `tests/test_integration/` — 2 test files (test_cli.py, test_full_pipeline.py)
- `tests/conftest.py` — Shared fixtures (fixture path helpers, temp directories, data loaders)

### Test Quality Highlights

**Each scanner detector test file includes:**
- Positive detection tests for each pattern type
- False positive prevention tests (safe values, placeholders, too-short matches)
- Character position accuracy tests (`assert text[f.char_start : f.char_end] == f.matched_text`)
- Context snippet presence tests
- Confidence level verification tests

**The redaction engine tests cover:**
- Stable numbering (same text = same replacement, different text = different number, independent per-category numbering)
- Overlap resolution (prefer higher confidence, prefer longer at same confidence, non-overlapping kept)
- Allowlist/denylist filtering (literal, case-insensitive, built-in safe emails/IPs)
- Confidence threshold filtering (high filters medium/low, low keeps everything)
- Redaction application (basic replacement, multiple in one block, raw dict updates, stats computation, empty findings, original not mutated)

**The integration tests provide:**
- Full pipeline tests for **7 fixture files** (simple_session, env_file_paste, git_config_leak, aws_cli_output, database_errors, web_session, clean_session)
- Expected-secrets lists that MUST be redacted in each fixture — e.g., `SIMPLE_SESSION_SECRETS = ["john.smith@acmecorp.com", "/home/jsmith/projects/myapp", "db.acmecorp.internal"]`
- Valid JSONL/JSON output verification
- Round-trip tests (redacted output is re-parseable)
- CLI command tests (scan, scrub, config, --help, --version, --in-place, --output, directory batch)
- Error handling tests (missing file, invalid file)

### Fixture Files (7 realistic test scenarios)

1. `simple_session.jsonl` — Basic conversation with email, path, internal hostname
2. `env_file_paste.jsonl` — .env file content via tool_result with AWS keys, Stripe keys, GitHub tokens
3. `git_config_leak.jsonl` — Git config output with email, SSH keys
4. `aws_cli_output.jsonl` — AWS CLI output with account IDs, IPs, JWTs, security groups
5. `database_errors.jsonl` — Database connection errors with passwords, URIs
6. `clean_session.jsonl` — Clean conversation with zero secrets (negative test)
7. `web_session.json` — Web session format with API keys, IPs, paths

## 5. CLI & UX

The CLI (`cli.py`, 300 lines) uses Click with Rich for output formatting:

### Three Commands:
- **`scan`** — Dry-run: shows colored diff of what would be redacted (original in red strikethrough, replacement in green)
- **`scrub`** — Apply redactions: writes to output file, in-place, or default `<name>.scrubbed.<ext>`
- **`config`** — Show current config or `--init` to create default `.claude-code-scrubber.toml`

### CLI Features:
- `--interactive` / `-i` on scan — step through medium/low confidence findings with y/n/a(dd to allowlist)/q(uit)
- `--confidence` override (high/medium/low)
- `--config` custom config path
- `--quiet` / `-q` and `--verbose` / `-v` flags
- `--output` / `-o` for explicit output path, `--in-place` for in-place modification
- **Directory batch processing** — `scan` and `scrub` both accept directories, processing all `.jsonl` and `.json` files with progress bars (Rich Progress)
- `--version` shows `0.1.0`

### Interactive Review Mode (interactive.py, 127 lines):
- Auto-confirms HIGH confidence findings
- Presents each MEDIUM/LOW finding with context panel (Rich Panel with yellow border)
- User choices: `y` (confirm), `n` (skip), `a` (add to allowlist — persists to config file), `q` (quit, skip remaining)
- Shows progress counter `(i/N)`

### Output Formatting (formatter.py, 149 lines):
- `print_scan_diff()` — Grouped by message, shows each finding as `original -> replacement (category, confidence)`
- `print_summary_table()` — Rich table with category counts + total
- `print_redaction_map()` — Original-to-replacement mapping table (truncated at 60 chars)
- `print_finding_context()` — Single finding with 40-char context window in Rich Panel

## 6. Key Strengths

### 1. Production-Grade Pipeline Architecture
The four-layer architecture with ABC base classes, registries, and clean data flow is genuinely extensible. Adding a new parser (e.g., for Claude Desktop format) or a new scanner (e.g., for social security numbers) requires implementing one class and one `register()` call.

### 2. Exceptional Detection Breadth
25+ patterns across 6 detectors covering API keys (8 providers), credentials (8 pattern types), PII (5 types), filesystem paths (3 OSes), network (5 types), and crypto (4 types). This is comprehensive coverage for the use case.

### 3. Nuanced Confidence System
The tri-level confidence (HIGH/MEDIUM/LOW) with configurable threshold, combined with per-pattern confidence tuning (Stripe test keys are LOW, SSH public keys are LOW, phone numbers are MEDIUM) reduces false positive noise while maintaining sensitivity.

### 4. Faithful Reconstruction
Both parsers implement `reconstruct()` with `copy.deepcopy` and raw dict preservation, ensuring redacted output is valid in the original format. Round-trip tests verify this property.

### 5. Comprehensive False Positive Prevention
The multi-layer allowlist system (RFC-based safe values, placeholder detection, configurable allowlist with regex support, interactive allowlist building) demonstrates maturity beyond a naive regex scanner.

### 6. Test-to-Source Parity
257 passing tests with a 0.88:1 test-to-source line ratio, 7 realistic fixtures, full integration coverage, and 100% pass rate in 0.18s show a well-tested, reliable codebase.

### 7. Real-World Usability
Directory batch processing, in-place editing, interactive review with allowlist persistence, configurable confidence, and rich terminal output make this ready for actual use.

## 7. Honest Weaknesses

### 1. No SSN/National ID Detection
The PII detector covers emails, phones, addresses, and names, but does not detect Social Security Numbers, national ID numbers, credit card numbers, or IBAN/bank account numbers.

### 2. No URL/Domain PII Detection
URLs containing usernames (e.g., `github.com/username/private-repo`) are not systematically detected outside the git credential pattern.

### 3. Limited Windows Path Coverage
While Windows paths with `C:\Users\` are detected, UNC paths (`\\server\share\user`) are not.

### 4. No Plugin System
While the architecture supports extension via subclassing, there is no formal plugin loading mechanism (e.g., entry points) for third-party detectors.

### 5. Duplicate `_snippet` Helper
The `_snippet()` function is defined identically in 5 scanner files. This could be extracted to a shared utility, though the pragmatic duplication keeps each detector self-contained.

### 6. No Coverage Reporting in CI
While `pytest-cov` is a dev dependency, there is no configured coverage threshold or CI integration visible.

### 7. Interactive Mode Untested
The interactive review module (`interactive.py`) is not covered by automated tests due to its terminal I/O nature. This is an inherent difficulty but could be addressed with mock-based tests.

## Summary Statistics

| Metric | Value |
|--------|-------|
| Source files | 22 |
| Source lines | 2,953 |
| Test files | 20 |
| Test lines | 2,594 |
| Test count | 257 |
| Tests passing | 257 (100%) |
| Test runtime | 0.18s |
| Fixture files | 7 |
| Detector modules | 6 |
| Detection patterns | 25+ |
| CLI commands | 3 (scan, scrub, config) |
| Parser formats | 2 (JSONL, JSON web) |
| Confidence levels | 3 (HIGH, MEDIUM, LOW) |
| Safe-value categories | 7 |
| Dependencies | 4 (click, rich, tomli, tomli-w) |
