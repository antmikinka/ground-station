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


async def edit_detection(session: AsyncSession, data: dict) -> dict:
    """Update an existing detection record."""
    try:
        detection_id = data.get("id")
        if not detection_id:
            return {"success": False, "error": "Detection id is required."}

        if isinstance(detection_id, str):
            detection_id = uuid.UUID(detection_id)

        data["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(ChemtrailDetections)
            .where(ChemtrailDetections.id == detection_id)
            .values(**{k: v for k, v in data.items() if k != "id"})
            .returning(ChemtrailDetections)
        )

        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()
        if not updated:
            return {"success": False, "error": f"Detection with id {detection_id} not found."}
        await session.commit()
        updated = serialize_object(updated)
        return {"success": True, "data": updated, "error": None}

    except Exception as e:
        await session.rollback()
        logger.error(f"Error editing detection: {e}")
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
