# Claude Code Agent Team Prompt: `claude-code-scrubber`

> A Python CLI tool to scrub personal/sensitive info from Claude Code transcripts before public sharing.

---

## Prompt to paste into Claude Code

```
I want to build a Python CLI tool called `claude-code-scrubber` that scrubs personal and sensitive information from Claude Code session transcripts, so they can be safely published to public GitHub repos or GitHub Pages.

The primary inspiration is Simon Willison's `claude-code-transcripts` tool — this tool would be a complementary pre-processing step. The first supported input format is the JSONL transcript files that Claude Code stores in `~/.claude/projects/`, and the JSON session files from Claude Code for web.

## Project setup

- Use `uv` for project management with a pyproject.toml
- Target Python 3.10+
- Use `click` for the CLI
- Use `rich` for terminal output (progress bars, colored diffs of what was scrubbed)
- Package name: `claude-code-scrubber`
- Entry point: `claude-code-scrubber`
- Include a comprehensive test suite with pytest from the start

## What to scrub — Detection categories

The tool must detect and redact the following categories of sensitive information found anywhere in transcript content (user messages, assistant messages, tool calls, tool results, thinking blocks):

### High-confidence patterns (auto-redact by default)
1. **API keys & tokens** — OpenAI (`sk-...`), Anthropic (`sk-ant-...`), AWS (`AKIA...`), GitHub (`ghp_`, `gho_`, `github_pat_`), Hugging Face (`hf_...`), Slack (`xoxb-`, `xoxp-`, `xoxs-`), Stripe (`sk_live_`, `pk_live_`), generic long hex/base64 tokens that look like secrets
2. **Private keys & certificates** — PEM blocks (`-----BEGIN ... PRIVATE KEY-----`), SSH private keys
3. **Passwords & connection strings** — `password=`, `passwd=`, database URIs with credentials (`postgres://user:pass@`), `.env` file contents with secret-looking values
4. **Email addresses** — standard email regex
5. **IP addresses** — IPv4 and IPv6 (with option to keep public/RFC-documented ranges like 192.0.2.x)
6. **Absolute filesystem paths** — `/Users/<username>/...`, `/home/<username>/...`, `C:\Users\<username>\...` → normalize to generic paths
7. **SSH/Git credentials** — `git@github.com:private-org/private-repo`, SSH config snippets
8. **Auth headers** — `Authorization: Bearer ...`, `Cookie: ...` with session tokens

### Medium-confidence patterns (auto-redact, configurable)
9. **Phone numbers** — US and international formats
10. **Physical addresses** — street addresses (heuristic)
11. **Names in common PII contexts** — e.g., `author: "FirstName LastName"` in git config, `user.name`, `user.email`
12. **Internal hostnames/URLs** — anything matching patterns like `*.internal.*`, `*.corp.*`, `*.local`, private GitHub org URLs
13. **AWS account IDs** — 12-digit numbers in ARN-like contexts
14. **Docker/container registry URLs** — private registries with auth

### Low-confidence patterns (flag for review, don't auto-redact)
15. **Potentially sensitive file contents** — `.env` files, `credentials.json`, `config.yaml` with secrets-like keys
16. **Hardcoded UUIDs** — might be session IDs, user IDs
17. **Organization-specific terms** — proper nouns that appear in internal paths/URLs

## Architecture — use an agent team

Create an agent team with the following roles:

### 1. `parser` — Transcript Format Expert
- Owns all input parsing: JSONL (local Claude Code), JSON (web sessions)
- Understands the Claude Code transcript schema deeply: message roles, tool_use blocks, tool_result blocks, thinking blocks, system messages, content arrays
- Produces a normalized internal representation that the scanners work on
- Handles edge cases: multi-line content in tool results, base64-encoded images (skip scanning binary), nested JSON in tool outputs
- Writes comprehensive parsing tests with real-world-shaped fixtures

### 2. `scanner` — Detection Engine Builder
- Owns ALL pattern detection logic
- Builds a registry of `Detector` classes, one per category above
- Each detector has: a name, confidence level (high/medium/low), a regex or heuristic, and a redaction strategy (replacement text)
- Detectors must work on both raw text AND structured contexts (e.g., knowing that a string inside a `tool_result` for `bash` is shell output vs. a user message)
- Must minimize false positives: e.g., don't flag `192.168.1.1` in a tutorial about networking if it's clearly example content, don't flag `test@example.com` which is a known placeholder
- Writes exhaustive tests: true positives, true negatives, edge cases
- Uses allowlists for known-safe patterns (RFC 5737 IPs, example.com domains, etc.)

### 3. `redactor` — Output & CLI Builder
- Owns the CLI interface, configuration system, and output generation
- Implements the redaction engine that takes scanner findings and applies them to the parsed transcript
- Redaction modes:
  - `[REDACTED-API-KEY-1]` — categorized placeholders with stable numbering (same key in multiple places gets same number)
  - `[REDACTED-EMAIL-3]` — so context is preserved ("sent to [REDACTED-EMAIL-3]" still reads naturally)
- CLI commands:
  - `claude-code-scrubber scan <file>` — dry-run, shows what WOULD be redacted with colored diff
  - `claude-code-scrubber scrub <file> -o <output>` — actually scrub and write output
  - `claude-code-scrubber scrub <file> --in-place` — scrub in place
  - `claude-code-scrubber scrub <directory>` — batch process all .jsonl files in a directory
  - `claude-code-scrubber config` — show/edit configuration (allowlists, confidence thresholds)
- Config file support: `.claude-code-scrubber.toml` in project root or `~/.config/claude-code-scrubber/config.toml`
- Config options:
  - `allowlist`: patterns to never redact (your public email, your public GitHub username)
  - `denylist`: additional patterns to always redact (company name, project codenames)
  - `confidence_threshold`: "high" (only auto-redact high confidence), "medium" (default), "low" (flag everything)
  - `redact_paths`: true/false — whether to normalize filesystem paths
  - `keep_example_ips`: true/false — whether to keep RFC 5737 / documentation IPs
- Interactive review mode: `claude-code-scrubber scan <file> --interactive` — shows each medium/low-confidence finding and asks confirm/skip/allowlist
- Summary report after scrubbing: count of redactions by category, list of unique redacted items (for verification)

### 4. `reviewer` — Quality & Integration
- Reviews all code written by other agents for:
  - Correctness and edge cases
  - Consistency of interfaces between parser → scanner → redactor
  - Test coverage gaps
  - False positive/negative scenarios
  - Performance on large transcripts (some sessions are 10k+ lines)
- Writes integration tests that run full pipeline: sample JSONL → scan → scrub → verify output
- Creates sample test fixtures that cover tricky real-world scenarios:
  - A transcript where the user pastes their `.env` file contents
  - A transcript with `git config` showing name/email
  - A transcript with AWS CLI output containing account IDs and ARNs
  - A transcript where Claude reads a file containing API keys
  - A transcript with database connection strings in error messages
- Ensures the tool doesn't corrupt the JSONL format (output must be valid JSONL that `claude-code-transcripts` can still process)

## Key design decisions

1. **Stable redaction IDs**: If the same API key appears 5 times, all 5 should become `[REDACTED-API-KEY-1]`, not different numbers. This preserves readability.
2. **Context preservation**: The transcript should still be readable and useful after scrubbing. Someone reviewing it should understand what happened, just not see the actual secrets.
3. **Composability with `claude-code-transcripts`**: The scrubbed JSONL/JSON must remain valid and parseable by Simon Willison's tool for HTML conversion.
4. **Speed**: Should handle a 50MB transcript directory in under 30 seconds.
5. **Zero network access**: This tool never phones home, never sends data anywhere. All processing is local.

## File structure

```
claude-code-scrubber/
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── src/
│   └── transcript_scrub/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entrypoint
│       ├── config.py           # Configuration loading/management
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── base.py         # Base parser protocol
│       │   ├── jsonl.py        # Local JSONL parser
│       │   └── json_web.py     # Web session JSON parser
│       ├── scanner/
│       │   ├── __init__.py
│       │   ├── registry.py     # Detector registry
│       │   ├── base.py         # Base detector protocol
│       │   ├── api_keys.py     # API key patterns
│       │   ├── credentials.py  # Passwords, connection strings
│       │   ├── pii.py          # Emails, phones, addresses
│       │   ├── paths.py        # Filesystem paths
│       │   ├── network.py      # IPs, hostnames, URLs
│       │   └── crypto.py       # Private keys, certificates
│       ├── redactor/
│       │   ├── __init__.py
│       │   ├── engine.py       # Core redaction engine
│       │   ├── formatter.py    # Output formatting (diff view, report)
│       │   └── interactive.py  # Interactive review mode
│       └── allowlists.py       # Built-in safe patterns
├── tests/
│   ├── conftest.py
│   ├── fixtures/               # Sample JSONL/JSON transcripts
│   │   ├── simple_session.jsonl
│   │   ├── env_file_paste.jsonl
│   │   ├── git_config_leak.jsonl
│   │   ├── aws_cli_output.jsonl
│   │   ├── database_errors.jsonl
│   │   └── clean_session.jsonl  # No secrets — should pass through unchanged
│   ├── test_parser/
│   ├── test_scanner/
│   ├── test_redactor/
│   └── test_integration/
└── .claude-code-scrubber.toml      # Example config
```

## Coordination instructions

- The `parser` should start first and define the internal `TranscriptMessage` / `TranscriptSession` data models that everyone else will use.
- The `scanner` can start building detectors in parallel once the base detector protocol is defined.
- The `redactor` should wait for at least the parser's data models before building the engine, but can start on CLI scaffolding immediately.
- The `reviewer` should begin writing integration test fixtures immediately and start reviewing as soon as code lands.
- All agents should communicate findings — especially the `scanner` should tell the `reviewer` about edge cases it's handling, and the `reviewer` should tell the `scanner` about false positive scenarios it discovers.

Please create this as an agent team with 4 teammates. Start by having the team lead coordinate the initial data model definitions, then let the agents work in parallel on their domains.
```

---

## How to use this prompt

1. Enable agent teams:
   ```bash
   # In your shell or settings.json
   export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
   ```

2. Create a new directory and open Claude Code:
   ```bash
   mkdir claude-code-scrubber && cd claude-code-scrubber
   git init
   claude
   ```

3. Paste the prompt above into Claude Code. It will propose a 4-agent team and ask for confirmation before spawning.

4. Monitor progress — you can check on individual teammates or ask the lead for a status update mid-task.

## Post-build next steps

- Wire it into a **GitHub Actions workflow** that auto-scrubs transcripts on push
- Add a `--pipe` mode for composing with `claude-code-transcripts`:
  ```bash
  claude-code-scrubber scrub session.jsonl | claude-code-transcripts json - --open
  ```
- Add support for more transcript formats (ChatGPT exports, Cursor logs, etc.)
- Publish to PyPI for `uvx claude-code-scrubber` usage
