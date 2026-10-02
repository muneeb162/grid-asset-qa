"""API tests for /api/assets. Test IDs map to docs/TEST_CASES.md."""
from __future__ import annotations

import pytest

from tests.conftest import asset_payload


@pytest.mark.smoke
def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# TC-001
@pytest.mark.smoke
def test_create_asset_returns_201_with_derived_fields(client):
    response = client.post("/api/assets", json=asset_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "TR Hoerde 04"
    assert body["voltage_level"] == "medium"
    assert body["status"] == "in_service"


# TC-002
def test_created_asset_can_be_read_back(client, create_asset):
    created = create_asset()
    response = client.get(f"/api/assets/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


# TC-003 | BR-01
@pytest.mark.parametrize("duplicate_name", ["TR Hoerde 04", "tr hoerde 04", "  TR HOERDE 04  "])
def test_duplicate_name_is_rejected_ignoring_case(client, create_asset, duplicate_name):
    create_asset(name="TR Hoerde 04")
    response = client.post("/api/assets", json=asset_payload(name=duplicate_name))
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


# TC-004 | BR-02, BR-03, BR-04: every invalid field is reported by name, in a consistent format
@pytest.mark.parametrize(
    ("overrides", "bad_field"),
    [
        ({"latitude": 40.4}, "latitude"),
        ({"longitude": 20.0}, "longitude"),
        ({"voltage_kv": 0}, "voltage_kv"),
        ({"voltage_kv": "ten"}, "voltage_kv"),
        ({"commissioned_on": "2999-01-01"}, "commissioned_on"),
        ({"commissioned_on": "01.06.2015"}, "commissioned_on"),  # German date format is not ISO 8601
        ({"type": "windmill"}, "type"),
        ({"name": ""}, "name"),
    ],
)
def test_invalid_input_returns_422_naming_the_field(client, overrides, bad_field):
    response = client.post("/api/assets", json=asset_payload(**overrides))

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Validation failed"
    assert [e["field"] for e in body["errors"]] == [bad_field]


def test_rejected_asset_is_not_stored(client):
    client.post("/api/assets", json=asset_payload(latitude=0))
    assert client.get("/api/assets").json() == []


# TC-005
@pytest.mark.parametrize("asset_id", [999, 0])
def test_unknown_asset_returns_404(client, asset_id):
    response = client.get(f"/api/assets/{asset_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Asset {asset_id} not found"


def test_non_numeric_asset_id_returns_422(client):
    assert client.get("/api/assets/abc").status_code == 422


# TC-006
def test_list_filters_by_type_and_status(client, create_asset):
    create_asset(name="TR 01", type="transformer")
    cable = create_asset(name="Cable 01", type="cable")
    create_asset(name="Cable 02", type="cable")
    client.patch(f"/api/assets/{cable['id']}/status", json={"status": "maintenance"})

    def names(query: str) -> list[str]:
        return [a["name"] for a in client.get(f"/api/assets{query}").json()]

    assert names("") == ["TR 01", "Cable 01", "Cable 02"]
    assert names("?type=cable") == ["Cable 01", "Cable 02"]
    assert names("?status=maintenance") == ["Cable 01"]
    assert names("?type=transformer&status=maintenance") == []


def test_list_with_invalid_filter_returns_422(client):
    assert client.get("/api/assets?status=broken").status_code == 422


# TC-007
def test_status_can_be_set_to_maintenance_and_back(client, create_asset):
    asset = create_asset()
    for status in ("maintenance", "in_service"):
        response = client.patch(f"/api/assets/{asset['id']}/status", json={"status": status})
        assert response.status_code == 200
        assert response.json()["status"] == status


# TC-008
def test_delete_asset(client, create_asset):
    asset = create_asset()
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert client.get(f"/api/assets/{asset['id']}").status_code == 404


def test_delete_unknown_asset_returns_404(client):
    assert client.delete("/api/assets/42").status_code == 404


def test_ids_are_not_reused_after_delete(client, create_asset):
    first = create_asset(name="Asset A")
    client.delete(f"/api/assets/{first['id']}")
    second = create_asset(name="Asset B")
    assert second["id"] != first["id"]


# TC-009 | GIS export
@pytest.mark.regression
def test_geojson_uses_longitude_latitude_order(client, create_asset):
    """GeoJSON (RFC 7946) expects [longitude, latitude]. Swapping them is a classic GIS defect:
    Dortmund at [51.49, 7.51] would be plotted in the Indian Ocean off Somalia instead of the Ruhr."""
    create_asset(latitude=51.4888, longitude=7.5147)

    response = client.get("/api/assets/geojson")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/geo+json")
    feature = response.json()["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [7.5147, 51.4888]}


def test_geojson_is_a_valid_feature_collection(client, create_asset):
    create_asset(name="Asset A")
    create_asset(name="Asset B", type="substation", voltage_kv=110)

    body = client.get("/api/assets/geojson").json()

    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2
    for feature in body["features"]:
        assert feature["type"] == "Feature"
        assert set(feature["properties"]) == {"name", "type", "voltage_kv", "voltage_level", "status"}
    assert body["features"][1]["properties"]["voltage_level"] == "high"


def test_geojson_with_no_assets_is_empty_collection(client):
    assert client.get("/api/assets/geojson").json() == {"type": "FeatureCollection", "features": []}


# TC-027 | German names: umlauts must survive the round trip
def test_umlauts_are_stored_unchanged(client, create_asset):
    asset = create_asset(name="Umspannwerk Hörde")
    assert client.get(f"/api/assets/{asset['id']}").json()["name"] == "Umspannwerk Hörde"


# TC-028 | BR-01 with German spelling rules. Regression test for DEF-001 (docs/defects/DEF-001.md)
@pytest.mark.regression
@pytest.mark.parametrize(
    ("existing", "duplicate"),
    [
        ("Umspannwerk Hörde", "UMSPANNWERK HÖRDE"),
        ("Trafo Kreuzstraße", "TRAFO KREUZSTRASSE"),  # ß is written SS in capitals
        ("Trafo Kreuzstraße", "Trafo Kreuzstrasse"),
    ],
)
def test_duplicate_check_follows_german_spelling(client, create_asset, existing, duplicate):
    create_asset(name=existing)
    response = client.post("/api/assets", json=asset_payload(name=duplicate))
    assert response.status_code == 409
