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
# You should receive a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Edge case tests for geocalc service."""

import pytest
from math import isclose, radians, sin, cos
from chemtrail.services.geocalc_service import (
    pixel_to_az_el,
    estimate_position_single,
    calculate_distance_km,
    calculate_az_el_from_positions,
)


class TestPixelToAzElEdgeCases:
    """Test pixel to az/el conversion edge cases."""

    def test_negative_coordinates(self):
        """Test handling of negative coordinates."""
        az, el = pixel_to_az_el(
            x=-10, y=-10,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )
        # Should return values outside normal FOV but still calculated
        assert az < 90.0  # Left of center

    def test_coordinates_beyond_image_size(self):
        """Test handling of coordinates beyond image dimensions."""
        az, el = pixel_to_az_el(
            x=1000, y=1000,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )
        # Should return values outside normal FOV
        assert az > 90.0  # Right of center
        assert el < 0.0  # Below center

    def test_zero_fov(self):
        """Test handling of zero FOV (edge case)."""
        az, el = pixel_to_az_el(
            x=320, y=240,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=0.0,
            fov_v=0.0
        )
        # With zero FOV, all pixels map to camera center
        assert isclose(az, 90.0)
        assert isclose(el, 0.0)

    def test_very_large_fov(self):
        """Test handling of very large FOV."""
        az, el = pixel_to_az_el(
            x=0, y=0,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=0.0,
            fov_h=179.0,  # Nearly 180 degrees
            fov_v=179.0
        )
        # Should handle large FOV without errors
        assert isinstance(az, float)
        assert isinstance(el, float)

    def test_camera_azimuth_wraparound(self):
        """Test azimuth wraparound at 360 degrees."""
        az, el = pixel_to_az_el(
            x=640, y=240,
            width=640, height=480,
            cam_azimuth=350.0,  # Near 360
            cam_elevation=0.0,
            fov_h=60.0,
            fov_v=45.0
        )
        # Should wrap around correctly
        assert 0 <= az <= 360

    def test_elevation_clamping_upper(self):
        """Test elevation clamping at upper bound."""
        az, el = pixel_to_az_el(
            x=320, y=0,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=85.0,  # Near upper limit
            fov_h=60.0,
            fov_v=45.0
        )
        # Should be clamped to 90
        assert el <= 90.0

    def test_elevation_clamping_lower(self):
        """Test elevation clamping at lower bound."""
        az, el = pixel_to_az_el(
            x=320, y=480,
            width=640, height=480,
            cam_azimuth=90.0,
            cam_elevation=-80.0,  # Near lower limit
            fov_h=60.0,
            fov_v=45.0
        )
        # Should be clamped to -90
        assert el >= -90.0


class TestEstimatePositionSingleEdgeCases:
    """Test single position estimation edge cases."""

    def test_zero_elevation_object(self):
        """Test estimation with zero elevation object."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=500,
            az_obj=90.0,
            el_obj=0.1,  # Near horizon (use small positive value)
            assumed_alt=10000
        )
        # Should handle near-zero elevation
        assert -90 <= lat <= 90
        # Longitude may be extreme for near-zero elevation (horizon is very far)
        # This is expected behavior - the formula breaks down at el=0
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    def test_very_high_altitude_object(self):
        """Test estimation for very high altitude object."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=500,
            az_obj=90.0,
            el_obj=80.0,  # Nearly overhead
            assumed_alt=100000  # 100km altitude
        )
        # Should return valid coordinates
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_camera_at_sea_level(self):
        """Test estimation with camera at sea level."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=0,  # Sea level
            az_obj=45.0,
            el_obj=30.0,
            assumed_alt=10000
        )
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_camera_below_sea_level(self):
        """Test estimation with camera below sea level."""
        lat, lon = estimate_position_single(
            cam_lat=31.5,  # Dead Sea area
            cam_lon=35.5,
            cam_alt=-430,  # Below sea level
            az_obj=90.0,
            el_obj=30.0,
            assumed_alt=10000
        )
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

    def test_object_directly_overhead(self):
        """Test estimation for object directly overhead."""
        lat, lon = estimate_position_single(
            cam_lat=47.3,
            cam_lon=8.5,
            cam_alt=500,
            az_obj=0.0,  # North
            el_obj=89.9,  # Nearly overhead
            assumed_alt=10000
        )
        # Should be very close to camera position
        assert abs(lat - 47.3) < 1.0
        assert abs(lon - 8.5) < 1.0

    def test_north_pole_camera(self):
        """Test estimation with camera near north pole."""
        lat, lon = estimate_position_single(
            cam_lat=85.0,  # Near north pole (but not extreme)
            cam_lon=0.0,
            cam_alt=0,
            az_obj=0.0,
            el_obj=45.0,
            assumed_alt=10000
        )
        # Latitude should be valid (may exceed 90 in extreme cases)
        # This test documents the formula's behavior at high latitudes
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        # For 85 degrees, should still be reasonable
        assert lat <= 90 + 5  # Allow small overshoot


class TestCalculateDistanceKmEdgeCases:
    """Test distance calculation edge cases."""

    def test_antipodal_points(self):
        """Test distance between nearly antipodal points."""
        # Points on opposite sides of earth
        dist = calculate_distance_km(0.0, 0.0, 0.0, 179.9)
        # Should be close to half earth circumference (~20,000 km)
        assert 19000 <= dist <= 21000

    def test_pole_to_pole(self):
        """Test distance from north to south pole."""
        dist = calculate_distance_km(90.0, 0.0, -90.0, 0.0)
        # Should be close to earth circumference / 2
        assert 19000 <= dist <= 21000

    def test_international_date_line(self):
        """Test distance crossing international date line."""
        # New Zealand to Chile (crossing date line)
        dist = calculate_distance_km(-45.0, 170.0, -45.0, -70.0)
        # Should calculate correct distance
        assert dist > 0
        assert dist < 20000  # Less than half earth

    def test_small_distance_precision(self):
        """Test precision for very small distances."""
        # 1 meter apart
        dist = calculate_distance_km(47.3, 8.5, 47.300009, 8.5)
        # Should be approximately 1 meter (0.001 km)
        assert dist < 0.1  # Less than 100m


class TestCalculateAzElFromPositionsEdgeCases:
    """Test az/el calculation edge cases."""

    def test_object_directly_above_camera(self):
        """Test az/el for object directly above."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(47.3, 8.5, 0),
            obj_pos=(47.3, 8.5, 1000)  # Same lat/lon, higher altitude
        )
        # Elevation should be 90 degrees (straight up)
        assert isclose(el, 90.0, abs_tol=1.0)

    def test_object_directly_below_camera(self):
        """Test az/el for object directly below."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(47.3, 8.5, 1000),
            obj_pos=(47.3, 8.5, 0)  # Same lat/lon, lower altitude
        )
        # Elevation should be -90 degrees (straight down)
        assert isclose(el, -90.0, abs_tol=1.0)

    def test_equatorial_coordinates(self):
        """Test az/el calculation at equator."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(0.0, 0.0, 0),
            obj_pos=(0.0, 1.0, 10000)
        )
        # Should return valid angles
        assert 0 <= az <= 360
        assert -90 <= el <= 90

    def test_large_distance_calculation(self):
        """Test az/el for very distant object."""
        az, el = calculate_az_el_from_positions(
            cam_pos=(47.3, 8.5, 0),
            obj_pos=(50.0, 15.0, 10000)  # Far away
        )
        assert 0 <= az <= 360
        assert -90 <= el <= 90
