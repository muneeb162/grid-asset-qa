"""Business logic for assets and outages, kept separate from HTTP so it can be unit tested."""
from __future__ import annotations

from .models import (
    Asset,
    AssetCreate,
    AssetStatus,
    AssetType,
    Outage,
    OutageCreate,
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class RuleViolationError(Exception):
    pass


class GridService:
    def __init__(self) -> None:
        self._assets: dict[int, Asset] = {}
        self._outages: dict[int, Outage] = {}
        self._next_asset_id = 1
        self._next_outage_id = 1

    # ---------- assets ----------

    def create_asset(self, data: AssetCreate) -> Asset:
        # BR-01: names are unique, ignoring case. casefold() (not lower()) so that
        # "Straße" and "STRASSE" count as the same name. See DEF-001.
        if any(a.name.casefold() == data.name.casefold() for a in self._assets.values()):
            raise ConflictError(f"An asset named '{data.name}' already exists")
        asset = Asset(id=self._next_asset_id, **data.model_dump())
        self._assets[asset.id] = asset
        self._next_asset_id += 1
        return asset

    def get_asset(self, asset_id: int) -> Asset:
        try:
            return self._assets[asset_id]
        except KeyError:
            raise NotFoundError(f"Asset {asset_id} not found") from None

    def list_assets(
        self, asset_type: AssetType | None = None, status: AssetStatus | None = None
    ) -> list[Asset]:
        assets = sorted(self._assets.values(), key=lambda a: a.id)
        if asset_type is not None:
            assets = [a for a in assets if a.type == asset_type]
        if status is not None:
            assets = [a for a in assets if a.status == status]
        return assets

    def set_status(self, asset_id: int, status: AssetStatus) -> Asset:
        asset = self.get_asset(asset_id)
        # BR-10: an asset with an open outage stays out of service until the outage is resolved
        if self._open_outage_for(asset_id) is not None and status != AssetStatus.OUT_OF_SERVICE:
            raise ConflictError("Resolve the open outage before changing this asset's status")
        asset.status = status
        return asset

    def delete_asset(self, asset_id: int) -> None:
        self.get_asset(asset_id)
        # BR-09: assets with an open outage cannot be deleted
        if self._open_outage_for(asset_id) is not None:
            raise ConflictError("Cannot delete an asset with an open outage")
        del self._assets[asset_id]

    # ---------- outages ----------

    def report_outage(self, data: OutageCreate) -> Outage:
        asset = self.get_asset(data.asset_id)
        # BR-06: only one open outage per asset
        if self._open_outage_for(asset.id) is not None:
            raise ConflictError(f"Asset {asset.id} already has an open outage")
        outage = Outage(id=self._next_outage_id, **data.model_dump())
        self._outages[outage.id] = outage
        self._next_outage_id += 1
        asset.status = AssetStatus.OUT_OF_SERVICE
        return outage

    def resolve_outage(self, outage_id: int, resolved_at) -> Outage:
        try:
            outage = self._outages[outage_id]
        except KeyError:
            raise NotFoundError(f"Outage {outage_id} not found") from None
        # BR-08: resolve once, and only after the outage started
        if not outage.is_open:
            raise ConflictError(f"Outage {outage_id} is already resolved")
        if resolved_at <= outage.started_at:
            raise RuleViolationError("resolved_at must be after started_at")
        outage.resolved_at = resolved_at
        if outage.asset_id in self._assets:
            self._assets[outage.asset_id].status = AssetStatus.IN_SERVICE
        return outage

    def list_outages(self, open_only: bool = False) -> list[Outage]:
        outages = sorted(self._outages.values(), key=lambda o: o.id)
        return [o for o in outages if o.is_open] if open_only else outages

    def _open_outage_for(self, asset_id: int) -> Outage | None:
        return next(
            (o for o in self._outages.values() if o.asset_id == asset_id and o.is_open), None
        )

    # ---------- GIS export ----------

    def to_geojson(self) -> dict:
        """GeoJSON FeatureCollection. GeoJSON (RFC 7946) orders coordinates as [longitude, latitude]."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": a.id,
                    "geometry": {"type": "Point", "coordinates": [a.longitude, a.latitude]},
                    "properties": {
                        "name": a.name,
                        "type": a.type.value,
                        "voltage_kv": a.voltage_kv,
                        "voltage_level": a.voltage_level.value,
                        "status": a.status.value,
                    },
                }
                for a in self.list_assets()
            ],
        }
