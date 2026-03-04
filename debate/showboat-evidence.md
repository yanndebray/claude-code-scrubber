# SHOWBOAT EVIDENCE REPORT

**Pipeline:** claude-code-scrubber branch comparison
**Capture Date:** 2026-03-03
**Branches Under Analysis:** `claude` (src/claude_code_scrubber) vs `team` (src/transcript_scrub)
**Motto:** "Here are the facts; judge for yourself."

---

## 1. EVIDENCE COLLECTION LOG

| # | Capture | Command | Status |
|---|---------|---------|--------|
| 1 | Diff stats | `git diff --stat main...{team,claude}` | Collected |
| 2 | Commit history | `git log --oneline main...{team,claude}` | Collected |
| 3 | File/function/class counts | `git ls-tree`, `grep`, `wc -l` | Collected |
| 4 | Claude branch tests | `python -m pytest src/claude_code_scrubber/test_scrubber.py` | Collected (FAIL) |
| 5 | Team branch tests | `python -m pytest tests/` after `pip install -e ".[dev]"` | Collected (PASS) |
| 6 | Pattern inventory | `grep` for pattern definitions per branch | Collected |
| 7 | Dependency audit | `git show {branch}:pyproject.toml` | Collected |
| 8 | Feature matrix | CLI options, modules, capabilities | Collected |

---

## 2. CAPTURE: Source Metrics

### 2.1 Lines Changed vs Main

| Dimension | claude | team |
|-----------|--------|------|
| Files changed vs main | 11 | 59 |
| Lines added vs main | +1,745 | +7,861 |
| Lines deleted vs main | -2 | 0 |

### 2.2 Source Code (Application Only)

| Dimension | claude (`src/claude_code_scrubber/`) | team (`src/transcript_scrub/`) |
|-----------|--------------------------------------|-------------------------------|
| Python source files | 6 (incl. test file) | 22 |
| Total source lines | 1,202 (incl. 236 test lines) | 2,953 |
| Source lines (excl. tests) | 966 | 2,953 |
| Functions (`def`) | 55 | 107 |
| Classes (`class`) | 11 | 22 |

### 2.3 Source File Breakdown -- Claude Branch

| File | Lines |
|------|-------|
| `__init__.py` | 3 |
| `cli.py` | 252 |
| `config.py` | 105 |
| `patterns.py` | 358 |
| `scrubber.py` | 248 |
| `test_scrubber.py` | 236 |
| **Total** | **1,202** |

### 2.4 Source File Breakdown -- Team Branch

| File | Lines |
|------|-------|
| `__init__.py` | 3 |
| `allowlists.py` | 114 |
| `cli.py` | 300 |
| `config.py` | 131 |
| `models.py` | 115 |
| `parser/__init__.py` | 80 |
| `parser/base.py` | 35 |
| `parser/json_web.py` | 150 |
| `parser/jsonl.py` | 263 |
| `redactor/__init__.py` | 15 |
| `redactor/engine.py` | 284 |
| `redactor/formatter.py` | 149 |
| `redactor/interactive.py` | 127 |
| `scanner/__init__.py` | 48 |
| `scanner/api_keys.py` | 138 |
| `scanner/base.py` | 55 |
| `scanner/credentials.py` | 186 |
| `scanner/crypto.py` | 152 |
| `scanner/network.py` | 202 |
| `scanner/paths.py` | 125 |
| `scanner/pii.py` | 197 |
| `scanner/registry.py` | 84 |
| **Total** | **2,953** |

### 2.5 Package Architecture

**Claude branch:** Flat module structure (single directory)
```
src/claude_code_scrubber/
    __init__.py
    cli.py
    config.py
    patterns.py
    scrubber.py
    test_scrubber.py
```

**Team branch:** Nested sub-package structure (4 sub-packages)
```
src/transcript_scrub/
    __init__.py
    allowlists.py
    cli.py
    config.py
    models.py
    parser/
        __init__.py
        base.py
        json_web.py
        jsonl.py
    redactor/
        __init__.py
        engine.py
        formatter.py
        interactive.py
    scanner/
        __init__.py
        api_keys.py
        base.py
        credentials.py
        crypto.py
        network.py
        paths.py
        pii.py
        registry.py
```

---

## 3. CAPTURE: Test Results

### 3.1 Claude Branch Tests

**Command:** `python -m pytest src/claude_code_scrubber/test_scrubber.py`
**Result:** ERROR -- 1 error during collection, 0 tests ran

**Error:**
```
File "src/claude_code_scrubber/test_scrubber.py", line 223
    from claude-code-scrubber.scrubber import ScrubReport
                 ^
SyntaxError: invalid syntax
```

**Observation:** The test file contains an invalid Python import statement (`from claude-code-scrubber.scrubber` -- hyphens are not valid in Python identifiers). This prevents test collection entirely. 30 test functions are defined in the file but none can execute.

### 3.2 Team Branch Tests

**Command:** `pip install -e ".[dev]" && python -m pytest tests/ -v`
**Result:** 257 passed in 0.25s

**Test breakdown by module:**

| Test Module | Test Count |
|-------------|-----------|
| `test_scanner/test_api_keys.py` | Tests for API key detection |
| `test_scanner/test_credentials.py` | Tests for credential detection |
| `test_scanner/test_crypto.py` | Tests for crypto material detection |
| `test_scanner/test_network.py` | Tests for network info detection |
| `test_scanner/test_paths.py` | Tests for filesystem path detection |
| `test_scanner/test_pii.py` | Tests for PII detection |
| `test_redactor/test_engine.py` | Tests for redaction engine |
| `test_redactor/test_cli.py` | Tests for CLI redaction commands |
| `test_redactor/test_config.py` | Tests for config handling |
| `test_parser/test_jsonl_parser.py` | Tests for JSONL parsing |
| `test_parser/test_json_web_parser.py` | Tests for JSON web parsing |
| `test_integration/test_cli.py` | CLI integration tests |
| `test_integration/test_full_pipeline.py` | Full pipeline integration tests |
| **Total** | **257 passed, 0 failed** |

### 3.3 Test Infrastructure

| Dimension | claude | team |
|-----------|--------|------|
| Test files | 1 | 14 (excl. `__init__.py`) |
| Test functions | 30 (defined) | 257 |
| Test lines | 236 | 2,594 |
| Test fixtures (data files) | 0 | 7 |
| conftest.py | No | Yes (118 lines) |
| Tests pass? | No (SyntaxError) | Yes (257/257) |

---

## 4. CAPTURE: Pattern Inventory

### 4.1 Claude Branch -- 40 Named Patterns (via `ScrubPattern`)

| # | Pattern Name | Category |
|---|-------------|----------|
| 1 | Anthropic API key | API Keys |
| 2 | OpenAI API key | API Keys |
| 3 | OpenAI project key | API Keys |
| 4 | GitHub token (classic) | API Keys |
| 5 | GitHub OAuth token | API Keys |
| 6 | GitHub App token | API Keys |
| 7 | GitHub fine-grained PAT | API Keys |
| 8 | AWS access key | API Keys |
| 9 | AWS secret key | API Keys |
| 10 | Google API key | API Keys |
| 11 | Slack token | API Keys |
| 12 | Stripe key | API Keys |
| 13 | HuggingFace token | API Keys |
| 14 | npm token | API Keys |
| 15 | PyPI token | API Keys |
| 16 | Vercel token | API Keys |
| 17 | Supabase key | API Keys |
| 18 | Cloudflare API token | API Keys |
| 19 | Netlify token | API Keys |
| 20 | SendGrid key | API Keys |
| 21 | Twilio key | API Keys |
| 22 | Generic secret assignment | Credentials |
| 23 | Bearer token | Credentials |
| 24 | Basic auth header | Credentials |
| 25 | Private key block | Crypto |
| 26 | JWT token | Crypto |
| 27 | Database connection string | Credentials |
| 28 | Claude .credentials.json content | Credentials |
| 29 | Email address | PII |
| 30 | Username in general text | PII |
| 31 | Shell prompt with user@host | PII |
| 32 | Home directory path (macOS) | Paths |
| 33 | Home directory path (Linux) | Paths |
| 34 | Home directory path (Windows) | Paths |
| 35 | Encoded home path in Claude project dir | Paths |
| 36 | Encoded home path in Claude project dir (Linux) | Paths |
| 37 | Private IPv4 (10.x.x.x) | Network |
| 38 | Private IPv4 (172.16-31.x.x) | Network |
| 39 | Private IPv4 (192.168.x.x) | Network |
| **Total** | **~39-40 patterns** | |

### 4.2 Team Branch -- 41 Compiled Regex Patterns (via `re.compile`)

Organized across 6 detector modules:

| Module | re.compile Count | Detected Categories |
|--------|-----------------|---------------------|
| `api_keys.py` | 13 | anthropic, openai, aws, github, github_pat, huggingface, slack, stripe_live, stripe_pub_live, sendgrid, twilio, vercel, generic_key |
| `credentials.py` | 9 | PEM private keys, password assignments, quoted passwords, DB URIs, env secrets, auth headers, cookie sessions |
| `crypto.py` | 4 | PEM blocks, SSH public keys, JWTs, git credentials |
| `network.py` | 6 | IPv4, IPv6, internal hostnames, AWS ARNs, ECR registries, private registries |
| `paths.py` | 3 | macOS paths, Linux paths, Windows paths |
| `pii.py` | 6 | Emails, US phone, international phone, addresses, name context, git author |
| **Total** | **41** | |

### 4.3 Pattern Coverage Comparison

| Detection Category | claude | team |
|-------------------|--------|------|
| API keys (named services) | 21 patterns | 13 patterns (fewer named services, more generic) |
| Credential patterns | 4 | 9 |
| Crypto material | 2 | 4 (adds SSH pubkeys, git credentials) |
| Network/infrastructure | 3 (IPv4 only) | 6 (adds IPv6, hostnames, AWS ARNs, ECR, registries) |
| Filesystem paths | 5 (incl. encoded) | 3 |
| PII | 3 | 6 (adds phone numbers, physical addresses, git author) |
| **Total compiled regexes** | **40** | **41** |

---

## 5. CAPTURE: Dependency Audit

### 5.1 Runtime Dependencies

| Dependency | claude | team |
|-----------|--------|------|
| click | >= 8.0 | >= 8.1 |
| rich | -- | >= 13.0 |
| tomli (< 3.11) | -- | >= 2.0 |
| tomli-w | -- | >= 1.0 |
| **Total runtime deps** | **1** | **4** |

### 5.2 Dev Dependencies

| Dependency | claude | team |
|-----------|--------|------|
| pytest | Yes | >= 7.0 |
| pytest-cov | Yes | >= 4.0 |
| **Total dev deps** | **2** | **2** |

### 5.3 Build System

| Dimension | claude | team |
|-----------|--------|------|
| Build backend | setuptools | hatchling |
| Lock file | None | `uv.lock` (359 lines) |
| Python requirement | >= 3.10 | >= 3.10 |
| Package metadata (classifiers, keywords, authors) | Yes | No |

---

## 6. CAPTURE: Feature Matrix

| Feature | claude | team |
|---------|--------|------|
| CLI framework | click | click |
| `scan` command | Yes | Yes |
| `scrub` command | Yes | Yes |
| `init` command | No | No |
| Multi-file argument | Yes (nargs=-1) | No (single file) |
| In-place editing | Yes (`--in-place`) | Yes (`--in-place`) |
| Output file/dir | Yes (`--output`) | Yes (`--output`) |
| Config file support | Yes (TOML) | Yes (TOML) |
| Sample config file | No | Yes (`.claude-code-scrubber.toml`) |
| Interactive review mode | No | Yes (`--interactive`) |
| Quiet mode | No | Yes (`--quiet`) |
| Verbose mode | Yes (`--verbose`) | Yes (`--verbose`) |
| Rich terminal output | No | Yes (tables, color) |
| Allowlists (safe values) | No | Yes (IPs, emails, domains) |
| Confidence levels | No | Yes (HIGH/MEDIUM/LOW enum) |
| Parser sub-package | No (inline) | Yes (base, JSONL, JSON web) |
| JSON web format support | No | Yes |
| JSONL format support | Yes | Yes |
| Scanner registry | No | Yes (pluggable detectors) |
| Data model classes | 1 (ScrubPattern) | 8 (Confidence, ContentType, MessageRole, ContentBlock, TranscriptMessage, TranscriptSession, Finding, RedactionResult) |
| Redaction engine | Inline in scrubber.py | Separate engine + formatter |
| Diff output | No | Yes (`print_scan_diff`) |
| Test suite | 30 tests (broken) | 257 tests (all pass) |
| Test fixtures | 0 | 7 data files |
| Integration tests | 0 | 2 test modules |
| Documentation files | 2 (README, prompt.md) | 0 added |
| Research notes | 1 (research/sensitive-data-scrubbing-tools-research.md) | 0 added |

---

## 7. CAPTURE: Commit History

### 7.1 Claude Branch Commits (divergent from initial state)

The `claude` branch was merged into `main` via PR #1 on 2026-03-01. The original commits:

| Hash | Date | Message |
|------|------|---------|
| `9595a5d` | 2026-03-01 10:19 | feat: add core scrubbing engine and detection patterns for sensitive information |
| `7df493c` | 2026-03-01 10:22 | fix: update import paths in test_scrubber.py and transcript-scrubber-prompt.md |
| `6972ac6` | 2026-03-01 10:33 | chore: add .gitignore file and update build backend in pyproject.toml |
| `2b335d7` | 2026-03-01 10:44 | docs: add PyPI badge to README for package version visibility |
| `ab85311` | 2026-03-01 15:45 | Research with Claude chat app |

5 commits over ~5.5 hours on 2026-03-01.

### 7.2 Team Branch Commits (unique, not in claude)

| Hash | Date | Message |
|------|------|---------|
| `7dc4924` | 2026-03-01 10:39 | Add claude-code-scrubber: CLI tool to scrub sensitive info from Claude Code transcripts |
| `282bca0` | 2026-03-01 17:15 | Add interactive HTML visualization of branch debate |
| `8f12905` | 2026-03-01 16:12 | Add puppets-style debate analysis comparing team vs claude branches |

1 code commit + 2 debate/analysis commits. The team's `src/transcript_scrub/` code was added in a single commit (`7dc4924`).

### 7.3 Branch Relationship

- The `claude` branch was merged into `main` first (PR #1)
- The `team` branch includes all of main's content (including claude's code) PLUS adds `src/transcript_scrub/` and `tests/`
- Both branches share the same base repository

---

## 8. DIMENSIONS GRID

| Dimension | claude | team | Delta |
|-----------|--------|------|-------|
| **Source files** | 5 (excl. test) | 22 | team +17 |
| **Source lines** | 966 (excl. test) | 2,953 | team +1,987 |
| **Test files** | 1 | 14 | team +13 |
| **Test lines** | 236 | 2,594 | team +2,358 |
| **Test functions** | 30 | 257 | team +227 |
| **Tests passing** | 0/30 (SyntaxError) | 257/257 | team +257 |
| **Functions defined** | 55 | 107 | team +52 |
| **Classes defined** | 11 | 22 | team +11 |
| **Detection patterns (regex)** | 40 | 41 | team +1 |
| **Named API key patterns** | 21 | 13 | claude +8 |
| **PII pattern types** | 3 | 6 | team +3 |
| **Network pattern types** | 3 | 6 | team +3 |
| **Runtime dependencies** | 1 | 4 | team +3 |
| **Sub-packages** | 0 | 4 | team +4 |
| **Data model classes** | 1 | 8 | team +7 |
| **Parser formats** | 1 (JSONL) | 2 (JSONL + JSON web) | team +1 |
| **Interactive mode** | No | Yes | team only |
| **Allowlists** | No | Yes | team only |
| **Confidence levels** | No | Yes | team only |
| **Rich terminal output** | No | Yes | team only |
| **Pluggable registry** | No | Yes | team only |
| **Multi-file CLI** | Yes | No | claude only |
| **Package metadata** | Yes | No | claude only |
| **Research docs** | Yes | No | claude only |
| **Commits (code only)** | 5 | 1 | claude +4 |

---

*End of Showboat Evidence Report. The evidence speaks for itself.*
