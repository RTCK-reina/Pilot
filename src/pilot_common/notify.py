"""Inter-process notification via UNIX domain socket (datagram).

tesla-poller sends a short datagram after each DB write.
pilot-dashboard receives it and broadcasts to WebSocket clients.

Socket path: /run/pilot/notify.sock (managed by tmpfiles.d/pilot.conf).
If the socket doesn't exist (dashboard not running), sends are silently ignored.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from pathlib import Path

from pilot_common.constants import NOTIFY_SOCKET_PATH

logger = logging.getLogger(__name__)


def send_notify(
    message: bytes = b"update",
    socket_path: str | Path = NOTIFY_SOCKET_PATH,
) -> bool:
    """Send a datagram notification (non-blocking, fire-and-forget).

    Returns True if sent, False if the socket is unavailable.
    """
    path = str(socket_path)
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.sendto(message, path)
        sock.close()
        return True
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return False


class NotifyReceiver:
    """Async receiver for datagram notifications.

    Usage:
        receiver = NotifyReceiver()
        await receiver.start()
        async for message in receiver:
            # broadcast to WebSocket clients
        await receiver.stop()
    """

    def __init__(self, socket_path: str | Path = NOTIFY_SOCKET_PATH):
        self._path = str(socket_path)
        self._transport: asyncio.DatagramTransport | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        """Bind the datagram socket and start receiving."""
        sock_path = Path(self._path)
        if sock_path.exists():
            sock_path.unlink()

        loop = asyncio.get_running_loop()

        class _Protocol(asyncio.DatagramProtocol):
            def __init__(self, queue: asyncio.Queue[bytes]):
                self._queue = queue

            def datagram_received(self, data: bytes, addr: tuple[str, int] | str) -> None:
                self._queue.put_nowait(data)

        transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self._queue),
            local_addr=self._path,
            family=socket.AF_UNIX,
        )
        self._transport = transport
        self._running = True
        logger.info("Notify receiver started on %s", self._path)

    async def stop(self) -> None:
        """Close the socket."""
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None
        sock_path = Path(self._path)
        if sock_path.exists():
            sock_path.unlink()

    async def wait(self, timeout: float = 5.0) -> bytes | None:
        """Wait for a notification with timeout. Returns None on timeout."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        if not self._running:
            raise StopAsyncIteration
        msg = await self.wait(timeout=5.0)
        if msg is None and not self._running:
            raise StopAsyncIteration
        return msg or b""
