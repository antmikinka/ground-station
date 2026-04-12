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

"""Chemtrail service layer with dual-source flight data support."""

__version__ = "0.1.0"

from .services import (
    FlightService,
    CameraService,
    FR24FlightService,
    pixel_to_az_el,
    estimate_position_single,
)

__all__ = [
    "FlightService",
    "CameraService",
    "FR24FlightService",
    "pixel_to_az_el",
    "estimate_position_single",
]
