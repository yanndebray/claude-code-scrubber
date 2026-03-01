"""Tests for PII detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.pii import PIIDetector


@pytest.fixture
def detector():
    return PIIDetector()


class TestEmails:
    def test_detects_standard_email(self, detector):
        text = "Contact me at john.doe@company.com for details."
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 1
        assert email_findings[0].matched_text == "john.doe@company.com"
        assert email_findings[0].confidence == Confidence.HIGH

    def test_detects_email_with_plus(self, detector):
        text = "Email: user+tag@domain.co.uk"
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 1

    def test_skips_safe_email(self, detector):
        text = "Send to test@example.com for testing."
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 0

    def test_skips_noreply_github(self, detector):
        text = "From noreply@github.com"
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 0

    def test_skips_example_domain(self, detector):
        text = "Contact admin@example.org"
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 0

    def test_no_false_positive_at_sign(self, detector):
        text = "Use @decorator for this function."
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 0


class TestPhoneNumbers:
    def test_detects_us_dashed(self, detector):
        text = "Call me at 555-123-4567."
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) == 1

    def test_detects_us_parenthesized(self, detector):
        text = "Phone: (555) 123-4567"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) == 1

    def test_detects_us_with_country_code(self, detector):
        text = "Reach me at +1-555-123-4567"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) >= 1

    def test_detects_international_phone(self, detector):
        text = "UK phone: +44 20 7946 0958"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) >= 1

    def test_no_false_positive_short_number(self, detector):
        text = "Error code: 404"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) == 0

    def test_confidence_is_medium(self, detector):
        text = "Phone: 555-123-4567"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) == 1
        assert phone_findings[0].confidence == Confidence.MEDIUM


class TestAddresses:
    def test_detects_street_address(self, detector):
        text = "Ship to 123 Main Street"
        findings = detector.scan(text)
        addr_findings = [f for f in findings if f.category == "ADDRESS"]
        assert len(addr_findings) == 1

    def test_detects_avenue(self, detector):
        text = "Located at 456 Park Avenue"
        findings = detector.scan(text)
        addr_findings = [f for f in findings if f.category == "ADDRESS"]
        assert len(addr_findings) == 1

    def test_detects_blvd(self, detector):
        text = "Office at 789 Sunset Blvd"
        findings = detector.scan(text)
        addr_findings = [f for f in findings if f.category == "ADDRESS"]
        assert len(addr_findings) == 1

    def test_no_false_positive_number_alone(self, detector):
        text = "Version 123 is the latest."
        findings = detector.scan(text)
        addr_findings = [f for f in findings if f.category == "ADDRESS"]
        assert len(addr_findings) == 0


class TestNamesInContext:
    def test_detects_username_assignment(self, detector):
        text = 'username="John Smith"'
        findings = detector.scan(text)
        name_findings = [f for f in findings if f.category == "NAME"]
        assert len(name_findings) == 1
        assert name_findings[0].matched_text == "John Smith"

    def test_detects_git_author(self, detector):
        text = "Author: Jane Doe <jane@company.com>"
        findings = detector.scan(text)
        name_findings = [f for f in findings if f.category == "NAME"]
        assert len(name_findings) >= 1
        assert any(f.matched_text == "Jane Doe" for f in name_findings)

    def test_detects_author_assignment(self, detector):
        text = 'author="Alice Johnson"'
        findings = detector.scan(text)
        name_findings = [f for f in findings if f.category == "NAME"]
        assert len(name_findings) == 1

    def test_no_false_positive_just_name(self, detector):
        """Names without PII context should not be detected."""
        text = "The function returns a string."
        findings = detector.scan(text)
        name_findings = [f for f in findings if f.category == "NAME"]
        assert len(name_findings) == 0


class TestCharPositions:
    def test_email_positions(self, detector):
        text = "email: user@real-domain.com ok"
        findings = detector.scan(text)
        email_findings = [f for f in findings if f.category == "EMAIL"]
        assert len(email_findings) == 1
        f = email_findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text

    def test_phone_positions(self, detector):
        text = "phone: 555-123-4567 done"
        findings = detector.scan(text)
        phone_findings = [f for f in findings if f.category == "PHONE"]
        assert len(phone_findings) == 1
        f = phone_findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text
