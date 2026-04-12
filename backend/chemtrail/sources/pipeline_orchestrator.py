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

"""Pipeline Orchestrator - End-to-End Workflow Coordination.

Responsibilities:
1. Coordinate acquisition -> sorting -> detection -> archive pipeline
2. Manage processing queues and priorities
3. Handle errors and retries
4. Track progress and generate reports
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from common.common import logger

if TYPE_CHECKING:
    from .video_catalog import VideoCatalog
    from .webcam_manager import WebcamManager
    from .historical_ingestor import HistoricalIngestor
    from .weather_service import WeatherService
    from ..archive.detection_service import DetectionService
    from ..archive.chunker import chunk_video


class PipelineStage(Enum):
    """Pipeline processing stages."""
    ACQUISITION = "acquisition"
    SORTING = "sorting"
    WEATHER_ENRICHMENT = "weather_enrichment"
    QUALITY_SCORING = "quality_scoring"
    CHUNKING = "chunking"
    DETECTION = "detection"
    ARCHIVAL = "archival"
    COMPLETE = "complete"


class PipelineStatus(Enum):
    """Pipeline job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class PipelineJob:
    """Represents a video processing job."""
    job_id: str
    source_path: str
    source_type: str  # webcam, local, youtube
    current_stage: PipelineStage
    status: PipelineStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    stage_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cancel_flag: bool = False


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    max_concurrent_jobs: int = 5
    stage_timeout_seconds: Dict[PipelineStage, int] = field(default_factory=lambda: {
        PipelineStage.ACQUISITION: 300,
        PipelineStage.SORTING: 60,
        PipelineStage.WEATHER_ENRICHMENT: 120,
        PipelineStage.QUALITY_SCORING: 120,
        PipelineStage.CHUNKING: 600,
        PipelineStage.DETECTION: 1800,
        PipelineStage.ARCHIVAL: 300,
    })
    enable_weather_enrichment: bool = True
    enable_quality_scoring: bool = True
    skip_still_frames: bool = True
    apply_overlay: bool = False
    chunk_duration_seconds: int = 30
    chunk_overlap_seconds: int = 5


class PipelineOrchestrator:
    """
    Orchestrates end-to-end video processing pipeline.

    Usage:
        orchestrator = PipelineOrchestrator(
            session=session,
            webcam_manager=webcam_manager,
            historical_ingestor=historical_ingestor,
            video_catalog=video_catalog,
            detection_service=detection_service,
            weather_service=weather_service,
            config=config,
        )
        await orchestrator.start()

        # Submit job
        job_id = await orchestrator.submit_job(video_path)

        # Check status
        status = await orchestrator.get_pipeline_status(job_id)

        # Wait for completion
        await orchestrator.wait_for_job(job_id)
    """

    def __init__(
        self,
        session: Any,
        webcam_manager: Optional["WebcamManager"] = None,
        historical_ingestor: Optional["HistoricalIngestor"] = None,
        video_catalog: Optional["VideoCatalog"] = None,
        detection_service: Optional["DetectionService"] = None,
        weather_service: Optional["WeatherService"] = None,
        config: Optional[PipelineConfig] = None,
    ):
        self.session = session
        self.webcam_manager = webcam_manager
        self.historical_ingestor = historical_ingestor
        self.video_catalog = video_catalog
        self.detection_service = detection_service
        self.weather_service = weather_service
        self.config = config or PipelineConfig()

        self._jobs: Dict[str, PipelineJob] = {}
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._pipeline_counter = 0

    async def start(self) -> None:
        """Start pipeline processing with worker pool."""
        self._running = True

        # Start worker tasks
        for i in range(self.config.max_concurrent_jobs):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Pipeline started with {self.config.max_concurrent_jobs} workers")

    async def stop(self) -> None:
        """Stop pipeline processing."""
        self._running = False

        # Cancel flag for all pending jobs
        for job in self._jobs.values():
            if job.status == PipelineStatus.PENDING:
                job.cancel_flag = True

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Pipeline stopped")

    async def submit_job(
        self,
        source_path: str,
        source_type: str = "local",
        priority: int = 0,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Submit a new processing job.

        Args:
            source_path: Path to source video or stream URL
            source_type: Type of source (webcam, local, youtube)
            priority: Job priority (lower = higher priority)
            metadata: Optional metadata overrides

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())

        job = PipelineJob(
            job_id=job_id,
            source_path=source_path,
            source_type=source_type,
            current_stage=PipelineStage.ACQUISITION,
            status=PipelineStatus.PENDING,
            metadata=metadata or {},
        )

        self._jobs[job_id] = job
        await self._job_queue.put((priority, job_id))
        logger.info(f"Submitted job {job_id} for {source_path}")

        return job_id

    async def get_pipeline_status(self, job_id: str) -> Optional[Dict]:
        """Get current job status."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "source_path": job.source_path,
            "source_type": job.source_type,
            "current_stage": job.current_stage.value,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
            "retry_count": job.retry_count,
            "stage_results": job.stage_results,
        }

    async def cancel_pipeline(self, job_id: str) -> bool:
        """Cancel a running or pending job."""
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED):
            return False

        job.cancel_flag = True
        job.status = PipelineStatus.CANCELLED
        logger.info(f"Cancelled job {job_id}")
        return True

    async def wait_for_job(
        self,
        job_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> Dict:
        """Wait for job completion.

        Args:
            job_id: Job identifier
            timeout_seconds: Optional timeout

        Raises:
            TimeoutError: If timeout expires before completion
            ValueError: If job not found
        """
        start_time = datetime.now(timezone.utc)

        while True:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED):
                return await self.get_pipeline_status(job_id)

            if timeout_seconds:
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    raise TimeoutError(f"Job {job_id} timed out after {timeout_seconds}s")

            await asyncio.sleep(1)

    # ==================== Pipeline Orchestration ====================

    async def run_live_pipeline(
        self,
        camera_id: str,
        duration_hours: float = 1,
        chunk_interval: int = 30,
        skip_still: bool = True,
        apply_overlay: bool = False,
    ) -> Dict:
        """Run live webcam pipeline continuously.

        Args:
            camera_id: Camera identifier
            duration_hours: How long to run in hours
            chunk_interval: Seconds between captures
            skip_still: Skip still-frame chunks
            apply_overlay: Apply flight telemetry overlay

        Returns:
            Pipeline results summary
        """
        if not self.webcam_manager:
            raise ValueError("WebcamManager not configured")

        end_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        results = {"jobs": [], "errors": []}

        logger.info(f"Starting live pipeline for {camera_id}")

        while datetime.now(timezone.utc) < end_time and self._running:
            try:
                # Capture segment
                source = self.webcam_manager.get_all_sources()
                source = next((s for s in source if s.id == camera_id), None)

                if not source:
                    logger.error(f"Camera {camera_id} not found")
                    await asyncio.sleep(chunk_interval)
                    continue

                segment_result = await self.webcam_manager.capture_segment(
                    source=source,
                    duration=chunk_interval,
                )

                if not segment_result:
                    logger.error(f"Failed to capture segment for {camera_id}")
                    await asyncio.sleep(chunk_interval)
                    continue

                # Submit for processing
                job_id = await self.submit_job(
                    source_path=segment_result["segment_path"],
                    source_type="webcam",
                    metadata={"camera_id": camera_id},
                )

                results["jobs"].append(job_id)

                await asyncio.sleep(chunk_interval)

            except Exception as e:
                logger.error(f"Live pipeline error: {e}")
                results["errors"].append(str(e))
                await asyncio.sleep(chunk_interval)

        return results

    async def run_historical_pipeline(
        self,
        directories: List[str],
        recursive: bool = True,
    ) -> Dict:
        """Run pipeline on historical video directories.

        Args:
            directories: List of directories to scan
            recursive: Whether to scan recursively

        Returns:
            Pipeline results summary
        """
        if not self.historical_ingestor:
            raise ValueError("HistoricalIngestor not configured")

        results = {"jobs": [], "errors": [], "stats": {}}

        logger.info(f"Starting historical pipeline for {directories}")

        # Scan directories
        all_videos = []
        for directory in directories:
            try:
                scan_result = self.historical_ingestor.scan_directory(directory, recursive)
                all_videos.extend(scan_result.found)
            except Exception as e:
                logger.error(f"Error scanning {directory}: {e}")
                results["errors"].append(f"Scan error: {e}")

        results["stats"]["total_videos"] = len(all_videos)

        # Ingest and submit for processing
        for video_path in all_videos:
            try:
                # Ingest video
                ingest_result = self.historical_ingestor.ingest_video(video_path)

                if not ingest_result["success"]:
                    results["errors"].append(f"Ingest failed: {video_path}")
                    continue

                # Submit for processing
                job_id = await self.submit_job(
                    source_path=video_path,
                    source_type="local",
                    metadata=ingest_result["data"],
                )

                results["jobs"].append(job_id)

            except Exception as e:
                logger.error(f"Error processing {video_path}: {e}")
                results["errors"].append(f"Processing error: {e}")

        results["stats"]["submitted_jobs"] = len(results["jobs"])

        return results

    async def run_youtube_pipeline(
        self,
        youtube_url: str,
    ) -> Dict:
        """Run pipeline on YouTube video.

        Args:
            youtube_url: YouTube video or stream URL

        Returns:
            Pipeline results summary
        """
        import yt_dlp
        import tempfile

        results = {"jobs": [], "errors": []}

        logger.info(f"Starting YouTube pipeline for {youtube_url}")

        try:
            # Download video
            output_dir = Path(tempfile.mkdtemp(prefix="chemtrail_youtube_"))
            output_pattern = str(output_dir / "%(id)s.%(ext)s")

            ydl_opts = {
                "format": "best[height<=720]",
                "outtmpl": output_pattern,
                "noplaylist": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_path = ydl.prepare_filename(info)

            # Submit for processing
            job_id = await self.submit_job(
                source_path=video_path,
                source_type="youtube",
                metadata={
                    "youtube_id": info.get("id"),
                    "youtube_title": info.get("title"),
                    "youtube_url": youtube_url,
                },
            )

            results["jobs"].append(job_id)

        except Exception as e:
            logger.error(f"YouTube pipeline error: {e}")
            results["errors"].append(str(e))

        return results

    # ==================== Worker Implementation ====================

    async def _worker(self, worker_id: int) -> None:
        """Worker task that processes jobs from queue."""
        logger.info(f"Worker {worker_id} started")

        while self._running:
            try:
                # Get job from queue
                priority, job_id = await self._job_queue.get()
                job = self._jobs[job_id]

                # Check cancel flag
                if job.cancel_flag:
                    logger.info(f"Job {job_id} was cancelled")
                    continue

                # Process job through all stages
                job.status = PipelineStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)

                await self._process_job(job)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

    async def _process_job(self, job: PipelineJob) -> None:
        """Process job through all pipeline stages."""
        stages = [
            PipelineStage.ACQUISITION,
            PipelineStage.SORTING,
            PipelineStage.WEATHER_ENRICHMENT,
            PipelineStage.QUALITY_SCORING,
            PipelineStage.CHUNKING,
            PipelineStage.DETECTION,
            PipelineStage.ARCHIVAL,
        ]

        for stage in stages:
            if job.cancel_flag:
                job.status = PipelineStatus.CANCELLED
                job.error_message = "Job cancelled by user"
                return

            job.current_stage = stage

            try:
                timeout = self.config.stage_timeout_seconds.get(stage, 300)
                await asyncio.wait_for(
                    self._execute_stage(job, stage),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                job.error_message = f"Stage {stage.value} timed out after {timeout}s"
                job.status = PipelineStatus.FAILED
                logger.error(f"Job {job.job_id} failed at {stage.value}: timeout")
                return
            except Exception as e:
                logger.error(f"Stage {stage.value} failed: {e}", exc_info=True)

                # Retry logic
                job.retry_count += 1
                if job.retry_count < job.max_retries:
                    logger.info(
                        f"Retrying stage {stage.value} ({job.retry_count}/{job.max_retries})"
                    )
                    job.current_stage = stage
                    continue
                else:
                    job.error_message = str(e)
                    job.status = PipelineStatus.FAILED
                    logger.error(f"Job {job.job_id} failed after {job.retry_count} retries")
                    return

        # All stages complete
        job.status = PipelineStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        logger.info(f"Job {job.job_id} completed successfully")

    async def _execute_stage(
        self,
        job: PipelineJob,
        stage: PipelineStage,
    ) -> None:
        """Execute a single pipeline stage."""

        if stage == PipelineStage.ACQUISITION:
            job.stage_results["acquisition"] = await self._acquire_video(job)

        elif stage == PipelineStage.SORTING:
            job.stage_results["sorting"] = await self._sort_video(job)

        elif stage == PipelineStage.WEATHER_ENRICHMENT:
            if self.config.enable_weather_enrichment and self.weather_service:
                job.stage_results["weather"] = await self._enrich_weather(job)

        elif stage == PipelineStage.QUALITY_SCORING:
            if self.config.enable_quality_scoring:
                job.stage_results["quality"] = self._calculate_quality(job)

        elif stage == PipelineStage.CHUNKING:
            job.stage_results["chunks"] = self._chunk_video(job)

        elif stage == PipelineStage.DETECTION:
            if self.detection_service and "chunks" in job.stage_results:
                job.stage_results["detections"] = await self._run_detection(job)

        elif stage == PipelineStage.ARCHIVAL:
            job.stage_results["archival"] = await self._archive_results(job)

    async def _acquire_video(self, job: PipelineJob) -> Dict:
        """Acquire/import video into catalog."""
        if job.source_type == "local" and self.historical_ingestor:
            result = self.historical_ingestor.ingest_video(job.source_path)
            return result

        return {"success": True, "data": job.metadata}

    async def _sort_video(self, job: PipelineJob) -> Dict:
        """Sort and categorize video."""
        # Metadata already set during acquisition
        return {"sorted": True}

    async def _enrich_weather(self, job: PipelineJob) -> Dict:
        """Fetch weather data for video."""
        if not self.weather_service:
            return {}

        lat = job.metadata.get("latitude", 0)
        lon = job.metadata.get("longitude", 0)
        recorded_at = job.metadata.get("recorded_at", datetime.now(timezone.utc))

        if isinstance(recorded_at, str):
            recorded_at = datetime.fromisoformat(recorded_at)

        weather = self.weather_service.get_historical_weather(
            lat=lat,
            lon=lon,
            timestamp=recorded_at,
        )

        return weather

    def _calculate_quality(self, job: PipelineJob) -> Dict:
        """Calculate video quality score."""
        if not self.video_catalog:
            return {}

        resolution = job.metadata.get("resolution", "unknown")
        duration = job.metadata.get("duration_seconds", 0)
        file_size = job.metadata.get("file_size_bytes", 0)

        score = self.video_catalog.calculate_quality_score(
            resolution=resolution,
            duration=duration,
            file_size=file_size,
        )

        return {"overall_score": score}

    def _chunk_video(self, job: PipelineJob) -> List[Dict]:
        """Chunk video for processing."""
        from ..archive.chunker import chunk_video

        chunks = chunk_video(
            job.source_path,
            chunk_duration=self.config.chunk_duration_seconds,
            overlap=self.config.chunk_overlap_seconds,
        )

        logger.info(f"Chunked {job.source_path} into {len(chunks)} segments")
        return chunks

    async def _run_detection(self, job: PipelineJob) -> List[Dict]:
        """Run detection pipeline."""
        if not self.detection_service:
            return []

        chunks = job.stage_results["chunks"]

        # Get camera metadata
        camera_id = job.metadata.get("camera_id")
        camera_metadata = job.metadata.get("camera_metadata", {})

        results = await self.detection_service.process_detection_batch(
            chunks=chunks,
            camera_id=camera_id,
            camera_metadata=camera_metadata,
            skip_still_frames=self.config.skip_still_frames,
            apply_overlay=self.config.apply_overlay,
        )

        return results

    async def _archive_results(self, job: PipelineJob) -> Dict:
        """Archive detection results."""
        detections = job.stage_results.get("detections", [])
        return {
            "detection_count": len(detections),
            "archived": True,
        }

    def get_all_jobs_status(self) -> List[Dict]:
        """Get status of all jobs."""
        return [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "current_stage": job.current_stage.value,
                "created_at": job.created_at.isoformat(),
            }
            for job in self._jobs.values()
        ]
