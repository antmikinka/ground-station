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

"""Chemtrail detection handlers."""

from typing import Any, Dict, Optional
from datetime import datetime

import crud
from db import AsyncSessionLocal
from common.common import logger


async def get_chemtrail_detections(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get chemtrail detections with optional filtering."""
    async with AsyncSessionLocal() as dbsession:
        camera_id = data.get("camera_id") if data else None
        limit = data.get("limit", 100) if data else 100

        logger.debug(f"Getting chemtrail detections, camera_id: {camera_id}, limit: {limit}")
        detections = await crud.chemtrail_detections.fetch_all_detections(dbsession, camera_id, limit)
        return {"success": detections["success"], "data": detections.get("data", [])}


async def get_chemtrail_detection(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get single chemtrail detection by ID."""
    async with AsyncSessionLocal() as dbsession:
        detection_id = data.get("id") if data else None
        if not detection_id:
            return {"success": False, "data": [], "error": "id required"}

        logger.debug(f"Getting chemtrail detection {detection_id}")
        detection = await crud.chemtrail_detections.fetch_detection(dbsession, detection_id)
        return {"success": detection["success"], "data": detection.get("data", [])}


async def submit_chemtrail_detection(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Add a new chemtrail detection."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug(f"Adding chemtrail detection, data: {data}")
        add_reply = await crud.chemtrail_detections.add_detection(dbsession, data)
        # Return refreshed list after mutation, matching satellites.py pattern
        detections = await crud.chemtrail_detections.fetch_all_detections(dbsession)
        return {
            "success": add_reply["success"],
            "data": detections.get("data", []),
            "error": add_reply.get("error"),
        }


async def edit_chemtrail_detection(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Edit an existing chemtrail detection."""
    async with AsyncSessionLocal() as dbsession:
        logger.debug(f"Editing chemtrail detection, data: {data}")
        edit_reply = await crud.chemtrail_detections.edit_detection(dbsession, data)
        # Return refreshed list after mutation
        detections = await crud.chemtrail_detections.fetch_all_detections(dbsession)
        return {
            "success": edit_reply["success"],
            "data": detections.get("data", []),
            "error": edit_reply.get("error"),
        }


async def delete_chemtrail_detection(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Delete a chemtrail detection."""
    async with AsyncSessionLocal() as dbsession:
        detection_id = data.get("id") if data else None
        if not detection_id:
            return {"success": False, "data": [], "error": "id required"}

        logger.debug(f"Delete chemtrail detection, data: {data}")
        delete_reply = await crud.chemtrail_detections.delete_detection(dbsession, detection_id)
        # Return refreshed list after mutation
        detections = await crud.chemtrail_detections.fetch_all_detections(dbsession)
        return {
            "success": delete_reply["success"],
            "data": detections.get("data", []),
            "error": delete_reply.get("error"),
        }


async def search_chemtrail_archive(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Search chemtrail detection archive with vector search."""
    try:
        from chemtrail.archive.searcher import search_detections
        from chemtrail.archive.vector_store import ChemtrailVectorStore, detect_index

        query = data.get("query") if data else None
        if not query:
            return {"success": False, "data": [], "error": "query required"}

        # Get filter parameters
        icao24 = data.get("icao24") if data else None
        camera_id = data.get("camera_id") if data else None
        n_results = data.get("n_results", 10) if data else 10

        # Parse date filters
        date_from = None
        date_to = None
        if data:
            if data.get("date_from"):
                try:
                    date_from = datetime.fromisoformat(data["date_from"])
                except (ValueError, TypeError):
                    pass
            if data.get("date_to"):
                try:
                    date_to = datetime.fromisoformat(data["date_to"])
                except (ValueError, TypeError):
                    pass

        logger.debug(f"Searching chemtrail archive, query: {query}, icao24: {icao24}, camera_id: {camera_id}")

        # Detect backend and initialize vector store
        backend, model = detect_index()
        if not backend:
            logger.warning("No vector index found with data")
            return {"success": False, "data": [], "error": "No vector index found. Please index some detections first."}

        logger.debug(f"Using backend: {backend}, model: {model}")
        vector_store = ChemtrailVectorStore(backend=backend, model=model)

        # Perform search
        results = search_detections(
            query=query,
            vector_store=vector_store,
            n_results=n_results,
            icao24=icao24,
            camera_id=camera_id,
            date_from=date_from,
            date_to=date_to,
            verbose=False,
        )

        logger.debug(f"Search returned {len(results)} results")
        return {"success": True, "data": results}

    except Exception as e:
        logger.error(f"Error searching chemtrail archive: {e}")
        return {"success": False, "data": [], "error": str(e)}


def register_handlers(registry):
    """Register detection handlers with the command registry."""
    registry.register_batch(
        {
            "get-chemtrail-detections": (get_chemtrail_detections, "data_request"),
            "get-chemtrail-detection": (get_chemtrail_detection, "data_request"),
            "submit-chemtrail-detection": (submit_chemtrail_detection, "data_submission"),
            "edit-chemtrail-detection": (edit_chemtrail_detection, "data_submission"),
            "delete-chemtrail-detection": (delete_chemtrail_detection, "data_submission"),
            "search-chemtrail-archive": (search_chemtrail_archive, "data_request"),
        }
    )
