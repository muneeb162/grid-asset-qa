"""API tests for the outage workflow: report, block conflicting actions, resolve.

These cover the state transitions an operator relies on, so they carry the most risk.
"""
from __future__ import annotations

import pytest


def asset_status(client, asset_id: int) -> str:
    return client.get(f"/api/assets/{asset_id}").json()["status"]


# TC-020 | BR-06
@pytest.mark.smoke
def test_reporting_outage_takes_asset_out_of_service(client, create_asset, report_outage):
    asset = create_asset()

    outage = report_outage(asset["id"])

    assert outage["resolved_at"] is None
    assert asset_status(client, asset["id"]) == "out_of_service"


# TC-021 | BR-06
def test_second_open_outage_on_same_asset_is_rejected(client, create_asset, report_outage):
    asset = create_asset()
    report_outage(asset["id"])

    response = client.post(
        "/api/outages",
        json={"asset_id": asset["id"], "started_at": "2026-03-02T08:00:00", "description": "Another fault"},
    )

    assert response.status_code == 409
    assert len(client.get("/api/outages").json()) == 1


def test_outage_for_unknown_asset_returns_404(client):
    response = client.post(
        "/api/outages", json={"asset_id": 77, "started_at": "2026-03-01T08:00:00", "description": "Ghost fault"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("description", ["", "abcd", "    x    ", "x" * 501])
def test_outage_description_length_is_validated(client, create_asset, description):
    asset = create_asset()
    response = client.post(
        "/api/outages",
        json={"asset_id": asset["id"], "started_at": "2026-03-01T08:00:00", "description": description},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "description"


# TC-022 | BR-08
@pytest.mark.smoke
def test_resolving_outage_returns_asset_to_service(client, create_asset, report_outage):
    asset = create_asset()
    outage = report_outage(asset["id"], started_at="2026-03-01T08:00:00")

    response = client.patch(f"/api/outages/{outage['id']}/resolve", json={"resolved_at": "2026-03-01T11:30:00"})

    assert response.status_code == 200
    assert response.json()["resolved_at"] == "2026-03-01T11:30:00"
    assert asset_status(client, asset["id"]) == "in_service"


# TC-023 | BR-08: end must be strictly after start (boundary: equal timestamps)
@pytest.mark.parametrize("resolved_at", ["2026-03-01T07:59:59", "2026-03-01T08:00:00"])
def test_resolve_before_or_at_start_is_rejected(client, create_asset, report_outage, resolved_at):
    asset = create_asset()
    outage = report_outage(asset["id"], started_at="2026-03-01T08:00:00")

    response = client.patch(f"/api/outages/{outage['id']}/resolve", json={"resolved_at": resolved_at})

    assert response.status_code == 422
    assert asset_status(client, asset["id"]) == "out_of_service"


def test_resolve_compares_across_timezones(client, create_asset, report_outage):
    """08:30 in Germany (CET, UTC+1) is 07:30 UTC, which is before an 08:00 UTC start."""
    asset = create_asset()
    outage = report_outage(asset["id"], started_at="2026-03-01T08:00:00Z")

    response = client.patch(
        f"/api/outages/{outage['id']}/resolve", json={"resolved_at": "2026-03-01T08:30:00+01:00"}
    )

    assert response.status_code == 422


# TC-024 | BR-08
def test_outage_cannot_be_resolved_twice(client, create_asset, report_outage):
    asset = create_asset()
    outage = report_outage(asset["id"])
    client.patch(f"/api/outages/{outage['id']}/resolve", json={"resolved_at": "2026-03-01T12:00:00"})

    response = client.patch(f"/api/outages/{outage['id']}/resolve", json={"resolved_at": "2026-03-01T13:00:00"})

    assert response.status_code == 409


def test_resolve_unknown_outage_returns_404(client):
    response = client.patch("/api/outages/5/resolve", json={"resolved_at": "2026-03-01T12:00:00"})
    assert response.status_code == 404


# TC-025 | BR-09
def test_asset_with_open_outage_cannot_be_deleted(client, create_asset, report_outage):
    asset = create_asset()
    report_outage(asset["id"])

    response = client.delete(f"/api/assets/{asset['id']}")

    assert response.status_code == 409
    assert client.get(f"/api/assets/{asset['id']}").status_code == 200


def test_asset_can_be_deleted_after_outage_is_resolved(client, create_asset, report_outage):
    asset = create_asset()
    outage = report_outage(asset["id"])
    client.patch(f"/api/outages/{outage['id']}/resolve", json={"resolved_at": "2026-03-01T12:00:00"})

    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204


# TC-026 | BR-10
@pytest.mark.parametrize("new_status", ["in_service", "maintenance"])
def test_status_cannot_bypass_open_outage(client, create_asset, report_outage, new_status):
    asset = create_asset()
    report_outage(asset["id"])

    response = client.patch(f"/api/assets/{asset['id']}/status", json={"status": new_status})

    assert response.status_code == 409
    assert asset_status(client, asset["id"]) == "out_of_service"


def test_new_outage_allowed_after_previous_one_is_resolved(client, create_asset, report_outage):
    asset = create_asset()
    first = report_outage(asset["id"], started_at="2026-03-01T08:00:00")
    client.patch(f"/api/outages/{first['id']}/resolve", json={"resolved_at": "2026-03-01T09:00:00"})

    second = report_outage(asset["id"], started_at="2026-03-05T08:00:00")

    assert second["id"] == first["id"] + 1
    assert asset_status(client, asset["id"]) == "out_of_service"


def test_open_only_filter(client, create_asset, report_outage):
    a = create_asset(name="Asset A")
    b = create_asset(name="Asset B")
    resolved = report_outage(a["id"])
    report_outage(b["id"])
    client.patch(f"/api/outages/{resolved['id']}/resolve", json={"resolved_at": "2026-03-01T12:00:00"})

    open_outages = client.get("/api/outages?open_only=true").json()

    assert [o["asset_id"] for o in open_outages] == [b["id"]]
    assert len(client.get("/api/outages").json()) == 2
