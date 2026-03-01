# Sensitive data scrubbing tools: a comprehensive benchmark for transcript-scrub

**No existing tool scrubs Claude Code session transcripts for secrets and PII before publishing — the gap is real and well-documented.** Across 40+ tools evaluated spanning secret scanners, PII detectors, LLM sanitizers, and log redactors, every tool either focuses on detection-only (alerting rather than redacting), operates on the input path (sanitizing prompts *before* they reach an LLM), or targets structured databases rather than conversation JSONL. The closest analog — OpenClaw's `sessions scrub` command — is embedded in a fork's CLI and not available standalone. A purpose-built `transcript-scrub` tool would fill a clear market gap, and critically, several high-quality Python libraries can serve as building blocks rather than starting from scratch.

---

## Secret scanners: strong detection, no redaction

The secret scanning ecosystem is mature but uniformly focused on *finding* secrets, not *replacing* them in-place. Three tools dominate.

**TruffleHog** (trufflesecurity/trufflehog) leads with **~24,500 GitHub stars** and **800+ credential detectors** covering AWS, GCP, Azure, Stripe, Slack, SSH keys, JWTs, and hundreds more. Its killer feature is active API verification — it actually authenticates discovered credentials to confirm they're live. However, it's written in Go (not importable as a Python library), outputs detection results only, and carries an **AGPL-3.0 license** that complicates embedding.

**Gitleaks** (gitleaks/gitleaks, **~18,000 stars**, MIT license) offers **160+ regex rules** in a clean TOML config, runs as a single Go binary, and is the fastest option for pre-commit hooks. Its `--redact` flag masks secrets in CLI output but does not modify source files. **detect-secrets** (Yelp/detect-secrets, **~4,300 stars**, Apache-2.0) is the standout for Python integration — it's pure Python, pip-installable, and exposes a `SecretsCollection` API with a pluggable architecture supporting ~20 built-in detectors covering entropy analysis, keyword matching, and service-specific regex patterns. It handles JSON files through a built-in transformer and supports custom plugins via simple subclassing.

| Tool | Stars | Language | Detectors | Redacts? | Python library? | License |
|------|-------|----------|-----------|----------|-----------------|---------|
| **TruffleHog** | ~24,500 | Go | 800+ (verified) | ❌ | No (subprocess) | AGPL-3.0 |
| **Gitleaks** | ~18,000 | Go | 160+ | Output only | No (subprocess) | MIT |
| **detect-secrets** | ~4,300 | Python | ~20 plugins | ❌ | **Yes — excellent** | Apache-2.0 |
| **GitGuardian ggshield** | ~2,000 | Python | 500+ (cloud) | Output only | Cloud API required | MIT |
| **Nosey Parker** | ~2,000 | Rust | 188 | ❌ | No | Apache-2.0 |
| **secretlint** | ~1,275 | TypeScript | ~15 rules | **Yes — file-level** | No (Node.js) | MIT |
| **git-secrets** | ~13,000 | Bash | AWS-focused | ❌ | No | Apache-2.0 |
| **Talisman** | ~2,100 | Go | Entropy + patterns | ❌ | No | MIT |
| **Whispers** | ~498 | Python | ~30 rules | ❌ | **Yes — good** | Apache-2.0 |

**secretlint** deserves special mention as the only secret scanner with actual file-level redaction — its `--format=mask-result --output=file` pipeline writes masked content back to disk. But it's TypeScript/Node.js, making it awkward as a Python dependency. **Whispers** (Skyscanner) uniquely parses structured files into key-value pairs before scanning, making it inherently JSON-aware — but the project was **archived in October 2023**.

For `transcript-scrub`, **detect-secrets is the clear dependency choice**: Apache-2.0 licensed, pure Python, extensible plugin architecture, and a JSON transformer. Its regex patterns for AWS keys, GitHub tokens, Slack tokens, Stripe keys, private keys, JWTs, and high-entropy strings provide a strong baseline. Custom plugins can extend coverage to Claude-specific patterns (e.g., `sk-ant-*` Anthropic API keys).

---

## PII detectors fill the other half of the equation

Secret scanners miss personally identifiable information — names, emails, phone numbers, addresses, and SSNs that frequently appear in coding transcripts when developers discuss user data or debug customer issues. The PII tool landscape splits into three tiers.

**Microsoft Presidio** (microsoft/presidio, **~6,900 stars**, MIT) is the gold standard for Python PII work. It combines spaCy NER models for names/locations/organizations with regex patterns for structured identifiers (emails, phones, credit cards, SSNs, IBANs) and adds **context-aware confidence scoring**. The two-component architecture — `presidio-analyzer` for detection and `presidio-anonymizer` for redaction — supports five replacement strategies: entity-type tokens (`<PERSON>`), character masking, hashing, AES encryption, and custom operators including Faker-based synthetic data replacement. It supports **50+ entity types** across multiple countries and allows custom recognizers. The main limitation: it treats input as flat text, so a JSONL wrapper is needed to extract and reassemble text fields.

**scrubadub** (~450 stars, MIT) offers a lighter-weight alternative at **<2MB with regex-only mode**, detecting emails, phones, URLs, credit cards, and SSNs out of the box. Adding spaCy NER for names requires the `scrubadub_spacy` plugin. **DataFog** (~300 stars, MIT) provides a similar lightweight profile with a CLI interface (`datafog scan-text`, `datafog redact-text`) and claims **190× performance advantage** in regex-only mode. **OpenPipe pii-redaction** takes a radically different approach, using a **fine-tuned Llama 3.2 1B model** to achieve **F1=0.98** on general text and — critically — includes **native JSONL dataset processing** via `clean_dataset()`. However, it requires a GPU and drops to F1=0.42 on domain-specific text.

Two niche tools deserve attention: **bigcode/pii-lib** was built specifically to detect PII **within source code** (emails, API keys, SSH keys in code datasets), and **Redactomatic** (eisenzopf/redactomatic) was designed for **conversation transcript anonymization** with multi-pass spaCy NER + regex detection and consistent fake-value replacement per conversation — the closest architectural precedent for transcript-scrub.

For `transcript-scrub`, **Presidio is the recommended PII dependency**. The Presidio + Faker integration pattern is well-established:

```python
# Detect PII → replace with realistic fake data
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
results = analyzer.analyze(text=content, language="en")
anonymized = anonymizer.anonymize(text=content, analyzer_results=results,
    operators={"PERSON": OperatorConfig("custom", {"lambda": lambda x: fake.name()})})
```

---

## The LLM transcript scrubbing gap is confirmed and documented

Every LLM-focused privacy tool found operates on the **input path** — intercepting prompts before they reach an API. Not one addresses post-hoc transcript sanitization.

**prompt-sentinel** (Python, `@sentinel` decorator) replaces secrets with `__SECRET_1__` tokens before API calls and restores them in responses. **LLM-Sentinel** (Node.js) masks 52 sensitive data types as a proxy layer with 1-3ms latency. **Sentinel** (Rust) provides a multi-provider LLM proxy with sub-millisecond overhead. Chrome extensions like **RedactChat**, **PasteSecure**, and **ChatGPT Privacy Shield** sanitize clipboard content before pasting. Enterprise solutions like **Prompt Security** (acquired by SentinelOne for ~$250M in August 2025) and **Strac** monitor LLM interactions in real time.

The **Claude Code transcript ecosystem** has three publishing tools but zero scrubbers. **simonw/claude-code-transcripts** (607 stars) converts `~/.claude/projects/` JSONL files to HTML with session picking, pagination, and gist publishing — but publishes content as-is with **no sanitization**. **daaain/claude-code-log** provides similar JSONL-to-HTML/Markdown conversion. **hjtenklooster/claude-file-recovery** demonstrates sophisticated JSONL parsing to reconstruct files from tool-use blocks, proving the format is well-understood.

The problem is explicitly documented. **OpenClaw Issue #12182** describes how tool output (stdout/stderr from bash commands) is saved verbatim to session JSONL — when an agent runs `cat ~/.openclaw/openclaw.json` or `grep -r "xoxb-"`, secrets land in plaintext in the transcript. OpenClaw's codebase includes `redactSensitiveText()` with patterns for `xoxb/xapp`, `sk-ant`, `AIza`, Bearer tokens, JWTs, and PEM keys, but this redaction runs only on the **read path** (memory search, status display), not on the write path. **OpenClaw PR #11544** added a `sessions scrub` command for after-the-fact cleanup — the closest existing implementation to transcript-scrub — but it's locked inside the OpenClaw CLI rather than being a standalone tool.

Broader evidence confirms the urgency. **Wiz Research** found hardcoded secrets in **20% of vibe-coded applications**. RedHunt Labs scanned 130,000+ vibe-coded domains and discovered **~25,000 unique leaked secrets** for OpenAI, Google, and ElevenLabs. A Hacker News thread ("Ask HN: Do you sanitize secrets before pasting code into ChatGPT?", February 2026) saw unanimous acknowledgment of the risk with no satisfactory tooling solutions. **DeepSeek exposed 1M+ AI chat logs and API keys** in January 2025, and 4,500+ ChatGPT conversations were indexed by Google due to a sharing toggle mishap.

---

## Cloud DLP services: powerful but impractical as dependencies

Three managed services offer comprehensive detection but impose cloud dependency, latency, and cost that make them poor fits as embedded dependencies.

**Google Cloud DLP** leads with **150+ built-in infoTypes**, format-preserving encryption, date shifting, and crypto-hashing operators at $1-3/GB. **AWS Comprehend** detects 36 PII entity types using proprietary ML models trained on transcribed speech. **AWS Macie** scans S3 objects with 100+ managed data identifiers but is a discovery service, not a text-processing API. All three require sending data to cloud endpoints — a non-starter for a tool whose purpose is preventing sensitive data exposure.

---

## Data masking tools complete the replacement pipeline

For generating realistic replacement data, **Faker** (joke2k/faker, **~18,000 stars**) is the de facto Python standard with 100+ data providers across 70+ locales. **Mimesis** (lk-geimfari/mimesis, ~4,400 stars) offers **10-50× better performance** than Faker but requires Python 3.10+. Both generate independent random values — neither preserves relationships between replaced entities (e.g., ensuring a replaced name stays consistent across a transcript). SDV (Synthetic Data Vault) preserves statistical relationships but targets tabular datasets and carries heavy PyTorch dependencies under a Business Source License.

For `transcript-scrub`, **Faker is the practical choice** for replacement data generation, with a consistency mapping layer built on top to ensure the same original value maps to the same fake value throughout a session.

---

## Recommended dependency architecture for transcript-scrub

No single tool covers the full pipeline. The optimal architecture composes three proven Python libraries with a custom JSONL-aware orchestration layer:

| Layer | Recommended dependency | Role | Alternative |
|-------|----------------------|------|-------------|
| **Secret detection** | `detect-secrets` | API keys, tokens, private keys, entropy analysis | Borrow TruffleHog/Gitleaks regex patterns |
| **PII detection** | `presidio-analyzer` | Names, emails, phones, SSNs, addresses, IPs | `scrubadub` (lighter), `DataFog` (minimal deps) |
| **PII redaction** | `presidio-anonymizer` | Replace/mask/hash with configurable operators | Custom replacement logic |
| **Fake data generation** | `Faker` | Realistic replacement values | `mimesis` (faster, Python 3.10+) |
| **JSONL parsing** | Custom (built-in) | Walk Claude Code session structure | Reference `claude-code-transcripts` parser |
| **Consistency mapping** | Custom (built-in) | Same secret → same replacement across session | — |

The JSONL orchestration layer must handle Claude Code's specific structure: user messages, assistant messages, `tool_use` blocks (where the model invokes bash/read/write), and `tool_result` blocks (where command output — the highest-risk content — lives verbatim). Borrowing OpenClaw's `DEFAULT_REDACT_PATTERNS` for Anthropic-specific tokens (`sk-ant-*`, `xoxb-*`, `AIza*`) would accelerate coverage of the most common AI-ecosystem secrets.

---

## What existing tools cannot do

Five critical gaps justify building transcript-scrub rather than assembling existing tools:

- **JSONL structure awareness**: No scanner understands Claude Code's nested message/tool-use/tool-result schema. Generic text scanning produces false positives on JSON syntax and misses secrets spanning multiple JSON fields.
- **Combined secret + PII detection**: Secret scanners ignore PII; PII detectors ignore API keys. No single tool covers both. Transcript-scrub must fuse both detection engines.
- **Context-aware redaction in code blocks**: Secrets embedded in code snippets, terminal output, and file contents within transcripts require different handling than secrets in prose. Existing tools treat all text uniformly.
- **Consistent replacement mapping**: When `john@example.com` appears 15 times across a session, it must map to the same fake email everywhere. No detection tool maintains this state — it must be built.
- **Publish-ready output**: The tool must preserve transcript readability and structure for HTML rendering by tools like `claude-code-transcripts`, not just flag line numbers or output detection reports.

The ecosystem has mature, battle-tested components for detection (detect-secrets' 20+ plugins, Presidio's 50+ entity types, TruffleHog's 800+ patterns) and replacement (Faker's 100+ providers). What's missing is the **orchestration layer** that reads Claude Code JSONL, walks its structure, routes text through the right detection engines, applies consistent replacements, and writes clean output. That is precisely the value `transcript-scrub` would provide.