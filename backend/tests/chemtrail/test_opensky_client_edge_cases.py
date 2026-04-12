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

"""Edge case and error handling tests for OpenSky client."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from chemtrail.api.opensky_client import OpenSkyClient, FlightState


class TestOpenSkyClientErrorHandling:
    """Test OpenSky client error handling."""

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test handling of HTTP errors."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("500 Server Error"))
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list on error
            assert flights == []

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """Test handling of timeout errors."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list on timeout
            assert flights == []

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection errors."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list on connection error
            assert flights == []

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Test handling of malformed JSON response."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_response = MagicMock()
            mock_response.json = MagicMock(side_effect=ValueError("Invalid JSON"))
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list on JSON error
            assert flights == []

    @pytest.mark.asyncio
    async def test_missing_states_key(self):
        """Test handling of response missing 'states' key."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"error": "API error"})
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list when 'states' key missing
            assert flights == []

    @pytest.mark.asyncio
    async def test_empty_states_list(self):
        """Test handling of empty states list."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"states": []})
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_all_flights()

            # Should return empty list
            assert flights == []

    @pytest.mark.asyncio
    async def test_get_flight_by_icao24_error_handling(self):
        """Test error handling for get_flight_by_icao24."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("500 Error"))
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flight = await client.get_flight_by_icao24("4b1a02")

            # Should return None on error
            assert flight is None

    @pytest.mark.asyncio
    async def test_get_flights_in_area_error_handling(self):
        """Test error handling for get_flights_in_area."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("500 Error"))
            mock_client_class.return_value = mock_client

            async with OpenSkyClient() as client:
                flights = await client.get_flights_in_area(
                    lat_min=40.0, lat_max=50.0,
                    lon_min=5.0, lon_max=15.0
                )

            # Should return empty list on error
            assert flights == []

    @pytest.mark.asyncio
    async def test_client_without_initialization(self):
        """Test calling methods without initializing client."""
        client = OpenSkyClient()
        # _client should be None before entering context
        assert client._client is None

        # Calling methods should handle None client gracefully
        flights = await client.get_all_flights()
        assert flights == []

    @pytest.mark.asyncio
    async def test_rate_limiting_with_zero_delay(self):
        """Test rate limiting with zero delay."""
        async with OpenSkyClient(rate_limit_delay=0) as client:
            import time
            start = time.time()
            # Make multiple rapid requests (mocked)
            with patch.object(client, '_client') as mock_client:
                mock_response = MagicMock()
                mock_response.json = MagicMock(return_value={"states": []})
                mock_response.raise_for_status = MagicMock()
                mock_client.get = AsyncMock(return_value=mock_response)

                await client.get_all_flights()
                await client.get_all_flights()
                await client.get_all_flights()

            # Should complete quickly with zero delay
            elapsed = time.time() - start
            assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_member_rate_limiting(self):
        """Test member rate limiting (1 second)."""
        async with OpenSkyClient(username="test", password="test") as client:
            # Should automatically set rate_limit_delay to 1.0 for members
            assert client.rate_limit_delay == 1.0

    def test_flight_state_with_none_values(self):
        """Test FlightState with None values."""
        flight = FlightState(
            icao24="4b1a02",
            callsign=None,
            origin_country=None,
            time_position=None,
            last_contact=None,
            longitude=None,
            latitude=None,
            baro_altitude=None,
            on_ground=False,
            velocity=None,
            true_track=None,
            vertical_rate=None,
            sensors=None,
            geo_altitude=None,
            squawk=None,
            spi=False,
            position_source=0,
        )

        assert flight.icao24 == "4b1a02"
        assert flight.callsign is None
        assert flight.on_ground is False

    def test_flight_state_with_empty_callsign(self):
        """Test FlightState with empty callsign."""
        flight = FlightState(
            icao24="4b1a02",
            callsign="",  # Empty string
            origin_country="Test",
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

        # Empty string should be preserved
        assert flight.callsign == ""

    def test_flight_state_position_source_values(self):
        """Test FlightState with different position_source values."""
        for ps in range(4):
            flight = FlightState(
                icao24="4b1a02",
                callsign=None,
                origin_country=None,
                time_position=None,
                last_contact=None,
                longitude=None,
                latitude=None,
                baro_altitude=None,
                on_ground=False,
                velocity=None,
                true_track=None,
                vertical_rate=None,
                sensors=None,
                geo_altitude=None,
                squawk=None,
                spi=False,
                position_source=ps,
            )
            assert flight.position_source == ps


class TestOpenSkyClientIntegration:
    """Integration tests for OpenSky client (may fail if API is down)."""

    @pytest.mark.asyncio
    async def test_real_api_response_structure(self):
        """Test that real API returns expected structure."""
        # This test makes a real API call
        async with OpenSkyClient() as client:
            flights = await client.get_all_flights()

        # If API is working, should get list
        assert isinstance(flights, list)

        # If there are flights, they should have required fields
        if flights:
            flight = flights[0]
            assert hasattr(flight, 'icao24')
            assert flight.icao24 is not None
