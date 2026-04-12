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

"""Tests for geocalc service."""

import pytest
from math import isclose
from chemtrail.services.geocalc_service import (
    pixel_to_az_el,
    estimate_position_single,
    calculate_distance_km,
    calculate_az_el_from_positions,
)


class TestPixelToAzEl:
    """Test pixel to azimuth/elevation conversion."""

    def test_center_pixel(self):
        """Test center pixel returns camera az/el."""
        az, el = pixel_to_az_el(
            x=320, y=240,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Center pixel should return camera orientation
        assert isclose(az, 90.0)
        assert isclose(el, 0.0)

    def test_left_edge_pixel(self):
        """Test left edge pixel returns az offset by -fov_h/2."""
        az, el = pixel_to_az_el(
            x=0, y=240,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Left edge should be -30 degrees from center
        assert isclose(az, 60.0)

    def test_right_edge_pixel(self):
        """Test right edge pixel returns az offset by +fov_h/2."""
        az, el = pixel_to_az_el(
            x=640, y=240,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Right edge should be +30 degrees from center
        assert isclose(az, 120.0)

    def test_top_edge_pixel(self):
        """Test top edge pixel returns el offset by +fov_v/2."""
        az, el = pixel_to_az_el(
            x=320, y=0,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Top edge should be +22.5 degrees from center
        assert isclose(el, 22.5)

    def test_bottom_edge_pixel(self):
        """Test bottom edge pixel returns el offset by -fov_v/2."""
        az, el = pixel_to_az_el(
            x=320, y=480,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Bottom edge should be -22.5 degrees from center
        assert isclose(el, -22.5)

    def test_elevation_clamping(self):
        """Test elevation is clamped to -90 to 90."""
        az, el = pixel_to_az_el(
            x=320, y=0,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=80.0,
            fov_h=60.0,
            fov_v=45.0
        )

        # Elevation should be clamped to 90
        assert el <= 90.0


class TestEstimatePositionSingle:
    """Test single-camera position estimation."""

    def test_basic_estimation(self):
        """Test basic position estimation."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=500,
            az_obj=90.0,
            el_obj=30.0,
            assumed_alt=10000
        )

        # Result should be valid coordinates
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_due_east(self):
        """Test estimation for object due east."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=0,
            az_obj=90.0,  # East
            el_obj=45.0,
            assumed_alt=10000
        )

        # Should be east of camera (higher longitude)
        assert lon > 8.5

    def test_due_north(self):
        """Test estimation for object due north."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=0,
            az_obj=0.0,  # North
            el_obj=45.0,
            assumed_alt=10000
        )

        # Should be north of camera (higher latitude)
        assert lat > 47.3


class TestCalculateDistanceKm:
    """Test distance calculation."""

    def test_same_point(self):
        """Test distance to same point is zero."""
        dist = calculate_distance_km(47.3, 8.5, 47.3, 8.5)
        assert isclose(dist, 0.0, abs_tol=0.001)

    def test_short_distance(self):
        """Test short distance calculation."""
        # Zurich to Bern (approx 100km)
        dist = calculate_distance_km(47.3769, 8.5417, 46.9480, 7.4474)
        assert 90 <= dist <= 110


class TestCalculateAzElFromPositions:
    """Test azimuth/elevation calculation from positions."""

    def test_same_position(self):
        """Test az/el for same position."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(47.3, 8.5, 0),
            obj_pos=(47.3, 8.5, 0)
        )

        # Should return valid angles
        assert 0 <= az <= 360
        assert -90 <= el <= 90

    def test_object_north(self):
        """Test az for object directly north."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(47.3, 8.5, 0),
            obj_pos=(47.4, 8.5, 0)
        )

        # Should be approximately north (0 degrees)
        assert isclose(az, 0.0, abs_tol=5.0)
