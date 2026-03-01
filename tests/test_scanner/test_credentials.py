"""Tests for credentials detector."""

import pytest

from transcript_scrub.models import Confidence
from transcript_scrub.scanner.credentials import CredentialsDetector


@pytest.fixture
def detector():
    return CredentialsDetector()


class TestPEMKeys:
    def test_detects_rsa_private_key(self, detector):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MhgHcTz6sE2I2yPB\n"
            "-----END RSA PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "PRIVATE-KEY" for f in findings)

    def test_detects_generic_private_key(self, detector):
        text = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIBVQIBADANBgkqhkiG9w0BAQEFAASCAT8wggE7AgEAAkEA\n"
            "-----END PRIVATE KEY-----"
        )
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_no_match_for_public_key(self, detector):
        """Public keys should not be matched by the credentials PEM pattern."""
        text = (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n"
            "-----END PUBLIC KEY-----"
        )
        findings = detector.scan(text)
        # The credentials detector specifically looks for PRIVATE KEY
        private_findings = [f for f in findings if f.category == "PRIVATE-KEY"]
        assert len(private_findings) == 0


class TestPasswordAssignments:
    def test_detects_quoted_password(self, detector):
        text = 'password="SuperSecret123!"'
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "CREDENTIAL" for f in findings)

    def test_detects_unquoted_password(self, detector):
        text = "password=MyS3cretP@ss"
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_detects_secret_assignment(self, detector):
        text = 'secret="very_secret_value_123"'
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_detects_token_assignment(self, detector):
        text = 'token="abc123def456ghi789"'
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_skips_placeholder_password(self, detector):
        text = 'password="changeme"'
        findings = detector.scan(text)
        cred_findings = [f for f in findings if f.category == "CREDENTIAL"]
        assert len(cred_findings) == 0

    def test_skips_placeholder_secret(self, detector):
        text = "password=placeholder"
        findings = detector.scan(text)
        cred_findings = [f for f in findings if f.category == "CREDENTIAL"]
        assert len(cred_findings) == 0


class TestDatabaseURIs:
    def test_detects_postgres_uri(self, detector):
        text = "DATABASE_URL=postgres://admin:s3cret@db.example.internal:5432/mydb"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "DB-URI" for f in findings)

    def test_detects_mysql_uri(self, detector):
        text = "mysql://root:password123@mysql.internal:3306/app"
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_detects_mongodb_uri(self, detector):
        text = "mongodb+srv://user:pass@cluster0.abc123.mongodb.net/mydb"
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_detects_redis_uri(self, detector):
        text = "redis://default:mypassword@redis.internal:6379/0"
        findings = detector.scan(text)
        assert len(findings) >= 1


class TestAuthHeaders:
    def test_detects_bearer_token(self, detector):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "AUTH-HEADER" for f in findings)

    def test_detects_basic_auth(self, detector):
        text = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        findings = detector.scan(text)
        assert len(findings) >= 1


class TestEnvSecrets:
    def test_detects_env_secret(self, detector):
        text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "ENV-SECRET" for f in findings)

    def test_detects_env_token(self, detector):
        text = "GITHUB_AUTH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        findings = detector.scan(text)
        assert len(findings) >= 1

    def test_skips_placeholder_env(self, detector):
        text = "MY_SECRET_KEY=placeholder"
        findings = detector.scan(text)
        env_findings = [f for f in findings if f.category == "ENV-SECRET"]
        assert len(env_findings) == 0


class TestCookieHeaders:
    def test_detects_cookie(self, detector):
        text = "Cookie: session=abc123def456; csrf_token=xyz789"
        findings = detector.scan(text)
        assert len(findings) >= 1
        assert any(f.category == "COOKIE" for f in findings)


class TestCharPositions:
    def test_positions_accurate(self, detector):
        text = 'config: password="ReallySecret123"'
        findings = detector.scan(text)
        assert len(findings) >= 1
        for f in findings:
            assert text[f.char_start : f.char_end] == f.matched_text

    def test_no_false_positives_normal_text(self, detector):
        text = "The user needs to set a password in their settings."
        findings = detector.scan(text)
        assert len(findings) == 0
