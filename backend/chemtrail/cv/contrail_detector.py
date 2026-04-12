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

"""Contrail detection using Hough transform."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import cv2
from common.common import logger


@dataclass
class ContrailDetection:
    """Represents a detected contrail."""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    confidence: float
    angle: float  # degrees from horizontal
    length_px: float
    width_px: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "confidence": self.confidence,
            "angle": self.angle,
            "length_px": self.length_px,
            "width_px": self.width_px,
        }


class ContrailDetector:
    """
    Detects contrails in sky images using Hough line transform.

    Pipeline:
    1. Convert to grayscale
    2. Apply CLAHE for contrast enhancement
    3. Denoise
    4. Canny edge detection
    5. Probabilistic Hough line detection
    6. Filter lines by length, angle, and position
    """

    def __init__(
        self,
        min_line_length: int = 100,
        max_line_gap: int = 10,
        hough_threshold: int = 80,
        max_angle_from_horizontal: float = 30.0,
    ):
        """
        Initialize detector with tunable parameters.

        Args:
            min_line_length: Minimum line length in pixels
            max_line_gap: Maximum gap between line segments
            hough_threshold: Hough transform threshold
            max_angle_from_horizontal: Maximum deviation from horizontal (0 or 180 deg)
        """
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
        self.hough_threshold = hough_threshold
        self.max_angle_from_horizontal = max_angle_from_horizontal

    def detect(self, frame: np.ndarray) -> List[ContrailDetection]:
        """
        Detect contrails in image frame.

        Args:
            frame: BGR image as numpy array (from OpenCV)

        Returns:
            List of ContrailDetection objects
        """
        try:
            # Stage 1: Preprocessing
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # CLAHE for contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

            # Stage 2: Edge Detection
            edges = cv2.Canny(denoised, threshold1=50, threshold2=150)

            # Stage 3: Line Detection (Probabilistic Hough)
            lines = cv2.HoughLinesP(
                edges,
                rho=1,
                theta=np.pi / 180,
                threshold=self.hough_threshold,
                minLineLength=self.min_line_length,
                maxLineGap=self.max_line_gap,
            )

            if lines is None:
                return []

            # Stage 4: Contrail Validation
            contrails = []
            for line in lines:
                detection = self._validate_line(line, frame.shape)
                if detection:
                    contrails.append(detection)

            return contrails

        except Exception as e:
            logger.error(f"Error in contrail detection: {e}")
            return []

    def _validate_line(
        self,
        line: np.ndarray,
        frame_shape: Tuple
    ) -> Optional[ContrailDetection]:
        """
        Validate if a line is likely a contrail.

        Checks:
        - Line is approximately horizontal (within angle bounds)
        - Line is in upper portion of image (sky region)
        - Line has sufficient contrast
        """
        x1, y1, x2, y2 = line[0]

        # Calculate angle (0-180 degrees from horizontal)
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            angle = 90.0  # Vertical line
        else:
            angle = abs(np.degrees(np.arctan2(dy, dx)))

        # Filter by angle: contrails are roughly horizontal (angle near 0 or near 180)
        # Calculate deviation from horizontal
        angle_deviation = min(angle, 180 - angle)
        if angle_deviation > self.max_angle_from_horizontal:
            return None

        # Calculate length
        length = np.sqrt(dx * dx + dy * dy)
        if length < self.min_line_length:
            return None

        # Calculate confidence based on various factors
        confidence = self._calculate_confidence(line, frame_shape, angle)

        if confidence < 0.3:  # Minimum confidence threshold
            return None

        return ContrailDetection(
            start_x=float(x1),
            start_y=float(y1),
            end_x=float(x2),
            end_y=float(y2),
            confidence=confidence,
            angle=angle,
            length_px=length,
        )

    def _calculate_confidence(
        self,
        line: np.ndarray,
        frame_shape: Tuple,
        angle: float
    ) -> float:
        """
        Calculate confidence score for a detected line.

        Factors:
        - Position in image (upper = more likely sky)
        - Angle (closer to horizontal = higher confidence)
        - Length (longer = higher confidence)
        """
        x1, y1, x2, y2 = line[0]
        height = frame_shape[0]

        # Position score: lines in upper 2/3 of image get higher score
        avg_y = (y1 + y2) / 2
        position_score = max(0, 1.0 - (avg_y / (height * 0.67)))

        # Angle score: closer to horizontal (0 or 180) = higher
        angle_deviation = min(abs(angle), abs(180 - angle))
        angle_score = max(0, 1.0 - (angle_deviation / 45.0))

        # Length score: longer lines get higher score
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        length_score = min(1.0, length / 500.0)  # 500px = max score

        # Combine scores with weights
        confidence = (position_score * 0.3 + angle_score * 0.4 + length_score * 0.3)

        return min(1.0, max(0.0, confidence))
