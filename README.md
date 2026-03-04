# 🧼 claude-code-scrubber🫧

[![PyPI](https://img.shields.io/pypi/v/claude-code-scrubber)](https://pypi.org/project/claude-code-scrubber/)

Scrub API keys, secrets, and personal information from Claude Code transcripts before publishing them to public repos.

## Artifacts

### Debate: Team vs Claude branch comparison
- [Final Verdict](debate/debate-final-verdict.md)
- [Team Report](debate/debate-team-report.md) | [Team Cross-Review](debate/debate-team-crossreview.md)
- [Claude Report](debate/debate-claude-report.md) | [Claude Cross-Review](debate/debate-claude-crossreview.md)
- [Interactive Debate Visualization](debate/debate.html)
- [Arena Battle](debate/arena-battle.md) | [Arena Battle (HTML)](debate/arena-battle.html)
- [Court Proceedings](debate/court-proceedings.md) | [Court Proceedings (HTML)](debate/court-proceedings.html)
- [Multiverse Analysis](debate/multiverse-analysis.md) | [Multiverse Analysis (HTML)](debate/multiverse-analysis.html)
- [Showboat Evidence](debate/showboat-evidence.md) | [Showboat Evidence (HTML)](debate/showboat-evidence.html)
- [Spectacle Showdown](debate/spectacle-showdown.md) | [Spectacle Showdown (HTML)](debate/spectacle-showdown.html)

### Research
- [Sensitive Data Scrubbing Tools Research](research/sensitive-data-scrubbing-tools-research.md)

Inspired by [Simon Willison's claude-code-transcripts](https://github.com/simonw/claude-code-transcripts) — this tool sits between your raw session data and your public GitHub Pages, giving you peace of mind that you're not leaking credentials.

## What it catches

| Severity | What's detected |
|----------|----------------|
| 🔴 High | Anthropic, OpenAI, GitHub, AWS, Google, Slack, Stripe, HuggingFace, SendGrid, Twilio, npm, PyPI, Vercel, Supabase, Netlify API keys & tokens. Bearer/Basic auth headers. JWT tokens. SSH private keys. Database connection strings. Generic `SECRET`/`TOKEN`/`PASSWORD` assignments. |
| 🟡 Medium | Email addresses. Private IP addresses (10.x, 192.168.x, 172.16-31.x). |
| 🔵 Low | OS usernames in file paths (`/Users/you/`, `/home/you/`). Encoded Claude project paths. Shell prompts with `user@host.local`. |

## Supported formats

- **JSONL** — Local Claude Code sessions from `~/.claude/projects/`
- **JSON** — Claude Code for web session exports
- **HTML** — Output from `claude-code-transcripts` (preserves HTML structure)

## Install

```bash
# With pip
pip install claude-code-scrubber

# With uv (no install needed)
uvx claude-code-scrubber scan session.jsonl

# From source
git clone https://github.com/yanndebray/claude-code-scrubber
cd claude-code-scrubber
pip install -e .
```

## Quick start

```bash
# 1. Scan first (dry-run) — see what would be scrubbed
claude-code-scrubber scan my-session.jsonl -u $(whoami)

# 2. Scrub and write clean output
claude-code-scrubber scrub my-session.jsonl -u $(whoami)
# → writes my-session.scrubbed.jsonl

# 3. Scrub HTML transcripts into an output directory
claude-code-scrubber scrub transcripts/*.html -u $(whoami) -o clean/
```

## Usage

### `scan` — Dry-run detection

```bash
# Scan with verbose output showing every match
claude-code-scrubber scan session.jsonl -u myuser -v

# Scan only high-severity items
claude-code-scrubber scan session.jsonl -s high

# Scan multiple files
claude-code-scrubber scan *.jsonl *.html
```

Example output:
```
📄 Scanning session.jsonl ...
  🔴 [HIGH] Anthropic API key  at line 1.message.content  → sk-ant-***…
  🔴 [HIGH] AWS access key     at line 3.message.content  → AKIAIOSFO…
  🟡 [MEDIUM] Email address    at line 3.message.content  → yann.dup…
  🔵 [LOW] Home directory path  at line 2.message.content  → /Users/yan…

🧼 Found 23 item(s) to scrub across 1 file(s):
  🔴 High:   19  (API keys, tokens, passwords)
  🟡 Medium: 2   (emails, private IPs)
  🔵 Low:    2   (usernames in paths)
```

The `scan` command exits with code `1` if findings exist — useful in CI.

### `scrub` — Redact and write clean files

```bash
# Write to a suffixed file (default: .scrubbed)
claude-code-scrubber scrub session.jsonl -u myuser
# → session.scrubbed.jsonl

# Write to an output directory
claude-code-scrubber scrub session.jsonl -o clean/

# Overwrite originals (careful!)
claude-code-scrubber scrub session.jsonl --in-place

# Custom suffix
claude-code-scrubber scrub session.jsonl --suffix .clean
```

### `init` — Create a config file

```bash
claude-code-scrubber init           # creates .claude-code-scrubber.json
claude-code-scrubber init -f toml   # creates .claude-code-scrubber.toml
```

## Configuration

Create a `.claude-code-scrubber.json` (or `.toml`) in your project root:

```json
{
    "username": "yann",
    "severity": ["high", "medium", "low"],
    "output_suffix": ".scrubbed",
    "allowlist": [
        "sk-ant-this-is-a-dummy-key-for-docs"
    ],
    "string_replacements": {
        "MyCompanyName": "ACME",
        "my-secret-project": "project-x"
    },
    "patterns": [
        {
            "name": "Internal ticket ID",
            "regex": "PROJ-[0-9]{4,}",
            "replacement": "PROJ-XXXX",
            "severity": "medium"
        }
    ]
}
```

| Field | Description |
|-------|-------------|
| `username` | Your OS username, used to redact paths like `/Users/you/` |
| `severity` | Which levels to scrub. Default: all three. |
| `allowlist` | Strings that should never be redacted (false positive prevention) |
| `string_replacements` | Exact string → replacement pairs, applied after regex |
| `patterns` | Extra regex patterns with name, regex, replacement, severity |
| `output_suffix` | Suffix for output files. Default: `.scrubbed` |

Config files are auto-discovered by walking up from the current directory.

## Workflow: Claude Code → Public GitHub

```bash
# 1. Generate HTML transcripts with Simon's tool
claude-code-transcripts local -o transcripts/

# 2. Scrub them
claude-code-scrubber scrub transcripts/*.html -u $(whoami) -o docs/

# 3. Push to GitHub Pages
git add docs/
git commit -m "Add scrubbed transcripts"
git push
```

### CI gate (GitHub Actions)

```yaml
- name: Check transcripts for secrets
  run: |
    pip install claude-code-scrubber
    claude-code-scrubber scan docs/**/*.html -u runner -s high
```

## How it works

1. **Pattern matching** — A curated set of 30+ regex patterns detect common API key formats, PII, and secrets
2. **Format-aware parsing** — JSONL/JSON files are parsed and scrubbed recursively at the value level (preserving valid JSON structure). HTML is split on tags to avoid breaking markup.
3. **Layered severity** — You control what gets scrubbed. Need to keep email addresses but redact API keys? Use `-s high`
4. **Allowlisting** — Known-safe strings (like dummy keys in docs) are never touched

## License

MIT
