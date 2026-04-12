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
            "extra_data": camera.extra_data,
            "created_at": camera.created_at.isoformat() if camera.created_at else None,
            "updated_at": camera.updated_at.isoformat() if camera.updated_at else None,
        }
