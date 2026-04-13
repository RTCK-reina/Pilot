"""Token encryption/decryption using Fernet.

Key derivation: PBKDF2(passphrase, device_salt) where device_salt is a random
file on the SD card. This means the encrypted tokens survive Pi hardware swaps
(the salt travels with the SD card).

If no passphrase is configured (v1.0 default), a fixed fallback passphrase is
used. This still provides encryption-at-rest against casual file reads, while
the salt prevents rainbow table attacks.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pilot_common.constants import SALT_FILE, SECRETS_DIR

_FALLBACK_PASSPHRASE = b"pilot-os-default-v1"
_PBKDF2_ITERATIONS = 480_000


def _ensure_salt(secrets_dir: str | Path = SECRETS_DIR) -> bytes:
    """Read or create the device salt file."""
    secrets_path = Path(secrets_dir)
    secrets_path.mkdir(parents=True, exist_ok=True)
    salt_path = secrets_path / SALT_FILE

    if salt_path.exists():
        return salt_path.read_bytes()

    salt = os.urandom(32)
    salt_path.write_bytes(salt)
    salt_path.chmod(0o600)
    return salt


def _derive_key(
    passphrase: bytes | None = None,
    secrets_dir: str | Path = SECRETS_DIR,
) -> bytes:
    """Derive a Fernet key from passphrase + device salt."""
    salt = _ensure_salt(secrets_dir)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    key_material = passphrase or _FALLBACK_PASSPHRASE
    return base64.urlsafe_b64encode(kdf.derive(key_material))


def encrypt(
    plaintext: str,
    passphrase: bytes | None = None,
    secrets_dir: str | Path = SECRETS_DIR,
) -> str:
    """Encrypt a string. Returns a base64 Fernet token."""
    key = _derive_key(passphrase, secrets_dir)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt(
    token: str,
    passphrase: bytes | None = None,
    secrets_dir: str | Path = SECRETS_DIR,
) -> str:
    """Decrypt a Fernet token back to a string."""
    key = _derive_key(passphrase, secrets_dir)
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()
