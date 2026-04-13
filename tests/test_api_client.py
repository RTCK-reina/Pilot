"""Tests for Tesla Owner's API client (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from tesla_poller.api_client import OwnerAPIClient

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_response(status: int, data: dict | list | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://test.local")
    resp = httpx.Response(status, json=data or {}, request=request)
    return resp


@pytest.fixture
def mock_transport():
    """Create a mock async transport for httpx."""
    transport = AsyncMock()
    return transport


@pytest.fixture
def client():
    c = OwnerAPIClient(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
    )
    return c


class TestGetVehicles:
    @pytest.mark.asyncio
    async def test_returns_vehicle_list(self, client):
        vehicles = _load("vehicles_list.json")
        resp = _mock_response(200, {"response": vehicles})

        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=resp)

        result = await client.get_vehicles()
        assert len(result) == 1
        assert result[0]["vin"] == "5YJ3E1EAXPF000001"


class TestGetVehicleData:
    @pytest.mark.asyncio
    async def test_returns_driving_data(self, client):
        data = _load("vehicle_data_driving.json")
        resp = _mock_response(200, {"response": data})

        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=resp)

        result = await client.get_vehicle_data("5YJ3E1EAXPF000001")
        assert result["drive_state"]["shift_state"] == "D"
        assert result["drive_state"]["speed"] == 65

    @pytest.mark.asyncio
    async def test_asleep_408_returns_marker(self, client):
        resp = _mock_response(408, {})

        client._client = AsyncMock()
        client._client.request = AsyncMock(return_value=resp)

        result = await client.get_vehicle_data("5YJ3E1EAXPF000001")
        assert result["state"] == "asleep"


class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_401_triggers_refresh(self, client):
        data = _load("vehicle_data_idle.json")
        resp_401 = _mock_response(401, {})
        resp_200 = _mock_response(200, {"response": data})
        resp_refresh = _mock_response(200, {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
        })

        call_count = 0

        async def request_side_effect(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return resp_401
            return resp_200

        client._client = AsyncMock()
        client._client.request = AsyncMock(side_effect=request_side_effect)
        client._client.post = AsyncMock(return_value=resp_refresh)

        result = await client.get_vehicle_data("VIN123")
        assert client.access_token == "new-access"
        assert client.refresh_token == "new-refresh"

    @pytest.mark.asyncio
    async def test_refresh_callback_called(self, client):
        callback = AsyncMock()
        client._on_token_refresh = callback

        data = _load("vehicle_data_idle.json")
        resp_401 = _mock_response(401, {})
        resp_200 = _mock_response(200, {"response": data})
        resp_refresh = _mock_response(200, {
            "access_token": "new-a",
            "refresh_token": "new-r",
        })

        call_count = 0

        async def request_side_effect(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return resp_401
            return resp_200

        client._client = AsyncMock()
        client._client.request = AsyncMock(side_effect=request_side_effect)
        client._client.post = AsyncMock(return_value=resp_refresh)

        await client.get_vehicle_data("VIN123")
        callback.assert_awaited_once_with("new-a", "new-r")
