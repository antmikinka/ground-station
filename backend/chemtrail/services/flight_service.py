# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Flight data service for caching and querying OpenSky + FR24 data."""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from db.models import FlightCache
from ..api.opensky_client import OpenSkyClient, FlightState
from ..services.fr24_flight_service import FR24FlightService


class FlightService:
    """Service for managing flight data cache with dual-source support."""

    def __init__(self, session: AsyncSession, fr24_api_token: Optional[str] = None):
        self.session = session
        self.fr24_service = FR24FlightService(api_token=fr24_api_token)

    async def sync_flights_from_opensky(
        self,
        client: OpenSkyClient,
        area_bounds: Optional[Dict[str, float]] = None
    ) -> int:
        """
        Sync current flights from OpenSky API to cache.

        Args:
            client: OpenSky API client
            area_bounds: Optional bounding box {lat_min, lat_max, lon_min, lon_max}

        Returns:
            Number of flights synced
        """
        try:
            if area_bounds:
                flights = await client.get_flights_in_area(**area_bounds)
            else:
                flights = await client.get_all_flights()

            synced = 0
            now = datetime.now(timezone.utc)

            for flight in flights:
                await self._upsert_flight(flight, now)
                synced += 1

            logger.info(f"Synced {synced} flights from OpenSky")
            return synced

        except Exception as e:
            logger.error(f"Error syncing flights: {e}")
            return 0

    async def _upsert_flight(self, flight: FlightState, timestamp: datetime):
        """Update or insert a single flight record."""
        position_data = {
            "lat": flight.latitude,
            "lon": flight.longitude,
            "alt": flight.baro_altitude,
            "heading": flight.true_track,
            "velocity": flight.velocity,
            "vertical_rate": flight.vertical_rate,
        }

        stmt = select(FlightCache).filter(FlightCache.icao24 == flight.icao24)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            position_history = existing.position_history or []
            position_history.append({
                "timestamp": timestamp.isoformat(),
                **position_data
            })
            position_history = position_history[-100:]

            upd_stmt = (
                update(FlightCache)
                .where(FlightCache.icao24 == flight.icao24)
                .values(
                    callsign=flight.callsign,
                    position=position_data,
                    last_position_update=timestamp,
                    position_history=position_history,
                    vertical_rate=flight.vertical_rate,
                    data_sources=self._merge_data_sources(existing.data_sources, "opensky"),
                    updated_at=timestamp,
                )
            )
            await self.session.execute(upd_stmt)
        else:
            insert_stmt = insert(FlightCache).values(
                icao24=flight.icao24,
                callsign=flight.callsign,
                origin_country=flight.origin_country,
                position=position_data,
                last_position_update=timestamp,
                position_history=[{"timestamp": timestamp.isoformat(), **position_data}],
                vertical_rate=flight.vertical_rate,
                first_seen=timestamp,
                data_sources=["opensky"],
                updated_at=timestamp,
            )
            await self.session.execute(insert_stmt)

    async def get_flight(self, icao24: str) -> Optional[Dict]:
        """Get cached flight by ICAO24."""
        stmt = select(FlightCache).filter(FlightCache.icao24 == icao24)
        result = await self.session.execute(stmt)
        flight = result.scalar_one_or_none()

        if flight:
            return {
                "icao24": flight.icao24,
                "callsign": flight.callsign,
                "position": flight.position,
                "last_update": flight.last_position_update,
                "fr24_id": flight.fr24_id,
                "registration": flight.registration,
                "aircraft_type": flight.aircraft_type,
            }
        return None

    async def get_flights_near_position(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get flights near a given position.

        Simple bounding box approximation.
        """
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * abs(lat / 90.0) if lat != 0 else 111.0)

        stmt = select(FlightCache).filter(
            FlightCache.position.is_not(None),
            FlightCache.position["lat"] >= lat - lat_delta,
            FlightCache.position["lat"] <= lat + lat_delta,
            FlightCache.position["lon"] >= lon - lon_delta,
            FlightCache.position["lon"] <= lon + lon_delta,
        ).limit(limit)

        result = await self.session.execute(stmt)
        flights = result.scalars().all()

        return [
            {
                "icao24": f.icao24,
                "callsign": f.callsign,
                "position": f.position,
                "last_update": f.last_position_update,
                "fr24_id": f.fr24_id,
                "registration": f.registration,
                "aircraft_type": f.aircraft_type,
                "painted_as": f.painted_as,
                "operating_as": f.operating_as,
                "origin_icao": f.origin_icao,
                "destination_icao": f.destination_icao,
                "data_sources": f.data_sources,
            }
            for f in flights
        ]

    async def _enrich_with_fr24_data(self) -> int:
        """
        Enrich cached flights with FR24 data.

        Runs FR24 queries in executor to avoid blocking async code.
        Returns number of flights enriched.
        """
        enriched = 0

        stmt = select(FlightCache)
        result = await self.session.execute(stmt)
        flights = result.scalars().all()

        for flight in flights[:50]:
            try:
                existing_data = {
                    "icao24": flight.icao24,
                    "callsign": flight.callsign,
                    "position": flight.position,
                    "last_update": flight.last_position_update,
                }

                enriched_data = await asyncio.to_thread(
                    self.fr24_service.enrich_flight_cache_entry,
                    flight.icao24,
                    existing_data,
                )

                if enriched_data.get("fr24_id"):
                    update_stmt = (
                        update(FlightCache)
                        .where(FlightCache.icao24 == flight.icao24)
                        .values(
                            fr24_id=enriched_data.get("fr24_id"),
                            painted_as=enriched_data.get("painted_as"),
                            operating_as=enriched_data.get("operating_as"),
                            origin_icao=enriched_data.get("origin_icao"),
                            origin_iata=enriched_data.get("origin_iata"),
                            destination_icao=enriched_data.get("destination_icao"),
                            destination_iata=enriched_data.get("destination_iata"),
                            flight_track=enriched_data.get("flight_track"),
                            data_sources=self._merge_data_sources(existing_data.get("data_sources", flight.data_sources), "fr24"),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    await self.session.execute(update_stmt)
                    enriched += 1

            except Exception as e:
                logger.error(f"Error enriching flight {flight.icao24} with FR24 data: {e}")
                continue

        if enriched > 0:
            logger.info(f"Enriched {enriched} flights with FR24 data")
        return enriched

    async def sync_flights_from_fr24(
        self,
        area_bounds: Optional[Dict[str, float]] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Sync flights directly from FR24 API.

        Args:
            area_bounds: Optional bounding box for filtering
            timestamp: For historical queries (defaults to now for live data)

        Returns:
            Number of flights synced
        """
        target_time = timestamp or datetime.now(timezone.utc)

        if area_bounds:
            center_lat = (area_bounds.get("lat_min", 0) + area_bounds.get("lat_max", 0)) / 2
            center_lon = (area_bounds.get("lon_min", 0) + area_bounds.get("lon_max", 0)) / 2
            radius = 500
        else:
            center_lat = 0
            center_lon = 0
            radius = 500

        def fetch_fr24_positions():
            return self.fr24_service.get_positions_near_time_and_location(
                timestamp=target_time,
                lat=center_lat,
                lon=center_lon,
                radius_km=radius,
                limit=1000,
            )

        try:
            positions = await asyncio.to_thread(fetch_fr24_positions)

            synced = 0
            now = datetime.now(timezone.utc)

            for pos in positions:
                await self._upsert_fr24_position(pos, now)
                synced += 1

            logger.info(f"Synced {synced} flights from FR24")
            return synced

        except Exception as e:
            logger.error(f"Error syncing flights from FR24: {e}")
            return 0

    async def _upsert_fr24_position(self, position: Dict, timestamp: datetime):
        """Insert or update a flight from FR24 data."""
        hex_code = position.get("hex", "")
        if not hex_code:
            return

        position_data = {
            "lat": position.get("latitude"),
            "lon": position.get("longitude"),
            "alt": position.get("altitude"),
            "heading": position.get("track"),
            "velocity": position.get("ground_speed"),
            "vertical_rate": position.get("vertical_rate"),
        }

        stmt = select(FlightCache).filter(FlightCache.icao24 == hex_code)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        eta_dt = None
        if position.get("eta"):
            try:
                eta_str = position["eta"]
                if isinstance(eta_str, str):
                    eta_str = eta_str.replace("Z", "+00:00")
                eta_dt = datetime.fromisoformat(eta_str)
            except (ValueError, TypeError):
                pass

        if existing:
            position_history = existing.position_history or []
            position_history.append({
                "timestamp": timestamp.isoformat(),
                **position_data
            })
            position_history = position_history[-100:]

            upd_stmt = (
                update(FlightCache)
                .where(FlightCache.icao24 == hex_code)
                .values(
                    callsign=position.get("callsign") or existing.callsign,
                    registration=position.get("registration") or existing.registration,
                    aircraft_type=position.get("aircraft_type") or existing.aircraft_type,
                    fr24_id=position.get("fr24_id"),
                    squawk=position.get("squawk"),
                    vertical_rate=position.get("vertical_rate"),
                    painted_as=position.get("painted_as"),
                    operating_as=position.get("operating_as"),
                    origin_icao=position.get("origin_icao"),
                    destination_icao=position.get("destination_icao"),
                    eta=eta_dt,
                    position=position_data,
                    last_position_update=timestamp,
                    position_history=position_history,
                    data_sources=self._merge_data_sources(existing.data_sources, "fr24"),
                    updated_at=timestamp,
                )
            )
            await self.session.execute(upd_stmt)
        else:
            insert_stmt = insert(FlightCache).values(
                icao24=hex_code,
                callsign=position.get("callsign"),
                registration=position.get("registration"),
                aircraft_type=position.get("aircraft_type"),
                fr24_id=position.get("fr24_id"),
                squawk=position.get("squawk"),
                vertical_rate=position.get("vertical_rate"),
                painted_as=position.get("painted_as"),
                operating_as=position.get("operating_as"),
                origin_icao=position.get("origin_icao"),
                origin_iata=position.get("origin_iata"),
                destination_icao=position.get("destination_icao"),
                destination_iata=position.get("destination_iata"),
                eta=eta_dt,
                position=position_data,
                last_position_update=timestamp,
                position_history=[{"timestamp": timestamp.isoformat(), **position_data}],
                first_seen=timestamp,
                data_sources=["fr24"],
                updated_at=timestamp,
            )
            await self.session.execute(insert_stmt)

    @staticmethod
    def _merge_data_sources(existing: Optional[List], new_source: str) -> List[str]:
        """Merge data source lists, avoiding duplicates."""
        sources = set(existing or [])
        sources.add(new_source)
        return list(sources)
