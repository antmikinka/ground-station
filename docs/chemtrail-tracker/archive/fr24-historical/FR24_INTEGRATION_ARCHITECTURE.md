# Flightradar24 (FR24) Integration Architecture

**Document Version:** 1.0  
**Date:** 2026-04-11  
**Author:** Dr. Sarah Kim, Technical Product Strategist  
**Status:** Ready for Implementation  

---

## Executive Summary

This document defines the architecture for integrating the Flightradar24 Python SDK into the existing chemtrail webcam tracker system. The integration enhances flight data coverage by adding FR24 as a secondary data source alongside OpenSky, providing richer flight metadata, historical data access (back to 2016-05-11), and improved correlation accuracy for contrail detection.

### Key Benefits

- **Dual-source redundancy:** FR24 supplements OpenSky data, improving coverage and reliability
- **Richer metadata:** Access to airline branding (`painted_as`, `operating_as`), detailed airport codes, and flight timing
- **Historical analysis:** Query flight positions dating back to May 2016
- **Flight track correlation:** Complete positional tracks for verified flight path matching
- **Enhanced detection metadata:** More comprehensive flight information in archived detection records

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Chemtrail Detection Pipeline                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐      ┌─────────────────────────────────────────────┐  │
│  │                  │      │           FlightService (Async)              │  │
│  │  OpenSkyClient   │─────►│  ┌─────────────────────────────────────┐    │  │
│  │  (Async Native)  │      │  │      Primary: OpenSky (async)       │    │  │
│  │                  │      │  │      Secondary: FR24 (executor)     │    │  │
│  └──────────────────┘      │  │      Correlation: ICAO hex merge    │    │  │
│                            │  └─────────────────────────────────────┘    │  │
│  ┌──────────────────┐      │                                              │  │
│  │                  │      │  ┌─────────────────────────────────────┐    │  │
│  │  FR24Client      │─────►│  │         FR24FlightService            │    │  │
│  │  (Sync Wrapper)  │      │  │  - Runs in asyncio.to_thread()       │    │  │
│  │                  │      │  │  - Sync FR24 SDK calls               │    │  │
│  └──────────────────┘      │  │  - Data transformation               │    │  │
│                            │  └─────────────────────────────────────┘    │  │
│                            └─────────────────────────────────────────────┘  │
│                                           │                                  │
│                                           ▼                                  │
│                            ┌─────────────────────────────────────────────┐  │
│                            │            FlightCache Model                 │  │
│                            │  - icao24 (PK) / hex (FR24 alias)           │  │
│                            │  - FR24-specific fields added               │  │
│                            │  - Unified position_history                 │  │
│                            └─────────────────────────────────────────────┘  │
│                                           │                                  │
│                                           ▼                                  │
│                            ┌─────────────────────────────────────────────┐  │
│                            │         DetectionService                     │  │
│                            │  - Enhanced flight correlation metadata      │  │
│                            │  - Priority: FR24 > OpenSky for richness    │  │
│                            │  - Flight tracks enrichment                 │  │
│                            └─────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Files to Create

### 1. `chemtrail/api/fr24_client.py`

**Purpose:** Synchronous wrapper around the FR24 SDK that provides a clean interface for the chemtrail system.

**Location:** `C:\Users\antmi\ground-station\backend\chemtrail\api\fr24_client.py`

```python
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

"""Flightradar24 API client wrapper for chemtrail tracker."""

from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass

from fr24sdk import Client as FR24BaseClient
from fr24sdk.models.flight import (
    FlightPositionsFull,
    FlightSummaryFull,
    FlightTracks,
    FlightTrackPoint,
)
from fr24sdk.models.geographic import Boundary, AltitudeRange


@dataclass
class FR24FlightPosition:
    """Normalized flight position from FR24."""
    fr24_id: str
    hex: str  # ICAO 24-bit hex (equivalent to OpenSky icao24)
    callsign: Optional[str]
    latitude: float
    longitude: float
    altitude: int  # feet
    ground_speed: int  # knots
    vertical_rate: int  # feet/min
    track: int  # heading degrees
    squawk: str
    timestamp: datetime
    aircraft_type: Optional[str]
    registration: Optional[str]
    origin_icao: Optional[str]
    origin_iata: Optional[str]
    destination_icao: Optional[str]
    destination_iata: Optional[str]
    eta: Optional[datetime]
    painted_as: Optional[str]  # Airline ICAO (branding)
    operating_as: Optional[str]  # Airline ICAO (operator)


@dataclass
class FR24FlightSummary:
    """Flight summary from FR24."""
    fr24_id: str
    hex: str
    callsign: Optional[str]
    flight_number: Optional[str]
    aircraft_type: Optional[str]
    registration: Optional[str]
    origin_icao: Optional[str]
    origin_iata: Optional[str]
    destination_icao: Optional[str]
    destination_iata: Optional[str]
    datetime_takeoff: Optional[datetime]
    runway_takeoff: Optional[str]
    datetime_landed: Optional[datetime]
    runway_landed: Optional[str]
    flight_time: Optional[float]  # seconds
    actual_distance: Optional[float]  # km
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    flight_ended: Optional[bool]
    painted_as: Optional[str]
    operating_as: Optional[str]


@dataclass
class FR24FlightTrack:
    """Flight track with positional points."""
    fr24_id: str
    tracks: List[Dict]  # List of {timestamp, lat, lon, alt, gspeed, vspeed, track, squawk}


class FR24Client:
    """
    Wrapper for Flightradar24 SDK client.
    
    Provides methods needed by chemtrail tracker with normalized data structures.
    All methods are synchronous and should be called via asyncio.to_thread()
    when used from async code.
    
    Usage:
        # Synchronous
        with FR24Client() as client:
            positions = client.get_live_positions(bounds={...})
        
        # Async (recommended)
        positions = await asyncio.to_thread(
            client.get_live_positions, bounds={...}
        )
    """
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize FR24 client.
        
        Args:
            api_token: FR24 API token. If None, reads from FR24_API_TOKEN env var.
        """
        self._client: Optional[FR24BaseClient] = None
        self._api_token = api_token
    
    def __enter__(self) -> "FR24Client":
        self._client = FR24BaseClient(api_token=self._api_token)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            self._client.close()
    
    def get_live_positions(
        self,
        bounds: Optional[Dict[str, float]] = None,
        callsigns: Optional[List[str]] = None,
        registrations: Optional[List[str]] = None,
        altitude_range: Optional[Dict[str, int]] = None,
        ground_speed: Optional[int] = None,
        limit: int = 1000,
    ) -> List[FR24FlightPosition]:
        """
        Get live flight positions with optional filters.
        
        Args:
            bounds: Bounding box {north, south, west, east}
            callsigns: Filter by callsigns
            registrations: Filter by aircraft registrations
            altitude_range: Altitude filter {min_altitude, max_altitude} in feet
            ground_speed: Maximum ground speed filter
            limit: Maximum number of results (1-30000)
        
        Returns:
            List of FR24FlightPosition objects
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")
        
        boundary = None
        if bounds:
            boundary = Boundary(
                north=bounds["north"],
                south=bounds["south"],
                west=bounds["west"],
                east=bounds["east"],
            )
        
        altitude_ranges = None
        if altitude_range:
            altitude_ranges = [AltitudeRange(
                min_altitude=altitude_range["min_altitude"],
                max_altitude=altitude_range["max_altitude"],
            )]
        
        response = self._client.live.get_full(
            bounds=boundary,
            callsigns=callsigns,
            registrations=registrations,
            altitude_ranges=altitude_ranges,
            gspeed=ground_speed,
            limit=limit,
        )
        
        return [self._map_position(pos) for pos in (response.data or [])]
    
    def get_historic_positions(
        self,
        timestamp: Union[int, datetime],
        bounds: Optional[Dict[str, float]] = None,
        callsigns: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> List[FR24FlightPosition]:
        """
        Get historical flight positions for a specific timestamp.
        
        Args:
            timestamp: UNIX timestamp or datetime object (min: 2016-05-11)
            bounds: Bounding box {north, south, west, east}
            callsigns: Filter by callsigns
            limit: Maximum number of results
        
        Returns:
            List of FR24FlightPosition objects
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")
        
        boundary = None
        if bounds:
            boundary = Boundary(
                north=bounds["north"],
                south=bounds["south"],
                west=bounds["west"],
                east=bounds["east"],
            )
        
        response = self._client.historic.get_full(
            timestamp=timestamp,
            bounds=boundary,
            callsigns=callsigns,
            limit=limit,
        )
        
        return [self._map_position(pos) for pos in (response.data or [])]
    
    def get_flight_tracks(self, flight_id: str) -> FR24FlightTrack:
        """
        Get positional track for a specific flight.
        
        Args:
            flight_id: FR24 flight ID (hex format, e.g., "34242a02")
        
        Returns:
            FR24FlightTrack with list of track points
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")
        
        response = self._client.flight_tracks.get(flight_id=flight_id)
        
        # Return first track if multiple exist
        track_data = response.data[0] if response.data else None
        if not track_data:
            return FR24FlightTrack(fr24_id=flight_id, tracks=[])
        
        return FR24FlightTrack(
            fr24_id=track_data.fr24_id,
            tracks=[
                {
                    "timestamp": point.timestamp,
                    "lat": point.lat,
                    "lon": point.lon,
                    "alt": point.alt,
                    "gspeed": point.gspeed,
                    "vspeed": point.vspeed,
                    "track": point.track,
                    "squawk": point.squawk,
                }
                for point in (track_data.tracks or [])
            ],
        )
    
    def get_flight_summary(
        self,
        flight_ids: Optional[List[str]] = None,
        callsigns: Optional[List[str]] = None,
        flight_datetime_from: Optional[datetime] = None,
        flight_datetime_to: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[FR24FlightSummary]:
        """
        Get flight summary information.
        
        Args:
            flight_ids: List of FR24 flight IDs
            callsigns: Filter by callsigns
            flight_datetime_from: Start of time range
            flight_datetime_to: End of time range
            limit: Maximum number of results
        
        Returns:
            List of FR24FlightSummary objects
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use context manager.")
        
        response = self._client.flight_summary.get_full(
            flight_ids=flight_ids,
            callsigns=callsigns,
            flight_datetime_from=flight_datetime_from,
            flight_datetime_to=flight_datetime_to,
            limit=limit,
        )
        
        return [self._map_summary(summary) for summary in (response.data or [])]
    
    @staticmethod
    def _map_position(pos: FlightPositionsFull) -> FR24FlightPosition:
        """Map FR24 API position to normalized dataclass."""
        # Parse timestamp
        try:
            ts = datetime.fromisoformat(pos.timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.now(timezone.utc)
        
        # Parse ETA if present
        eta = None
        if pos.eta:
            try:
                eta = datetime.fromisoformat(pos.eta.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return FR24FlightPosition(
            fr24_id=pos.fr24_id,
            hex=pos.hex or "",
            callsign=pos.callsign,
            latitude=pos.lat,
            longitude=pos.lon,
            altitude=pos.alt,
            ground_speed=pos.gspeed,
            vertical_rate=pos.vspeed,
            track=pos.track,
            squawk=pos.squawk,
            timestamp=ts,
            aircraft_type=pos.type,
            registration=pos.reg,
            origin_icao=pos.orig_icao,
            origin_iata=pos.orig_iata,
            destination_icao=pos.dest_icao,
            destination_iata=pos.dest_iata,
            eta=eta,
            painted_as=pos.painted_as,
            operating_as=pos.operating_as,
        )
    
    @staticmethod
    def _map_summary(summary: FlightSummaryFull) -> FR24FlightSummary:
        """Map FR24 API summary to normalized dataclass."""
        def parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        
        return FR24FlightSummary(
            fr24_id=summary.fr24_id,
            hex=summary.hex or "",
            callsign=summary.callsign,
            flight_number=summary.flight,
            aircraft_type=summary.type,
            registration=summary.reg,
            origin_icao=summary.orig_icao,
            origin_iata=summary.orig_iata,
            destination_icao=summary.dest_icao,
            destination_iata=summary.dest_iata,
            datetime_takeoff=parse_dt(summary.datetime_takeoff),
            runway_takeoff=summary.runway_takeoff,
            datetime_landed=parse_dt(summary.datetime_landed),
            runway_landed=summary.runway_landed,
            flight_time=summary.flight_time,
            actual_distance=summary.actual_distance,
            first_seen=parse_dt(summary.first_seen),
            last_seen=parse_dt(summary.last_seen),
            flight_ended=summary.flight_ended,
            painted_as=summary.painted_as,
            operating_as=summary.operating_as,
        )
```

---

### 2. `chemtrail/services/fr24_flight_service.py`

**Purpose:** Synchronous service that uses FR24 client to fetch and transform flight data. Runs in executor for async compatibility.

**Location:** `C:\Users\antmi\ground-station\backend\chemtrail\services\fr24_flight_service.py`

```python
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

"""FR24 flight data service for chemtrail tracker."""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import asyncio

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from ..db.models import FlightCache
from ..api.fr24_client import FR24Client, FR24FlightPosition, FR24FlightSummary


class FR24FlightService:
    """
    Service for fetching flight data from Flightradar24 API.
    
    This service is synchronous and should be called via asyncio.to_thread()
    when used from async code. It handles FR24-specific data transformation
    and correlation with the FlightCache model.
    
    Key responsibilities:
    - Fetch live/historic positions from FR24
    - Fetch flight summaries and tracks
    - Transform FR24 data to FlightCache-compatible format
    - Correlate FR24 hex codes with OpenSky icao24 (same format)
    """
    
    def __init__(self, session: AsyncSession, api_token: Optional[str] = None):
        """
        Initialize FR24 flight service.
        
        Args:
            session: Async SQLAlchemy session (used synchronously via run_sync)
            api_token: FR24 API token (optional, falls back to env var)
        """
        self.session = session
        self.api_token = api_token
    
    def get_positions_near_time_and_location(
        self,
        timestamp: datetime,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        time_tolerance_seconds: int = 60,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get FR24 flight positions near a specific time and location.
        
        Args:
            timestamp: Target timestamp for historical query
            lat: Latitude center point
            lon: Longitude center point
            radius_km: Search radius in kilometers
            time_tolerance_seconds: Time window for historical search
            limit: Maximum results
        
        Returns:
            List of normalized flight position dicts
        """
        # Calculate bounding box
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * abs(lat / 90.0) if lat != 0 else 111.0)
        
        bounds = {
            "north": lat + lat_delta,
            "south": lat - lat_delta,
            "west": lon - lon_delta,
            "east": lon + lon_delta,
        }
        
        # Determine if querying historical or live data
        now = datetime.now(timezone.utc)
        time_diff = abs((now - timestamp).total_seconds())
        
        with FR24Client(api_token=self.api_token) as client:
            if time_diff > time_tolerance_seconds:
                # Historical query
                positions = client.get_historic_positions(
                    timestamp=timestamp,
                    bounds=bounds,
                    limit=limit,
                )
            else:
                # Live query
                positions = client.get_live_positions(
                    bounds=bounds,
                    limit=limit,
                )
            
            return [self._position_to_dict(pos) for pos in positions]
    
    def get_flight_track(self, fr24_id: str) -> Optional[Dict]:
        """
        Get flight track for a specific flight.
        
        Args:
            fr24_id: FR24 flight ID (hex format)
        
        Returns:
            Dict with fr24_id and tracks list, or None if not found
        """
        try:
            with FR24Client(api_token=self.api_token) as client:
                track = client.get_flight_tracks(flight_id=fr24_id)
                
                if not track.tracks:
                    return None
                
                return {
                    "fr24_id": track.fr24_id,
                    "tracks": track.tracks,
                }
        except Exception as e:
            logger.error(f"Error fetching FR24 flight track for {fr24_id}: {e}")
            return None
    
    def get_flight_summary_by_hex(self, hex_code: str) -> Optional[Dict]:
        """
        Get flight summary by ICAO hex code.
        
        Args:
            hex_code: ICAO 24-bit hex code
        
        Returns:
            Dict with flight summary data, or None if not found
        """
        try:
            with FR24Client(api_token=self.api_token) as client:
                # Search by callsign derived from hex (if available)
                # Note: FR24 doesn't support direct hex search in summary
                # We use flight_tracks to get fr24_id first, then summary
                tracks = client.get_flight_tracks(flight_id=hex_code)
                
                if not tracks.tracks:
                    return None
                
                # Get summary using fr24_id from track
                summaries = client.get_flight_summary(
                    flight_ids=[tracks.fr24_id],
                    limit=1,
                )
                
                if not summaries:
                    return None
                
                return self._summary_to_dict(summaries[0])
        except Exception as e:
            logger.error(f"Error fetching FR24 flight summary for {hex_code}: {e}")
            return None
    
    def enrich_flight_cache_entry(
        self,
        icao24: str,
        existing_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Enrich a FlightCache entry with FR24-specific data.
        
        Args:
            icao24: ICAO 24-bit hex code (same format in FR24 and OpenSky)
            existing_data: Existing flight data from OpenSky (optional)
        
        Returns:
            Dict with merged data from both sources
        """
        enriched = existing_data or {}
        
        # Get flight summary from FR24
        summary = self.get_flight_summary_by_hex(icao24)
        if summary:
            enriched.update({
                "fr24_id": summary.get("fr24_id"),
                "painted_as": summary.get("painted_as"),
                "operating_as": summary.get("operating_as"),
                "origin_icao": summary.get("origin_icao"),
                "origin_iata": summary.get("origin_iata"),
                "destination_icao": summary.get("destination_icao"),
                "destination_iata": summary.get("destination_iata"),
                "datetime_takeoff": summary.get("datetime_takeoff"),
                "datetime_landed": summary.get("datetime_landed"),
                "flight_time": summary.get("flight_time"),
            })
        
        # Get flight track
        track = self.get_flight_track(icao24)
        if track:
            enriched["flight_track"] = track.get("tracks", [])
        
        return enriched
    
    @staticmethod
    def _position_to_dict(pos: FR24FlightPosition) -> Dict:
        """Convert FR24FlightPosition to dict for FlightCache."""
        return {
            "fr24_id": pos.fr24_id,
            "hex": pos.hex,
            "callsign": pos.callsign,
            "latitude": pos.latitude,
            "longitude": pos.longitude,
            "altitude": pos.altitude,
            "ground_speed": pos.ground_speed,
            "vertical_rate": pos.vertical_rate,
            "track": pos.track,
            "squawk": pos.squawk,
            "timestamp": pos.timestamp.isoformat(),
            "aircraft_type": pos.aircraft_type,
            "registration": pos.registration,
            "origin_icao": pos.origin_icao,
            "destination_icao": pos.destination_icao,
            "painted_as": pos.painted_as,
            "operating_as": pos.operating_as,
            "eta": pos.eta.isoformat() if pos.eta else None,
        }
    
    @staticmethod
    def _summary_to_dict(summary: FR24FlightSummary) -> Dict:
        """Convert FR24FlightSummary to dict."""
        return {
            "fr24_id": summary.fr24_id,
            "hex": summary.hex,
            "callsign": summary.callsign,
            "flight_number": summary.flight_number,
            "aircraft_type": summary.aircraft_type,
            "registration": summary.registration,
            "origin_icao": summary.origin_icao,
            "origin_iata": summary.origin_iata,
            "destination_icao": summary.destination_icao,
            "destination_iata": summary.destination_iata,
            "datetime_takeoff": summary.datetime_takeoff.isoformat() if summary.datetime_takeoff else None,
            "runway_takeoff": summary.runway_takeoff,
            "datetime_landed": summary.datetime_landed.isoformat() if summary.datetime_landed else None,
            "runway_landed": summary.runway_landed,
            "flight_time": summary.flight_time,
            "actual_distance": summary.actual_distance,
            "first_seen": summary.first_seen.isoformat() if summary.first_seen else None,
            "last_seen": summary.last_seen.isoformat() if summary.last_seen else None,
            "flight_ended": summary.flight_ended,
            "painted_as": summary.painted_as,
            "operating_as": summary.operating_as,
        }
```

---

## Files to Modify

### 3. `db/models.py` - Enhance FlightCache Model

**Purpose:** Add FR24-specific fields to the FlightCache model.

**Location:** `C:\Users\antmi\ground-station\backend\db\models.py`

**Changes:** Modify the `FlightCache` class (lines 571-603) to add the following fields:

```python
class FlightCache(Base):
    """
    Cached flight data from OpenSky/FR24 APIs.

    Stores recent flight positions and history for correlation with detections.
    Supports dual-source data from both OpenSky and Flightradar24.
    """
    __tablename__ = "flight_cache"

    icao24 = Column(String, primary_key=True, nullable=False)
    callsign = Column(String, nullable=True, index=True)
    registration = Column(String, nullable=True)
    aircraft_type = Column(String, nullable=True)
    origin = Column(String, nullable=True)  # OpenSky origin_country
    destination = Column(String, nullable=True)

    # FR24-specific fields
    fr24_id = Column(String, nullable=True, index=True)  # FR24 flight ID
    squawk = Column(String, nullable=True)  # Transponder code
    vertical_rate = Column(Integer, nullable=True)  # Feet per minute
    painted_as = Column(String, nullable=True)  # Airline ICAO (branding)
    operating_as = Column(String, nullable=True)  # Airline ICAO (operator)
    eta = Column(AwareDateTime, nullable=True)  # Estimated time of arrival
    
    # FR24 airport codes (more detailed than origin/destination)
    origin_icao = Column(String, nullable=True)
    origin_iata = Column(String, nullable=True)
    destination_icao = Column(String, nullable=True)
    destination_iata = Column(String, nullable=True)

    # Current position (updated from API)
    position = Column(JSON, nullable=True)  # {lat, lon, alt, heading, velocity}
    last_position_update = Column(AwareDateTime, nullable=True, index=True)

    # Position history (for correlation with detections)
    position_history = Column(JSON, nullable=True)  # Array of {timestamp, lat, lon, alt}

    # Flight track data from FR24
    flight_track = Column(JSON, nullable=True)  # Array of track points from FR24

    # Raw API responses (for debugging/reprocessing)
    raw_message = Column(JSON, nullable=True)  # OpenSky raw response
    fr24_raw_message = Column(JSON, nullable=True)  # FR24 raw response

    # Data source tracking
    data_sources = Column(JSON, nullable=True)  # ["opensky", "fr24"] - which sources contributed

    # Timestamps
    first_seen = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )
```

**Database Migration Required:** Create an Alembic migration to add the new columns:

```bash
alembic revision -m "add_fr24_fields_to_flight_cache"
```

---

### 4. `chemtrail/services/flight_service.py` - Integrate FR24 as Secondary Source

**Purpose:** Modify existing FlightService to use FR24 data alongside OpenSky.

**Location:** `C:\Users\antmi\ground-station\backend\chemtrail\services\flight_service.py`

**Key Changes:**

1. Add import for FR24 client and asyncio
2. Add methods for FR24 integration
3. Modify `_upsert_flight` to handle FR24 data
4. Add correlation logic for merging OpenSky and FR24 data

**Modified file structure:**

```python
# Add imports at top
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from db.models import FlightCache
from ..api.opensky_client import OpenSkyClient, FlightState
from ..api.fr24_client import FR24Client
from .fr24_flight_service import FR24FlightService


class FlightService:
    """Service for managing flight data cache with dual-source support."""

    def __init__(self, session: AsyncSession, fr24_api_token: Optional[str] = None):
        self.session = session
        self.fr24_service = FR24FlightService(session, api_token=fr24_api_token)

    async def sync_flights_from_opensky(
        self,
        client: OpenSkyClient,
        area_bounds: Optional[Dict[str, float]] = None
    ) -> int:
        # ... existing implementation ...
        # After syncing from OpenSky, enrich with FR24 data
        await self._enrich_with_fr24_data()
        return synced

    async def _enrich_with_fr24_data(self) -> int:
        """
        Enrich cached flights with FR24 data.
        
        Runs FR24 queries in executor to avoid blocking async code.
        Returns number of flights enriched.
        """
        enriched = 0
        
        # Get all cached flights
        stmt = select(FlightCache)
        result = await self.session.execute(stmt)
        flights = result.scalars().all()
        
        for flight in flights[:50]:  # Rate limit: process 50 at a time
            try:
                # Run FR24 enrichment in thread
                enriched_data = await asyncio.to_thread(
                    self.fr24_service.enrich_flight_cache_entry,
                    flight.icao24,
                    self._flight_to_dict(flight),
                )
                
                # Update if FR24 data found
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
                            data_sources=["opensky", "fr24"],
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                    await self.session.execute(update_stmt)
                    enriched += 1
                    
            except Exception as e:
                logger.error(f"Error enriching flight {flight.icao24} with FR24 data: {e}")
                continue
        
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
        
        def fetch_fr24_positions():
            return self.fr24_service.get_positions_near_time_and_location(
                timestamp=target_time,
                lat=(area_bounds.get("lat_min", 0) + area_bounds.get("lat_max", 0)) / 2 if area_bounds else 0,
                lon=(area_bounds.get("lon_min", 0) + area_bounds.get("lon_max", 0)) / 2 if area_bounds else 0,
                radius_km=500 if area_bounds else 500,  # Wide area
                limit=1000,
            )
        
        try:
            # Run FR24 query in thread
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
        
        # Check if exists
        stmt = select(FlightCache).filter(FlightCache.icao24 == hex_code)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing with FR24 data
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
                    eta=datetime.fromisoformat(position["eta"]) if position.get("eta") else None,
                    position=position_data,
                    last_position_update=timestamp,
                    position_history=position_history,
                    data_sources=self._merge_data_sources(existing.data_sources, "fr24"),
                    updated_at=timestamp,
                )
            )
            await self.session.execute(upd_stmt)
        else:
            # Insert new
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
                eta=datetime.fromisoformat(position["eta"]) if position.get("eta") else None,
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

    @staticmethod
    def _flight_to_dict(flight: FlightCache) -> Dict:
        """Convert FlightCache to dict."""
        return {
            "icao24": flight.icao24,
            "callsign": flight.callsign,
            "position": flight.position,
            "last_update": flight.last_position_update,
        }
```

---

### 5. `chemtrail/archive/detection_service.py` - Enhanced Flight Correlation

**Purpose:** Modify detection service to use FR24 data for richer flight correlation.

**Location:** `C:\Users\antmi\ground-station\backend\chemtrail\archive\detection_service.py`

**Key Changes:**

1. Import FR24 service
2. Enhance `_process_single_detection` to include FR24 flight data
3. Add flight track correlation for better matching
4. Include FR24-specific metadata in archived detections

**Changes to imports:**
```python
from ..services.fr24_flight_service import FR24FlightService
```

**Changes to `__init__`:**
```python
def __init__(
    self,
    session: AsyncSession,
    vector_store: ChemtrailVectorStore,
    flight_service: FlightService,
    contrail_detector: ContrailDetector,
    embedder: Optional[BaseEmbedder] = None,
    fr24_service: Optional[FR24FlightService] = None,  # Add this
):
    self.session = session
    self.vector_store = vector_store
    self.flight_service = flight_service
    self.fr24_service = fr24_service  # Store FR24 service
    self.contrail_detector = contrail_detector
    self.embedder = embedder or get_embedder()
```

**Changes to `_process_single_detection`:**

```python
async def _process_single_detection(
    self,
    detection: ContrailDetection,
    chunk: Dict,
    camera_id: str,
    camera_metadata: Dict,
    apply_overlay: bool,
) -> Dict:
    # ... existing az/el calculation code ...

    # Correlate with flights (existing OpenSky-based correlation)
    timestamp = datetime.fromtimestamp(
        chunk.get("start_time", 0),
        tz=timezone.utc
    )
    flight_match = await self.flight_service.get_flights_near_position(
        lat=est_lat,
        lon=est_lon,
        radius_km=10,
        limit=5,  # Get more candidates for better matching
    )

    icao24 = flight_match[0]["icao24"] if flight_match else None
    callsign = flight_match[0].get("callsign") if flight_match else None

    # Enhance with FR24 data if available and flight matched
    fr24_metadata = {}
    if icao24 and self.fr24_service:
        try:
            # Fetch FR24 enrichment in thread
            fr24_enrichment = await asyncio.to_thread(
                self.fr24_service.enrich_flight_cache_entry,
                icao24,
            )
            
            if fr24_enrichment:
                fr24_metadata = {
                    "fr24_id": fr24_enrichment.get("fr24_id"),
                    "painted_as": fr24_enrichment.get("painted_as"),
                    "operating_as": fr24_enrichment.get("operating_as"),
                    "origin_icao": fr24_enrichment.get("origin_icao"),
                    "origin_iata": fr24_enrichment.get("origin_iata"),
                    "destination_icao": fr24_enrichment.get("destination_icao"),
                    "destination_iata": fr24_enrichment.get("destination_iata"),
                    "flight_track": fr24_enrichment.get("flight_track"),
                    "data_sources": fr24_enrichment.get("data_sources", ["fr24"]),
                }
                
                # Update callsign if FR24 has better data
                if fr24_enrichment.get("callsign") and not callsign:
                    callsign = fr24_enrichment.get("callsign")
                    
        except Exception as e:
            logger.warning(f"FR24 enrichment failed for {icao24}: {e}")

    # Build enhanced metadata for archive
    archive_metadata = {
        "source_file": chunk["source_file"],
        "start_time": chunk["start_time"],
        "end_time": chunk["end_time"],
        "camera_id": camera_id,
        "camera_name": camera_metadata.get("name", "unknown"),
        "camera_lat": camera_metadata["latitude"],
        "camera_lon": camera_metadata["longitude"],
        "camera_alt": camera_metadata["altitude"],
        "detection_type": "contrail",
        "pixel_x": detection.start_x,
        "pixel_y": detection.start_y,
        "azimuth": az,
        "elevation": el,
        "estimated_lat": est_lat,
        "estimated_lon": est_lon,
        "estimated_alt": 10000,
        "confidence": detection.confidence,
        "contrail_vector": detection.to_dict(),
        "icao24": icao24,
        "callsign": callsign,
        "correlation_score": self._calculate_correlation_score(
            flight_match, fr24_metadata, est_lat, est_lon
        ),
        "position_method": "single_camera",
        "overlay_applied": False,
        # FR24-specific metadata
        "fr24_id": fr24_metadata.get("fr24_id"),
        "painted_as": fr24_metadata.get("painted_as"),
        "operating_as": fr24_metadata.get("operating_as"),
        "flight_origin": fr24_metadata.get("origin_iata") or fr24_metadata.get("origin_icao"),
        "flight_destination": fr24_metadata.get("destination_iata") or fr24_metadata.get("destination_icao"),
        "flight_track_points": len(fr24_metadata.get("flight_track", [])),
        "data_sources": fr24_metadata.get("data_sources", ["opensky"] if flight_match else []),
    }

    # ... rest of existing overlay and archival code ...
```

**Add new helper method:**
```python
def _calculate_correlation_score(
    self,
    flight_match: List[Dict],
    fr24_metadata: Dict,
    est_lat: float,
    est_lon: float,
) -> float:
    """
    Calculate correlation score based on flight match quality.
    
    Args:
        flight_match: List of matched flights from OpenSky
        fr24_metadata: Enrichment data from FR24
        est_lat: Estimated latitude of detection
        est_lon: Estimated longitude of detection
    
    Returns:
        Correlation score 0.0-1.0
    """
    if not flight_match:
        return 0.0
    
    base_score = 0.7  # Base score for OpenSky match
    
    # Boost score if FR24 data confirms the match
    if fr24_metadata.get("fr24_id"):
        base_score += 0.15
    
    # Boost if flight track available for verification
    if fr24_metadata.get("flight_track"):
        track = fr24_metadata["flight_track"]
        # Check if detection position is near any track point
        for point in track[:10]:  # Check first 10 points
            track_lat = point.get("lat", 0)
            track_lon = point.get("lon", 0)
            distance = ((est_lat - track_lat) ** 2 + (est_lon - track_lon) ** 2) ** 0.5
            if distance < 0.1:  # Within ~11km
                base_score += 0.15
                break
    
    return min(base_score, 1.0)
```

---

## Configuration Requirements

### 6. Configuration: FR24 API Key Setup

**Location:** Environment variable or application config

**Method 1: Environment Variable (Recommended)**
```bash
export FR24_API_TOKEN="your-fr24-api-token-here"
```

**Method 2: Application Config File**

Add to `data/configs/app_config.json`:
```json
{
  "chemtrail": {
    "fr24_api_token": "your-fr24-api-token-here",
    "fr24_enabled": true,
    "fr24_enrichment_limit": 50,
    "fr24_rate_limit_delay_ms": 1000
  }
}
```

**Access in code:**
```python
# From environment
import os
fr24_token = os.environ.get("FR24_API_TOKEN")

# Or from app config
from common.appconfig import load_app_config
config = load_app_config(Path("data/configs/app_config.json"))
fr24_token = config.get("chemtrail", {}).get("fr24_api_token")
```

---

## Architecture Decision Rationale

### 1. Sync FR24 SDK in Async Codebase

**Decision:** Use `asyncio.to_thread()` for FR24 SDK calls.

**Rationale:**
- FR24 SDK is synchronous (uses `httpx.Client`, not `httpx.AsyncClient`)
- `asyncio.to_thread()` (Python 3.9+) provides clean async/await syntax
- Avoids blocking the event loop during API calls
- Simpler than `run_in_executor` with equivalent performance

**Usage pattern:**
```python
result = await asyncio.to_thread(
    fr24_service.get_positions_near_time_and_location,
    timestamp=ts,
    lat=lat,
    lon=lon,
)
```

### 2. Separate FR24 Service vs Direct Integration

**Decision:** Create separate `FR24FlightService` class.

**Rationale:**
- Clean separation of concerns (OpenSky vs FR24)
- Easier to test and maintain
- Allows independent enablement/disablement
- Follows existing architecture pattern (`OpenSkyClient` + `FlightService`)

### 3. ICAO Hex Code Correlation

**Decision:** Use ICAO 24-bit hex codes as the correlation key.

**Rationale:**
- Both OpenSky (`icao24`) and FR24 (`hex`) use the same ICAO 24-bit format
- Unique identifier per aircraft (more reliable than callsign)
- Already the primary key in `FlightCache` model
- Enables seamless data merging from both sources

**Correlation logic:**
```python
# OpenSky icao24 == FR24 hex
icao24 = "4b1a02"  # OpenSky format
hex_code = "4b1a02"  # FR24 format - identical
```

### 4. Flight Track Storage Strategy

**Decision:** Store flight tracks in `FlightCache.flight_track` JSON column.

**Rationale:**
- Tracks are relatively small (typically 50-200 points)
- JSON provides flexible schema for track point structure
- Avoids creating separate table for simple use case
- Can be queried with SQLAlchemy JSON operators if needed

**Track point structure:**
```json
{
  "fr24_id": "34242a02",
  "tracks": [
    {
      "timestamp": "2026-04-11T10:30:00Z",
      "lat": 40.7128,
      "lon": -74.0060,
      "alt": 35000,
      "gspeed": 450,
      "vspeed": 0,
      "track": 270,
      "squawk": "1200"
    }
  ]
}
```

### 5. Data Source Priority

**Decision:** FR24 takes priority for metadata richness; OpenSky for real-time updates.

**Priority matrix:**

| Data Field | Primary Source | Fallback |
|------------|----------------|----------|
| Position (lat/lon/alt) | OpenSky (real-time) | FR24 |
| Callsign | OpenSky | FR24 |
| Aircraft Type | FR24 | OpenSky |
| Registration | FR24 | OpenSky |
| Origin/Destination | FR24 (ICAO/IATA) | OpenSky (country) |
| Airline Branding | FR24 (`painted_as`, `operating_as`) | N/A |
| Flight Track | FR24 | N/A |
| Squawk | FR24 | OpenSky |

**Merge strategy:**
1. OpenSky provides frequent position updates
2. FR24 enriches with detailed metadata
3. Both sources tracked in `data_sources` JSON field
4. Detection service uses merged data for correlation

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `chemtrail/api/fr24_client.py`
- [ ] Create `chemtrail/services/fr24_flight_service.py`
- [ ] Add FR24 fields to `FlightCache` model
- [ ] Create Alembic migration for FlightCache changes
- [ ] Configure FR24 API token in environment/config

### Phase 2: Flight Service Integration
- [ ] Modify `FlightService.__init__` to initialize FR24 service
- [ ] Add `sync_flights_from_fr24()` method
- [ ] Add `_upsert_fr24_position()` method
- [ ] Add `_enrich_with_fr24_data()` method
- [ ] Update `_upsert_flight()` to handle FR24 fields
- [ ] Test dual-source sync functionality

### Phase 3: Detection Service Enhancement
- [ ] Update `DetectionService.__init__` to accept FR24 service
- [ ] Enhance `_process_single_detection()` with FR24 enrichment
- [ ] Add `_calculate_correlation_score()` method
- [ ] Update archive metadata structure for FR24 fields
- [ ] Test detection correlation with FR24 data

### Phase 4: Testing & Validation
- [ ] Unit tests for `FR24Client`
- [ ] Unit tests for `FR24FlightService`
- [ ] Integration tests for dual-source sync
- [ ] Test historical data queries
- [ ] Test flight track retrieval
- [ ] Performance testing (rate limiting, caching)
- [ ] Error handling tests (API failures, timeouts)

### Phase 5: Documentation & Deployment
- [ ] Update README with FR24 integration details
- [ ] Document API token setup process
- [ ] Add monitoring/logging for FR24 API usage
- [ ] Create runbook for FR24 API issues
- [ ] Deploy to staging environment
- [ ] Validate in production

---

## API Rate Limits & Quotas

### FR24 API Limits

| Tier | Requests/Minute | Historical Access |
|------|-----------------|-------------------|
| Free | 60 | Last 7 days |
| Standard | 300 | Last 90 days |
| Premium | 1000+ | Full history (2016+) |

**Recommended rate limiting:**
- Implement request caching (5-minute TTL for live data)
- Batch enrichment requests (50 flights per batch)
- Use exponential backoff on 429 errors

### OpenSky API Limits

| Tier | Requests/Second |
|------|-----------------|
| Anonymous | 1 per 10 seconds |
| Member | 1 per second |

---

## Error Handling Strategy

### FR24 Client Error Handling

```python
from fr24sdk.exceptions import (
    Fr24SdkError,
    TransportError,
    ApiError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
)

async def safe_fr24_call(func, *args, **kwargs):
    """Wrapper for FR24 calls with error handling."""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except RateLimitError:
        logger.warning("FR24 rate limit hit, backing off")
        await asyncio.sleep(60)  # 1-minute backoff
        return None
    except AuthenticationError:
        logger.error("FR24 API authentication failed")
        return None
    except NotFoundError:
        logger.debug("FR24 data not found for request")
        return None
    except TransportError as e:
        logger.error(f"FR24 transport error: {e}")
        return None
    except Fr24SdkError as e:
        logger.error(f"FR24 SDK error: {e}")
        return None
```

---

## Monitoring & Observability

### Key Metrics to Track

```python
# Add to monitoring/observability system
FR24_API_REQUESTS_TOTAL = Counter(
    'fr24_api_requests_total',
    'Total FR24 API requests',
    ['endpoint', 'status']
)

FR24_ENRICHMENT_SUCCESS = Counter(
    'fr24_enrichment_success_total',
    'Successful FR24 enrichments'
)

FR24_ENRICHMENT_FAILURE = Counter(
    'fr24_enrichment_failure_total',
    'Failed FR24 enrichments'
)

FR24_API_LATENCY = Histogram(
    'fr24_api_latency_seconds',
    'FR24 API call latency',
    ['endpoint']
)
```

### Logging Requirements

```python
# Log FR24 API usage
logger.info(f"FR24 enrichment: {icao24} -> fr24_id={fr24_id}")
logger.debug(f"FR24 flight track: {fr24_id} has {len(tracks)} points")

# Log errors with context
logger.error(f"FR24 enrichment failed for {icao24}: {error_details}")
```

---

## Security Considerations

1. **API Token Storage:** Never commit tokens to version control
2. **Environment Variables:** Use `.env` files (gitignored) or secrets manager
3. **Token Rotation:** Implement token rotation procedure
4. **Rate Limiting:** Prevent accidental quota exhaustion
5. **Error Messages:** Don't expose API errors to end users

---

## Testing Strategy

### Unit Tests

```python
# tests/chemtrail/test_fr24_client.py
import pytest
from chemtrail.api.fr24_client import FR24Client, FR24FlightPosition

def test_fr24_client_initialization():
    with FR24Client(api_token="test_token") as client:
        assert client._client is not None

def test_fr24_position_mapping():
    # Test _map_position with sample FR24 data
    pass

# tests/chemtrail/test_fr24_flight_service.py
@pytest.mark.asyncio
async def test_fr24_enrichment(async_session):
    service = FR24FlightService(async_session)
    result = await asyncio.to_thread(
        service.enrich_flight_cache_entry,
        "4b1a02"
    )
    assert result is not None
```

### Integration Tests

```python
# tests/chemtrail/test_dual_source_sync.py
@pytest.mark.asyncio
async def test_opensky_fr24_merge(async_session):
    flight_service = FlightService(async_session)
    
    # Sync from OpenSky
    async with OpenSkyClient() as opensky:
        await flight_service.sync_flights_from_opensky(opensky)
    
    # Enrich with FR24
    enriched = await flight_service._enrich_with_fr24_data()
    
    # Verify merged data
    assert enriched > 0
```

---

## Migration Path

### Database Migration Script

```python
"""add_fr24_fields_to_flight_cache

Revision ID: fr24_integration_001
Revises: previous_revision
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'fr24_integration_001'
down_revision = 'previous_revision'

def upgrade():
    # Add FR24-specific columns
    op.add_column('flight_cache', sa.Column('fr24_id', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('squawk', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('vertical_rate', sa.Integer(), nullable=True))
    op.add_column('flight_cache', sa.Column('painted_as', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('operating_as', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('eta', sa.DateTime(), nullable=True))
    op.add_column('flight_cache', sa.Column('origin_icao', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('origin_iata', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('destination_icao', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('destination_iata', sa.String(), nullable=True))
    op.add_column('flight_cache', sa.Column('flight_track', sa.JSON(), nullable=True))
    op.add_column('flight_cache', sa.Column('fr24_raw_message', sa.JSON(), nullable=True))
    op.add_column('flight_cache', sa.Column('data_sources', sa.JSON(), nullable=True))
    
    # Add index on fr24_id for faster lookups
    op.create_index('idx_flight_cache_fr24_id', 'flight_cache', ['fr24_id'])

def downgrade():
    op.drop_index('idx_flight_cache_fr24_id')
    op.drop_column('flight_cache', 'data_sources')
    op.drop_column('flight_cache', 'fr24_raw_message')
    op.drop_column('flight_cache', 'flight_track')
    op.drop_column('flight_cache', 'destination_iata')
    op.drop_column('flight_cache', 'destination_icao')
    op.drop_column('flight_cache', 'origin_iata')
    op.drop_column('flight_cache', 'origin_icao')
    op.drop_column('flight_cache', 'eta')
    op.drop_column('flight_cache', 'operating_as')
    op.drop_column('flight_cache', 'painted_as')
    op.drop_column('flight_cache', 'vertical_rate')
    op.drop_column('flight_cache', 'squawk')
    op.drop_column('flight_cache', 'fr24_id')
```

---

## Rollback Plan

If FR24 integration causes issues:

1. **Disable FR24 enrichment:** Set `FR24_ENABLED=false` in config
2. **Revert database changes:** Run Alembic downgrade
3. **Remove code:** Revert to previous FlightService version
4. **Data cleanup:** Script to remove FR24 fields from FlightCache

---

## Conclusion

This architecture provides a robust, maintainable integration of Flightradar24 data into the chemtrail tracker system. The dual-source approach improves data reliability and enrichment while maintaining backward compatibility with existing OpenSky-based functionality.

**Key Success Criteria:**
- Zero disruption to existing OpenSky sync
- <100ms latency impact on detection pipeline
- 95%+ flight enrichment success rate
- Graceful degradation on FR24 API failures

**Next Steps:**
1. Review and approve this architecture document
2. Obtain FR24 API token
3. Begin Phase 1 implementation
4. Schedule testing window for integration validation
