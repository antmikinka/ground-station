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

"""Chemtrail pipeline control handlers.

Provides Socket.IO event handlers for managing the chemtrail detection
pipeline: starting/stopping live processing, submitting jobs, monitoring
progress, and configuring pipeline parameters.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from db import AsyncSessionLocal
from common.common import logger

# Global pipeline orchestrator instance (set during app startup)
_pipeline_orchestrator = None
_pipeline_running = False


def set_pipeline_orchestrator(orchestrator) -> None:
    """Set the global pipeline orchestrator instance."""
    global _pipeline_orchestrator
    _pipeline_orchestrator = orchestrator


def get_pipeline_orchestrator():
    """Get the global pipeline orchestrator instance."""
    return _pipeline_orchestrator


def is_pipeline_running() -> bool:
    """Check if the pipeline is currently running."""
    return _pipeline_running


def set_pipeline_running(value: bool) -> None:
    """Set the pipeline running state."""
    global _pipeline_running
    _pipeline_running = value


# ==================== Pipeline Status & Stats ====================


async def get_pipeline_status(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get status of all pipeline jobs."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        jobs = orchestrator.get_all_jobs_status()
        running = is_pipeline_running()

        return {
            "success": True,
            "data": {
                "jobs": jobs,
                "pipeline_running": running,
            }
        }
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return {"success": False, "error": str(e)}


async def get_pipeline_stats(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get aggregate pipeline statistics."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        jobs = orchestrator.get_all_jobs_status()
        total = len(jobs)
        completed = sum(1 for j in jobs if j["status"] == "completed")
        failed = sum(1 for j in jobs if j["status"] == "failed")
        running = sum(1 for j in jobs if j["status"] == "running")
        pending = sum(1 for j in jobs if j["status"] == "pending")
        cancelled = sum(1 for j in jobs if j["status"] == "cancelled")

        # Count total detections from completed jobs
        total_detections = 0
        for job in jobs:
            job_status = orchestrator._jobs.get(job["job_id"])
            if job_status and "archival" in job_status.stage_results:
                arch = job_status.stage_results["archival"]
                total_detections += arch.get("detection_count", 0)

        success_rate = round((completed / total * 100) if total > 0 else 0)

        return {
            "success": True,
            "data": {
                "total_jobs": total,
                "completed_jobs": completed,
                "failed_jobs": failed,
                "running_jobs": running,
                "pending_jobs": pending,
                "cancelled_jobs": cancelled,
                "total_detections": total_detections,
                "success_rate": success_rate,
            }
        }
    except Exception as e:
        logger.error(f"Error getting pipeline stats: {e}")
        return {"success": False, "error": str(e)}


# ==================== Live Pipeline Control ====================


async def start_live_pipeline(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Start live webcam processing pipeline."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        if is_pipeline_running():
            return {"success": False, "error": "Live pipeline is already running"}

        camera_id = data.get("camera_id") if data else None
        if not camera_id:
            return {"success": False, "error": "camera_id is required"}

        duration_hours = float(data.get("duration_hours", 1)) if data else 1
        chunk_interval = int(data.get("chunk_interval", 30)) if data else 30
        skip_still = bool(data.get("skip_still", True)) if data else True
        apply_overlay = bool(data.get("apply_overlay", False)) if data else False

        set_pipeline_running(True)

        # Emit pipeline started event
        await sio.emit("chemtrail:pipeline-started", {
            "camera_id": camera_id,
            "duration_hours": duration_hours,
        })

        # Run live pipeline in background
        async def _run_live():
            try:
                results = await orchestrator.run_live_pipeline(
                    camera_id=camera_id,
                    duration_hours=duration_hours,
                    chunk_interval=chunk_interval,
                    skip_still=skip_still,
                    apply_overlay=apply_overlay,
                )
                set_pipeline_running(False)
                await sio.emit("chemtrail:pipeline-stopped", {
                    "camera_id": camera_id,
                    "jobs_submitted": len(results.get("jobs", [])),
                    "errors": len(results.get("errors", [])),
                })
                logger.info(f"Live pipeline completed: {results}")
            except Exception as e:
                set_pipeline_running(False)
                await sio.emit("chemtrail:pipeline-stopped", {
                    "camera_id": camera_id,
                    "error": str(e),
                })
                logger.error(f"Live pipeline error: {e}")

        asyncio.create_task(_run_live())

        return {
            "success": True,
            "data": {
                "camera_id": camera_id,
                "duration_hours": duration_hours,
                "chunk_interval": chunk_interval,
            }
        }
    except Exception as e:
        set_pipeline_running(False)
        logger.error(f"Error starting live pipeline: {e}")
        return {"success": False, "error": str(e)}


async def stop_live_pipeline(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Stop live webcam processing pipeline."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        if not is_pipeline_running():
            return {"success": False, "error": "Live pipeline is not running"}

        # Cancel all pending jobs
        for job in orchestrator._jobs.values():
            if job.status.value == "pending":
                job.cancel_flag = True

        # Stop the orchestrator workers
        await orchestrator.stop()

        set_pipeline_running(False)

        await sio.emit("chemtrail:pipeline-stopped", {"reason": "user_stopped"})

        return {"success": True, "data": {"message": "Live pipeline stopped"}}
    except Exception as e:
        logger.error(f"Error stopping live pipeline: {e}")
        return {"success": False, "error": str(e)}


# ==================== Job Submission ====================


async def submit_local_job(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Submit a local video file for processing."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        source_path = data.get("source_path") if data else None
        if not source_path:
            return {"success": False, "error": "source_path is required"}

        # Validate file exists
        file_path = Path(source_path)
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {source_path}"}

        metadata = data.get("metadata", {}) if data else {}

        job_id = await orchestrator.submit_job(
            source_path=source_path,
            source_type="local",
            metadata=metadata,
        )

        # Emit job submitted event
        await sio.emit("chemtrail:job-submitted", {
            "job_id": job_id,
            "source_path": source_path,
            "source_type": "local",
        })

        return {"success": True, "data": {"job_id": job_id}}
    except Exception as e:
        logger.error(f"Error submitting local job: {e}")
        return {"success": False, "error": str(e)}


async def submit_youtube_job(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Submit a YouTube video URL for processing."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        youtube_url = data.get("youtube_url") if data else None
        if not youtube_url:
            return {"success": False, "error": "youtube_url is required"}

        # Run YouTube pipeline in background (can take long to download)
        async def _run_youtube():
            try:
                results = await orchestrator.run_youtube_pipeline(youtube_url=youtube_url)
                if results.get("jobs"):
                    await sio.emit("chemtrail:job-submitted", {
                        "job_id": results["jobs"][0],
                        "source_path": youtube_url,
                        "source_type": "youtube",
                    })
                logger.info(f"YouTube pipeline completed: {results}")
            except Exception as e:
                logger.error(f"YouTube pipeline error: {e}")

        asyncio.create_task(_run_youtube())

        return {
            "success": True,
            "data": {"message": "YouTube job submitted, processing in background"}
        }
    except Exception as e:
        logger.error(f"Error submitting YouTube job: {e}")
        return {"success": False, "error": str(e)}


async def cancel_pipeline_job(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Cancel a running or pending pipeline job."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        job_id = data.get("job_id") if data else None
        if not job_id:
            return {"success": False, "error": "job_id is required"}

        result = await orchestrator.cancel_pipeline(job_id)
        if not result:
            return {"success": False, "error": f"Job {job_id} not found or already completed"}

        await sio.emit("chemtrail:job-cancelled", {"job_id": job_id})

        return {"success": True, "data": {"job_id": job_id, "message": "Job cancelled"}}
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        return {"success": False, "error": str(e)}


# ==================== Pipeline Configuration ====================


async def get_pipeline_config(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get current pipeline configuration."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        config = orchestrator.config
        timeouts = {k.value: v for k, v in config.stage_timeout_seconds.items()}

        return {
            "success": True,
            "data": {
                "max_concurrent_jobs": config.max_concurrent_jobs,
                "stage_timeouts": timeouts,
                "enable_weather_enrichment": config.enable_weather_enrichment,
                "enable_quality_scoring": config.enable_quality_scoring,
                "skip_still_frames": config.skip_still_frames,
                "apply_overlay": config.apply_overlay,
                "chunk_duration_seconds": config.chunk_duration_seconds,
                "chunk_overlap_seconds": config.chunk_overlap_seconds,
            }
        }
    except Exception as e:
        logger.error(f"Error getting pipeline config: {e}")
        return {"success": False, "error": str(e)}


async def update_pipeline_config(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Update pipeline configuration."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        if data:
            if "max_concurrent_jobs" in data:
                orchestrator.config.max_concurrent_jobs = int(data["max_concurrent_jobs"])
            if "enable_weather_enrichment" in data:
                orchestrator.config.enable_weather_enrichment = bool(data["enable_weather_enrichment"])
            if "enable_quality_scoring" in data:
                orchestrator.config.enable_quality_scoring = bool(data["enable_quality_scoring"])
            if "skip_still_frames" in data:
                orchestrator.config.skip_still_frames = bool(data["skip_still_frames"])
            if "apply_overlay" in data:
                orchestrator.config.apply_overlay = bool(data["apply_overlay"])
            if "chunk_duration_seconds" in data:
                orchestrator.config.chunk_duration_seconds = int(data["chunk_duration_seconds"])
            if "chunk_overlap_seconds" in data:
                orchestrator.config.chunk_overlap_seconds = int(data["chunk_overlap_seconds"])

        return {"success": True, "data": {"message": "Configuration updated"}}
    except Exception as e:
        logger.error(f"Error updating pipeline config: {e}")
        return {"success": False, "error": str(e)}


# ==================== Video Catalog & Historical ====================


async def get_video_catalog(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Get catalog of processed videos."""
    try:
        from sqlalchemy import select
        from db.models import VideoCatalog as VideoCatalogModel

        async with AsyncSessionLocal() as dbsession:
            limit = data.get("limit", 100) if data else 100
            offset = data.get("offset", 0) if data else 0

            stmt = select(VideoCatalogModel).order_by(
                VideoCatalogModel.created_at.desc()
            ).offset(offset).limit(limit)
            result = await dbsession.execute(stmt)
            entries = result.scalars().all()

            catalog = []
            for entry in entries:
                catalog.append({
                    "id": entry.id,
                    "source_type": entry.source_type,
                    "source_url": entry.source_url,
                    "local_path": entry.local_path,
                    "camera_id": entry.camera_id,
                    "camera_name": entry.camera_name,
                    "latitude": entry.latitude,
                    "longitude": entry.longitude,
                    "duration_seconds": entry.duration_seconds,
                    "resolution": entry.resolution,
                    "file_size_bytes": entry.file_size_bytes,
                    "quality_score": entry.quality_score,
                    "processing_status": entry.processing_status,
                    "chunk_count": entry.chunk_count,
                    "detection_count": entry.detection_count,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                })

            return {"success": True, "data": catalog}
    except Exception as e:
        logger.error(f"Error getting video catalog: {e}")
        return {"success": False, "error": str(e)}


async def start_historical_scan(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """Scan a directory for videos and submit for processing."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        directory = data.get("directory") if data else None
        if not directory:
            return {"success": False, "error": "directory is required"}

        dir_path = Path(directory)
        if not dir_path.is_dir():
            return {"success": False, "error": f"Directory not found: {directory}"}

        recursive = bool(data.get("recursive", True)) if data else True

        # Run historical scan in background
        async def _run_historical():
            try:
                results = await orchestrator.run_historical_pipeline(
                    directories=[directory],
                    recursive=recursive,
                )
                await sio.emit("chemtrail:historical-scan-complete", {
                    "directory": directory,
                    "jobs_submitted": len(results.get("jobs", [])),
                    "errors": len(results.get("errors", [])),
                })
                logger.info(f"Historical scan completed: {results}")
            except Exception as e:
                logger.error(f"Historical scan error: {e}")

        asyncio.create_task(_run_historical())

        return {
            "success": True,
            "data": {"message": f"Scanning {directory} for videos..."}
        }
    except Exception as e:
        logger.error(f"Error starting historical scan: {e}")
        return {"success": False, "error": str(e)}


# ==================== Webcam Sources ====================


async def get_webcam_sources(
    sio: Any,
    data: Optional[Dict],
    logger: Any,
    sid: str
) -> Dict[str, Any]:
    """List available webcam sources."""
    try:
        orchestrator = get_pipeline_orchestrator()
        if not orchestrator:
            return {"success": False, "error": "Pipeline orchestrator not initialized"}

        webcam_manager = orchestrator.webcam_manager
        if not webcam_manager:
            return {"success": False, "error": "Webcam manager not configured"}

        sources = webcam_manager.get_all_sources()
        sources_data = []
        for source in sources:
            sources_data.append({
                "id": source.id,
                "name": source.name,
                "url": source.url,
                "status": source.status if hasattr(source, "status") else "unknown",
            })

        return {"success": True, "data": sources_data}
    except Exception as e:
        logger.error(f"Error getting webcam sources: {e}")
        return {"success": False, "error": str(e)}


# ==================== Registration ====================


def register_handlers(registry):
    """Register all pipeline control handlers with the Socket.IO registry."""
    registry.register_batch({
        # Status & Stats
        "get-pipeline-status": (get_pipeline_status, "data_request"),
        "get-pipeline-stats": (get_pipeline_stats, "data_request"),

        # Live Pipeline Control
        "start-live-pipeline": (start_live_pipeline, "data_submission"),
        "stop-live-pipeline": (stop_live_pipeline, "data_submission"),

        # Job Submission
        "submit-local-job": (submit_local_job, "data_submission"),
        "submit-youtube-job": (submit_youtube_job, "data_submission"),
        "cancel-pipeline-job": (cancel_pipeline_job, "data_submission"),

        # Configuration
        "get-pipeline-config": (get_pipeline_config, "data_request"),
        "update-pipeline-config": (update_pipeline_config, "data_submission"),

        # Video Catalog & Historical
        "get-video-catalog": (get_video_catalog, "data_request"),
        "start-historical-scan": (start_historical_scan, "data_submission"),

        # Webcam Sources
        "get-webcam-sources": (get_webcam_sources, "data_request"),
    })

    logger.info("Registered chemtrail pipeline control handlers")
