# THE SPECTACLE SHOWDOWN

## Two Branches Enter. One Spec. Who Builds It Best?

---

## 1. THE HOOK

Picture this.

A single specification drops into a repository. Two words: **"scrub transcripts."** Strip every API key, every leaked credential, every home directory path, every email address from Claude Code session logs before they see the light of day.

Two builders answer the call.

One is a solo operator -- fast, instinctive, shipping code the way a street fighter throws punches: raw and relentless. The other is an engineering platoon -- methodical, layered, building infrastructure the way you build a cathedral: stone by deliberate stone.

They never saw each other's code. They worked from the same spec. They arrived at *radically* different machines.

Tonight, we tear them both open and ask the only question that matters:

**Which one would you trust with your secrets?**

---

## 2. THE SPEC

A Claude Code transcript scrubber exists for one reason: **people share their AI transcripts publicly**, and those transcripts are *riddled* with secrets.

Think about what appears in a typical Claude Code session:

- `sk-ant-api03-...` Anthropic API keys pasted into prompts
- `ghp_x7KmN2p...` GitHub tokens passed to tool calls
- `AKIA3EXAMPLE...` AWS access keys in CLI output
- `/Users/jane.doe/Documents/secret-project/` home directory paths everywhere
- `jane.doe@company.com` email addresses in git configs
- Database connection strings with embedded passwords
- PEM private keys dumped into terminal output

A scrubber must find all of this. It must replace it with something safe. It must not destroy the transcript's readability. And it must not miss anything -- because one leaked key is one key too many.

The spec calls for: JSONL parsing (local sessions), JSON parsing (web sessions), HTML parsing (exported transcripts), configurable patterns, allowlists, severity levels, and a CLI that works in both human and CI contexts.

Simple enough to describe. Devilishly hard to get right.

Let the showdown begin.

---

## 3. THE CONTENDERS

### The Scrappy Underdog: `claude` Branch (The Solo Build)

Born from a single developer's pragmatic instinct. Four files. 966 lines of source code. No committee, no architecture meetings, no layer diagrams -- just a developer, a spec, and a keyboard.

This branch *moves*. It ships 39 detection patterns covering 20+ distinct providers. It reads HTML, JSONL, and JSON out of the box. Its only dependency is `click`. It carries CI exit codes so your pipeline can gate on leaked secrets. It even detects Claude's own `.credentials.json` content -- a detail that speaks to someone who has *lived* in this ecosystem.

Its philosophy: **do one thing, do it now, ship it.**

### The Engineering Colossus: `team` Branch (The Team Build)

Built by a coordinated team with production ambitions. 2,953 lines of source across a 4-layer pipeline architecture: **Parser -> Scanner -> Redactor -> CLI**. Twenty-two source files organized into four packages. A data model layer (`models.py`) that would make a domain-driven design textbook proud.

This branch *engineers*. It has 257 tests, all passing, verified in 0.18 seconds. Its redaction engine assigns stable numbered placeholders -- `[REDACTED-API-KEY-1]`, `[REDACTED-API-KEY-2]` -- so you can tell two different leaked keys apart in the scrubbed output. It resolves overlapping pattern matches. It ships an interactive review mode with Rich terminal UI. It has built-in allowlists for RFC-5737 documentation IPs and RFC-2606 example domains.

Its philosophy: **build it right, test it thoroughly, make it maintainable.**

---

## 4. THE NUMBERS

Here is the tale of the tape.

| Metric | Claude Branch | Team Branch | Edge |
|--------|:------------:|:-----------:|:----:|
| **Source lines (src/)** | 966 | 2,953 | -- |
| **Source files** | 4 | 22 | -- |
| **Test functions** | 30 | 257 | TEAM |
| **Tests passing** | 0/30 | 257/257 | TEAM |
| **Test execution time** | N/A (broken) | 0.18s | TEAM |
| **Detection patterns** | 39 | 27 | CLAUDE |
| **Provider coverage** | 20+ providers | 12 providers | CLAUDE |
| **Input formats** | JSONL, JSON, HTML | JSONL, JSON | CLAUDE |
| **Dependencies** | 1 (click) | 4 (click, rich, tomli, tomli-w) | CLAUDE |
| **CI exit codes** | Yes (exit 1 on findings) | No | CLAUDE |
| **Stable numbered redactions** | No | Yes | TEAM |
| **Overlap resolution** | No | Yes | TEAM |
| **Interactive review mode** | No | Yes | TEAM |
| **Allowlist system** | Basic (set of strings) | Smart (RFC-aware, per-type) | TEAM |
| **Rich terminal output** | No | Yes (colored diffs, tables) | TEAM |
| **Round-trip fidelity** | Untested | Verified by tests | TEAM |
| **Architecture layers** | 1 (monolith) | 4 (parser/scanner/redactor/cli) | TEAM |
| **Config format** | TOML (basic) | TOML (with interactive updates) | TEAM |

Read that table carefully. It tells two very different stories depending on which column catches your eye.

---

## 5. CROSS-EXAMINATION HIGHLIGHTS

### Five Damning Revelations About the Claude Branch

**Revelation 1: The test suite is theater.**
Thirty test functions exist. Zero pass. The tests import from a module path that was refactored but never updated. This is not "tests need work" -- this is a test suite that has *never run green against the current code*. In a security tool, untested code is untrustworthy code.

**Revelation 2: Two secrets walk into a bar... and come out identical.**
The claude branch replaces every Anthropic API key with `sk-ant-***REDACTED***`. Every single one. If your transcript contained three different leaked keys, the scrubbed output gives you no way to know that. Were they the same key reused? Three different keys? You cannot tell. For forensic review, this is a critical blind spot.

**Revelation 3: Pattern overlap is a land mine.**
The OpenAI pattern `sk-[a-zA-Z0-9]{20,}` matches *before* the Anthropic pattern `sk-ant-[a-zA-Z0-9_\-]{20,}` can. Pattern ordering matters, and there is no overlap resolution engine. The same string can be partially redacted by one pattern, then mangled by another. The code applies patterns sequentially with `re.sub` in a loop -- the classic "regex chain of destruction" anti-pattern.

**Revelation 4: HTML scrubbing is brave but naive.**
The HTML parser splits on `<[^>]+>` and scrubs both tags and text nodes. This works for simple cases, but any attribute containing a `>` character, any inline JavaScript, any CDATA section -- all of these will break the split and potentially leak secrets through parser confusion.

**Revelation 5: No data model means no contract.**
There is no intermediate representation. Raw strings go in, scrubbed strings come out. The scrubber cannot tell you *where* in the transcript structure a secret was found -- only "line 42" or "text@17". This makes debugging false positives a manual archaeology exercise.

---

### Five Damning Revelations About the Team Branch

**Revelation 1: HTML is a foreign language.**
The team branch cannot read HTML at all. Its parser registry contains exactly two parsers: JSONL and JSON Web. If someone hands it an HTML transcript export, it throws a `ValueError`. For a scrubber that claims production readiness, this is a format gap that real users will hit.

**Revelation 2: Twelve missing provider patterns.**
The claude branch detects Vercel tokens, Supabase keys, Cloudflare API tokens, Netlify tokens, SendGrid keys, Twilio keys, npm tokens, PyPI tokens, Google API keys, and more. The team branch detects... none of these. Its API key scanner covers 7 named providers plus generic patterns. In a world where developers use dozens of SaaS services, those missing patterns are real secrets that walk through undetected.

**Revelation 3: No CI exit codes -- the pipeline is blind.**
The team branch CLI does not set a non-zero exit code when secrets are found. In a CI/CD pipeline, `claude-code-scrubber scan transcript.jsonl` will always exit 0 whether it found 100 secrets or none. The scan command exists, but it cannot gate a pipeline. For the DevSecOps use case, this is a showstopper.

**Revelation 4: Four dependencies where one would do.**
`click`, `rich`, `tomli`, `tomli-w`. The Rich dependency alone pulls in a tree of sub-dependencies. For a security-sensitive tool that users install into their development environments, a minimal dependency surface is a feature, not a limitation. Every dependency is an attack surface.

**Revelation 5: 2,953 lines to do what 966 lines also do.**
Three times the code means three times the surface area for bugs, three times the code to audit, three times the maintenance burden. The team branch is undeniably more *capable*, but capability has a carrying cost. The 4-layer architecture is elegant -- but is it *necessary* for what is fundamentally a regex-and-replace tool?

---

## 6. THE VERDICT

Here is the uncomfortable truth that neither side wants to hear:

**Neither branch is ready for production.**

The claude branch has the *instincts* of a great tool -- broader detection, lighter footprint, format flexibility -- but it ships with a broken test suite and no overlap resolution. You cannot deploy a security tool that has never proven it works. That is not pragmatism; it is negligence dressed in a shipping jacket.

The team branch has the *engineering* of a great tool -- tested, layered, maintainable, with features like stable numbering that matter deeply in practice -- but it has format gaps, pattern gaps, and cannot integrate into a CI pipeline. You cannot call a tool production-ready when it misses entire categories of secrets and cannot gate a deployment.

**But if forced to choose -- and we are forced to choose -- the team branch wins.**

Why? Because a tested, architecturally sound codebase with missing features is a *solvable problem*. Adding 12 more regex patterns to a well-tested scanner registry is a pull request. Adding an HTML parser that implements the `BaseParser` interface is a pull request. Adding `sys.exit(1)` to the scan command is a one-line change.

But taking an untested monolith with overlapping patterns and no data model and retrofitting it with stable numbering, overlap resolution, and round-trip fidelity? That is a *rewrite*. You would tear out the sequential `re.sub` loop and replace it with a position-tracking engine. You would invent the data model that the team branch already has. You would, in effect, arrive at the team branch's architecture -- having spent twice the effort to get there.

**The team branch is closer to done. The claude branch would need to become the team branch to finish.**

---

## 7. LESSONS AND WHEN TO USE WHAT

### If you need a quick one-off scrub of a single transcript...

**Choose the claude branch.** Fix the import path in the tests (a 5-minute fix), verify the patterns work, and run it. Its single-file simplicity means you can read the entire codebase in 15 minutes. For a one-time "scrub this before I post it on Twitter" use case, it is perfectly adequate.

### If you are building scrubbing into a team workflow or CI pipeline...

**Choose the team branch.** Its architecture was built for exactly this. The parser/scanner/redactor separation means you can swap components without rewriting the pipeline. The stable numbered redactions mean your team can discuss "REDACTED-API-KEY-2" in a code review without confusion. Add the CI exit codes (a trivial patch) and you have a pipeline-ready tool.

### If you are auditing transcripts for security compliance...

**Choose the team branch.** The overlap resolution and stable numbering are not nice-to-haves -- they are requirements. You need to know that every finding is distinct, that nothing was double-redacted into gibberish, and that the redaction map gives you an auditable trail from original to replacement.

### If you care about detection breadth above all else...

**Choose the claude branch's pattern library, transplanted into the team branch's scanner registry.** This is the real answer. The claude branch's 39 patterns are the most comprehensive catalog in this repository. The team branch's scanner architecture is the most robust execution engine. Marry them.

### The meta-lesson...

Speed without correctness is dangerous. Correctness without coverage is incomplete. The best tool is the one that ships both -- and neither branch has arrived there yet.

But the path from the team branch to that destination is shorter, straighter, and paved with 257 green tests.

**That is the Spectacle's verdict. The show is over. Now build the merge.**

---

*Generated by Spectacle -- the narrative engine that turns branch diffs into drama.*
