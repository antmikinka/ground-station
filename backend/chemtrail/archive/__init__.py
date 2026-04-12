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

"""Chemtrail archive modules - SentrySearch integration.

This package provides video chunking, embedding, vector storage,
semantic search, and telemetry overlay capabilities for the
Chemtrail Webcam Tracker.
"""

from .base_embedder import BaseEmbedder
from .embedder import (
    embed_query,
    embed_video_chunk,
    get_embedder,
    reset_embedder,
    GeminiAPIKeyError,
    GeminiQuotaError,
)
from .gemini_embedder import GeminiEmbedder
from .chunker import (
    chunk_video,
    is_still_frame_chunk,
    is_still_frame_sequence,
    preprocess_chunk,
    scan_directory,
    SUPPORTED_VIDEO_EXTENSIONS,
)
from .vector_store import (
    ChemtrailVectorStore,
    detect_backend,
    detect_index,
    BackendMismatchError,
)
from .searcher import search_detections, search_footage
from .telemetry_overlay import (
    apply_flight_overlay,
    build_hud_overlay,
    get_flight_metadata,
    reverse_geocode,
)

__all__ = [
    # Embedder
    "BaseEmbedder",
    "GeminiEmbedder",
    "get_embedder",
    "reset_embedder",
    "embed_query",
    "embed_video_chunk",
    "GeminiAPIKeyError",
    "GeminiQuotaError",
    # Chunker
    "chunk_video",
    "is_still_frame_chunk",
    "is_still_frame_sequence",
    "preprocess_chunk",
    "scan_directory",
    "SUPPORTED_VIDEO_EXTENSIONS",
    # Vector Store
    "ChemtrailVectorStore",
    "detect_backend",
    "detect_index",
    "BackendMismatchError",
    # Search
    "search_detections",
    "search_footage",
    # Overlay
    "apply_flight_overlay",
    "build_hud_overlay",
    "get_flight_metadata",
    "reverse_geocode",
]
