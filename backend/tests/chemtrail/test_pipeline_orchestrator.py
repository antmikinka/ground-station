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

"""Tests for PipelineOrchestrator module."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from chemtrail.sources.pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineStage,
    PipelineStatus,
    PipelineJob,
)


class TestPipelineStage:
    """Test PipelineStage enum."""

    def test_stage_values(self):
        """Test all stage values exist."""
        assert PipelineStage.ACQUISITION.value == "acquisition"
        assert PipelineStage.SORTING.value == "sorting"
        assert PipelineStage.WEATHER_ENRICHMENT.value == "weather_enrichment"
        assert PipelineStage.QUALITY_SCORING.value == "quality_scoring"
        assert PipelineStage.CHUNKING.value == "chunking"
        assert PipelineStage.DETECTION.value == "detection"
        assert PipelineStage.ARCHIVAL.value == "archival"
        assert PipelineStage.COMPLETE.value == "complete"


class TestPipelineStatus:
    """Test PipelineStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.COMPLETED.value == "completed"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.PAUSED.value == "paused"
        assert PipelineStatus.CANCELLED.value == "cancelled"


class TestPipelineJob:
    """Test PipelineJob dataclass."""

    def test_job_creation(self):
        """Test creating a pipeline job."""
        job = PipelineJob(
            job_id="test-job-123",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )

        assert job.job_id == "test-job-123"
        assert job.source_path == "/videos/test.mp4"
        assert job.source_type == "local"
        assert job.status == PipelineStatus.PENDING
        assert job.current_stage == PipelineStage.ACQUISITION
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.cancel_flag is False

    def test_job_with_metadata(self):
        """Test job with metadata."""
        metadata = {"camera_id": "cam-001", "location": "Seattle"}
        job = PipelineJob(
            job_id="job-with-metadata",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
            metadata=metadata,
        )

        assert job.metadata["camera_id"] == "cam-001"
        assert job.metadata["location"] == "Seattle"

    def test_job_created_at_timestamp(self):
        """Test that created_at is set automatically."""
        job = PipelineJob(
            job_id="test-job",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )

        assert job.created_at is not None
        assert job.created_at.tzinfo == timezone.utc


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PipelineConfig()

        assert config.max_concurrent_jobs == 5
        assert config.enable_weather_enrichment is True
        assert config.enable_quality_scoring is True
        assert config.skip_still_frames is True
        assert config.apply_overlay is False
        assert config.chunk_duration_seconds == 30
        assert config.chunk_overlap_seconds == 5

    def test_stage_timeouts(self):
        """Test stage timeout configuration."""
        config = PipelineConfig()

        assert config.stage_timeout_seconds[PipelineStage.ACQUISITION] == 300
        assert config.stage_timeout_seconds[PipelineStage.SORTING] == 60
        assert config.stage_timeout_seconds[PipelineStage.WEATHER_ENRICHMENT] == 120
        assert config.stage_timeout_seconds[PipelineStage.QUALITY_SCORING] == 120
        assert config.stage_timeout_seconds[PipelineStage.CHUNKING] == 600
        assert config.stage_timeout_seconds[PipelineStage.DETECTION] == 1800
        assert config.stage_timeout_seconds[PipelineStage.ARCHIVAL] == 300

    def test_custom_config(self):
        """Test custom configuration."""
        config = PipelineConfig(
            max_concurrent_jobs=10,
            enable_weather_enrichment=False,
            chunk_duration_seconds=60,
            chunk_overlap_seconds=10,
        )

        assert config.max_concurrent_jobs == 10
        assert config.enable_weather_enrichment is False
        assert config.chunk_duration_seconds == 60
        assert config.chunk_overlap_seconds == 10


class TestPipelineOrchestrator:
    """Test PipelineOrchestrator class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock SQLAlchemy session."""
        return MagicMock()

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies."""
        return {
            "webcam_manager": AsyncMock(),
            "historical_ingestor": MagicMock(),
            "video_catalog": AsyncMock(),
            "weather_service": MagicMock(),
            "detection_service": AsyncMock(),
        }

    @pytest.fixture
    def orchestrator(self, mock_session, mock_dependencies):
        """Create PipelineOrchestrator instance."""
        return PipelineOrchestrator(
            session=mock_session,
            webcam_manager=mock_dependencies["webcam_manager"],
            historical_ingestor=mock_dependencies["historical_ingestor"],
            video_catalog=mock_dependencies["video_catalog"],
            weather_service=mock_dependencies["weather_service"],
            detection_service=mock_dependencies["detection_service"],
        )

    def test_init_default_config(self, mock_session, mock_dependencies):
        """Test initialization with default config."""
        orchestrator = PipelineOrchestrator(
            session=mock_session,
            webcam_manager=mock_dependencies["webcam_manager"],
            historical_ingestor=mock_dependencies["historical_ingestor"],
            video_catalog=mock_dependencies["video_catalog"],
            weather_service=mock_dependencies["weather_service"],
            detection_service=mock_dependencies["detection_service"],
        )

        assert orchestrator.config.max_concurrent_jobs == 5

    def test_init_custom_config(self, mock_session, mock_dependencies):
        """Test initialization with custom config."""
        config = PipelineConfig(max_concurrent_jobs=10)
        orchestrator = PipelineOrchestrator(
            session=mock_session,
            webcam_manager=mock_dependencies["webcam_manager"],
            historical_ingestor=mock_dependencies["historical_ingestor"],
            video_catalog=mock_dependencies["video_catalog"],
            weather_service=mock_dependencies["weather_service"],
            detection_service=mock_dependencies["detection_service"],
            config=config,
        )

        assert orchestrator.config.max_concurrent_jobs == 10

    @pytest.mark.asyncio
    async def test_start(self, orchestrator):
        """Test starting the orchestrator."""
        await orchestrator.start()

        assert orchestrator._running is True
        assert len(orchestrator._workers) == 5  # Default workers

        # Cleanup
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_stop(self, orchestrator):
        """Test stopping the orchestrator."""
        await orchestrator.start()
        await orchestrator.stop()

        assert orchestrator._running is False

    @pytest.mark.asyncio
    async def test_submit_job(self, orchestrator):
        """Test submitting a pipeline job."""
        job_id = await orchestrator.submit_job(
            source_path="/videos/test.mp4",
            source_type="local",
            priority=3,
            metadata={"camera_id": "cam-001"},
        )

        assert job_id is not None
        assert job_id in orchestrator._jobs

        job = orchestrator._jobs[job_id]
        assert job.source_path == "/videos/test.mp4"
        assert job.source_type == "local"
        assert job.status == PipelineStatus.PENDING
        assert job.current_stage == PipelineStage.ACQUISITION
        assert job.metadata["camera_id"] == "cam-001"

    @pytest.mark.asyncio
    async def test_get_pipeline_status_found(self, orchestrator):
        """Test getting status of existing job."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")

        status = await orchestrator.get_pipeline_status(job_id)

        assert status is not None
        assert status["job_id"] == job_id
        assert status["source_path"] == "/videos/test.mp4"
        assert status["current_stage"] == "acquisition"
        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_pipeline_status_not_found(self, orchestrator):
        """Test getting status of non-existent job."""
        status = await orchestrator.get_pipeline_status("non-existent-job")

        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_pipeline_pending(self, orchestrator):
        """Test cancelling pending job."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")

        result = await orchestrator.cancel_pipeline(job_id)

        assert result is True

        job = orchestrator._jobs[job_id]
        assert job.cancel_flag is True
        assert job.status == PipelineStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_pipeline_completed(self, orchestrator):
        """Test cancelling completed job."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")
        orchestrator._jobs[job_id].status = PipelineStatus.COMPLETED

        result = await orchestrator.cancel_pipeline(job_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_pipeline_not_found(self, orchestrator):
        """Test cancelling non-existent job."""
        result = await orchestrator.cancel_pipeline("non-existent-job")

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_job_completion(self, orchestrator):
        """Test waiting for job completion."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")

        # Simulate job completion in background
        async def complete_job():
            await asyncio.sleep(0.1)
            orchestrator._jobs[job_id].status = PipelineStatus.COMPLETED

        asyncio.create_task(complete_job())

        result = await orchestrator.wait_for_job(job_id, timeout_seconds=1.0)

        assert result is not None
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_wait_for_job_timeout(self, orchestrator):
        """Test waiting for job times out."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")

        with pytest.raises(TimeoutError):
            await orchestrator.wait_for_job(job_id, timeout_seconds=0.1)

    @pytest.mark.asyncio
    async def test_wait_for_job_not_found(self, orchestrator):
        """Test waiting for non-existent job."""
        with pytest.raises(ValueError):
            await orchestrator.wait_for_job("non-existent-job")

    @pytest.mark.asyncio
    async def test_run_live_pipeline_no_webcam_manager(self, orchestrator):
        """Test run_live_pipeline without webcam manager."""
        orchestrator.webcam_manager = None

        with pytest.raises(ValueError, match="WebcamManager not configured"):
            await orchestrator.run_live_pipeline(camera_id="cam-001")

    @pytest.mark.asyncio
    async def test_run_live_pipeline_camera_not_found(self, orchestrator, mock_dependencies):
        """Test run_live_pipeline with unknown camera."""
        mock_dependencies["webcam_manager"].get_all_sources = MagicMock(return_value=[])
        orchestrator.webcam_manager = mock_dependencies["webcam_manager"]
        orchestrator._running = True

        result = await orchestrator.run_live_pipeline(
            camera_id="unknown",
            duration_hours=0.001,
            chunk_interval=1,
        )

        assert "errors" in result

    @pytest.mark.asyncio
    async def test_run_historical_pipeline_no_ingestor(self, orchestrator):
        """Test run_historical_pipeline without historical ingestor."""
        orchestrator.historical_ingestor = None

        with pytest.raises(ValueError, match="HistoricalIngestor not configured"):
            await orchestrator.run_historical_pipeline(directories=["/videos"])

    @pytest.mark.asyncio
    async def test_run_historical_pipeline(self, orchestrator, mock_dependencies):
        """Test running historical pipeline."""
        # Mock scan result
        mock_scan_result = MagicMock()
        mock_scan_result.found = ["/videos/test1.mp4", "/videos/test2.mp4"]

        mock_dependencies["historical_ingestor"].scan_directory = MagicMock(
            return_value=mock_scan_result
        )
        mock_dependencies["historical_ingestor"].ingest_video = MagicMock(return_value={
            "success": True,
            "data": {"local_path": "/videos/test.mp4"},
        })

        orchestrator.historical_ingestor = mock_dependencies["historical_ingestor"]

        result = await orchestrator.run_historical_pipeline(
            directories=["/videos"],
            recursive=True,
        )

        assert isinstance(result, dict)
        assert "jobs" in result
        assert "stats" in result

    @pytest.mark.asyncio
    async def test_run_historical_pipeline_scan_error(self, orchestrator, mock_dependencies):
        """Test historical pipeline with scan error."""
        mock_dependencies["historical_ingestor"].scan_directory = MagicMock(
            side_effect=RuntimeError("Scan failed")
        )
        orchestrator.historical_ingestor = mock_dependencies["historical_ingestor"]

        result = await orchestrator.run_historical_pipeline(
            directories=["/nonexistent"],
            recursive=True,
        )

        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_run_youtube_pipeline(self, orchestrator):
        """Test running YouTube pipeline."""
        # Mock yt_dlp import
        mock_ytdlp = MagicMock()
        mock_ydl_class = MagicMock()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=None)
        mock_ydl.extract_info = MagicMock(return_value={"id": "test123"})
        mock_ydl.prepare_filename = MagicMock(return_value="/tmp/test.mp4")
        mock_ydl_class.return_value = mock_ydl
        mock_ytdlp.YoutubeDL = mock_ydl_class

        with patch.dict("sys.modules", {"yt_dlp": mock_ytdlp}):
            # Mock Path.exists
            with patch("pathlib.Path.exists", return_value=True):
                result = await orchestrator.run_youtube_pipeline(
                    youtube_url="https://youtube.com/watch?v=test",
                )

                assert isinstance(result, dict)
                assert "jobs" in result

    def test_stage_results_storage(self, orchestrator):
        """Test that stage results are stored."""
        job = PipelineJob(
            job_id="test-job",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )

        job.stage_results["acquisition"] = {"local_path": "/videos/test.mp4"}

        assert "acquisition" in job.stage_results
        assert job.stage_results["acquisition"]["local_path"] == "/videos/test.mp4"

    def test_error_message_storage(self, orchestrator):
        """Test that error messages are stored."""
        job = PipelineJob(
            job_id="test-job",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.FAILED,
            error_message="Test error message",
        )

        assert "Test error message" in job.error_message
        assert job.status == PipelineStatus.FAILED

    def test_retry_count(self, orchestrator):
        """Test retry count tracking."""
        job = PipelineJob(
            job_id="test-job",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.RUNNING,
        )

        assert job.retry_count == 0
        job.retry_count = 1
        assert job.retry_count == 1

    def test_cancel_flag(self, orchestrator):
        """Test cancel flag."""
        job = PipelineJob(
            job_id="test-job",
            source_path="/videos/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.RUNNING,
        )

        assert job.cancel_flag is False
        job.cancel_flag = True
        assert job.cancel_flag is True

    @pytest.mark.asyncio
    async def test_jobs_are_queued(self, orchestrator):
        """Test that submitted jobs are queued."""
        job_id = await orchestrator.submit_job("/videos/test.mp4", "local")

        # Job should be in queue
        assert not orchestrator._job_queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_jobs_submitted(self, orchestrator):
        """Test submitting multiple jobs."""
        job_ids = []
        for i in range(3):
            job_id = await orchestrator.submit_job(f"/videos/test{i}.mp4", "local")
            job_ids.append(job_id)

        assert len(job_ids) == 3
        assert len(orchestrator._jobs) == 3

    def test_job_initialization_values(self, orchestrator):
        """Test job initialization values."""
        job = PipelineJob(
            job_id="test",
            source_path="/test.mp4",
            source_type="local",
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
        )

        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_message is None
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.cancel_flag is False
        assert isinstance(job.stage_results, dict)
        assert isinstance(job.metadata, dict)
