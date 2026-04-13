"""Sync orchestrator — entry point for the pilot-sync systemd timer.

Execution flow:
    1. Always create a local ``.bak`` snapshot and rotate to 7 daily backups.
    2. If Google Drive sync is enabled, encrypt and upload to Drive.
    3. If USB storage is active, verify the symlink target is still mounted.
"""

from __future__ import annotations

import logging
import sys

from pilot_common.config import get_setting
from pilot_common.constants import DB_PATH_DEFAULT
from pilot_common.db import get_connection

from pilot_sync.backup import create_backup, rotate_backups
from pilot_sync.gdrive import enforce_remote_retention, upload_to_gdrive
from pilot_sync.usb_storage import verify_usb_storage

logger = logging.getLogger(__name__)


def run_sync(db_path: str = DB_PATH_DEFAULT) -> None:
    """Execute a full sync cycle."""
    conn = get_connection(db_path)

    try:
        # --- 1. Local backup ---------------------------------------------------
        logger.info("Creating local backup snapshot")
        backup_path = create_backup(conn, db_path)
        rotate_backups(db_path)

        # --- 2. Google Drive ---------------------------------------------------
        gdrive_enabled = get_setting(conn, "gdrive_enabled", "false")
        if gdrive_enabled == "true":
            logger.info("Google Drive sync enabled — uploading")
            try:
                secrets_dir = get_setting(conn, "secrets_dir", "/var/lib/pilot/secrets")
                upload_to_gdrive(backup_path, secrets_dir=secrets_dir)
                enforce_remote_retention()
            except Exception:
                logger.exception("Google Drive sync failed (backup is still local)")

        # --- 3. USB verification -----------------------------------------------
        usb_enabled = get_setting(conn, "usb_storage_enabled", "false")
        if usb_enabled == "true":
            logger.info("Verifying USB storage")
            if not verify_usb_storage():
                logger.warning("USB storage verification failed — data may be on SD card only")

        logger.info("Sync cycle complete")
    finally:
        conn.close()


def main() -> None:
    """Sync entry point for systemd timer."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    try:
        run_sync()
    except Exception:
        logger.exception("Sync failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
