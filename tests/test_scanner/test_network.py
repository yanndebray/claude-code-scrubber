"""Tests for network detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.network import NetworkDetector


@pytest.fixture
def detector():
    return NetworkDetector()


class TestIPv4:
    def test_detects_private_ip(self, detector):
        text = "Server running on 10.0.1.42"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 1
        assert ipv4[0].matched_text == "10.0.1.42"
        assert ipv4[0].confidence == Confidence.HIGH

    def test_detects_public_ip(self, detector):
        text = "External IP: 54.239.28.85"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 1

    def test_skips_localhost(self, detector):
        text = "Listening on 127.0.0.1:8080"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 0

    def test_skips_all_zeros(self, detector):
        text = "Bind to 0.0.0.0:3000"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 0

    def test_skips_rfc5737_test_net(self, detector):
        text = "Example: 192.0.2.1"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 0

    def test_skips_subnet_mask(self, detector):
        text = "Subnet mask: 255.255.255.0"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 0

    def test_no_false_positive_version_numbers(self, detector):
        text = "python 3.10.12"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 0


class TestIPv6:
    def test_detects_full_ipv6(self, detector):
        text = "Address: 2607:f8b0:4004:0800:0000:0000:0000:200e"
        findings = detector.scan(text)
        ipv6 = [f for f in findings if f.category == "IPV6"]
        assert len(ipv6) == 1

    def test_skips_loopback(self, detector):
        text = "Localhost IPv6: ::1"
        findings = detector.scan(text)
        ipv6 = [f for f in findings if f.category == "IPV6"]
        assert len(ipv6) == 0

    def test_skips_documentation_prefix(self, detector):
        text = "Example: 2001:db8::1"
        findings = detector.scan(text)
        ipv6 = [f for f in findings if f.category == "IPV6"]
        assert len(ipv6) == 0


class TestInternalHostnames:
    def test_detects_internal_domain(self, detector):
        text = "Connect to api.service.internal"
        findings = detector.scan(text)
        host_findings = [f for f in findings if f.category == "INTERNAL-HOST"]
        assert len(host_findings) == 1
        assert host_findings[0].confidence == Confidence.MEDIUM

    def test_detects_corp_domain(self, detector):
        text = "VPN: vpn.mycompany.corp"
        findings = detector.scan(text)
        host_findings = [f for f in findings if f.category == "INTERNAL-HOST"]
        assert len(host_findings) == 1

    def test_detects_local_domain(self, detector):
        text = "mDNS: myserver.local"
        findings = detector.scan(text)
        host_findings = [f for f in findings if f.category == "INTERNAL-HOST"]
        assert len(host_findings) == 1

    def test_detects_private_domain(self, detector):
        text = "Database at db.staging.private"
        findings = detector.scan(text)
        host_findings = [f for f in findings if f.category == "INTERNAL-HOST"]
        assert len(host_findings) == 1


class TestAWSAccountIDs:
    def test_detects_account_in_arn(self, detector):
        text = "arn:aws:iam::123456789012:role/MyRole"
        findings = detector.scan(text)
        aws_findings = [f for f in findings if f.category == "AWS-ACCOUNT-ID"]
        assert len(aws_findings) == 1
        assert aws_findings[0].matched_text == "123456789012"
        assert aws_findings[0].confidence == Confidence.MEDIUM

    def test_detects_account_in_s3_arn(self, detector):
        text = "arn:aws:s3:us-east-1:987654321098:bucket/my-bucket"
        findings = detector.scan(text)
        aws_findings = [f for f in findings if f.category == "AWS-ACCOUNT-ID"]
        assert len(aws_findings) == 1

    def test_no_false_positive_random_12_digits(self, detector):
        """12-digit numbers outside ARN context should not match."""
        text = "Order number: 123456789012"
        findings = detector.scan(text)
        aws_findings = [f for f in findings if f.category == "AWS-ACCOUNT-ID"]
        assert len(aws_findings) == 0


class TestECRRegistries:
    def test_detects_ecr_registry(self, detector):
        text = "Pull from 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app:latest"
        findings = detector.scan(text)
        reg_findings = [f for f in findings if f.category == "PRIVATE-REGISTRY"]
        assert len(reg_findings) == 1


class TestCharPositions:
    def test_ipv4_positions(self, detector):
        text = "Server at 10.0.1.42 is running"
        findings = detector.scan(text)
        ipv4 = [f for f in findings if f.category == "IPV4"]
        assert len(ipv4) == 1
        f = ipv4[0]
        assert text[f.char_start : f.char_end] == f.matched_text

    def test_aws_account_positions(self, detector):
        text = "arn:aws:iam::123456789012:user/admin"
        findings = detector.scan(text)
        aws_findings = [f for f in findings if f.category == "AWS-ACCOUNT-ID"]
        assert len(aws_findings) == 1
        f = aws_findings[0]
        assert text[f.char_start : f.char_end] == "123456789012"
