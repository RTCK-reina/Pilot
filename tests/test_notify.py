"""Tests for UNIX domain socket IPC notification."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from pilot_common.notify import NotifyReceiver, send_notify


@pytest.fixture
def sock_path() -> Path:
    """Short socket path to avoid AF_UNIX path length limit (~104 chars on macOS)."""
    d = tempfile.mkdtemp(prefix="plt")
    return Path(d) / "n.sock"


class TestSendNotify:
    def test_send_to_nonexistent_socket(self, sock_path):
        """Should return False without error when socket doesn't exist."""
        result = send_notify(b"test", socket_path=sock_path)
        assert result is False


class TestNotifyReceiver:
    @pytest.mark.asyncio
    async def test_receive_message(self, sock_path):
        receiver = NotifyReceiver(socket_path=sock_path)
        await receiver.start()

        send_notify(b"update", socket_path=sock_path)
        msg = await receiver.wait(timeout=2.0)
        assert msg == b"update"

        await receiver.stop()

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, sock_path):
        receiver = NotifyReceiver(socket_path=sock_path)
        await receiver.start()

        msg = await receiver.wait(timeout=0.1)
        assert msg is None

        await receiver.stop()

    @pytest.mark.asyncio
    async def test_multiple_messages(self, sock_path):
        receiver = NotifyReceiver(socket_path=sock_path)
        await receiver.start()

        for i in range(3):
            send_notify(f"msg-{i}".encode(), socket_path=sock_path)

        messages = []
        for _ in range(3):
            msg = await receiver.wait(timeout=2.0)
            if msg:
                messages.append(msg)

        assert len(messages) == 3
        assert b"msg-0" in messages
        assert b"msg-2" in messages

        await receiver.stop()

    @pytest.mark.asyncio
    async def test_cleanup_on_stop(self, sock_path):
        receiver = NotifyReceiver(socket_path=sock_path)
        await receiver.start()
        assert sock_path.exists()

        await receiver.stop()
        assert not sock_path.exists()
