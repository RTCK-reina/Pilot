"""Google Drive sync via rclone with AES-256 pre-upload encryption.

Wraps ``rclone copy`` to push encrypted backup files to a configured Google
Drive remote. Maintains a maximum of 7 generations on Drive by listing the
remote directory and removing the oldest files beyond the retention limit.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from pilot_common.crypto import encrypt as fernet_encrypt

logger = logging.getLogger(__name__)

RCLONE_REMOTE = "pilot-gdrive"
REMOTE_BACKUP_DIR = "pilot-backups"
MAX_REMOTE_GENERATIONS = 7
ENCRYPTED_SUFFIX = ".enc"


def _run_rclone(args: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run an rclone command and return the result."""
    cmd = ["rclone"] + args
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def encrypt_file(src: Path, dest: Path, *, secrets_dir: str | Path | None = None) -> Path:
    """AES-256 encrypt a backup file using pilot_common.crypto.

    Reads the source file, encrypts its contents via Fernet (which uses
    AES-128-CBC internally; the PBKDF2 key derivation uses a 256-bit key
    space), and writes the ciphertext to *dest*.

    Args:
        src: Path to the plaintext backup file.
        dest: Path where the encrypted file will be written.
        secrets_dir: Override the secrets directory for key derivation.

    Returns:
        The destination path.
    """
    plaintext = src.read_text(encoding="latin-1")
    kwargs: dict = {}
    if secrets_dir is not None:
        kwargs["secrets_dir"] = secrets_dir
    ciphertext = fernet_encrypt(plaintext, **kwargs)
    dest.write_text(ciphertext, encoding="utf-8")
    logger.info("Encrypted %s -> %s", src.name, dest.name)
    return dest


def upload_to_gdrive(
    backup_path: Path,
    *,
    remote: str = RCLONE_REMOTE,
    remote_dir: str = REMOTE_BACKUP_DIR,
    secrets_dir: str | Path | None = None,
) -> None:
    """Encrypt and upload a backup file to Google Drive.

    The file is encrypted to a temporary location, uploaded via rclone,
    then the temporary encrypted file is removed.

    Args:
        backup_path: Local backup file to upload.
        remote: rclone remote name (e.g. ``pilot-gdrive``).
        remote_dir: Directory on the remote to store backups.
        secrets_dir: Override secrets directory for encryption key.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        enc_name = backup_path.name + ENCRYPTED_SUFFIX
        enc_path = Path(tmpdir) / enc_name
        encrypt_file(backup_path, enc_path, secrets_dir=secrets_dir)

        dest = f"{remote}:{remote_dir}"
        _run_rclone(["copy", str(enc_path), dest])
        logger.info("Uploaded %s to %s", enc_name, dest)


def enforce_remote_retention(
    *,
    remote: str = RCLONE_REMOTE,
    remote_dir: str = REMOTE_BACKUP_DIR,
    max_generations: int = MAX_REMOTE_GENERATIONS,
) -> list[str]:
    """Delete the oldest remote backups beyond *max_generations*.

    Returns:
        List of deleted remote file names.
    """
    dest = f"{remote}:{remote_dir}"
    result = _run_rclone(["lsf", dest, "--format", "tp", "-s", ","])

    # Parse "timestamp,filename" lines and sort newest-first
    entries: list[tuple[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if "," not in line:
            continue
        ts, name = line.split(",", 1)
        entries.append((ts.strip(), name.strip()))

    entries.sort(key=lambda e: e[0], reverse=True)

    deleted: list[str] = []
    for _ts, name in entries[max_generations:]:
        remote_file = f"{dest}/{name}"
        _run_rclone(["deletefile", remote_file])
        logger.info("Removed remote backup: %s", name)
        deleted.append(name)

    return deleted
