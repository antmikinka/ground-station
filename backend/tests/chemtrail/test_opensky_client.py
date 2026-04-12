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

"""Tests for OpenSky API client."""

import pytest
import asyncio
from chemtrail.api.opensky_client import OpenSkyClient, FlightState


class TestOpenSkyClient:
    """Test OpenSky API client."""

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test async context manager."""
        async with OpenSkyClient() as client:
            assert client._client is not None
        # Client should be closed after exit
        assert client._client is None or client._client.is_closed

    @pytest.mark.asyncio
    async def test_get_all_flights(self):
        """Test fetching all flights (integration test)."""
        async with OpenSkyClient() as client:
            flights = await client.get_all_flights()

        # Should return list of FlightState objects
        assert isinstance(flights, list)
        # May be empty if API fails or no flights
        if flights:
            assert isinstance(flights[0], FlightState)

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting works."""
        async with OpenSkyClient(rate_limit_delay=0.1) as client:
            # Make two quick requests
            import time
            start = time.time()
            await client.get_all_flights()
            await client.get_all_flights()
            elapsed = time.time() - start

            # Should have been rate limited
            assert elapsed >= 0.1

    def test_flight_state_dataclass(self):
        """Test FlightState dataclass creation."""
        flight = FlightState(
            icao24="4b1a02",
            callsign="SWR123",
            origin_country="Switzerland",
            time_position=1234567890,
            last_contact=1234567890,
            longitude=8.5,
            latitude=47.3,
            baro_altitude=10000,
            on_ground=False,
            velocity=250.0,
            true_track=90.0,
            vertical_rate=0.0,
            sensors=None,
            geo_altitude=10000,
            squawk="1000",
            spi=False,
            position_source=0,
        )

        assert flight.icao24 == "4b1a02"
        assert flight.callsign == "SWR123"
        assert flight.baro_altitude == 10000
