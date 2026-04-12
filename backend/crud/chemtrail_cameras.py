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
