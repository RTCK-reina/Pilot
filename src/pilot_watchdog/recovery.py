"""Automatic recovery actions with rate limiting.

Provides ``restart_service()`` which calls ``systemctl restart`` with a
per-service rate limit of 3 restarts per rolling hour to prevent restart
storms.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_RESTARTS_PER_HOUR = 3
_HOUR_SECONDS = 3600

# service_name -> list of restart epoch timestamps
_restart_history: dict[str, list[float]] = defaultdict(list)


def _prune_history(name: str, now: float) -> None:
    """Remove timestamps older than 1 hour from the history for *name*."""
    cutoff = now - _HOUR_SECONDS
    _restart_history[name] = [t for t in _restart_history[name] if t > cutoff]


def is_rate_limited(name: str, *, now: float | None = None) -> bool:
    """Return ``True`` if *name* has been restarted too many times recently."""
    ts = now if now is not None else time.monotonic()
    _prune_history(name, ts)
    return len(_restart_history[name]) >= MAX_RESTARTS_PER_HOUR


def restart_service(name: str) -> bool:
    """Restart a systemd service if the rate limit allows.

    Args:
        name: systemd unit name (e.g. ``tesla-poller``).

    Returns:
        ``True`` if the restart command was executed successfully,
        ``False`` if rate-limited or the command failed.
    """
    now = time.monotonic()

    if is_rate_limited(name, now=now):
        logger.warning(
            "Rate limited: %s restarted %d times in the last hour (max %d)",
            name,
            len(_restart_history[name]),
            MAX_RESTARTS_PER_HOUR,
        )
        return False

    try:
        subprocess.run(
            ["systemctl", "restart", name],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        _restart_history[name].append(now)
        logger.info("Restarted service: %s", name)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to restart %s: %s", name, exc.stderr)
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("Cannot restart %s: %s", name, exc)
        return False


def reset_rate_limits() -> None:
    """Clear all rate-limit history (useful for testing)."""
    _restart_history.clear()
