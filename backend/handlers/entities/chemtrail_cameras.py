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
        # Return refreshed list after mutation, matching satellites.py pattern
        cameras = await crud.chemtrail_cameras.fetch_all_cameras(dbsession)
        return {
            "success": add_reply["success"],
            "data": cameras.get("data", []),
            "error": add_reply.get("error"),
        }


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
        # Return refreshed list after mutation
        cameras = await crud.chemtrail_cameras.fetch_all_cameras(dbsession)
        return {
            "success": edit_reply["success"],
            "data": cameras.get("data", []),
            "error": edit_reply.get("error"),
        }


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
        # Return refreshed list after mutation
        cameras = await crud.chemtrail_cameras.fetch_all_cameras(dbsession)
        return {
            "success": delete_reply["success"],
            "data": cameras.get("data", []),
            "error": delete_reply.get("error"),
        }


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
