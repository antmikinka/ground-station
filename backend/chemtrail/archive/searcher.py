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

"""Query and retrieval logic for chemtrail detection archive."""

from datetime import datetime

from .embedder import embed_query
from .vector_store import ChemtrailVectorStore


def search_detections(
    query: str,
    vector_store: ChemtrailVectorStore,
    n_results: int = 10,
    icao24: str | None = None,
    camera_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    detection_type: str | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Search detection archive with natural language and metadata filters.

    Args:
        query: Natural language search query
        vector_store: ChemtrailVectorStore instance
        n_results: Max results to return
        icao24: Filter by flight ICAO24 hex code
        camera_id: Filter by camera UUID
        date_from: Start of date range
        date_to: End of date range
        detection_type: Filter by type ("contrail" or "aircraft")
        verbose: Print debug info

    Returns:
        List of matching detections with metadata
    """
    # Step 1: Embed query
    query_embedding = embed_query(query, verbose=verbose)

    # Step 2: Build where clause for metadata filtering
    where_conditions = []

    if icao24:
        where_conditions.append({"icao24": icao24})
    if camera_id:
        where_conditions.append({"camera_id": str(camera_id)})
    if detection_type:
        where_conditions.append({"detection_type": detection_type})

    # Combine with AND
    where = {"$and": where_conditions} if len(where_conditions) > 1 else (where_conditions[0] if where_conditions else None)

    # Step 3: Query ChromaDB
    count = vector_store.collection.count()
    if count == 0:
        return []

    results = vector_store.collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results * 3, count),
        where=where,
        include=["metadatas", "distances"],
    )

    # Step 4: Format and filter results
    hits = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        # Apply date filter in Python
        if date_from or date_to:
            indexed_at = meta.get("indexed_at")
            if indexed_at:
                try:
                    dt = datetime.fromisoformat(indexed_at)
                    if date_from and dt < date_from:
                        continue
                    if date_to and dt > date_to:
                        continue
                except ValueError:
                    pass

        hit = {
            "chunk_id": results["ids"][0][i],
            "source_file": meta["source_file"],
            "start_time": meta["start_time"],
            "end_time": meta["end_time"],
            "score": 1.0 - distance,
            "camera_id": meta.get("camera_id"),
            "camera_name": meta.get("camera_name"),
            "icao24": meta.get("icao24"),
            "callsign": meta.get("callsign"),
            "detection_type": meta.get("detection_type"),
            "confidence": meta.get("confidence", 0),
            "estimated_lat": meta.get("estimated_lat"),
            "estimated_lon": meta.get("estimated_lon"),
        }
        hits.append(hit)

    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:n_results]


def search_footage(
    query: str,
    store: ChemtrailVectorStore,
    n_results: int = 5,
    verbose: bool = False,
) -> list[dict]:
    """Search indexed footage with a natural language query.

    Legacy function name for backward compatibility.
    Use search_detections() for new code.

    Args:
        query: Natural language search string.
        store: ChemtrailVectorStore instance to search against.
        n_results: Maximum number of results to return.
        verbose: If True, print debug info.

    Returns:
        List of result dicts sorted by relevance (best first).
        Each dict contains: source_file, start_time, end_time, similarity_score.
    """
    return search_detections(
        query=query,
        vector_store=store,
        n_results=n_results,
        verbose=verbose,
    )
