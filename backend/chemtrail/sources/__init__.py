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

"""Chemtrail sources module - Phase 2 footage acquisition and orchestration.

This package provides:
- Live webcam feed acquisition (RTSP/MJPEG/HLS)
- Historical video ingestion and cataloging
- Video sorting by location, weather, and quality
- End-to-end pipeline orchestration
- Weather enrichment from Open-Meteo API
"""

from .webcam_manager import (
    WebcamManager,
    WebcamSource,
    StreamType,
)

from .historical_ingestor import (
    HistoricalIngestor,
    VideoScanner,
    MetadataExtractor,
)

from .video_catalog import (
    VideoCatalog,
)

from .weather_service import (
    WeatherService,
)

from .pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineStage,
    PipelineStatus,
)

__all__ = [
    # Webcam Manager
    "WebcamManager",
    "WebcamSource",
    "StreamType",
    # Historical Ingestor
    "HistoricalIngestor",
    "VideoScanner",
    "MetadataExtractor",
    # Video Catalog
    "VideoCatalog",
    # Weather Service
    "WeatherService",
    # Pipeline Orchestrator
    "PipelineOrchestrator",
    "PipelineConfig",
    "PipelineStage",
    "PipelineStatus",
]
