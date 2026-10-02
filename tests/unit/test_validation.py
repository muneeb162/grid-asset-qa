"""Unit tests for input validation.

Technique: boundary value analysis and equivalence partitioning.
Each test ID (TC-xxx) maps to docs/TEST_CASES.md.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    AssetCreate,
    OutageCreate,
    VoltageLevel,
    classify_voltage,
)
from tests.conftest import asset_payload


# TC-010 | BR-05: voltage level classification at every boundary
@pytest.mark.parametrize(
    ("voltage_kv", "expected"),
    [
        (0.23, VoltageLevel.LOW),      # typical household supply
        (0.999, VoltageLevel.LOW),     # just below 1 kV boundary
        (1.0, VoltageLevel.MEDIUM),    # on the boundary
        (10.0, VoltageLevel.MEDIUM),   # typical distribution grid
        (59.999, VoltageLevel.MEDIUM), # just below 60 kV boundary
        (60.0, VoltageLevel.HIGH),     # on the boundary
        (110.0, VoltageLevel.HIGH),
        (380.0, VoltageLevel.HIGH),    # maximum allowed
    ],
)
def test_voltage_level_boundaries(voltage_kv, expected):
    assert classify_voltage(voltage_kv) == expected


# TC-011 | BR-04: voltage must be > 0 and <= 380 kV
@pytest.mark.parametrize("voltage_kv", [0, -0.4, 380.001, 1000])
def test_voltage_outside_range_is_rejected(voltage_kv):
    with pytest.raises(ValidationError) as exc:
        AssetCreate(**asset_payload(voltage_kv=voltage_kv))
    assert exc.value.errors()[0]["loc"] == ("voltage_kv",)


# TC-012 | BR-02: coordinates exactly on the Germany bounding box are accepted
@pytest.mark.parametrize(
    ("lat", "lon"),
    [(LAT_MIN, LON_MIN), (LAT_MAX, LON_MAX), (LAT_MIN, LON_MAX), (LAT_MAX, LON_MIN)],
)
def test_coordinates_on_boundary_are_accepted(lat, lon):
    asset = AssetCreate(**asset_payload(latitude=lat, longitude=lon))
    assert (asset.latitude, asset.longitude) == (lat, lon)


# TC-013 | BR-02: coordinates just outside Germany are rejected, naming the right field
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", LAT_MIN - 0.01),
        ("latitude", LAT_MAX + 0.01),
        ("longitude", LON_MIN - 0.01),
        ("longitude", LON_MAX + 0.01),
        ("longitude", 2.3522),   # Paris: a realistic wrong input, not just a boundary
    ],
)
def test_coordinates_outside_germany_are_rejected(field, value):
    with pytest.raises(ValidationError) as exc:
        AssetCreate(**asset_payload(**{field: value}))
    assert exc.value.errors()[0]["loc"] == (field,)


# TC-014 | BR-03: commissioning date may be today but not tomorrow
def test_commissioned_today_is_accepted(today):
    assert AssetCreate(**asset_payload(commissioned_on=today.isoformat())).commissioned_on == today


def test_commissioned_in_future_is_rejected(today):
    tomorrow = (today + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="cannot be in the future"):
        AssetCreate(**asset_payload(commissioned_on=tomorrow))


# TC-015: name length limits (3 to 60 characters after trimming whitespace)
@pytest.mark.parametrize(
    ("name", "valid"),
    [("ab", False), ("abc", True), ("x" * 60, True), ("x" * 61, False), ("   ab   ", False), ("  T12  ", True)],
)
def test_name_length_limits(name, valid):
    if valid:
        assert AssetCreate(**asset_payload(name=name)).name == name.strip()
    else:
        with pytest.raises(ValidationError):
            AssetCreate(**asset_payload(name=name))


# TC-016: timezone-aware timestamps are normalised to UTC
def test_outage_timestamp_is_normalised_to_utc():
    cest = timezone(timedelta(hours=2))
    outage = OutageCreate(
        asset_id=1, started_at=datetime(2026, 7, 1, 10, 0, tzinfo=cest), description="Fuse blown"
    )
    assert outage.started_at == datetime(2026, 7, 1, 8, 0)
    assert outage.started_at.tzinfo is None


def test_missing_required_fields_are_all_reported():
    with pytest.raises(ValidationError) as exc:
        AssetCreate()
    missing = {err["loc"][0] for err in exc.value.errors()}
    assert missing == {"name", "type", "voltage_kv", "latitude", "longitude", "commissioned_on"}


def test_unknown_asset_type_is_rejected():
    with pytest.raises(ValidationError):
        AssetCreate(**asset_payload(type="windmill"))


def test_default_test_data_is_valid():
    """Guard test: if the default test data ever becomes invalid, every other test is meaningless."""
    assert AssetCreate(**asset_payload()).commissioned_on <= date.today()
