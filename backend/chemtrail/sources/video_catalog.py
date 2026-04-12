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

"""Video Catalog - Sorting and Indexing.

Responsibilities:
1. Store video metadata in PostgreSQL
2. Create ChromaDB embeddings for semantic search
3. Sort and filter by camera, date, weather, quality
4. Manage video processing queue
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

import chromadb

from common.common import logger
from ..archive.vector_store import ChemtrailVectorStore

# ChromaDB collection name for video catalog
VIDEO_CATALOG_COLLECTION = "chemtrail_video_catalog"


class VideoCatalog:
    """
    Video catalog database operations.

    Usage:
        catalog = VideoCatalog(session, vector_store)
        await catalog.initialize()

        # Add video
        result = catalog.add_entry(metadata_dict)

        # Search with filters
        videos = catalog.search(
            date_from=datetime(2026, 4, 1),
            min_quality=70,
        )
    """

    def __init__(
        self,
        session: AsyncSession,
        vector_store: ChemtrailVectorStore,
    ):
        self.session = session
        self.vector_store = vector_store
        self._chroma_client: Optional[chromadb.Client] = None
        self._chroma_collection: Optional[chromadb.Collection] = None

    async def initialize(self) -> None:
        """Initialize ChromaDB connection."""
        # Get ChromaDB path from vector_store
        db_path = getattr(self.vector_store, '_db_path', None)

        if db_path:
            self._chroma_client = chromadb.PersistentClient(path=str(db_path))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=VIDEO_CATALOG_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Initialized ChromaDB video catalog")

    # ==================== CRUD Operations ====================

    def add_entry(self, metadata_dict: Dict[str, Any]) -> Dict:
        """Add video entry to PostgreSQL and ChromaDB.

        Args:
            metadata_dict: Video metadata with keys:
                - source_type, source_url, local_path
                - camera_id, camera_name
                - latitude, longitude, altitude
                - title, description
                - duration_seconds, resolution, codec, file_size_bytes
                - quality_score, quality_metrics
                - recorded_at, weather_data, tags

        Returns:
            Dict with success, data (record), error
        """
        try:
            from db.models import VideoCatalog as VideoCatalogModel
            import uuid

            # Generate ID if not provided
            record_id = metadata_dict.get("id", str(uuid.uuid4()))

            # Create SQLAlchemy model instance
            record = VideoCatalogModel(
                id=uuid.UUID(record_id),
                source_type=metadata_dict.get("source_type", "local"),
                source_url=metadata_dict.get("source_url"),
                local_path=metadata_dict.get("local_path"),
                camera_id=metadata_dict.get("camera_id"),
                camera_name=metadata_dict.get("camera_name"),
                latitude=metadata_dict.get("latitude", 0.0),
                longitude=metadata_dict.get("longitude", 0.0),
                altitude=metadata_dict.get("altitude", 0.0),
                title=metadata_dict.get("title"),
                description=metadata_dict.get("description"),
                duration_seconds=metadata_dict.get("duration_seconds", 0),
                resolution=metadata_dict.get("resolution", "unknown"),
                codec=metadata_dict.get("codec"),
                file_size_bytes=metadata_dict.get("file_size_bytes"),
                quality_score=metadata_dict.get("quality_score", 0.0),
                quality_metrics=metadata_dict.get("quality_metrics", {}),
                recorded_at=metadata_dict.get("recorded_at", datetime.now(timezone.utc)),
                ingested_at=datetime.now(timezone.utc),
                weather_data=metadata_dict.get("weather_data", {}),
                tags=metadata_dict.get("tags", []),
                checksum_sha256=metadata_dict.get("checksum_sha256"),
                processing_status=metadata_dict.get("processing_status", "pending"),
            )

            # Add to session (caller must commit)
            self.session.add(record)

            # Index in ChromaDB
            self.index_in_chromadb(record)

            logger.info(f"Added video catalog entry: {record_id}")

            return {
                "success": True,
                "data": self._record_to_dict(record),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error adding catalog entry: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
            }

    def search(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        camera_id: Optional[str] = None,
        min_quality: Optional[float] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search video catalog with filters.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            camera_id: Filter by camera ID
            min_quality: Minimum quality score (0-100)
            tags: Filter by tags
            limit: Maximum results

        Returns:
            List of video records
        """
        from db.models import VideoCatalog as VideoCatalogModel
        from sqlalchemy import select

        query = select(VideoCatalogModel)

        # Apply filters
        if date_from:
            query = query.where(VideoCatalogModel.recorded_at >= date_from)
        if date_to:
            query = query.where(VideoCatalogModel.recorded_at <= date_to)
        if camera_id:
            query = query.where(VideoCatalogModel.camera_id == camera_id)
        if min_quality is not None:
            query = query.where(VideoCatalogModel.quality_score >= min_quality)

        # Order by quality descending
        query = query.order_by(VideoCatalogModel.quality_score.desc())
        query = query.limit(limit)

        # Execute query
        result = self.session.execute(query)
        records = result.scalars().all()

        return [self._record_to_dict(record) for record in records]

    def search_by_location(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        limit: int = 50,
    ) -> List[Dict]:
        """Search videos near a location.

        Args:
            lat: Center latitude
            lon: Center longitude
            radius_km: Search radius in kilometers
            limit: Maximum results

        Returns:
            List of video records
        """
        from db.models import VideoCatalog as VideoCatalogModel
        from sqlalchemy import select
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1, lon1, lat2, lon2):
            r = 6371  # Earth radius in km
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            return 2 * asin(sqrt(a)) * r

        query = select(VideoCatalogModel)
        result = self.session.execute(query)
        records = result.scalars().all()

        # Filter by location in Python
        filtered = [
            record for record in records
            if haversine(lat, lon, record.latitude, record.longitude) <= radius_km
        ]

        # Sort by quality and limit
        filtered.sort(key=lambda r: r.quality_score, reverse=True)

        return [self._record_to_dict(record) for record in filtered[:limit]]

    def get_quality_distribution(self) -> Dict[str, int]:
        """Get distribution of videos by quality score."""
        from db.models import VideoCatalog as VideoCatalogModel
        from sqlalchemy import select, func
        from sqlalchemy import case

        # Create quality buckets
        quality_buckets = case(
            (VideoCatalogModel.quality_score >= 90, "excellent"),
            (VideoCatalogModel.quality_score >= 70, "good"),
            (VideoCatalogModel.quality_score >= 50, "fair"),
            (VideoCatalogModel.quality_score >= 30, "poor"),
            else_="very_poor",
        )

        query = select(
            quality_buckets.label("quality_tier"),
            func.count().label("count"),
        ).group_by(quality_buckets)

        result = self.session.execute(query)

        return {row.quality_tier: row.count for row in result}

    def get_stats(self) -> Dict[str, Any]:
        """Get catalog statistics."""
        from db.models import VideoCatalog as VideoCatalogModel
        from sqlalchemy import select, func

        # Total videos
        total_query = select(func.count()).select_from(VideoCatalogModel)
        total = self.session.execute(total_query).scalar()

        # Total duration
        duration_query = select(func.sum(VideoCatalogModel.duration_seconds))
        total_duration = self.session.execute(duration_query).scalar() or 0

        # Sources breakdown
        from sqlalchemy import distinct
        source_query = select(
            VideoCatalogModel.source_type,
            func.count().label("count"),
        ).group_by(VideoCatalogModel.source_type)

        source_result = self.session.execute(source_query)
        sources_breakdown = {row.source_type: row.count for row in source_result}

        return {
            "total_videos": total,
            "total_duration_seconds": total_duration,
            "total_duration_hours": round(total_duration / 3600, 2),
            "sources_breakdown": sources_breakdown,
        }

    # ==================== Quality Scoring ====================

    def calculate_quality_score(
        self,
        resolution: str,
        duration: float,
        file_size: int,
        metrics: Optional[Dict] = None,
    ) -> float:
        """Calculate overall quality score (0-100).

        Args:
            resolution: Resolution string (480p, 720p, 1080p, 4K)
            duration: Duration in seconds
            file_size: File size in bytes
            metrics: Optional additional metrics

        Returns:
            Quality score 0-100
        """
        # Resolution score (40 points max)
        resolution_scores = {
            "4K": 40,
            "1080p": 35,
            "720p": 25,
            "480p": 15,
            "unknown": 10,
        }
        res_score = resolution_scores.get(resolution, 10)

        # Duration score (20 points max)
        # Prefer videos between 30s and 10 minutes
        if 30 <= duration <= 600:
            duration_score = 20
        elif duration < 30:
            duration_score = max(5, 20 - (30 - duration))
        else:
            duration_score = max(10, 20 - (duration - 600) / 60)

        # Bitrate proxy score (20 points max)
        if duration > 0 and file_size > 0:
            bitrate_kbps = (file_size * 8) / (duration * 1000)
            if bitrate_kbps >= 2000:
                bitrate_score = 20
            elif bitrate_kbps >= 1000:
                bitrate_score = 15
            elif bitrate_kbps >= 500:
                bitrate_score = 10
            else:
                bitrate_score = 5
        else:
            bitrate_score = 10

        # Additional metrics (20 points max)
        metrics_score = 10  # Base score
        if metrics:
            if metrics.get("stability_score", 0) > 0.7:
                metrics_score += 5
            if metrics.get("lighting_score", 0) > 0.7:
                metrics_score += 5

        total = res_score + duration_score + bitrate_score + metrics_score
        return min(100, max(0, total))

    # ==================== Weather Enrichment ====================

    def enrich_weather(
        self,
        video_path: str,
        lat: float,
        lon: float,
        timestamp: datetime,
    ) -> Dict:
        """Fetch weather data for a video.

        Args:
            video_path: Path to video file
            lat: Video latitude
            lon: Video longitude
            timestamp: Video timestamp

        Returns:
            Weather data dict
        """
        from .weather_service import WeatherService

        weather_service = WeatherService()

        try:
            weather = weather_service.get_historical_weather(
                lat=lat,
                lon=lon,
                timestamp=timestamp,
            )

            logger.info(f"Enriched weather for {video_path}")
            return weather

        except Exception as e:
            logger.error(f"Error enriching weather for {video_path}: {e}")
            return {}

    # ==================== ChromaDB Integration ====================

    def index_in_chromadb(self, record: Any) -> None:
        """Add catalog entry to ChromaDB for semantic search.

        Args:
            record: VideoCatalog model instance
        """
        if not self._chroma_collection:
            logger.warning("ChromaDB not initialized")
            return

        try:
            # Create metadata for search
            metadata = {
                "source_type": record.source_type,
                "camera_id": str(record.camera_id) if record.camera_id else None,
                "camera_name": record.camera_name,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "altitude": record.altitude,
                "duration_seconds": record.duration_seconds,
                "resolution": record.resolution,
                "quality_score": record.quality_score,
                "recorded_at": record.recorded_at.isoformat(),
                "source_url": record.source_url,
                "local_path": record.local_path,
            }

            # Create simple embedding based on metadata
            # In production, use a proper embedding model
            embedding = self._create_metadata_embedding(metadata)

            # Add to ChromaDB
            self._chroma_collection.upsert(
                ids=[str(record.id)],
                embeddings=[embedding],
                metadatas=[metadata],
            )

            logger.debug(f"Indexed in ChromaDB: {record.id}")

        except Exception as e:
            logger.error(f"Error indexing in ChromaDB: {e}")

    def _create_metadata_embedding(self, metadata: Dict) -> List[float]:
        """Create simple embedding from metadata.

        This is a placeholder - in production use a proper embedding model.
        """
        # Create a simple numeric representation
        features = [
            metadata.get("latitude", 0) / 90,  # Normalize to -1 to 1
            metadata.get("longitude", 0) / 180,
            metadata.get("altitude", 0) / 10000,
            metadata.get("duration_seconds", 0) / 3600,
            metadata.get("quality_score", 0) / 100,
        ]

        # Add resolution encoding
        resolution_map = {"4K": 1.0, "1080p": 0.75, "720p": 0.5, "480p": 0.25}
        features.append(resolution_map.get(metadata.get("resolution", "unknown"), 0))

        # Pad to fixed dimension (768 for compatibility with common models)
        embedding = np.array(features)
        embedding = np.pad(embedding, (0, 768 - len(features)), mode="constant")

        return embedding.tolist()

    # ==================== Utilities ====================

    def _record_to_dict(self, record: Any) -> Dict:
        """Convert SQLAlchemy record to dict."""
        return {
            "id": str(record.id),
            "source_type": record.source_type,
            "source_url": record.source_url,
            "local_path": record.local_path,
            "camera_id": str(record.camera_id) if record.camera_id else None,
            "camera_name": record.camera_name,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "altitude": record.altitude,
            "title": record.title,
            "description": record.description,
            "duration_seconds": record.duration_seconds,
            "resolution": record.resolution,
            "codec": record.codec,
            "file_size_bytes": record.file_size_bytes,
            "quality_score": record.quality_score,
            "quality_metrics": record.quality_metrics,
            "recorded_at": record.recorded_at.isoformat(),
            "ingested_at": record.ingested_at.isoformat(),
            "weather_data": record.weather_data,
            "tags": record.tags,
            "checksum_sha256": record.checksum_sha256,
            "processing_status": record.processing_status,
        }
