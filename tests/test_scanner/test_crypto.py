"""Tests for crypto material detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.crypto import CryptoDetector


@pytest.fixture
def detector():
    return CryptoDetector()


class TestPEMBlocks:
    def test_detects_private_key(self, detector):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MhgHcTz6sE2I2yPB\n"
            "aFDrBz3tCP46B+PaFQtFYGLgyA=\n"
            "-----END RSA PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        assert len(findings) >= 1
        pk_findings = [f for f in findings if f.category == "PRIVATE-KEY"]
        assert len(pk_findings) == 1
        assert pk_findings[0].confidence == Confidence.HIGH

    def test_detects_ec_private_key(self, detector):
        text = (
            "-----BEGIN EC PRIVATE KEY-----\n"
            "MHQCAQEEIBkg4LVWM9nuwNSk3yByxZpYRTBnVJk5GhEkp6tMcTChBwYFK4EEAAOD\n"
            "-----END EC PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        pk_findings = [f for f in findings if f.category == "PRIVATE-KEY"]
        assert len(pk_findings) == 1

    def test_detects_certificate(self, detector):
        text = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIDXTCCAkWgAwIBAgIJAJC1HiIAZAiUMA0GCSqGSIb3Qw0BAQsFADAvMQswCQYD\n"
            "-----END CERTIFICATE-----"
        )
        findings = detector.scan(text)
        cert_findings = [f for f in findings if f.category == "CERTIFICATE"]
        assert len(cert_findings) == 1
        assert cert_findings[0].confidence == Confidence.MEDIUM

    def test_detects_openssh_private_key(self, detector):
        text = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAA\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        pk_findings = [f for f in findings if f.category == "PRIVATE-KEY"]
        assert len(pk_findings) == 1


class TestSSHPublicKeys:
    def test_detects_ssh_rsa_pubkey(self, detector):
        text = (
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7FK2n6s"
            "7GqKr7Nap4gTKhWxMDFjzL3NmMR5S0t9JzBT3XH4ZHBfk"
            "AAAA user@host"
        )
        findings = detector.scan(text)
        ssh_findings = [f for f in findings if f.category == "SSH-PUBKEY"]
        assert len(ssh_findings) == 1
        assert ssh_findings[0].confidence == Confidence.LOW

    def test_detects_ssh_ed25519_pubkey(self, detector):
        text = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl user@host"
        findings = detector.scan(text)
        ssh_findings = [f for f in findings if f.category == "SSH-PUBKEY"]
        assert len(ssh_findings) == 1


class TestJWTs:
    def test_detects_jwt(self, detector):
        text = (
            "token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        findings = detector.scan(text)
        jwt_findings = [f for f in findings if f.category == "JWT"]
        assert len(jwt_findings) == 1
        assert jwt_findings[0].confidence == Confidence.HIGH

    def test_no_false_positive_short_dots(self, detector):
        text = "version 1.2.3 is released"
        findings = detector.scan(text)
        jwt_findings = [f for f in findings if f.category == "JWT"]
        assert len(jwt_findings) == 0


class TestGitCredentials:
    def test_detects_git_credential(self, detector):
        text = "https://user:token123@github.com/org/repo.git"
        findings = detector.scan(text)
        git_findings = [f for f in findings if f.category == "GIT-CREDENTIAL"]
        assert len(git_findings) == 1
        assert git_findings[0].confidence == Confidence.HIGH

    def test_detects_http_credential(self, detector):
        text = "http://admin:password@internal-gitlab.com/project.git"
        findings = detector.scan(text)
        git_findings = [f for f in findings if f.category == "GIT-CREDENTIAL"]
        assert len(git_findings) == 1


class TestEdgeCases:
    def test_multiple_pem_blocks(self, detector):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\ndata1\n-----END RSA PRIVATE KEY-----\n"
            "some text\n"
            "-----BEGIN CERTIFICATE-----\ndata2\n-----END CERTIFICATE-----"
        )
        findings = detector.scan(text)
        assert len(findings) >= 2
        categories = {f.category for f in findings}
        assert "PRIVATE-KEY" in categories
        assert "CERTIFICATE" in categories

    def test_no_false_positive_begin_only(self, detector):
        """A BEGIN without matching END should not match PEM."""
        text = "-----BEGIN RSA PRIVATE KEY----- but no end"
        findings = detector.scan(text)
        pem_findings = [f for f in findings if f.category in ("PRIVATE-KEY", "CERTIFICATE")]
        assert len(pem_findings) == 0


class TestCharPositions:
    def test_jwt_positions(self, detector):
        prefix = "token="
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        text = prefix + jwt
        findings = detector.scan(text)
        jwt_findings = [f for f in findings if f.category == "JWT"]
        assert len(jwt_findings) == 1
        f = jwt_findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text

    def test_pem_positions(self, detector):
        text = (
            "key:\n"
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIBVQIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7\n"
            "-----END PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        pk_findings = [f for f in findings if f.category == "PRIVATE-KEY"]
        assert len(pk_findings) == 1
        f = pk_findings[0]
        assert text[f.char_start : f.char_end] == f.matched_text
