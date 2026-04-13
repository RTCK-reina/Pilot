"""USB storage detection and data migration.

Detects USB block devices via ``/sys/block/``, checks for ext4 filesystem
support, and migrates the PiLot data directory to USB with a symlink swap.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SYS_BLOCK = Path("/sys/block")
PILOT_DATA_DIR = Path("/var/lib/pilot")
PREFERRED_FS = "ext4"


def detect_usb_devices() -> list[str]:
    """Return a list of block device names that are USB-attached.

    Examines ``/sys/block/<dev>/device`` symlinks; USB devices have
    ``usb`` in their resolved device path.

    Returns:
        List of device names, e.g. ``["sda", "sdb"]``.
    """
    usb_devs: list[str] = []
    if not SYS_BLOCK.exists():
        return usb_devs

    for block in SYS_BLOCK.iterdir():
        device_link = block / "device"
        if not device_link.exists():
            continue
        try:
            real = device_link.resolve().as_posix()
            if "usb" in real:
                usb_devs.append(block.name)
        except OSError:
            continue

    logger.info("Detected USB block devices: %s", usb_devs)
    return usb_devs


def check_filesystem(device: str) -> str | None:
    """Return the filesystem type of the first partition on *device*.

    Uses ``blkid`` to query the partition. Returns ``None`` if the device
    has no recognisable filesystem.

    Args:
        device: Block device name (e.g. ``sda``).

    Returns:
        Filesystem type string (e.g. ``"ext4"``) or ``None``.
    """
    partition = f"/dev/{device}1"
    try:
        result = subprocess.run(
            ["blkid", "-o", "value", "-s", "TYPE", partition],
            capture_output=True,
            text=True,
            timeout=10,
        )
        fs_type = result.stdout.strip()
        if fs_type:
            logger.info("Filesystem on %s: %s", partition, fs_type)
            return fs_type
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Could not determine filesystem for %s", partition)
    return None


def is_ext4(device: str) -> bool:
    """Check whether *device* has an ext4 first partition."""
    return check_filesystem(device) == PREFERRED_FS


def mount_device(device: str, mount_point: Path) -> bool:
    """Mount the first partition of *device* at *mount_point*.

    Returns:
        ``True`` if mount succeeds.
    """
    partition = f"/dev/{device}1"
    mount_point.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["mount", partition, str(mount_point)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        logger.info("Mounted %s at %s", partition, mount_point)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to mount %s: %s", partition, exc.stderr)
        return False


def migrate_data_to_usb(
    device: str,
    mount_point: Path,
    *,
    data_dir: Path = PILOT_DATA_DIR,
) -> bool:
    """Copy PiLot data directory to USB and replace original with a symlink.

    Steps:
        1. Mount the USB device if not already mounted.
        2. Copy ``data_dir`` contents to ``mount_point/pilot/``.
        3. Rename the original ``data_dir`` to ``data_dir.orig``.
        4. Create a symlink from ``data_dir`` -> ``mount_point/pilot/``.

    Args:
        device: USB block device name (e.g. ``sda``).
        mount_point: Where the USB device is mounted.
        data_dir: The PiLot data directory (default ``/var/lib/pilot``).

    Returns:
        ``True`` on success, ``False`` on any failure.
    """
    usb_data = mount_point / "pilot"

    # Ensure the device is mounted
    if not mount_point.is_mount():
        if not mount_device(device, mount_point):
            return False

    # Copy data
    try:
        if data_dir.is_dir() and not data_dir.is_symlink():
            shutil.copytree(str(data_dir), str(usb_data), dirs_exist_ok=True)
            logger.info("Copied %s -> %s", data_dir, usb_data)
        elif not usb_data.exists():
            usb_data.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Data copy failed: %s", exc)
        return False

    # Swap original directory with symlink
    orig_backup = data_dir.with_suffix(".orig")
    try:
        if data_dir.is_dir() and not data_dir.is_symlink():
            data_dir.rename(orig_backup)
        data_dir.symlink_to(usb_data)
        logger.info("Symlinked %s -> %s", data_dir, usb_data)
        return True
    except OSError as exc:
        logger.error("Symlink swap failed: %s", exc)
        # Attempt rollback
        if orig_backup.exists() and not data_dir.exists():
            orig_backup.rename(data_dir)
        return False


def verify_usb_storage(data_dir: Path = PILOT_DATA_DIR) -> bool:
    """Check that *data_dir* is a symlink pointing to a mounted USB path.

    Returns:
        ``True`` if the symlink target exists and is a directory.
    """
    if not data_dir.is_symlink():
        return False

    target = data_dir.resolve()
    ok = target.is_dir()
    if ok:
        logger.info("USB storage verified: %s -> %s", data_dir, target)
    else:
        logger.warning("USB storage target missing: %s -> %s", data_dir, target)
    return ok
