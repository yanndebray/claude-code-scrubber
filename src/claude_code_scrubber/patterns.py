"""
Detection patterns for secrets, API keys, PII, and sensitive data.

Each pattern is a dict with:
  - name: human-readable label
  - pattern: compiled regex
  - replacement: what to substitute (can use \\1, \\2 for groups)
  - severity: "high" (API keys, passwords) | "medium" (emails, IPs) | "low" (paths)
"""

import re
from dataclasses import dataclass, field


@dataclass
class ScrubPattern:
    name: str
    pattern: re.Pattern
    replacement: str
    severity: str = "high"
    enabled: bool = True


def build_patterns(username: str | None = None) -> list[ScrubPattern]:
    """Build the full list of scrub patterns.

    Args:
        username: If provided, also scrub OS username from paths.
    """
    patterns: list[ScrubPattern] = []

    # ── API Keys & Tokens (high) ──────────────────────────────────────────

    patterns.append(ScrubPattern(
        name="Anthropic API key",
        pattern=re.compile(r'sk-ant-[a-zA-Z0-9_\-]{20,}'),
        replacement="sk-ant-***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="OpenAI API key",
        pattern=re.compile(r'sk-[a-zA-Z0-9]{20,}'),
        replacement="sk-***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="OpenAI project key",
        pattern=re.compile(r'sk-proj-[a-zA-Z0-9_\-]{20,}'),
        replacement="sk-proj-***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="GitHub token (classic)",
        pattern=re.compile(r'ghp_[a-zA-Z0-9]{36,}'),
        replacement="ghp_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="GitHub OAuth token",
        pattern=re.compile(r'gho_[a-zA-Z0-9]{36,}'),
        replacement="gho_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="GitHub App token",
        pattern=re.compile(r'(?:ghu|ghs|ghr)_[a-zA-Z0-9]{36,}'),
        replacement="gh*_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="GitHub fine-grained PAT",
        pattern=re.compile(r'github_pat_[a-zA-Z0-9_]{22,}'),
        replacement="github_pat_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="AWS access key",
        pattern=re.compile(r'(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}'),
        replacement="AKIA***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="AWS secret key",
        pattern=re.compile(
            r'''(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY|secret_access_key)'''
            r'''[\s]*[=:]\s*['"]?([a-zA-Z0-9/+=]{40})['"]?'''
        ),
        replacement="***AWS_SECRET_REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Google API key",
        pattern=re.compile(r'AIza[a-zA-Z0-9_\-]{35}'),
        replacement="AIza***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Slack token",
        pattern=re.compile(r'xox[bposatrce]-[a-zA-Z0-9\-]{10,}'),
        replacement="xox?-***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Stripe key",
        pattern=re.compile(r'(?:sk|pk|rk)_(?:test|live)_[a-zA-Z0-9]{10,}'),
        replacement="s?_****_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="HuggingFace token",
        pattern=re.compile(r'hf_[a-zA-Z0-9]{34,}'),
        replacement="hf_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="npm token",
        pattern=re.compile(r'npm_[a-zA-Z0-9]{36,}'),
        replacement="npm_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="PyPI token",
        pattern=re.compile(r'pypi-[a-zA-Z0-9_\-]{50,}'),
        replacement="pypi-***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Vercel token",
        pattern=re.compile(r'vercel_[a-zA-Z0-9_\-]{20,}'),
        replacement="vercel_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Supabase key",
        pattern=re.compile(r'sbp_[a-zA-Z0-9]{40,}'),
        replacement="sbp_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Cloudflare API token",
        pattern=re.compile(r'[a-f0-9]{37}'),  # too broad alone; handled contextually
        replacement="***CF_TOKEN_REDACTED***",
        enabled=False,  # disabled by default, too many false positives
    ))

    patterns.append(ScrubPattern(
        name="Netlify token",
        pattern=re.compile(r'nfp_[a-zA-Z0-9]{40,}'),
        replacement="nfp_***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="SendGrid key",
        pattern=re.compile(r'SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}'),
        replacement="SG.***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Twilio key",
        pattern=re.compile(r'SK[a-f0-9]{32}'),
        replacement="SK***REDACTED***",
    ))

    # ── Generic secrets in env/config (high) ──────────────────────────────

    patterns.append(ScrubPattern(
        name="Generic secret assignment",
        pattern=re.compile(
            r'''((?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|ACCESS_KEY|AUTH|CREDENTIAL)'''
            r'''[\w]*)'''
            r'''(\s*[=:]\s*)'''
            r'''(['"]?)([^\s'"]{8,})(\3)''',
            re.IGNORECASE,
        ),
        replacement=r"\1\2\3***REDACTED***\5",
    ))

    # ── Bearer / Authorization tokens (high) ──────────────────────────────

    patterns.append(ScrubPattern(
        name="Bearer token",
        pattern=re.compile(
            r'(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}',
            re.IGNORECASE,
        ),
        replacement=r"\1***REDACTED***",
    ))

    patterns.append(ScrubPattern(
        name="Basic auth header",
        pattern=re.compile(
            r'(Basic\s+)[a-zA-Z0-9+/=]{20,}',
            re.IGNORECASE,
        ),
        replacement=r"\1***REDACTED***",
    ))

    # ── SSH / Crypto keys (high) ──────────────────────────────────────────

    patterns.append(ScrubPattern(
        name="Private key block",
        pattern=re.compile(
            r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----'
            r'[\s\S]*?'
            r'-----END (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----'
        ),
        replacement="-----PRIVATE KEY REDACTED-----",
    ))

    # ── JWT tokens (high) ─────────────────────────────────────────────────

    patterns.append(ScrubPattern(
        name="JWT token",
        pattern=re.compile(
            r'eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]+'
        ),
        replacement="***JWT_REDACTED***",
    ))

    # ── Database connection strings (high) ─────────────────────────────────

    patterns.append(ScrubPattern(
        name="Database connection string",
        pattern=re.compile(
            r'(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql)'
            r'://[^\s"\'`<>]{10,}',
            re.IGNORECASE,
        ),
        replacement="***DB_CONNECTION_REDACTED***",
    ))

    # ── PII: email addresses (medium) ─────────────────────────────────────

    patterns.append(ScrubPattern(
        name="Email address",
        pattern=re.compile(
            r'[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}'
        ),
        replacement="***@***.***",
        severity="medium",
    ))

    # ── PII: private IP addresses (medium) ────────────────────────────────

    patterns.append(ScrubPattern(
        name="Private IPv4 (10.x.x.x)",
        pattern=re.compile(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        replacement="10.x.x.x",
        severity="medium",
    ))

    patterns.append(ScrubPattern(
        name="Private IPv4 (192.168.x.x)",
        pattern=re.compile(r'\b192\.168\.\d{1,3}\.\d{1,3}\b'),
        replacement="192.168.x.x",
        severity="medium",
    ))

    patterns.append(ScrubPattern(
        name="Private IPv4 (172.16-31.x.x)",
        pattern=re.compile(r'\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b'),
        replacement="172.x.x.x",
        severity="medium",
    ))

    # ── File paths with username (low) ────────────────────────────────────

    if username:
        # macOS / Linux home directory paths
        patterns.append(ScrubPattern(
            name="Home directory path (macOS)",
            pattern=re.compile(
                rf'/Users/{re.escape(username)}(?=/|$|["\'\\s])'
            ),
            replacement="/Users/REDACTED_USER",
            severity="low",
        ))
        patterns.append(ScrubPattern(
            name="Home directory path (Linux)",
            pattern=re.compile(
                rf'/home/{re.escape(username)}(?=/|$|["\'\\s])'
            ),
            replacement="/home/REDACTED_USER",
            severity="low",
        ))
        # Windows
        patterns.append(ScrubPattern(
            name="Home directory path (Windows)",
            pattern=re.compile(
                rf'C:\\\\Users\\\\{re.escape(username)}(?=\\\\|$|["\'\\s])',
                re.IGNORECASE,
            ),
            replacement="C:\\\\Users\\\\REDACTED_USER",
            severity="low",
        ))
        # Also the encoded form used in ~/.claude/projects/ paths
        patterns.append(ScrubPattern(
            name="Encoded home path in Claude project dir",
            pattern=re.compile(
                rf'-Users-{re.escape(username)}-'
            ),
            replacement="-Users-REDACTED_USER-",
            severity="low",
        ))
        patterns.append(ScrubPattern(
            name="Encoded home path in Claude project dir (Linux)",
            pattern=re.compile(
                rf'-home-{re.escape(username)}-'
            ),
            replacement="-home-REDACTED_USER-",
            severity="low",
        ))
        # The tilde shorthand
        patterns.append(ScrubPattern(
            name="Username in general text",
            pattern=re.compile(
                rf'(?<=[/\\@]){re.escape(username)}(?=[/\\@\s"\'.,;:!?\)\]}}]|$)'
            ),
            replacement="REDACTED_USER",
            severity="low",
        ))

    # ── Hostname in prompts (low) ─────────────────────────────────────────
    # e.g., "user@hostname:" in bash prompts
    patterns.append(ScrubPattern(
        name="Shell prompt with user@host",
        pattern=re.compile(
            r'([a-zA-Z0-9_\-]+)@([a-zA-Z0-9_\-]+\.local)\b'
        ),
        replacement=r"user@host.local",
        severity="low",
    ))

    # ── Claude credentials file (high) ────────────────────────────────────

    patterns.append(ScrubPattern(
        name="Claude .credentials.json content",
        pattern=re.compile(
            r'"(?:oauth_token|api_key|session_key)"'
            r'\s*:\s*"[^"]{10,}"'
        ),
        replacement='"***":"***REDACTED***"',
    ))

    return patterns


# ── Custom pattern support ────────────────────────────────────────────────

def pattern_from_string(name: str, regex_str: str, replacement: str,
                        severity: str = "high") -> ScrubPattern:
    """Create a ScrubPattern from a user-supplied regex string."""
    return ScrubPattern(
        name=name,
        pattern=re.compile(regex_str),
        replacement=replacement,
        severity=severity,
    )
