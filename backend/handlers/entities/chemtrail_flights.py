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

"""Chemtrail flight data handlers."""

import os
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import logger
from db import AsyncSessionLocal
from db.models import FlightCache
from chemtrail.services.flight_service import FlightService
from chemtrail.services.fr24_flight_service import FR24FlightService


async def get_live_flights(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get live flights near a position or all cached flights."""
    async with AsyncSessionLocal() as dbsession:
        try:
            # Get FR24 API token from environment
            fr24_token = os.environ.get("FR24_API_TOKEN")

            # Create flight service
            service = FlightService(dbsession, fr24_api_token=fr24_token)

            # Check if position-based query
            lat = data.get("lat") if data else None
            lon = data.get("lon") if data else None

            if lat is not None and lon is not None:
                radius_km = data.get("radius_km", 50.0) if data else 50.0
                limit = data.get("limit", 10) if data else 10

                logger.debug(f"Getting flights near position: lat={lat}, lon={lon}, radius={radius_km}km")
                flights = await service.get_flights_near_position(lat, lon, radius_km, limit)
            else:
                # Get all cached flights
                logger.debug("Getting all cached flights")
                stmt = select(FlightCache).limit(100)
                result = await dbsession.execute(stmt)
                flights = result.scalars().all()

                flights = [
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

            return {"success": True, "data": flights}

        except Exception as e:
            logger.error(f"Error getting live flights: {e}")
            return {"success": False, "data": [], "error": str(e)}


async def get_flight_details(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get detailed flight information for a specific ICAO24 hex code."""
    try:
        icao24 = data.get("icao24") if data else None
        if not icao24:
            return {"success": False, "data": {}, "error": "icao24 required"}

        logger.debug(f"Getting flight details for ICAO24: {icao24}")

        # Get FR24 API token and create service
        fr24_token = os.environ.get("FR24_API_TOKEN")
        fr24_service = FR24FlightService(api_token=fr24_token)

        # Get flight summary from FR24
        summary = fr24_service.get_flight_summary_by_hex(icao24)

        if not summary:
            # Fallback to cached data
            async with AsyncSessionLocal() as dbsession:
                stmt = select(FlightCache).filter(FlightCache.icao24 == icao24)
                result = await dbsession.execute(stmt)
                cached = result.scalar_one_or_none()

                if cached:
                    flight_data = {
                        "icao24": cached.icao24,
                        "callsign": cached.callsign,
                        "registration": cached.registration,
                        "aircraft_type": cached.aircraft_type,
                        "origin_icao": cached.origin_icao,
                        "destination_icao": cached.destination_icao,
                        "position": cached.position,
                        "last_update": cached.last_position_update,
                    }
                    return {"success": True, "data": flight_data}

                return {"success": False, "data": {}, "error": f"Flight {icao24} not found"}

        return {"success": True, "data": summary}

    except Exception as e:
        logger.error(f"Error getting flight details: {e}")
        return {"success": False, "data": {}, "error": str(e)}


async def get_flight_track(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get flight track/history for a specific ICAO24 hex code."""
    try:
        icao24 = data.get("icao24") if data else None
        if not icao24:
            return {"success": False, "data": {}, "error": "icao24 required"}

        logger.debug(f"Getting flight track for ICAO24: {icao24}")

        # Get FR24 API token and create service
        fr24_token = os.environ.get("FR24_API_TOKEN")
        fr24_service = FR24FlightService(api_token=fr24_token)

        # Get flight track from FR24
        track = fr24_service.get_flight_track(icao24)

        if not track:
            # Fallback to cached position history
            async with AsyncSessionLocal() as dbsession:
                stmt = select(FlightCache).filter(FlightCache.icao24 == icao24)
                result = await dbsession.execute(stmt)
                cached = result.scalar_one_or_none()

                if cached and cached.position_history:
                    return {"success": True, "data": {"icao24": icao24, "tracks": cached.position_history}}

                return {"success": False, "data": {}, "error": f"No track data found for flight {icao24}"}

        return {"success": True, "data": track}

    except Exception as e:
        logger.error(f"Error getting flight track: {e}")
        return {"success": False, "data": {}, "error": str(e)}


async def get_fr24_health(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get FR24 service health status."""
    try:
        logger.debug("Getting FR24 health status")

        # Get FR24 API token and create service
        fr24_token = os.environ.get("FR24_API_TOKEN")
        fr24_service = FR24FlightService(api_token=fr24_token)

        health = fr24_service.health_check()

        return {"success": True, "data": health}

    except Exception as e:
        logger.error(f"Error getting FR24 health: {e}")
        return {"success": False, "data": {}, "error": str(e)}


async def get_fr24_metrics(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get FR24 service metrics."""
    try:
        logger.debug("Getting FR24 metrics")

        # Get FR24 API token and create service
        fr24_token = os.environ.get("FR24_API_TOKEN")
        fr24_service = FR24FlightService(api_token=fr24_token)

        metrics = fr24_service.get_metrics()

        return {"success": True, "data": metrics}

    except Exception as e:
        logger.error(f"Error getting FR24 metrics: {e}")
        return {"success": False, "data": {}, "error": str(e)}


async def get_flm_status(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get FLM (FastFlowLM) server status."""
    try:
        logger.debug("Getting FLM server status")

        # Import here to avoid circular imports
        from chemtrail.archive.flm_embedder import FLMConfig, FLMEmbedder

        config = FLMConfig.from_env()
        embedder = FLMEmbedder(config)
        model_info = embedder.get_model_info()
        embedder.close()

        return {"success": True, "data": model_info}

    except Exception as e:
        logger.error(f"Error getting FLM status: {e}")
        return {
            "success": True,
            "data": {
                "server_connected": False,
                "embedding_model": os.environ.get("FLM_EMBEDDING_MODEL", "embed-gemma:300m"),
                "vision_model": os.environ.get("FLM_VISION_MODEL", "qwen3vl-it:4b"),
                "available_models": [],
                "error": str(e),
            }
        }


def register_handlers(registry):
    """Register flight handlers with the command registry."""
    registry.register_batch(
        {
            "get-live-flights": (get_live_flights, "data_request"),
            "get-flight-details": (get_flight_details, "data_request"),
            "get-flight-track": (get_flight_track, "data_request"),
            "get-fr24-health": (get_fr24_health, "data_request"),
            "get-fr24-metrics": (get_fr24_metrics, "data_request"),
            "get-flm-status": (get_flm_status, "data_request"),
        }
    )
