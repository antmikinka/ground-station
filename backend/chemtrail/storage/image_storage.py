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

"""Image storage utilities for chemtrail detections."""

import os
import uuid
import re
from datetime import datetime
from typing import Optional, Tuple
import numpy as np

import cv2
from common.common import logger


# Base directory for storing detection images
DETECTIONS_BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "chemtrail",
    "detections"
)

# Pattern for safe filename/ID components - only allow UUIDs and safe characters
_SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-]+$')


def _validate_path_component(component: str) -> str:
    """
    Validate a path component to prevent path traversal attacks.

    Args:
        component: The path component to validate

    Returns:
        The validated component

    Raises:
        ValueError: If the component contains unsafe characters
    """
    if not component:
        raise ValueError("Path component cannot be empty")
    if not _SAFE_ID_PATTERN.match(component):
        raise ValueError(f"Unsafe path component: {component}")
    return component


def _ensure_within_base(full_path: str) -> str:
    """
    Ensure a resolved path is within the expected base directory.

    Args:
        full_path: The full path to validate

    Returns:
        The validated full path

    Raises:
        ValueError: If the path escapes the base directory
    """
    base_real = os.path.realpath(DETECTIONS_BASE_DIR)
    resolved = os.path.realpath(full_path)
    if not resolved.startswith(base_real):
        raise ValueError(f"Path escapes base directory: {full_path}")
    return resolved


def get_detections_dir() -> str:
    """Get the base directory for detection images, creating if needed."""
    os.makedirs(DETECTIONS_BASE_DIR, exist_ok=True)
    return DETECTIONS_BASE_DIR


def get_image_path(
    camera_id: str,
    timestamp: datetime,
    detection_id: Optional[str] = None
) -> str:
    """
    Generate file path for a detection image.

    Args:
        camera_id: UUID of the camera
        timestamp: Timestamp of detection
        detection_id: Optional detection UUID (uses timestamp if not provided)

    Returns:
        Full file path for the image
    """
    detections_dir = get_detections_dir()

    # Validate camera_id to prevent path traversal
    safe_camera_id = _validate_path_component(str(camera_id))

    # Create camera-specific subdirectory
    camera_dir = os.path.join(detections_dir, safe_camera_id)
    os.makedirs(camera_dir, exist_ok=True)

    # Create year/month subdirectories
    year_month = timestamp.strftime("%Y/%m")
    date_dir = os.path.join(camera_dir, year_month)
    os.makedirs(date_dir, exist_ok=True)

    # Generate filename - sanitize detection_id if provided
    if detection_id:
        safe_detection_id = _validate_path_component(str(detection_id))
        filename = f"{safe_detection_id}.jpg"
    else:
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp_str}.jpg"

    full_path = os.path.join(date_dir, filename)
    return _ensure_within_base(full_path)


def save_detection_image(
    image: np.ndarray,
    camera_id: str,
    timestamp: datetime,
    detection_id: Optional[str] = None,
    jpeg_quality: int = 85
) -> Tuple[str, str]:
    """
    Save detection image to disk.

    Args:
        image: BGR image as numpy array
        camera_id: UUID of the camera
        timestamp: Timestamp of detection
        detection_id: Optional detection UUID
        jpeg_quality: JPEG compression quality (1-100)

    Returns:
        Tuple of (file_path, relative_path)
    """
    try:
        # Get full path
        full_path = get_image_path(camera_id, timestamp, detection_id)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Compress and save image
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        cv2.imwrite(full_path, image, encode_params)

        # Calculate relative path (from backend root)
        rel_path = os.path.join(
            "data",
            "chemtrail",
            "detections",
            str(camera_id),
            timestamp.strftime("%Y/%m"),
            os.path.basename(full_path)
        )

        logger.debug(f"Saved detection image to {full_path}")
        return full_path, rel_path

    except Exception as e:
        logger.error(f"Error saving detection image: {e}")
        raise


def load_detection_image(file_path: str) -> Optional[np.ndarray]:
    """
    Load a detection image from disk.

    Args:
        file_path: Path to image file (absolute or relative)

    Returns:
        BGR image as numpy array, or None if not found
    """
    try:
        if not os.path.isabs(file_path):
            # Convert relative path to absolute
            backend_dir = os.path.dirname(os.path.dirname(__file__))
            file_path = os.path.join(backend_dir, file_path)

        if not os.path.exists(file_path):
            logger.warning(f"Detection image not found: {file_path}")
            return None

        image = cv2.imread(file_path)
        return image

    except Exception as e:
        logger.error(f"Error loading detection image: {e}")
        return None


def delete_detection_image(file_path: str) -> bool:
    """
    Delete a detection image from disk.

    Args:
        file_path: Path to image file

    Returns:
        True if deleted, False if not found or error
    """
    try:
        if not os.path.isabs(file_path):
            backend_dir = os.path.dirname(os.path.dirname(__file__))
            file_path = os.path.join(backend_dir, file_path)

        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Deleted detection image: {file_path}")
            return True
        return False

    except Exception as e:
        logger.error(f"Error deleting detection image: {e}")
        return False


def get_camera_detection_images(
    camera_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> list:
    """
    List detection images for a camera.

    Args:
        camera_id: UUID of the camera
        year: Optional year filter
        month: Optional month filter

    Returns:
        List of file paths
    """
    try:
        camera_dir = os.path.join(DETECTIONS_BASE_DIR, str(camera_id))

        if not os.path.exists(camera_dir):
            return []

        images = []

        # Build path based on filters
        if year:
            camera_dir = os.path.join(camera_dir, str(year))
            if month and os.path.exists(camera_dir):
                camera_dir = os.path.join(camera_dir, f"{month:02d}")

        # Walk directory and collect images
        for root, dirs, files in os.walk(camera_dir):
            for file in files:
                if file.endswith(('.jpg', '.jpeg', '.png')):
                    images.append(os.path.join(root, file))

        return sorted(images)

    except Exception as e:
        logger.error(f"Error listing detection images: {e}")
        return []
