"""Tests for token encryption/decryption."""

from __future__ import annotations

import pytest

from pilot_common.crypto import decrypt, encrypt


class TestCrypto:
    def test_round_trip(self, tmp_secrets_dir):
        original = "my-secret-refresh-token-abc123"
        encrypted = encrypt(original, secrets_dir=tmp_secrets_dir)
        decrypted = decrypt(encrypted, secrets_dir=tmp_secrets_dir)
        assert decrypted == original

    def test_encrypted_differs_from_plaintext(self, tmp_secrets_dir):
        original = "my-secret-token"
        encrypted = encrypt(original, secrets_dir=tmp_secrets_dir)
        assert encrypted != original

    def test_different_passphrases_incompatible(self, tmp_secrets_dir):
        original = "my-secret-token"
        encrypted = encrypt(original, passphrase=b"pass-a", secrets_dir=tmp_secrets_dir)
        with pytest.raises(Exception):
            decrypt(encrypted, passphrase=b"pass-b", secrets_dir=tmp_secrets_dir)

    def test_salt_file_created(self, tmp_secrets_dir):
        encrypt("test", secrets_dir=tmp_secrets_dir)
        salt_file = tmp_secrets_dir / "device.salt"
        assert salt_file.exists()
        assert len(salt_file.read_bytes()) == 32

    def test_salt_reused_across_calls(self, tmp_secrets_dir):
        encrypt("test1", secrets_dir=tmp_secrets_dir)
        salt1 = (tmp_secrets_dir / "device.salt").read_bytes()
        encrypt("test2", secrets_dir=tmp_secrets_dir)
        salt2 = (tmp_secrets_dir / "device.salt").read_bytes()
        assert salt1 == salt2

    def test_consistent_key_derivation(self, tmp_secrets_dir):
        """Same passphrase + same salt = same encryption key."""
        original = "consistent-token"
        enc1 = encrypt(original, passphrase=b"mypass", secrets_dir=tmp_secrets_dir)
        dec1 = decrypt(enc1, passphrase=b"mypass", secrets_dir=tmp_secrets_dir)
        assert dec1 == original

    def test_unicode_content(self, tmp_secrets_dir):
        original = "テスラのトークン🔑"
        encrypted = encrypt(original, secrets_dir=tmp_secrets_dir)
        decrypted = decrypt(encrypted, secrets_dir=tmp_secrets_dir)
        assert decrypted == original

    def test_empty_string(self, tmp_secrets_dir):
        encrypted = encrypt("", secrets_dir=tmp_secrets_dir)
        decrypted = decrypt(encrypted, secrets_dir=tmp_secrets_dir)
        assert decrypted == ""
