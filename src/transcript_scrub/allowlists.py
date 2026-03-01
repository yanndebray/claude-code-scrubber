"""Built-in allowlists for known-safe patterns that should not be redacted."""

from __future__ import annotations

# RFC 5737 documentation IP addresses (safe to keep)
SAFE_IPV4 = {
    "192.0.2.0/24",  # TEST-NET-1
    "198.51.100.0/24",  # TEST-NET-2
    "203.0.113.0/24",  # TEST-NET-3
}

# RFC 3849 documentation IPv6
SAFE_IPV6_PREFIX = "2001:db8:"

# Known example/documentation domains (RFC 2606)
SAFE_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "test.com",
    "localhost",
}

# Known placeholder/example email addresses
SAFE_EMAILS = {
    "test@example.com",
    "user@example.com",
    "admin@example.com",
    "noreply@example.com",
    "hello@example.com",
    "foo@bar.com",
    "user@localhost",
    "noreply@anthropic.com",
    "noreply@github.com",
}

# Known safe API key prefixes that are clearly test/example keys
SAFE_API_KEY_PATTERNS = {
    "sk-test-",
    "sk_test_",
    "pk_test_",
    "test-key-",
}

# Common placeholder values that appear in documentation
SAFE_PLACEHOLDER_VALUES = {
    "your-api-key-here",
    "YOUR_API_KEY",
    "INSERT_KEY_HERE",
    "xxx",
    "***",
    "placeholder",
    "changeme",
}

# Loopback and link-local IPs that are safe
SAFE_SPECIAL_IPS = {
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "255.255.255.255",
    "255.255.255.0",
}

# Common example paths used in documentation
SAFE_PATHS = {
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/etc",
    "/tmp",
    "/var",
    "/dev/null",
    "/dev/stdin",
    "/dev/stdout",
    "/dev/stderr",
}


def is_safe_ipv4(ip: str) -> bool:
    """Check if an IPv4 address is in a known-safe documentation range."""
    if ip in SAFE_SPECIAL_IPS:
        return True
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    # Check RFC 5737 ranges
    if octets[0] == 192 and octets[1] == 0 and octets[2] == 2:
        return True
    if octets[0] == 198 and octets[1] == 51 and octets[2] == 100:
        return True
    if octets[0] == 203 and octets[1] == 0 and octets[2] == 113:
        return True
    return False


def is_safe_email(email: str) -> bool:
    """Check if an email is a known-safe placeholder."""
    lower = email.lower()
    if lower in SAFE_EMAILS:
        return True
    # Check if domain is a safe domain
    domain = lower.split("@")[-1] if "@" in lower else ""
    return domain in SAFE_DOMAINS


def is_safe_domain(domain: str) -> bool:
    """Check if a domain is a known-safe documentation domain."""
    lower = domain.lower()
    return lower in SAFE_DOMAINS or lower.endswith((".example.com", ".example.org", ".example.net"))
