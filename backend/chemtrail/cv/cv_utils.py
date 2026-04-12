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

"""Computer vision utilities."""

import hashlib
from typing import List, Tuple
import numpy as np

import cv2


def compute_image_hash(image: np.ndarray) -> str:
    """
    Compute perceptual hash of image for deduplication.

    Args:
        image: Image as numpy array

    Returns:
        Hex string hash
    """
    # Resize to small fixed size for comparison
    resized = cv2.resize(image, (32, 32))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # Compute simple hash
    hash_bytes = hashlib.md5(gray.tobytes()).hexdigest()
    return hash_bytes


def draw_detections(
    image: np.ndarray,
    detections: List,
    color: Tuple[int, int, int] = (0, 255, 0)
) -> np.ndarray:
    """
    Draw detection lines on image for visualization.

    Args:
        image: BGR image
        detections: List of ContrailDetection objects
        color: BGR color tuple (default: green)

    Returns:
        Image with drawn detections
    """
    output = image.copy()
    for det in detections:
        pt1 = (int(det.start_x), int(det.start_y))
        pt2 = (int(det.end_x), int(det.end_y))
        cv2.line(output, pt1, pt2, color, 2)

        # Draw confidence score
        label = f"{det.confidence:.2f}"
        cv2.putText(
            output,
            label,
            (int(det.start_x), int(det.start_y) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1
        )

    return output


def preprocess_frame(
    frame: np.ndarray,
    apply_clahe: bool = True,
    denoise: bool = True
) -> np.ndarray:
    """
    Preprocess frame for contrail detection.

    Args:
        frame: BGR input frame
        apply_clahe: Apply Contrast Limited Adaptive Histogram Equalization
        denoise: Apply noise reduction

    Returns:
        Preprocessed grayscale image
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if apply_clahe:
        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    if denoise:
        # Apply denoising
        gray = cv2.fastNlMeansDenoising(gray, h=10)

    return gray


def detect_edges(
    image: np.ndarray,
    threshold1: int = 50,
    threshold2: int = 150
) -> np.ndarray:
    """
    Detect edges using Canny algorithm.

    Args:
        image: Grayscale input image
        threshold1: Lower threshold for edge detection
        threshold2: Upper threshold for edge detection

    Returns:
        Binary edge image
    """
    return cv2.Canny(image, threshold1=threshold1, threshold2=threshold2)
