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

"""Tests for contrail detection."""

import pytest
import numpy as np
import cv2
from chemtrail.cv.contrail_detector import ContrailDetector, ContrailDetection


class TestContrailDetector:
    """Test contrail detection algorithm."""

    def test_detector_initialization(self):
        """Test detector creates with default params."""
        detector = ContrailDetector()
        assert detector.min_line_length == 100
        assert detector.hough_threshold == 80

    def test_detect_empty_image(self):
        """Test detection on blank image returns empty."""
        detector = ContrailDetector()
        # Black image
        blank = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = detector.detect(blank)
        assert isinstance(detections, list)
        # Should find no contrails in blank image
        assert len(detections) == 0

    def test_detect_synthetic_contrail(self):
        """Test detection on synthetic contrail-like line."""
        detector = ContrailDetector(min_line_length=50)

        # Create image with horizontal line (contrail-like)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw white horizontal line in upper portion
        cv2.line(img, (100, 100), (500, 105), (255, 255, 255), 3)

        detections = detector.detect(img)

        assert isinstance(detections, list)
        # Should detect the line as contrail
        assert len(detections) > 0

        if detections:
            det = detections[0]
            assert isinstance(det, ContrailDetection)
            assert det.confidence > 0
            assert det.length_px > 50

    def test_contrail_detection_to_dict(self):
        """Test serialization."""
        det = ContrailDetection(
            start_x=100.0,
            start_y=100.0,
            end_x=500.0,
            end_y=105.0,
            confidence=0.85,
            angle=2.5,
            length_px=400.0,
        )

        result = det.to_dict()
        assert isinstance(result, dict)
        assert result["start_x"] == 100.0
        assert result["confidence"] == 0.85

    def test_angle_filtering(self):
        """Test that vertical lines are filtered out."""
        detector = ContrailDetector(min_line_length=50)

        # Create image with vertical line
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.line(img, (320, 50), (320, 400), (255, 255, 255), 3)

        detections = detector.detect(img)

        # Vertical lines should be filtered out
        assert len(detections) == 0

    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        detector = ContrailDetector()

        # Create detector and test confidence calculation
        line = np.array([[100, 50, 500, 55]])
        frame_shape = (480, 640, 3)

        confidence = detector._calculate_confidence(line, frame_shape, 5.0)

        # Confidence should be in valid range
        assert 0.0 <= confidence <= 1.0
        # Upper image horizontal line should have decent confidence
        assert confidence > 0.3
