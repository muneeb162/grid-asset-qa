"""Shared fixtures. Each test gets a fresh app, so tests never depend on each other's data."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.service import GridService

# A known valid location: Dortmund, Phoenix-See
DORTMUND = {"latitude": 51.4888, "longitude": 7.5147}


def asset_payload(**overrides) -> dict:
    """Test data builder: a valid asset, with any field overridable."""
    payload = {
        "name": "TR Hoerde 04",
        "type": "transformer",
        "voltage_kv": 10.0,
        **DORTMUND,
        "commissioned_on": "2015-06-01",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def service() -> GridService:
    return GridService()


@pytest.fixture
def client(service: GridService) -> TestClient:
    return TestClient(create_app(service))


@pytest.fixture
def create_asset(client: TestClient):
    """Create an asset through the API and return the JSON body."""

    def _create(**overrides) -> dict:
        response = client.post("/api/assets", json=asset_payload(**overrides))
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture
def report_outage(client: TestClient):
    def _report(asset_id: int, started_at: str = "2026-03-01T08:00:00", description: str = "Cable fault") -> dict:
        response = client.post(
            "/api/outages",
            json={"asset_id": asset_id, "started_at": started_at, "description": description},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _report


@pytest.fixture
def today() -> date:
    return date.today()
