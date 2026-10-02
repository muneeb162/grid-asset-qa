"""Domain models for the grid asset register.

Every validation rule here maps to a business rule (BR-xx) in docs/TEST_CASES.md.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# BR-02: assets must lie inside Germany (approximate bounding box, WGS84)
LAT_MIN, LAT_MAX = 47.27, 55.06
LON_MIN, LON_MAX = 5.87, 15.04

# BR-05: voltage level thresholds in kV
LOW_VOLTAGE_LIMIT_KV = 1.0
HIGH_VOLTAGE_FROM_KV = 60.0
MAX_VOLTAGE_KV = 380.0


class AssetType(str, Enum):
    TRANSFORMER = "transformer"
    CABLE = "cable"
    SUBSTATION = "substation"
    SWITCHGEAR = "switchgear"


class VoltageLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssetStatus(str, Enum):
    IN_SERVICE = "in_service"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"


def classify_voltage(voltage_kv: float) -> VoltageLevel:
    """BR-05: below 1 kV is low, 1 kV up to below 60 kV is medium, 60 kV and above is high."""
    if voltage_kv < LOW_VOLTAGE_LIMIT_KV:
        return VoltageLevel.LOW
    if voltage_kv < HIGH_VOLTAGE_FROM_KV:
        return VoltageLevel.MEDIUM
    return VoltageLevel.HIGH


class AssetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    type: AssetType
    voltage_kv: float = Field(gt=0, le=MAX_VOLTAGE_KV)  # BR-04
    latitude: float
    longitude: float
    commissioned_on: date

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("latitude")
    @classmethod
    def latitude_in_germany(cls, value: float) -> float:
        if not LAT_MIN <= value <= LAT_MAX:
            raise ValueError(f"must be between {LAT_MIN} and {LAT_MAX} (Germany)")
        return value

    @field_validator("longitude")
    @classmethod
    def longitude_in_germany(cls, value: float) -> float:
        if not LON_MIN <= value <= LON_MAX:
            raise ValueError(f"must be between {LON_MIN} and {LON_MAX} (Germany)")
        return value

    @field_validator("commissioned_on")
    @classmethod
    def not_in_future(cls, value: date) -> date:  # BR-03
        if value > date.today():
            raise ValueError("cannot be in the future")
        return value


class Asset(AssetCreate):
    id: int
    status: AssetStatus = AssetStatus.IN_SERVICE

    @property
    def voltage_level(self) -> VoltageLevel:
        return classify_voltage(self.voltage_kv)


class AssetOut(BaseModel):
    id: int
    name: str
    type: AssetType
    voltage_kv: float
    voltage_level: VoltageLevel
    latitude: float
    longitude: float
    commissioned_on: date
    status: AssetStatus

    @classmethod
    def from_asset(cls, asset: Asset) -> "AssetOut":
        return cls(**asset.model_dump(), voltage_level=asset.voltage_level)


class StatusUpdate(BaseModel):
    status: AssetStatus


def to_naive_utc(value: datetime) -> datetime:
    """Store all timestamps as naive UTC so aware and naive inputs compare safely."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class OutageCreate(BaseModel):
    asset_id: int
    started_at: datetime
    description: str = Field(min_length=5, max_length=500)

    @field_validator("started_at")
    @classmethod
    def normalise_started_at(cls, value: datetime) -> datetime:
        return to_naive_utc(value)

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class OutageResolve(BaseModel):
    resolved_at: datetime

    @field_validator("resolved_at")
    @classmethod
    def normalise_resolved_at(cls, value: datetime) -> datetime:
        return to_naive_utc(value)


class Outage(BaseModel):
    id: int
    asset_id: int
    started_at: datetime
    description: str
    resolved_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None
