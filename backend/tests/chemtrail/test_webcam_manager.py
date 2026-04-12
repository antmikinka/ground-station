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

"""Tests for WebcamManager module."""

import pytest
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from chemtrail.sources.webcam_manager import (
    WebcamManager,
    WebcamSource,
    StreamType,
    StreamHealth,
)


class TestWebcamSource:
    """Test WebcamSource dataclass."""

    def test_source_id_generation(self):
        """Test unique ID generation from URL."""
        source = WebcamSource(
            name="Test Camera",
            url="rtsp://192.168.1.100:554/stream",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        # ID should be first 16 chars of SHA256 hash
        expected_id = hashlib.sha256(source.url.encode()).hexdigest()[:16]
        assert source.id == expected_id

    def test_source_id_uniqueness(self):
        """Test different URLs produce different IDs."""
        source1 = WebcamSource(
            name="Camera 1",
            url="rtsp://192.168.1.100:554/stream1",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        source2 = WebcamSource(
            name="Camera 2",
            url="rtsp://192.168.1.100:554/stream2",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        assert source1.id != source2.id

    def test_source_with_optional_fields(self):
        """Test source with all optional fields."""
        source = WebcamSource(
            name="Full Camera",
            url="rtsp://192.168.1.100:554/stream",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
            azimuth=180.0,
            elevation=45.0,
            fov_horizontal=60.0,
            fov_vertical=45.0,
            is_sky_facing=True,
            tags=["test", "outdoor"],
        )
        assert source.azimuth == 180.0
        assert source.elevation == 45.0
        assert source.fov_horizontal == 60.0
        assert source.fov_vertical == 45.0
        assert "test" in source.tags
        assert "outdoor" in source.tags


class TestWebcamManager:
    """Test WebcamManager class."""

    @pytest.fixture
    def manager(self):
        """Create WebcamManager instance."""
        return WebcamManager(max_concurrent=5)

    @pytest.fixture
    def sample_source(self):
        """Create sample webcam source."""
        return WebcamSource(
            name="Test Camera",
            url="rtsp://192.168.1.100:554/stream",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
            azimuth=90.0,
            elevation=0.0,
            is_sky_facing=True,
            tags=["test"],
        )

    @pytest.mark.asyncio
    async def test_initialize(self, manager):
        """Test manager initialization."""
        await manager.initialize(windy_api_key="test-key")
        assert manager._windy_api_key == "test-key"
        assert manager._http_client is not None

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self, manager):
        """Test initialization without API key."""
        await manager.initialize()
        assert manager._windy_api_key is None
        assert manager._http_client is not None

    @pytest.mark.asyncio
    async def test_close(self, manager):
        """Test manager cleanup."""
        await manager.initialize()
        await manager.close()
        # Client should be closed (we can't directly test this, but no error)

    @pytest.mark.asyncio
    async def test_add_manual_source(self, manager, sample_source):
        """Test manually adding a webcam source."""
        source = manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
            azimuth=sample_source.azimuth,
            elevation=sample_source.elevation,
            is_sky_facing=sample_source.is_sky_facing,
            tags=sample_source.tags,
        )
        assert source.id in manager._sources
        assert source.id in manager._health
        assert manager._health[source.id].status == "offline"

    @pytest.mark.asyncio
    async def test_get_all_sources(self, manager, sample_source):
        """Test retrieving all sources."""
        manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
        )
        sources = manager.get_all_sources()
        assert len(sources) == 1
        assert sources[0].name == sample_source.name

    @pytest.mark.asyncio
    async def test_remove_source(self, manager, sample_source):
        """Test removing a source."""
        manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
        )
        assert len(manager._sources) == 1

        result = manager.remove_source(sample_source.id)
        assert result is True
        assert len(manager._sources) == 0
        assert len(manager._health) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_source(self, manager):
        """Test removing a source that doesn't exist."""
        result = manager.remove_source("nonexistent-id")
        assert result is False

    def test_get_sources_near(self, manager, sample_source):
        """Test proximity search for sources."""
        manager.add_manual_source(
            name="Nearby Camera",
            url="rtsp://192.168.1.100:554/nearby",
            stream_type=StreamType.RTSP,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        manager.add_manual_source(
            name="Distant Camera",
            url="rtsp://192.168.1.100:554/distant",
            stream_type=StreamType.RTSP,
            latitude=34.0522,
            longitude=-118.2437,
            altitude=50.0,
        )
        # Search near Seattle
        nearby = manager.get_sources_near(
            lat=47.6062,
            lon=-122.3321,
            radius_km=10.0,
        )
        assert len(nearby) == 1
        assert nearby[0].name == "Nearby Camera"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_discover_windy_camels_nearby(
        self, mock_client_class, manager, sample_source
    ):
        """Test Windy.com webcam discovery with nearby search."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "webcams": [
                    {
                        "status": "active",
                        "location": {
                            "city": "Seattle",
                            "latitude": 47.6062,
                            "longitude": -122.3321,
                        },
                        "player": {
                            "live": {"embed": "https://example.com/stream.m3u8"}
                        },
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await manager.initialize(windy_api_key="test-key")

        sources = await manager.discover_windy_camels(
            api_key="test-key",
            lat=47.6062,
            lon=-122.3321,
            radius_km=50.0,
        )

        assert len(sources) == 1
        assert sources[0].name == "Seattle"
        assert sources[0].stream_type == StreamType.HLS
        assert "windy" in sources[0].tags

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_discover_windy_camels_bbox(
        self, mock_client_class, manager, sample_source
    ):
        """Test Windy.com webcam discovery with bounding box."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "webcams": [
                    {
                        "status": "active",
                        "location": {
                            "city": "Portland",
                            "latitude": 45.5152,
                            "longitude": -122.6784,
                        },
                        "player": {
                            "live": {"embed": "https://example.com/portland.m3u8"}
                        },
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await manager.initialize(windy_api_key="test-key")

        sources = await manager.discover_windy_camels(
            api_key="test-key",
            bbox={"north": 46.0, "south": 45.0, "east": -122.0, "west": -123.0},
        )

        assert len(sources) == 1
        assert sources[0].name == "Portland"

    @pytest.mark.asyncio
    async def test_discover_windy_camels_invalid_params(self, manager):
        """Test Windy.com discovery with invalid parameters."""
        await manager.initialize()

        with pytest.raises(ValueError):
            await manager.discover_windy_camels(api_key="test-key")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_discover_windy_camels_http_error(self, mock_client_class, manager):
        """Test Windy.com discovery with HTTP error."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection error"))
        mock_client_class.return_value = mock_client

        await manager.initialize(windy_api_key="test-key")

        sources = await manager.discover_windy_camels(
            api_key="test-key",
            lat=47.6062,
            lon=-122.3321,
            radius_km=50.0,
        )

        assert sources == []

    @pytest.mark.asyncio
    async def test_discover_windy_camels_inactive_webcam(self, manager):
        """Test filtering inactive webcams."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "webcams": [
                    {
                        "status": "inactive",
                        "location": {"city": "Seattle"},
                        "player": {"live": {"embed": "https://example.com/stream"}},
                    }
                ]
            }
        }
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await manager.initialize(windy_api_key="test-key")

            sources = await manager.discover_windy_camels(
                api_key="test-key",
                lat=47.6062,
                lon=-122.3321,
                radius_km=50.0,
            )

            assert len(sources) == 0

    @pytest.mark.asyncio
    async def test_discover_opensky_webcams(self, manager):
        """Test OpenSky webcam discovery (placeholder)."""
        sources = await manager.discover_opensky_webcams()
        assert sources == []

    def test_get_stream_url(self, manager, sample_source):
        """Test getting stream URL."""
        url = manager.get_stream_url(sample_source)
        assert url == sample_source.url

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_capture_segment_success(
        self, mock_subprocess, manager, sample_source, tmp_path
    ):
        """Test successful segment capture."""
        import time

        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        await manager.initialize()

        # Get timestamp that will be used
        timestamp = int(time.time())
        output_file = tmp_path / f"{sample_source.id}_{timestamp}.mp4"
        output_file.touch()  # Pre-create file since capture_segment checks existence

        result = await manager.capture_segment(
            source=sample_source,
            duration=10,
            output_dir=str(tmp_path),
        )

        assert result is not None
        assert result["source_id"] == sample_source.id
        assert result["duration"] == 10
        assert "segment_path" in result

        # Check health was updated
        health = manager._health.get(sample_source.id)
        if health:
            assert health.segment_count >= 1

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_capture_segment_failure(self, mock_subprocess, manager, sample_source):
        """Test segment capture failure."""
        # Mock subprocess failure
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"ffmpeg error"))
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        await manager.initialize()

        result = await manager.capture_segment(
            source=sample_source,
            duration=10,
            output_dir="/tmp",
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_capture_segment_timeout(self, mock_subprocess, manager, sample_source):
        """Test segment capture timeout."""
        import asyncio

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        mock_subprocess.return_value = mock_process

        await manager.initialize()

        result = await manager.capture_segment(
            source=sample_source,
            duration=10,
        )

        assert result is None

    def test_check_source_health_live(self, manager, sample_source):
        """Test health check for live stream."""
        manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
        )
        # Set recent segment time
        manager._health[sample_source.id].last_segment_time = datetime.now(timezone.utc)
        manager._health[sample_source.id].status = "live"

        health = manager.check_source_health(sample_source)
        assert health.status == "live"

    def test_check_source_health_stale(self, manager, sample_source):
        """Test health check for stale stream."""
        manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
        )
        # Set old segment time (3 minutes ago)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        manager._health[sample_source.id].last_segment_time = old_time
        manager._health[sample_source.id].status = "live"

        health = manager.check_source_health(sample_source)
        assert health.status == "error"
        assert "No segments" in health.error_message

    def test_check_source_health_offline(self, manager, sample_source):
        """Test health check for unknown source."""
        health = manager.check_source_health(sample_source)
        assert health.status == "offline"

    @pytest.mark.asyncio
    async def test_run_forever(self, manager, sample_source):
        """Test continuous capture loop."""
        manager.add_manual_source(
            name=sample_source.name,
            url=sample_source.url,
            stream_type=sample_source.stream_type,
            latitude=sample_source.latitude,
            longitude=sample_source.longitude,
            altitude=sample_source.altitude,
        )
        await manager.initialize()

        # Run for short time then stop
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            await manager.stop()

        # Start both tasks
        run_task = asyncio.create_task(manager.run_forever(capture_interval=0.05))
        stop_task = asyncio.create_task(stop_after_delay())

        # Wait for both to complete
        await asyncio.gather(run_task, stop_task)

        assert manager._running is False

    @pytest.mark.asyncio
    async def test_context_manager(self, manager):
        """Test async context manager."""
        async with WebcamManager() as cm:
            assert cm._running is False
            assert cm._http_client is not None

        assert cm._running is False

    def test_stream_type_values(self):
        """Test StreamType enum values."""
        assert StreamType.RTSP.value == "rtsp"
        assert StreamType.MJPEG.value == "mjpeg"
        assert StreamType.HLS.value == "hls"
        assert StreamType.YOUTUBE.value == "youtube"

    def test_ffmpeg_command_rtsp(self, manager, sample_source):
        """Test ffmpeg command building for RTSP."""
        cmd = manager._build_ffmpeg_command(
            sample_source, duration=10, output_path="/tmp/test.mp4"
        )
        assert "ffmpeg" in cmd
        assert "-rtsp_transport" in cmd
        assert "tcp" in cmd
        assert "-t" in cmd
        assert "10" in cmd

    def test_ffmpeg_command_hls(self, manager):
        """Test ffmpeg command building for HLS."""
        source = WebcamSource(
            name="HLS Camera",
            url="https://example.com/stream.m3u8",
            stream_type=StreamType.HLS,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        cmd = manager._build_ffmpeg_command(
            source, duration=10, output_path="/tmp/test.mp4"
        )
        assert "-strict" in cmd
        assert "experimental" in cmd

    def test_ffmpeg_command_youtube(self, manager):
        """Test ffmpeg command building for YouTube."""
        source = WebcamSource(
            name="YouTube Camera",
            url="https://youtube.com/watch?v=xxx",
            stream_type=StreamType.YOUTUBE,
            latitude=47.6062,
            longitude=-122.3321,
            altitude=100.0,
        )
        cmd = manager._build_ffmpeg_command(
            source, duration=10, output_path="/tmp/test.mp4"
        )
        assert "-user_agent" in cmd
