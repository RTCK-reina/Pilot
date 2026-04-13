"""Tests for setup wizard flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pilot_setup.app import create_app


@pytest.fixture
def client():
    app = create_app(":memory:")
    with TestClient(app) as c:
        yield c


class TestWizardSteps:
    def test_step1_get(self, client):
        r = client.get("/setup/step/1")
        assert r.status_code == 200

    def test_step1_post(self, client):
        r = client.post(
            "/setup/step/1",
            data={
                "language": "ja",
                "timezone": "Asia/Tokyo",
                "efficiency_unit": "km_kwh",
                "currency": "JPY",
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303, 307)

    def test_step4_get(self, client):
        r = client.get("/setup/step/4")
        assert r.status_code == 200

    def test_step4_post_fixed_rate(self, client):
        r = client.post(
            "/setup/step/4",
            data={
                "rate_type": "fixed",
                "fixed_rate": "28",
                "sc_rate": "55",
            },
            follow_redirects=False,
        )
        assert r.status_code in (302, 303, 307)

    def test_step5_get(self, client):
        r = client.get("/setup/step/5")
        assert r.status_code == 200

    def test_step6_get(self, client):
        r = client.get("/setup/step/6")
        assert r.status_code == 200

    def test_step7_get(self, client):
        r = client.get("/setup/step/7")
        assert r.status_code == 200

    def test_status_endpoint(self, client):
        r = client.get("/setup/status")
        assert r.status_code == 200
        data = r.json()
        assert "current_step" in data


class TestOAuth:
    def test_oauth_start_redirects(self, client):
        r = client.get("/setup/oauth/start", follow_redirects=False)
        assert r.status_code in (302, 303, 307)
        location = r.headers.get("location", "")
        assert "auth.tesla.com" in location

    def test_oauth_status(self, client):
        r = client.get("/setup/oauth/status")
        assert r.status_code == 200
        data = r.json()
        assert "oauth_complete" in data
