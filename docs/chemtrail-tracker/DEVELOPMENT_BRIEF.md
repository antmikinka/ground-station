# Chemtrail Webcam Tracker - Development Brief

**Document Version:** 1.0.0  
**Phase:** 1 (Foundation)  
**Priority:** CRITICAL  
**Created:** 2026-04-11  
**Target Branch:** `chemtrail-webcam-tracker`

---

## Overview for Senior Developer

This brief provides detailed implementation specifications for Phase 1 of the Chemtrail Webcam Tracker. Follow existing project patterns precisely. All new code should integrate seamlessly with the current backend architecture.

**Key Reference Files:**
- CRUD Pattern: `backend/crud/locations.py`
- Handler Pattern: `backend/handlers/entities/locations.py`
- Model Pattern: `backend/db/models.py`
- App Startup: `backend/app.py`

---

## 1. Database Models

### File: `backend/db/models.py`

**Action:** Extend existing models file with chemtrail-specific classes.

Add the following model classes at the end of the file (before any `if __name__` blocks):

```python
# ============================================================================
# CHEMTRAIL TRACKER MODELS
# Add these classes to backend/db/models.py
# ============================================================================


class DetectionType(str, PyEnum):
    """Enum for detection types."""
    CONTRAIL = "contrail"
    AIRCRAFT = "aircraft"
    UNKNOWN = "unknown"


class ProcessingStatus(str, PyEnum):
    """Enum for processing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChemtrailCameras(Base):
    """
    Extended camera model with geolocalization metadata for contrail tracking.
    
    Stores camera position, orientation, and optical characteristics needed
    for azimuth/elevation calculations and triangulation.
    """
    __tablename__ = "chemtrail_cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)  # RTSP/MJPEG URL or API endpoint
    type = Column(Enum(CameraType), nullable=False)
    
    # Geolocation (required for triangulation)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    altitude = Column(Float, nullable=False)  # meters AMSL
    
    # Orientation (required for az/el calculation)
    azimuth = Column(Float, nullable=False, default=0.0)  # 0-360 degrees
    elevation = Column(Float, nullable=False, default=0.0)  # -90 to 90 degrees
    
    # Optical characteristics
    fov_horizontal = Column(Float, nullable=True)  # degrees
    fov_vertical = Column(Float, nullable=True)  # degrees
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    lens_distortion = Column(JSON, nullable=True)  # {k1, k2, p1, p2}
    
    # Operational
    status = Column(String, nullable=False, default="inactive")  # active, inactive, error
    last_image_at = Column(AwareDateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime, 
        nullable=True, 
        default=datetime.now(timezone.utc), 
        onupdate=datetime.now(timezone.utc)
    )


class ChemtrailDetections(Base):
    """
    Core detection records linking cameras, flights, and observations.
    
    Stores contrail/aircraft detections with image-space coordinates,
    calculated azimuth/elevation, and estimated 3D position.
    """
    __tablename__ = "chemtrail_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    camera_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("chemtrail_cameras.id"), 
        nullable=False, 
        index=True
    )
    icao24 = Column(
        String, 
        ForeignKey("flight_cache.icao24"), 
        nullable=True, 
        index=True
    )
    
    # Detection type
    detection_type = Column(Enum(DetectionType), nullable=False, index=True)
    
    # Timing
    timestamp = Column(AwareDateTime, nullable=False, index=True)
    processing_latency_ms = Column(Integer, nullable=True)
    
    # Image reference
    image_path = Column(String, nullable=False)
    image_hash = Column(String, nullable=True, index=True)  # For deduplication
    
    # Detection location (image space)
    pixel_x = Column(Float, nullable=False)
    pixel_y = Column(Float, nullable=False)
    bounding_box = Column(JSON, nullable=True)  # [x1, y1, x2, y2] for aircraft
    
    # Calculated az/el from camera
    azimuth = Column(Float, nullable=False)
    elevation = Column(Float, nullable=False)
    
    # Estimated 3D position (WGS84)
    estimated_latitude = Column(Float, nullable=True, index=True)
    estimated_longitude = Column(Float, nullable=True, index=True)
    estimated_altitude = Column(Float, nullable=True)
    position_method = Column(String, nullable=True)  # "single_camera", "triangulation", "flight_correlation"
    
    # Detection quality
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    correlation_score = Column(Float, nullable=True)  # 0.0-1.0 for flight match
    
    # Contrail-specific data
    contrail_vector = Column(JSON, nullable=True)  # {angle, length_px, width_px, persistence}
    
    # Processing metadata
    processing_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )


class FlightCache(Base):
    """
    Cached flight data from OpenSky/ADS-B APIs.
    
    Stores recent flight positions and history for correlation with detections.
    """
    __tablename__ = "flight_cache"

    icao24 = Column(String, primary_key=True, nullable=False)
    callsign = Column(String, nullable=True, index=True)
    registration = Column(String, nullable=True)
    aircraft_type = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    
    # Current position (updated from API)
    position = Column(JSON, nullable=True)  # {lat, lon, alt, heading, velocity}
    last_position_update = Column(AwareDateTime, nullable=True, index=True)
    
    # Position history (for correlation with detections)
    position_history = Column(JSON, nullable=True)  # Array of {timestamp, lat, lon, alt}
    
    # Raw API response (for debugging/reprocessing)
    raw_message = Column(JSON, nullable=True)
    
    # Timestamps
    first_seen = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )
```

**Note:** After adding models, create Alembic migration (see Section 5).

---

## 2. OpenSky Network API Client

### File: `backend/chemtrail/api/opensky_client.py`

**Action:** Create new file.

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

"""OpenSky Network API client for flight data."""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import httpx
from common.common import logger


@dataclass
class FlightState:
    """Represents current state of a flight."""
    icao24: str
    callsign: Optional[str]
    origin_country: Optional[str]
    time_position: Optional[int]
    last_contact: Optional[int]
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]
    on_ground: bool
    velocity: Optional[float]
    true_track: Optional[float]
    vertical_rate: Optional[float]
    sensors: Optional[List[int]]
    geo_altitude: Optional[float]
    squawk: Optional[str]
    spi: bool
    position_source: int


class OpenSkyClient:
    """
    Async client for OpenSky Network API.
    
    Implements rate limiting and basic caching to respect API limits:
    - Anonymous: 1 request per 10 seconds
    - Member: 1 request per second
    
    Usage:
        async with OpenSkyClient() as client:
            flights = await client.get_all_flights()
    """
    
    BASE_URL = "https://opensky-network.org/api"
    
    def __init__(
        self, 
        username: Optional[str] = None, 
        password: Optional[str] = None,
        rate_limit_delay: float = 10.0
    ):
        """
        Initialize OpenSky client.
        
        Args:
            username: OpenSky username (optional, for member rate limits)
            password: OpenSky password (optional)
            rate_limit_delay: Minimum seconds between requests
        """
        self.username = username
        self.password = password
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
            self.rate_limit_delay = 1.0  # Member rate limit
            
        self._client = httpx.AsyncClient(auth=auth, timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            
    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
        
    async def get_all_flights(self) -> List[FlightState]:
        """
        Fetch all currently airborne flights.
        
        Returns:
            List of FlightState objects
        """
        await self._rate_limit()
        
        try:
            response = await self._client.get(f"{self.BASE_URL}/states/all")
            response.raise_for_status()
            data = response.json()
            
            if not data.get("states"):
                return []
                
            flights = []
            for state in data["states"]:
                flights.append(FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                ))
            return flights
            
        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching flights: {e}")
            return []
            
    async def get_flight_by_icao24(self, icao24: str) -> Optional[FlightState]:
        """
        Fetch state for a specific flight by ICAO24 hex code.
        
        Args:
            icao24: 24-bit ICAO hex code (e.g., "4b1a02")
            
        Returns:
            FlightState or None if not found
        """
        await self._rate_limit()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/states/all",
                params={"icao24": icao24}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("states"):
                state = data["states"][0]
                return FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                )
            return None
            
        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return None
            
    async def get_flights_in_area(
        self, 
        lat_min: float, 
        lat_max: float, 
        lon_min: float, 
        lon_max: float
    ) -> List[FlightState]:
        """
        Fetch flights within a bounding box.
        
        Args:
            lat_min: Minimum latitude
            lat_max: Maximum latitude
            lon_min: Minimum longitude
            lon_max: Maximum longitude
            
        Returns:
            List of FlightState objects within the area
        """
        await self._rate_limit()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/states/all",
                params={
                    "lamin": lat_min,
                    "lamax": lat_max,
                    "lomin": lon_min,
                    "lomax": lon_max,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("states"):
                return []
                
            flights = []
            for state in data["states"]:
                flights.append(FlightState(
                    icao24=state[0],
                    callsign=state[1].strip() if state[1] else None,
                    origin_country=state[2],
                    time_position=state[3],
                    last_contact=state[4],
                    longitude=state[5],
                    latitude=state[6],
                    baro_altitude=state[7],
                    on_ground=state[8],
                    velocity=state[9],
                    true_track=state[10],
                    vertical_rate=state[11],
                    sensors=state[12],
                    geo_altitude=state[13],
                    squawk=state[14],
                    spi=state[15],
                    position_source=state[16],
                ))
            return flights
            
        except httpx.HTTPError as e:
            logger.error(f"OpenSky API error: {e}")
            return []
```

### File: `backend/chemtrail/api/__init__.py`

**Action:** Create new file.

```python
"""Chemtrail API clients."""

from .opensky_client import OpenSkyClient, FlightState

__all__ = ["OpenSkyClient", "FlightState"]
```

---

## 3. Service Layer

### File: `backend/chemtrail/services/flight_service.py`

**Action:** Create new file.

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

"""Flight data service for caching and querying OpenSky data."""

from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from db.models import FlightCache
from ..api.opensky_client import OpenSkyClient, FlightState


class FlightService:
    """Service for managing flight data cache."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
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
                # Update or insert flight
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
        
        # Check if exists
        stmt = select(FlightCache).filter(FlightCache.icao24 == flight.icao24)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            position_history = existing.position_history or []
            position_history.append({
                "timestamp": timestamp.isoformat(),
                **position_data
            })
            # Keep last 100 positions
            position_history = position_history[-100:]
            
            upd_stmt = (
                update(FlightCache)
                .where(FlightCache.icao24 == flight.icao24)
                .values(
                    callsign=flight.callsign,
                    position=position_data,
                    last_position_update=timestamp,
                    position_history=position_history,
                    updated_at=timestamp,
                )
            )
            await self.session.execute(upd_stmt)
        else:
            # Insert new
            insert_stmt = insert(FlightCache).values(
                icao24=flight.icao24,
                callsign=flight.callsign,
                origin_country=flight.origin_country,
                position=position_data,
                last_position_update=timestamp,
                position_history=[{"timestamp": timestamp.isoformat(), **position_data}],
                first_seen=timestamp,
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
        
        Simple bounding box approximation for Phase 1.
        """
        # Rough conversion: 1 degree ~ 111 km
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
            }
            for f in flights
        ]
```

### File: `backend/chemtrail/services/camera_service.py`

**Action:** Create new file.

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

"""Camera service for chemtrail tracker."""

from typing import Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.common import logger
from db.models import ChemtrailCameras


class CameraService:
    """Service for managing chemtrail cameras."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def get_camera(self, camera_id: uuid.UUID) -> Optional[Dict]:
        """Get camera by ID."""
        stmt = select(ChemtrailCameras).filter(ChemtrailCameras.id == camera_id)
        result = await self.session.execute(stmt)
        camera = result.scalar_one_or_none()
        
        if camera:
            return self._serialize_camera(camera)
        return None
        
    async def get_all_cameras(self) -> List[Dict]:
        """Get all cameras."""
        stmt = select(ChemtrailCameras)
        result = await self.session.execute(stmt)
        cameras = result.scalars().all()
        
        return [self._serialize_camera(c) for c in cameras]
        
    async def get_active_cameras(self) -> List[Dict]:
        """Get only active cameras."""
        stmt = select(ChemtrailCameras).filter(ChemtrailCameras.status == "active")
        result = await self.session.execute(stmt)
        cameras = result.scalars().all()
        
        return [self._serialize_camera(c) for c in cameras]
        
    def _serialize_camera(self, camera: ChemtrailCameras) -> Dict:
        """Serialize camera model to dict."""
        return {
            "id": str(camera.id),
            "name": camera.name,
            "url": camera.url,
            "type": camera.type.value if hasattr(camera.type, 'value') else camera.type,
            "latitude": camera.latitude,
            "longitude": camera.longitude,
            "altitude": camera.altitude,
            "azimuth": camera.azimuth,
            "elevation": camera.elevation,
            "fov_horizontal": camera.fov_horizontal,
            "fov_vertical": camera.fov_vertical,
            "image_width": camera.image_width,
            "image_height": camera.image_height,
            "lens_distortion": camera.lens_distortion,
            "status": camera.status,
            "last_image_at": camera.last_image_at.isoformat() if camera.last_image_at else None,
            "metadata": camera.metadata,
            "created_at": camera.created_at.isoformat() if camera.created_at else None,
            "updated_at": camera.updated_at.isoformat() if camera.updated_at else None,
        }
```

### File: `backend/chemtrail/services/geocalc_service.py`

**Action:** Create new file.

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

"""Geolocalization calculations for contrail tracking."""

from typing import Tuple, Optional
from math import radians, degrees, sin, cos, tan, atan2


def pixel_to_az_el(
    x: float, 
    y: float,
    width: int, 
    height: int,
    cam_azimuth: float, 
    cam_elevation: float,
    fov_h: float, 
    fov_v: float
) -> Tuple[float, float]:
    """
    Convert pixel coordinates to absolute azimuth/elevation.
    
    Args:
        x, y: Pixel coordinates (0,0 = top-left)
        width, height: Image dimensions in pixels
        cam_azimuth: Camera heading (0-360 degrees, N=0, E=90)
        cam_elevation: Camera tilt (-90 to 90, 0=horizon)
        fov_h, fov_v: Horizontal/vertical field of view in degrees
        
    Returns:
        (azimuth, elevation) in degrees
    """
    # Normalize pixel to [-1, 1] range (center = 0,0)
    x_norm = (x - width / 2) / (width / 2)
    y_norm = (height / 2 - y) / (height / 2)  # Flip Y axis (image Y goes down)
    
    # Convert to angular offset from camera center
    az_offset = x_norm * (fov_h / 2)
    el_offset = y_norm * (fov_v / 2)
    
    # Calculate absolute azimuth/elevation
    az_obj = (cam_azimuth + az_offset) % 360
    el_obj = cam_elevation + el_offset
    
    # Clamp elevation to valid range
    el_obj = max(-90, min(90, el_obj))
    
    return az_obj, el_obj


def estimate_position_single(
    cam_lat: float, 
    cam_lon: float, 
    cam_alt: float,
    az_obj: float, 
    el_obj: float,
    assumed_alt: float
) -> Tuple[float, float]:
    """
    Estimate object lat/lon assuming known altitude.
    
    Uses simple spherical projection (sufficient for visual range < 50km).
    
    Args:
        cam_lat, cam_lon, cam_alt: Camera position (alt in meters AMSL)
        az_obj: Object azimuth (degrees)
        el_obj: Object elevation (degrees)
        assumed_alt: Assumed object altitude (meters AMSL)
        
    Returns:
        (lat_obj, lon_obj) in degrees
    """
    # Altitude difference
    delta_alt = assumed_alt - cam_alt
    
    # Horizontal distance (assuming flat earth for short range)
    el_rad = radians(el_obj)
    if el_rad <= 0:
        el_rad = radians(0.1)  # Prevent division by zero
        
    horizontal_dist = delta_alt / tan(el_rad)
    
    # Calculate displacement
    az_rad = radians(az_obj)
    delta_north = horizontal_dist * cos(az_rad)
    delta_east = horizontal_dist * sin(az_rad)
    
    # Convert to lat/lon offset (approximate)
    # 1 degree latitude ~ 111.32 km
    # 1 degree longitude ~ 111.32 km * cos(latitude)
    lat_obj = cam_lat + degrees(delta_north / 111320)
    lon_obj = cam_lon + degrees(delta_east / (111320 * cos(radians(cam_lat))))
    
    return lat_obj, lon_obj


def calculate_distance_km(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.
    
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = (sin(delta_lat / 2) ** 2 + 
         cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2)
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c
```

### File: `backend/chemtrail/services/__init__.py`

**Action:** Create new file.

```python
"""Chemtrail service layer."""

from .flight_service import FlightService
from .camera_service import CameraService
from .geocalc_service import pixel_to_az_el, estimate_position_single

__all__ = [
    "FlightService",
    "CameraService",
    "pixel_to_az_el",
    "estimate_position_single",
]
```

---

## 4. CRUD Operations

### File: `backend/crud/chemtrail_cameras.py`

**Action:** Create new file. Follow pattern from `backend/crud/locations.py`.

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

"""CRUD operations for chemtrail cameras."""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger, serialize_object
from db.models import ChemtrailCameras


async def fetch_camera(session: AsyncSession, camera_id: Union[uuid.UUID, str]) -> dict:
    """Fetch a single camera by UUID."""
    try:
        if isinstance(camera_id, str):
            camera_id = uuid.UUID(camera_id)

        stmt = select(ChemtrailCameras).filter(ChemtrailCameras.id == camera_id)
        result = await session.execute(stmt)
        camera = result.scalar_one_or_none()
        camera = serialize_object(camera)
        return {"success": True, "data": camera, "error": None}

    except Exception as e:
        logger.error(f"Error fetching camera: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def fetch_all_cameras(session: AsyncSession) -> dict:
    """Fetch all camera records."""
    try:
        stmt = select(ChemtrailCameras)
        result = await session.execute(stmt)
        cameras = result.scalars().all()
        cameras = serialize_object(cameras)
        return {"success": True, "data": cameras, "error": None}

    except Exception as e:
        logger.error(f"Error fetching cameras: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def add_camera(session: AsyncSession, data: dict) -> dict:
    """Create and add a new camera record."""
    try:
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        data["id"] = new_id
        data["created_at"] = now
        data["updated_at"] = now

        stmt = insert(ChemtrailCameras).values(**data).returning(ChemtrailCameras)

        result = await session.execute(stmt)
        await session.commit()
        new_camera = result.scalar_one()
        new_camera = serialize_object(new_camera)
        return {"success": True, "data": new_camera, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding camera: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def edit_camera(session: AsyncSession, data: dict) -> dict:
    """Edit an existing camera record."""
    try:
        camera_id = data.pop("id", None)
        if not camera_id:
            raise Exception("id is required.")

        # Remove timestamps from update data
        for key in ["created_at", "updated_at"]:
            if key in data:
                del data[key]

        if isinstance(camera_id, str):
            camera_id = uuid.UUID(camera_id)

        # Verify camera exists
        stmt = select(ChemtrailCameras).filter(ChemtrailCameras.id == camera_id)
        result = await session.execute(stmt)
        camera = result.scalar_one_or_none()
        if not camera:
            return {"success": False, "error": f"Camera with id {camera_id} not found."}

        upd_stmt = (
            update(ChemtrailCameras)
            .where(ChemtrailCameras.id == camera_id)
            .values(**data)
            .returning(ChemtrailCameras)
        )
        upd_result = await session.execute(upd_stmt)
        await session.commit()
        updated_camera = upd_result.scalar_one_or_none()
        updated_camera = serialize_object(updated_camera)
        return {"success": True, "data": updated_camera, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error editing camera: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def delete_camera(session: AsyncSession, camera_id: Union[uuid.UUID, str]) -> dict:
    """Delete a camera record by UUID."""
    try:
        if isinstance(camera_id, str):
            camera_id = uuid.UUID(camera_id)

        stmt = delete(ChemtrailCameras).where(ChemtrailCameras.id == camera_id).returning(ChemtrailCameras)
        result = await session.execute(stmt)
        deleted = result.scalar_one_or_none()
        if not deleted:
            return {"success": False, "error": f"Camera with id {camera_id} not found."}
        await session.commit()
        return {"success": True, "data": None, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting camera: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}
```

### File: `backend/crud/chemtrail_detections.py`

**Action:** Create new file.

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

"""CRUD operations for chemtrail detections."""

import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger, serialize_object
from db.models import ChemtrailDetections


async def fetch_detection(session: AsyncSession, detection_id: Union[uuid.UUID, str]) -> dict:
    """Fetch a single detection by UUID."""
    try:
        if isinstance(detection_id, str):
            detection_id = uuid.UUID(detection_id)

        stmt = select(ChemtrailDetections).filter(ChemtrailDetections.id == detection_id)
        result = await session.execute(stmt)
        detection = result.scalar_one_or_none()
        detection = serialize_object(detection)
        return {"success": True, "data": detection, "error": None}

    except Exception as e:
        logger.error(f"Error fetching detection: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def fetch_all_detections(
    session: AsyncSession,
    camera_id: Optional[str] = None,
    limit: int = 100
) -> dict:
    """Fetch detection records with optional filtering."""
    try:
        stmt = select(ChemtrailDetections)
        
        if camera_id:
            if isinstance(camera_id, str):
                camera_id = uuid.UUID(camera_id)
            stmt = stmt.filter(ChemtrailDetections.camera_id == camera_id)
            
        stmt = stmt.order_by(ChemtrailDetections.timestamp.desc()).limit(limit)
        
        result = await session.execute(stmt)
        detections = result.scalars().all()
        detections = serialize_object(detections)
        return {"success": True, "data": detections, "error": None}

    except Exception as e:
        logger.error(f"Error fetching detections: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def add_detection(session: AsyncSession, data: dict) -> dict:
    """Create and add a new detection record."""
    try:
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        data["id"] = new_id
        data["created_at"] = now
        data["updated_at"] = now

        stmt = insert(ChemtrailDetections).values(**data).returning(ChemtrailDetections)

        result = await session.execute(stmt)
        await session.commit()
        new_detection = result.scalar_one()
        new_detection = serialize_object(new_detection)
        return {"success": True, "data": new_detection, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error adding detection: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def delete_detection(session: AsyncSession, detection_id: Union[uuid.UUID, str]) -> dict:
    """Delete a detection record by UUID."""
    try:
        if isinstance(detection_id, str):
            detection_id = uuid.UUID(detection_id)

        stmt = delete(ChemtrailDetections).where(ChemtrailDetections.id == detection_id).returning(ChemtrailDetections)
        result = await session.execute(stmt)
        deleted = result.scalar_one_or_none()
        if not deleted:
            return {"success": False, "error": f"Detection with id {detection_id} not found."}
        await session.commit()
        return {"success": True, "data": None, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error deleting detection: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}
```

### Update: `backend/crud/__init__.py`

**Action:** Modify existing file to export new modules.

```python
from .groups import *  # noqa: F401, F403
from .hardware import *  # noqa: F401, F403
from .locations import *  # noqa: F401, F403
from .preferences import *  # noqa: F401, F403
from .satellites import *  # noqa: F401, F403
from .tlesources import *  # noqa: F401, F403
from .trackingstate import *  # noqa: F401, F403
from .transmitters import *  # noqa: F401, F403
from .chemtrail_cameras import *  # noqa: F401, F403
from .chemtrail_detections import *  # noqa: F401, F403
```

---

## 5. Database Migration

### File: `backend/alembic/versions/002_add_chemtrail_tracker_schema.py`

**Action:** Create new migration file. Use next sequential revision number.

First, get current head revision:
```bash
cd backend
alembic heads
```

Then create migration with proper `down_revision`:

```python
"""Add chemtrail tracker schema

Revision ID: 002
Revises: 001
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'  # UPDATE THIS to actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Create chemtrail_cameras table
    op.create_table(
        'chemtrail_cameras',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('altitude', sa.Float(), nullable=False),
        sa.Column('azimuth', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('elevation', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('fov_horizontal', sa.Float(), nullable=True),
        sa.Column('fov_vertical', sa.Float(), nullable=True),
        sa.Column('image_width', sa.Integer(), nullable=True),
        sa.Column('image_height', sa.Integer(), nullable=True),
        sa.Column('lens_distortion', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='inactive'),
        sa.Column('last_image_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cameras_location', 'chemtrail_cameras', ['latitude', 'longitude'])
    
    # Create flight_cache table
    op.create_table(
        'flight_cache',
        sa.Column('icao24', sa.String(), nullable=False),
        sa.Column('callsign', sa.String(), nullable=True),
        sa.Column('registration', sa.String(), nullable=True),
        sa.Column('aircraft_type', sa.String(), nullable=True),
        sa.Column('origin', sa.String(), nullable=True),
        sa.Column('destination', sa.String(), nullable=True),
        sa.Column('position', sa.JSON(), nullable=True),
        sa.Column('last_position_update', sa.DateTime(timezone=True), nullable=True),
        sa.Column('position_history', sa.JSON(), nullable=True),
        sa.Column('raw_message', sa.JSON(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('icao24')
    )
    op.create_index('idx_flight_cache_callsign', 'flight_cache', ['callsign'])
    op.create_index('idx_flight_cache_last_pos', 'flight_cache', ['last_position_update'])
    
    # Create chemtrail_detections table
    op.create_table(
        'chemtrail_detections',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('camera_id', UUID(as_uuid=True), nullable=False),
        sa.Column('icao24', sa.String(), nullable=True),
        sa.Column('detection_type', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processing_latency_ms', sa.Integer(), nullable=True),
        sa.Column('image_path', sa.String(), nullable=False),
        sa.Column('image_hash', sa.String(), nullable=True),
        sa.Column('pixel_x', sa.Float(), nullable=False),
        sa.Column('pixel_y', sa.Float(), nullable=False),
        sa.Column('bounding_box', sa.JSON(), nullable=True),
        sa.Column('azimuth', sa.Float(), nullable=False),
        sa.Column('elevation', sa.Float(), nullable=False),
        sa.Column('estimated_latitude', sa.Float(), nullable=True),
        sa.Column('estimated_longitude', sa.Float(), nullable=True),
        sa.Column('estimated_altitude', sa.Float(), nullable=True),
        sa.Column('position_method', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('correlation_score', sa.Float(), nullable=True),
        sa.Column('contrail_vector', sa.JSON(), nullable=True),
        sa.Column('processing_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['camera_id'], ['chemtrail_cameras.id'], ),
        sa.ForeignKeyConstraint(['icao24'], ['flight_cache.icao24'], ),
    )
    op.create_index('idx_detections_camera', 'chemtrail_detections', ['camera_id'])
    op.create_index('idx_detections_icao24', 'chemtrail_detections', ['icao24'])
    op.create_index('idx_detections_time', 'chemtrail_detections', ['timestamp'])
    op.create_index('idx_detections_camera_time', 'chemtrail_detections', ['camera_id', 'timestamp'])
    op.create_index('idx_detections_location', 'chemtrail_detections', ['estimated_latitude', 'estimated_longitude'])


def downgrade():
    op.drop_table('chemtrail_detections')
    op.drop_table('flight_cache')
    op.drop_table('chemtrail_cameras')
```

**Run migration:**
```bash
cd backend
alembic upgrade head
```

---

## 6. Computer Vision Module

### File: `backend/chemtrail/cv/contrail_detector.py`

**Action:** Create new file.

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

"""Contrail detection using Hough transform."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import cv2
from common.common import logger


@dataclass
class ContrailDetection:
    """Represents a detected contrail."""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    confidence: float
    angle: float  # degrees from horizontal
    length_px: float
    width_px: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "confidence": self.confidence,
            "angle": self.angle,
            "length_px": self.length_px,
            "width_px": self.width_px,
        }


class ContrailDetector:
    """
    Detects contrails in sky images using Hough line transform.
    
    Pipeline:
    1. Convert to grayscale
    2. Apply CLAHE for contrast enhancement
    3. Denoise
    4. Canny edge detection
    5. Probabilistic Hough line detection
    6. Filter lines by length, angle, and position
    """
    
    def __init__(
        self,
        min_line_length: int = 100,
        max_line_gap: int = 10,
        hough_threshold: int = 80,
        min_contrail_angle: float = 5.0,
        max_contrail_angle: float = 175.0,
    ):
        """
        Initialize detector with tunable parameters.
        
        Args:
            min_line_length: Minimum line length in pixels
            max_line_gap: Maximum gap between line segments
            hough_threshold: Hough transform threshold
            min_contrail_angle: Minimum angle for contrail-like lines
            max_contrail_angle: Maximum angle for contrail-like lines
        """
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.hough_threshold = hough_threshold
        self.min_contrail_angle = min_contrail_angle
        self.max_contrail_angle = max_contrail_angle
        
    def detect(self, frame: np.ndarray) -> List[ContrailDetection]:
        """
        Detect contrails in image frame.
        
        Args:
            frame: BGR image as numpy array (from OpenCV)
            
        Returns:
            List of ContrailDetection objects
        """
        try:
            # Stage 1: Preprocessing
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # CLAHE for contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
            
            # Stage 2: Edge Detection
            edges = cv2.Canny(denoised, threshold1=50, threshold2=150)
            
            # Stage 3: Line Detection (Probabilistic Hough)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=self.hough_threshold,
                minLineLength=self.min_line_length,
                maxLineGap=self.max_line_gap,
            )
            
            if lines is None:
                return []
            
            # Stage 4: Contrail Validation
            contrails = []
            for line in lines:
                detection = self._validate_line(line, frame.shape)
                if detection:
                    contrails.append(detection)
            
            return contrails
            
        except Exception as e:
            logger.error(f"Error in contrail detection: {e}")
            return []
            
    def _validate_line(
        self, 
        line: np.ndarray, 
        frame_shape: Tuple
    ) -> Optional[ContrailDetection]:
        """
        Validate if a line is likely a contrail.
        
        Checks:
        - Line is approximately horizontal (within angle bounds)
        - Line is in upper portion of image (sky region)
        - Line has sufficient contrast
        """
        x1, y1, x2, y2 = line[0]
        
        # Calculate angle
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            return None
            
        angle = abs(np.degrees(np.arctan2(dy, dx)))
        
        # Filter by angle (contrails are roughly horizontal)
        if not (self.min_contrail_angle <= angle <= self.max_contrail_angle):
            return None
            
        # Calculate length
        length = np.sqrt(dx * dx + dy * dy)
        if length < self.min_line_length:
            return None
            
        # Calculate confidence based on various factors
        confidence = self._calculate_confidence(line, frame_shape, angle)
        
        if confidence < 0.3:  # Minimum confidence threshold
            return None
            
        return ContrailDetection(
            start_x=float(x1),
            start_y=float(y1),
            end_x=float(x2),
            end_y=float(y2),
            confidence=confidence,
            angle=angle,
            length_px=length,
        )
        
    def _calculate_confidence(
        self,
        line: np.ndarray,
        frame_shape: Tuple,
        angle: float
    ) -> float:
        """
        Calculate confidence score for a detected line.
        
        Factors:
        - Position in image (upper = more likely sky)
        - Angle (closer to horizontal = higher confidence)
        - Length (longer = higher confidence)
        """
        x1, y1, x2, y2 = line[0]
        height = frame_shape[0]
        
        # Position score: lines in upper 2/3 of image get higher score
        avg_y = (y1 + y2) / 2
        position_score = max(0, 1.0 - (avg_y / (height * 0.67)))
        
        # Angle score: closer to horizontal (0 or 180) = higher
        angle_deviation = min(abs(angle), abs(180 - angle))
        angle_score = max(0, 1.0 - (angle_deviation / 45.0))
        
        # Combine scores
        confidence = (position_score * 0.4 + angle_score * 0.6)
        
        return min(1.0, max(0.0, confidence))
```

### File: `backend/chemtrail/cv/cv_utils.py`

**Action:** Create new file.

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

"""Computer vision utilities."""

import hashlib
from typing import Optional
import numpy as np


def compute_image_hash(image: np.ndarray) -> str:
    """
    Compute perceptual hash of image for deduplication.
    
    Args:
        image: Image as numpy array
        
    Returns:
        Hex string hash
    """
    # Resize to small fixed size for comparison
    resized = cv2.resize(image, (32, 32))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    # Compute simple hash
    hash_bytes = hashlib.md5(gray.tobytes()).hexdigest()
    return hash_bytes


def draw_detections(
    image: np.ndarray,
    detections: list,
    color: tuple = (0, 255, 0)
) -> np.ndarray:
    """
    Draw detection lines on image for visualization.
    
    Args:
        image: BGR image
        detections: List of ContrailDetection objects
        color: BGR color tuple
        
    Returns:
        Image with drawn detections
    """
    import cv2
    
    output = image.copy()
    for det in detections:
        pt1 = (int(det.start_x), int(det.start_y))
        pt2 = (int(det.end_x), int(det.end_y))
        cv2.line(output, pt1, pt2, color, 2)
        
    return output
```

### File: `backend/chemtrail/cv/__init__.py`

**Action:** Create new file.

```python
"""Chemtrail computer vision module."""

from .contrail_detector import ContrailDetector, ContrailDetection

__all__ = ["ContrailDetector", "ContrailDetection"]
```

---

## 7. Handler/Router Integration

### File: `backend/handlers/entities/chemtrail_cameras.py`

**Action:** Create new file following handler pattern.

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

"""Chemtrail camera handlers."""

from typing import Any, Dict, Optional

import crud
from db import AsyncSessionLocal


async def get_chemtrail_cameras(
    sio: Any, 
    data: Optional[Dict], 
    logger: Any, 
    sid: str
) -> Dict[str, Any]:
    """Get all chemtrail cameras."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug("Getting all chemtrail cameras")
        cameras = await crud.chemtrail_cameras.fetch_all_cameras(dbsession)
        return {"success": cameras["success"], "data": cameras.get("data", [])}


async def get_chemtrail_camera(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get single chemtrail camera by ID."""
    async with AsyncSessionLocal() as dbsession:
        camera_id = data.get("id") if data else None
        if not camera_id:
            return {"success": False, "data": [], "error": "id required"}
            
        logger.debug(f"Getting chemtrail camera {camera_id}")
        camera = await crud.chemtrail_cameras.fetch_camera(dbsession, camera_id)
        return {"success": camera["success"], "data": camera.get("data", [])}


async def submit_chemtrail_camera(
    sio: Any, 
    data: Optional[Dict], 
    logger: Any, 
    sid: str
) -> Dict[str, Any]:
    """Add a new chemtrail camera."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug(f"Adding chemtrail camera, data: {data}")
        add_reply = await crud.chemtrail_cameras.add_camera(dbsession, data)
        return {"success": add_reply["success"], "data": None}


async def edit_chemtrail_camera(
    sio: Any, 
    data: Optional[Dict], 
    logger: Any, 
    sid: str
) -> Dict[str, Any]:
    """Edit an existing chemtrail camera."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug(f"Editing chemtrail camera, data: {data}")
        edit_reply = await crud.chemtrail_cameras.edit_camera(dbsession, data)
        return {"success": edit_reply["success"], "data": None}


async def delete_chemtrail_camera(
    sio: Any, 
    data: Optional[Dict], 
    logger: Any, 
    sid: str
) -> Dict[str, Any]:
    """Delete a chemtrail camera."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug(f"Delete chemtrail camera, data: {data}")
        delete_reply = await crud.chemtrail_cameras.delete_camera(dbsession, data)
        return {"success": delete_reply["success"], "data": None}


def register_handlers(registry):
    """Register camera handlers with the command registry."""
    registry.register_batch(
        {
            "get-chemtrail-cameras": (get_chemtrail_cameras, "data_request"),
            "get-chemtrail-camera": (get_chemtrail_camera, "data_request"),
            "submit-chemtrail-camera": (submit_chemtrail_camera, "data_submission"),
            "edit-chemtrail-camera": (edit_chemtrail_camera, "data_submission"),
            "delete-chemtrail-camera": (delete_chemtrail_camera, "data_submission"),
        }
    )
```

### Update: `backend/handlers/entities/__init__.py`

**Action:** Add import for new handler.

```python
from . import tlesources  # noqa: F401
from . import (
    filebrowser,
    groups,
    hardware,
    locations,
    preferences,
    satellites,
    sdr,
    sessions,
    systeminfo,
    tracking,
    transmitters,
    vfo,
    chemtrail_cameras,  # Add this line
)

__all__ = [
    "satellites",
    "tlesources",
    "groups",
    "hardware",
    "locations",
    "preferences",
    "transmitters",
    "tracking",
    "filebrowser",
    "sdr",
    "vfo",
    "systeminfo",
    "sessions",
    "chemtrail_cameras",  # Add this line
]
```

---

## 8. Module Package Structure

### File: `backend/chemtrail/__init__.py`

**Action:** Create new file.

```python
"""Chemtrail Webcam Tracker module."""

__version__ = "0.1.0"
```

---

## 9. Update pyproject.toml

### File: `backend/pyproject.toml`

**Action:** Add new dependencies to the `dependencies` list.

Add these entries (maintain alphabetical order):

```python
    # ... existing dependencies ...
    "geopy>=2.4.0",
    "imageio>=2.31.0",
    "opencv-contrib-python>=4.8.0",
    "opencv-python>=4.8.0",
    "pyproj>=3.6.0",
    "scikit-image>=0.21.0",
    # ... rest of dependencies ...
```

---

## 10. Test Files

### File: `backend/tests/chemtrail/__init__.py`

**Action:** Create new file.

```python
"""Chemtrail tracker tests."""
```

### File: `backend/tests/chemtrail/test_opensky_client.py`

**Action:** Create new file.

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

"""Tests for OpenSky API client."""

import pytest
from chemtrail.api.opensky_client import OpenSkyClient, FlightState


class TestOpenSkyClient:
    """Test OpenSky API client."""
    
    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test async context manager."""
        async with OpenSkyClient() as client:
            assert client._client is not None
        # Client should be closed after exit
        assert client._client is None or client._client.is_closed
        
    @pytest.mark.asyncio  
    async def test_get_all_flights(self):
        """Test fetching all flights (integration test)."""
        async with OpenSkyClient() as client:
            flights = await client.get_all_flights()
            
        # Should return list of FlightState objects
        assert isinstance(flights, list)
        # May be empty if API fails or no flights
        if flights:
            assert isinstance(flights[0], FlightState)
            
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting works."""
        async with OpenSkyClient(rate_limit_delay=0.1) as client:
            # Make two quick requests
            import time
            start = time.time()
            await client.get_all_flights()
            await client.get_all_flights()
            elapsed = time.time() - start
            
            # Should have been rate limited
            assert elapsed >= 0.1
```

### File: `backend/tests/chemtrail/test_contrail_detector.py`

**Action:** Create new file.

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

"""Tests for contrail detection."""

import pytest
import numpy as np
import cv2
from chemtrail.cv.contrail_detector import ContrailDetector, ContrailDetection


class TestContrailDetector:
    """Test contrail detection algorithm."""
    
    def test_detector_initialization(self):
        """Test detector creates with default params."""
        detector = ContrailDetector()
        assert detector.min_line_length == 100
        assert detector.hough_threshold == 80
        
    def test_detect_empty_image(self):
        """Test detection on blank image returns empty."""
        detector = ContrailDetector()
        # Black image
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        
        detections = detector.detect(blank)
        assert isinstance(detections, list)
        # Should find no contrails in blank image
        assert len(detections) == 0
        
    def test_detect_synthetic_contrail(self):
        """Test detection on synthetic contrail-like line."""
        detector = ContrailDetector(min_line_length=50)
        
        # Create image with horizontal line (contrail-like)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw white horizontal line in upper portion
        cv2.line(img, (100, 100), (500, 105), (255, 255, 255), 3)
        
        detections = detector.detect(img)
        
        assert isinstance(detections, list)
        # Should detect the line as contrail
        assert len(detections) > 0
        
        if detections:
            det = detections[0]
            assert isinstance(det, ContrailDetection)
            assert det.confidence > 0
            assert det.length_px > 50
            
    def test_contrail_detection_to_dict(self):
        """Test serialization."""
        det = ContrailDetection(
            start_x=100.0,
            start_y=100.0,
            end_x=500.0,
            end_y=105.0,
            confidence=0.85,
            angle=2.5,
            length_px=400.0,
        )
        
        result = det.to_dict()
        assert isinstance(result, dict)
        assert result["start_x"] == 100.0
        assert result["confidence"] == 0.85
```

---

## 11. Priority Order

Implement in this exact order:

1. **Database Models** (`backend/db/models.py`) - Foundation for everything
2. **Alembic Migration** - Create and test schema
3. **OpenSky Client** (`backend/chemtrail/api/opensky_client.py`) - External data source
4. **Flight Service** (`backend/chemtrail/services/flight_service.py`) - Data caching
5. **Camera CRUD** (`backend/crud/chemtrail_cameras.py`) - Basic operations
6. **Camera Handler** (`backend/handlers/entities/chemtrail_cameras.py`) - API exposure
7. **Camera Service** (`backend/chemtrail/services/camera_service.py`) - Business logic
8. **Geocalc Service** (`backend/chemtrail/services/geocalc_service.py`) - Math utilities
9. **Contrail Detector** (`backend/chemtrail/cv/contrail_detector.py`) - CV algorithm
10. **Detection CRUD** (`backend/crud/chemtrail_detections.py`) - Logging
11. **Test Suite** - All unit tests
12. **Integration Tests** - End-to-end pipeline

---

## 12. Code Style Guidelines

Follow existing project conventions:

1. **Copyright Header**: Include GPL license header on all new files
2. **Docstrings**: Use Google-style docstrings for all public functions
3. **Type Hints**: Add type hints to all function signatures
4. **Logging**: Use `from common.common import logger`
5. **Error Handling**: Return dict with `success`, `data`, `error` keys
6. **Async**: Use async/await for all I/O operations
7. **Imports**: Follow existing import order (stdlib, third-party, local)

---

## 13. Verification Checklist

Before marking Phase 1 complete:

- [ ] Database migration runs without errors
- [ ] All models import correctly
- [ ] OpenSky client fetches real flight data
- [ ] Camera CRUD operations work via API
- [ ] Contrail detector processes test images
- [ ] All unit tests pass (`pytest backend/tests/chemtrail/`)
- [ ] Code follows existing patterns
- [ ] No new linting errors introduced

---

*Development Brief prepared for Chemtrail Webcam Tracker Phase 1*
