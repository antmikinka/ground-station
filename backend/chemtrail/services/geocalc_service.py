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
from math import radians, degrees, sin, cos, tan, atan2, sqrt


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


def calculate_az_el_from_positions(
    cam_pos: Tuple[float, float, float],
    obj_pos: Tuple[float, float, float]
) -> Tuple[float, float]:
    """
    Calculate azimuth and elevation from camera position to object position.

    Args:
        cam_pos: (lat, lon, alt) camera position in degrees and meters AMSL
        obj_pos: (lat, lon, alt) object position in degrees and meters AMSL

    Returns:
        (azimuth, elevation) in degrees
    """
    cam_lat, cam_lon, cam_alt = cam_pos
    obj_lat, obj_lon, obj_alt = obj_pos

    # Calculate differences
    delta_lat = obj_lat - cam_lat
    delta_lon = obj_lon - cam_lon
    delta_alt = obj_alt - cam_alt

    # Convert to meters (approximate)
    meters_north = delta_lat * 111320
    meters_east = delta_lon * 111320 * cos(radians(cam_lat))

    # Horizontal distance
    horizontal_dist = sqrt(meters_north ** 2 + meters_east ** 2)

    # Elevation angle
    el_rad = atan2(delta_alt, horizontal_dist)
    el_deg = degrees(el_rad)

    # Azimuth angle (0 = North, 90 = East)
    az_rad = atan2(meters_east, meters_north)
    az_deg = degrees(az_rad)

    # Normalize azimuth to 0-360
    if az_deg < 0:
        az_deg += 360

    return az_deg, el_deg
