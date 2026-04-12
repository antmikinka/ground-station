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

"""ChromaDB vector store for chemtrail detection archive."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb

DEFAULT_DB_PATH = Path.home() / ".chemtrail" / "db"


class BackendMismatchError(RuntimeError):
    """Raised when search backend/model doesn't match the indexed backend/model."""


def _collection_name(backend: str, model: str | None = None) -> str:
    """Return ChromaDB collection name for chemtrail detections."""
    if backend == "gemini":
        return "chemtrail_detections"
    if model:
        return f"chemtrail_detections_local_{model}"
    return "chemtrail_detections_local"


def detect_index(db_path: str | Path | None = None) -> tuple[str | None, str | None]:
    """Return ``(backend, model)`` for the first index with data.

    Returns ``(None, None)`` when no index contains data.
    Checks gemini first, then model-specific local collections, then the
    legacy ``chemtrail_detections_local`` collection (treated as qwen8b).
    """
    db_path = str(db_path or DEFAULT_DB_PATH)
    if not Path(db_path).exists():
        return None, None
    client = chromadb.PersistentClient(path=db_path)
    existing = {c.name for c in client.list_collections()}

    # Gemini first (default / legacy)
    if "chemtrail_detections" in existing:
        col = client.get_collection("chemtrail_detections")
        if col.count() > 0:
            return "gemini", None

    # Model-specific local collections (chemtrail_detections_local_<model>)
    for name in sorted(existing):
        if name.startswith("chemtrail_detections_local_"):
            col = client.get_collection(name)
            if col.count() > 0:
                meta = col.metadata or {}
                model = meta.get("embedding_model")
                if model is None:
                    model = name.removeprefix("chemtrail_detections_local_")
                return "local", model

    # Legacy local collection (no model suffix) — treat as qwen8b
    if "chemtrail_detections_local" in existing:
        col = client.get_collection("chemtrail_detections_local")
        if col.count() > 0:
            meta = col.metadata or {}
            return "local", meta.get("embedding_model", "qwen8b")

    return None, None


def detect_backend(db_path: str | Path | None = None) -> str | None:
    """Return the backend that has indexed data, or None if empty."""
    backend, _ = detect_index(db_path)
    return backend


def _make_chunk_id(source_file: str, start_time: float) -> str:
    """Deterministic chunk ID from source file + start time."""
    raw = f"{source_file}:{start_time}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ChemtrailVectorStore:
    """Persistent vector store for chemtrail detections backed by ChromaDB."""

    def __init__(self, db_path: str | Path | None = None, backend: str = "gemini",
                 model: str | None = None):
        db_path = str(db_path or DEFAULT_DB_PATH)
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=db_path)
        self._backend = backend
        self._model = model
        # Separate collection per backend+model so incompatible vectors never mix.
        col_name = _collection_name(backend, model)
        metadata = {"hnsw:space": "cosine", "embedding_backend": backend}
        if model:
            metadata["embedding_model"] = model
        self._collection = self._client.get_or_create_collection(
            name=col_name,
            metadata=metadata,
        )

    @property
    def collection(self) -> chromadb.Collection:
        return self._collection

    def get_backend(self) -> str:
        """Return the backend this index was built with."""
        meta = self._collection.metadata or {}
        return meta.get("embedding_backend", "gemini")

    def get_model(self) -> str | None:
        """Return the model this index was built with, or None."""
        meta = self._collection.metadata or {}
        return meta.get("embedding_model")

    def check_backend(self, backend: str) -> None:
        """Raise BackendMismatchError if *backend* doesn't match the index."""
        indexed_backend = self.get_backend()
        if indexed_backend != backend:
            raise BackendMismatchError(
                f"This index was built with the {indexed_backend} backend. "
                f"Search with --backend {indexed_backend} or re-index with "
                f"--backend {backend}."
            )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_detection(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """Store a chemtrail detection with extended metadata.

        Required metadata keys:
        - source_file, start_time, end_time (base)
        - camera_id, camera_name, camera_lat, camera_lon, camera_alt
        - detection_type, pixel_x, pixel_y, azimuth, elevation, confidence
        - indexed_at (auto-added)

        Optional metadata keys:
        - contrail_vector, icao24, callsign, aircraft_type
        - estimated_lat, estimated_lon, estimated_alt
        - correlation_score, position_method
        - overlay_applied, clip_path
        """
        required = ["source_file", "start_time", "end_time", "camera_id", "confidence"]
        for key in required:
            if key not in metadata:
                raise ValueError(f"Missing required metadata: {key}")

        import json

        meta = {
            "source_file": metadata["source_file"],
            "start_time": float(metadata["start_time"]),
            "end_time": float(metadata["end_time"]),
            "camera_id": str(metadata["camera_id"]),
            "camera_name": metadata.get("camera_name", "unknown"),
            "camera_lat": float(metadata.get("camera_lat", 0)),
            "camera_lon": float(metadata.get("camera_lon", 0)),
            "camera_alt": float(metadata.get("camera_alt", 0)),
            "detection_type": metadata.get("detection_type", "contrail"),
            "pixel_x": float(metadata.get("pixel_x", 0)),
            "pixel_y": float(metadata.get("pixel_y", 0)),
            "azimuth": float(metadata.get("azimuth", 0)),
            "elevation": float(metadata.get("elevation", 0)),
            "confidence": float(metadata["confidence"]),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Add optional fields if present - convert complex types to JSON strings
        optional_fields = [
            "contrail_vector", "icao24", "callsign", "aircraft_type",
            "estimated_lat", "estimated_lon", "estimated_alt",
            "correlation_score", "position_method", "overlay_applied", "clip_path"
        ]
        for field in optional_fields:
            if field in metadata:
                value = metadata[field]
                # ChromaDB only supports str, int, float, bool, None
                # Convert dict/list to JSON string
                if isinstance(value, (dict, list)):
                    meta[field] = json.dumps(value)
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    meta[field] = value
                else:
                    meta[field] = str(value)

        self._collection.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            metadatas=[meta],
        )

    def add_detections(self, chunks: list[dict]) -> None:
        """Batch-store detections. Each dict must have 'embedding' and metadata keys."""
        now = datetime.now(timezone.utc).isoformat()
        ids = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            chunk_id = _make_chunk_id(chunk["source_file"], chunk["start_time"])
            ids.append(chunk_id)
            embeddings.append(chunk["embedding"])
            metadatas.append({
                "source_file": chunk["source_file"],
                "start_time": float(chunk["start_time"]),
                "end_time": float(chunk["end_time"]),
                "camera_id": chunk.get("camera_id", "unknown"),
                "camera_name": chunk.get("camera_name", "unknown"),
                "camera_lat": float(chunk.get("camera_lat", 0)),
                "camera_lon": float(chunk.get("camera_lon", 0)),
                "camera_alt": float(chunk.get("camera_alt", 0)),
                "detection_type": chunk.get("detection_type", "contrail"),
                "pixel_x": float(chunk.get("pixel_x", 0)),
                "pixel_y": float(chunk.get("pixel_y", 0)),
                "azimuth": float(chunk.get("azimuth", 0)),
                "elevation": float(chunk.get("elevation", 0)),
                "confidence": float(chunk.get("confidence", 0)),
                "indexed_at": now,
            })

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[dict]:
        """Return top N results with distances and metadata."""
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, count),
        )

        hits = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            hits.append({
                "source_file": meta["source_file"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "score": 1.0 - distance,  # cosine distance -> similarity
                "distance": distance,
            })
        return hits

    def search_by_flight(
        self,
        icao24: str,
        n_results: int = 10,
    ) -> list[dict]:
        """Search detections for a specific flight."""
        count = self._collection.count()
        if count == 0:
            return []

        # Use get() with where filter for metadata-only search (no embedding needed)
        results = self._collection.get(
            where={"icao24": icao24},
            include=["metadatas"],
            limit=n_results,
        )

        return self._format_get_results(results)

    def search_by_camera(
        self,
        camera_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        n_results: int = 10,
    ) -> list[dict]:
        """Search detections for a specific camera with optional date range."""
        where = {"camera_id": str(camera_id)}

        count = self._collection.count()
        if count == 0:
            return []

        # Use get() with where filter for metadata-only search (no embedding needed)
        results = self._collection.get(
            where=where,
            include=["metadatas"],
            limit=n_results * 3,
        )

        filtered = self._format_get_results(results)

        if date_from or date_to:
            filtered = [
                r for r in filtered
                if self._matches_date_range(r, date_from, date_to)
            ]

        return filtered[:n_results]

    def search_by_location(
        self,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        n_results: int = 10,
    ) -> list[dict]:
        """Search detections within a geographic bounding box."""
        count = self._collection.count()
        if count == 0:
            return []

        # Fetch results and filter by location in Python
        results = self._collection.query(
            query_embeddings=[[0] * 768],  # Dummy query - get all
            n_results=min(n_results * 5, count),
            include=["metadatas"],
        )

        filtered = []
        for meta in results["metadatas"][0]:
            est_lat = meta.get("estimated_lat")
            est_lon = meta.get("estimated_lon")

            if est_lat is None or est_lon is None:
                continue

            if (lat_min <= est_lat <= lat_max and
                    lon_min <= est_lon <= lon_max):
                filtered.append({
                    "source_file": meta["source_file"],
                    "start_time": meta["start_time"],
                    "end_time": meta["end_time"],
                    "icao24": meta.get("icao24"),
                    "callsign": meta.get("callsign"),
                    "estimated_lat": est_lat,
                    "estimated_lon": est_lon,
                    "confidence": meta.get("confidence", 0),
                })

        # Sort by confidence
        filtered.sort(key=lambda x: x["confidence"], reverse=True)
        return filtered[:n_results]

    def search_by_date_range(
        self,
        date_from: datetime,
        date_to: datetime,
        n_results: int = 50,
    ) -> list[dict]:
        """Search detections within a date range."""
        count = self._collection.count()
        if count == 0:
            return []

        # Fetch results and filter by date in Python
        results = self._collection.query(
            query_embeddings=[[0] * 768],
            n_results=min(n_results * 5, count),
            include=["metadatas"],
        )

        filtered = [
            self._format_single_result(meta)
            for meta in results["metadatas"][0]
            if self._matches_date_range(self._format_single_result(meta), date_from, date_to)
        ]

        return filtered[:n_results]

    def is_indexed(self, source_file: str) -> bool:
        """Check whether any chunks from source_file are already stored."""
        results = self._collection.get(
            where={"source_file": source_file},
            limit=1,
        )
        return len(results["ids"]) > 0

    def remove_file(self, source_file: str) -> int:
        """Remove all chunks for a given source file. Returns count removed."""
        results = self._collection.get(where={"source_file": source_file})
        ids = results["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def get_stats(self) -> dict:
        """Return store statistics."""
        total = self._collection.count()
        if total == 0:
            return {"total_chunks": 0, "unique_source_files": 0, "source_files": []}

        # Fetch all metadata (only the fields we need)
        all_meta = self._collection.get(include=["metadatas"])
        source_files = sorted({m["source_file"] for m in all_meta["metadatas"]})
        return {
            "total_chunks": total,
            "unique_source_files": len(source_files),
            "source_files": source_files,
        }

    def _format_results(self, results: dict) -> list[dict]:
        """Format ChromaDB query results."""
        import json

        hits = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results["distances"] else 0

            hit = {
                "chunk_id": results["ids"][0][i],
                "source_file": meta["source_file"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "camera_id": meta.get("camera_id"),
                "camera_name": meta.get("camera_name"),
                "detection_type": meta.get("detection_type"),
                "confidence": meta.get("confidence", 0),
                "score": 1.0 - distance,
            }

            # Add optional fields - parse JSON strings back to dict/list
            for field in ["icao24", "callsign", "aircraft_type",
                          "estimated_lat", "estimated_lon", "contrail_vector"]:
                if field in meta:
                    value = meta[field]
                    # Parse JSON strings back to Python objects
                    if isinstance(value, str) and field == "contrail_vector":
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    hit[field] = value

            hits.append(hit)

        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

    def _format_get_results(self, results: dict) -> list[dict]:
        """Format ChromaDB get results (no distances)."""
        import json

        hits = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i]

            hit = {
                "chunk_id": results["ids"][i],
                "source_file": meta["source_file"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "camera_id": meta.get("camera_id"),
                "camera_name": meta.get("camera_name"),
                "detection_type": meta.get("detection_type"),
                "confidence": meta.get("confidence", 0),
                "score": meta.get("confidence", 0),  # Use confidence as score for get results
            }

            # Add optional fields - parse JSON strings back to dict/list
            for field in ["icao24", "callsign", "aircraft_type",
                          "estimated_lat", "estimated_lon", "contrail_vector"]:
                if field in meta:
                    value = meta[field]
                    # Parse JSON strings back to Python objects
                    if isinstance(value, str) and field == "contrail_vector":
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    hit[field] = value

            hits.append(hit)

        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

    def _format_single_result(self, meta: dict) -> dict:
        """Format a single result metadata dict."""
        return {
            "chunk_id": meta.get("chunk_id", meta.get("source_file", "unknown")),
            "source_file": meta["source_file"],
            "start_time": meta["start_time"],
            "end_time": meta["end_time"],
            "camera_id": meta.get("camera_id"),
            "camera_name": meta.get("camera_name"),
            "detection_type": meta.get("detection_type"),
            "confidence": meta.get("confidence", 0),
            "icao24": meta.get("icao24"),
            "callsign": meta.get("callsign"),
            "estimated_lat": meta.get("estimated_lat"),
            "estimated_lon": meta.get("estimated_lon"),
            "indexed_at": meta.get("indexed_at"),
        }

    def _matches_date_range(
        self,
        result: dict,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> bool:
        """Check if result falls within date range."""
        indexed_at = result.get("indexed_at")
        if not indexed_at:
            return True

        try:
            dt = datetime.fromisoformat(indexed_at)
            if date_from and dt < date_from:
                return False
            if date_to and dt > date_to:
                return False
            return True
        except (ValueError, TypeError):
            return True
