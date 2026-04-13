#!/usr/bin/env python
"""Lightweight processing: detect contrails + embed metadata text via Lemonade.

This version skips the heavy vision-language frame description and just
embeds the detection metadata as text, which uses only the embedding
model (nomic-embed-text) - much lighter on the NPU.
"""

import os
import sys
import json
import cv2
import httpx
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from chemtrail.archive.chunker import chunk_video
from chemtrail.cv.contrail_detector import ContrailDetector

LEMONADE_URL = "http://localhost:8000"
EMBEDDING_MODEL = "nomic-embed-text-v2-moe-GGUF"
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "chemtrail_samples"
CHUNKS_DIR = SAMPLES_DIR / "chunks"
DETECTIONS_DIR = SAMPLES_DIR / "detections"

detector = ContrailDetector()


def embed_text(text: str) -> list[float]:
    """Embed text using Lemonade Server's embedding endpoint."""
    resp = httpx.post(
        f"{LEMONADE_URL}/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def process_video(video_path: str, verbose: bool = True):
    """Process a single video: chunk, detect, embed metadata."""
    video_name = Path(video_path).stem

    print(f"\n{'='*60}")
    print(f"Processing: {video_name}")
    print(f"{'='*60}")

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    DETECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Chunk video
    print(f"\n[1/3] Chunking video (15s segments)...")
    chunks = list(chunk_video(video_path, output_dir=str(CHUNKS_DIR), chunk_duration=15))
    print(f"  Created {len(chunks)} chunks")

    # Step 2: Contrail detection on each chunk
    print(f"\n[2/3] Running contrail detection (CLAHE+Canny+Hough)...")
    detections = []
    for i, chunk_info in enumerate(chunks):
        chunk_str = chunk_info["chunk_path"]
        try:
            cap = cv2.VideoCapture(chunk_str)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                print(f"  Chunk {i}: Empty chunk")
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                print(f"  Chunk {i}: Could not read frame")
                continue

            results = detector.detect(frame)
            if results:
                best = results[0]
                det_desc = (
                    f"Contrail detected in {video_name} chunk {i}: "
                    f"{len(results)} line(s), confidence {best.confidence:.3f}, "
                    f"angle {best.angle:.1f} degrees from horizontal, "
                    f"length {best.length_px:.0f}px, "
                    f"start ({best.start_x:.0f},{best.start_y:.0f}) "
                    f"to ({best.end_x:.0f},{best.end_y:.0f})"
                )
                detections.append({
                    "chunk_path": chunk_str,
                    "chunk_index": i,
                    "start_time": chunk_info["start_time"],
                    "end_time": chunk_info["end_time"],
                    "source_video": video_name,
                    "description": det_desc,
                    "contrails": [c.to_dict() for c in results],
                })
                print(f"  Chunk {i}: DETECTED - {len(results)} line(s), "
                      f"score={best.confidence:.3f}, angle={best.angle:.1f}deg")
            elif verbose:
                print(f"  Chunk {i}: No detection")
        except Exception as e:
            print(f"  Chunk {i}: Error - {e}")

    print(f"  Found {len(detections)} detections out of {len(chunks)} chunks")

    if not detections:
        print("  No contrails detected.")
        return detections

    # Step 3: Embed detection descriptions via Lemonade
    print(f"\n[3/3] Embedding detection descriptions via Lemonade Server (NPU)...")
    for det in detections:
        try:
            emb = embed_text(det["description"])
            det["embedding"] = emb
            det["embedding_dim"] = len(emb)
            print(f"  Embedded chunk {det['chunk_index']}: dim={len(emb)}, "
                  f"first3=[{emb[0]:.4f}, {emb[1]:.4f}, {emb[2]:.4f}]")
        except Exception as e:
            print(f"  Error embedding chunk {det['chunk_index']}: {e}")

    # Save results
    output_file = DETECTIONS_DIR / f"{video_name}_detections.json"
    output_data = []
    for det in detections:
        entry = {k: v for k, v in det.items() if k != "embedding"}
        entry["embedding_preview"] = det.get("embedding", [])[:10] if det.get("embedding") else []
        entry["embedding_dim"] = det.get("embedding_dim", 0)
        output_data.append(entry)

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n  Saved {len(detections)} detections to {output_file}")
    return detections


def main():
    videos = list(SAMPLES_DIR.glob("*.mp4"))
    if not videos:
        print(f"No videos found in {SAMPLES_DIR}")
        return

    print(f"Found {len(videos)} video(s) to process:")
    for v in videos:
        print(f"  - {v.name} ({v.stat().st_size / 1024 / 1024:.1f} MB)")

    all_detections = []
    for video in videos:
        detections = process_video(str(video))
        all_detections.extend(detections)

    print(f"\n{'='*60}")
    print(f"PIPELINE SUMMARY")
    print(f"{'='*60}")
    print(f"Videos processed: {len(videos)}")
    print(f"Total detections: {len(all_detections)}")
    if all_detections:
        scores = [d["contrails"][0]["confidence"] for d in all_detections]
        print(f"Detection scores: min={min(scores):.3f}, max={max(scores):.3f}, avg={sum(scores)/len(scores):.3f}")
        print(f"Videos with detections: {set(d['source_video'] for d in all_detections)}")

    # Test Lemonade embedding
    print(f"\nVerifying Lemonade Server embedding...")
    try:
        test_emb = embed_text("sky with airplane contrails")
        print(f"  Test embedding: dim={len(test_emb)}")
        print(f"  SUCCESS: Lemonade Server NPU embedding working")
    except Exception as e:
        print(f"  WARNING: Lemonade Server not available: {e}")


if __name__ == "__main__":
    main()
