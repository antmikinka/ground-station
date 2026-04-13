#!/usr/bin/env python
"""Generate detection visualization images with contrail lines drawn on frames."""

import os
import sys
import cv2
import json
from pathlib import Path

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from chemtrail.archive.chunker import chunk_video
from chemtrail.cv.contrail_detector import ContrailDetector
import tempfile
import shutil

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "chemtrail_samples"
VIS_DIR = SAMPLES_DIR / "visualizations"
VIS_DIR.mkdir(parents=True, exist_ok=True)

detector = ContrailDetector()


def draw_detection(frame, detection_result, color=(0, 255, 0), thickness=2):
    """Draw detected contrail lines on frame."""
    img = frame.copy()
    for contrail in detection_result:
        start = (int(contrail.start_x), int(contrail.start_y))
        end = (int(contrail.end_x), int(contrail.end_y))
        cv2.line(img, start, end, color, thickness)
        # Draw endpoints
        cv2.circle(img, start, 5, (0, 0, 255), -1)
        cv2.circle(img, end, 5, (0, 0, 255), -1)
    # Add info overlay
    h, w = img.shape[:2]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
    text = (f"Score: {detection_result[0].confidence:.3f} | "
            f"Angle: {detection_result[0].angle:.1f}deg | "
            f"Lines: {len(detection_result)} | "
            f"Length: {detection_result[0].length_px:.0f}px")
    cv2.putText(img, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(img, "GREEN=contrail  RED=endpoints", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return img


def process_video(video_path):
    """Process one video and save detection visualization images."""
    video_name = Path(video_path).stem
    out_dir = VIS_DIR / video_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clean temp after chunking
    temp_dir = tempfile.mkdtemp()

    chunks = list(chunk_video(video_path, output_dir=temp_dir, chunk_duration=15))
    print(f"\n{'='*60}")
    print(f"VIDEO: {video_name} ({len(chunks)} chunks)")
    print(f"{'='*60}")

    count = 0
    for i, chunk_info in enumerate(chunks):
        chunk_str = str(chunk_info["chunk_path"])
        try:
            cap = cv2.VideoCapture(chunk_str)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                continue

            results = detector.detect(frame)
            if results:
                vis_frame = draw_detection(frame, results, color=(0, 255, 0))
                out_path = out_dir / f"chunk_{i:03d}_detected.jpg"
                cv2.imwrite(str(out_path), vis_frame)
                best = results[0]
                print(f"  [SAVED] chunk {i}: score={best.confidence:.3f}, "
                      f"lines={len(results)}, angle={best.angle:.1f}deg, "
                      f"length={best.length_px:.0f}px -> {out_path.name}")
                count += 1
            else:
                # Save negative examples too (every 5th)
                if i % 5 == 0:
                    out_path = out_dir / f"chunk_{i:03d}_no_detection.jpg"
                    cv2.imwrite(str(out_path), frame)
        except Exception as e:
            print(f"  [ERROR] chunk {i}: {e}")

    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"  Total detections saved: {count}")
    return count


def main():
    videos = list(SAMPLES_DIR.glob("*.mp4"))
    print(f"Found {len(videos)} videos")

    total = 0
    for video in videos:
        total += process_video(str(video))

    print(f"\n{'='*60}")
    print(f"TOTAL: {total} detection images saved to {VIS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
