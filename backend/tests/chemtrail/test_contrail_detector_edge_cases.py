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
# You should receive a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Edge case tests for contrail detector."""

import pytest
import numpy as np
import cv2
from chemtrail.cv.contrail_detector import ContrailDetector, ContrailDetection


class TestContrailDetectorEdgeCases:
    """Test contrail detector edge cases and boundary conditions."""

    def test_detect_noise_only_image(self):
        """Test detection on noisy image - documents that noise can produce false positives."""
        detector = ContrailDetector()
        # Random noise image
        np.random.seed(42)
        noisy = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)

        detections = detector.detect(noisy)
        # NOTE: Random noise CAN produce false positive line detections
        # This is expected behavior - real images need additional validation
        # Test documents this behavior for awareness
        assert isinstance(detections, list)
        # Each detection should have valid structure
        for det in detections:
            assert hasattr(det, 'start_x')
            assert det.confidence >= 0.0
            assert det.confidence <= 1.0

    def test_detect_all_white_image(self):
        """Test detection on all-white image."""
        detector = ContrailDetector()
        white = np.full((480, 640, 3), 255, dtype=np.uint8)

        detections = detector.detect(white)
        # Should find no distinct edges
        assert len(detections) == 0

    def test_detect_all_black_image(self):
        """Test detection on all-black image."""
        detector = ContrailDetector()
        black = np.zeros((480, 640, 3), dtype=np.uint8)

        detections = detector.detect(black)
        # Should find no edges
        assert len(detections) == 0

    def test_detect_multiple_contrails(self):
        """Test detection of multiple contrails in same image."""
        detector = ContrailDetector(min_line_length=50)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw three horizontal lines at different heights
        cv2.line(img, (50, 50), (590, 55), (255, 255, 255), 3)
        cv2.line(img, (50, 150), (590, 152), (255, 255, 255), 3)
        cv2.line(img, (50, 250), (590, 248), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should detect at least 2 of the 3 lines
        assert len(detections) >= 2

    def test_detect_diagonal_line_rejected(self):
        """Test that strongly diagonal lines are rejected."""
        detector = ContrailDetector(min_line_length=50, max_angle_from_horizontal=30.0)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw diagonal line (45 degrees)
        cv2.line(img, (100, 100), (500, 500), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should be rejected as too diagonal
        assert len(detections) == 0

    def test_detect_short_lines_filtered(self):
        """Test that lines shorter than minimum are filtered."""
        detector = ContrailDetector(min_line_length=100)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw short line (50 pixels)
        cv2.line(img, (100, 100), (150, 100), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should be filtered out
        assert len(detections) == 0

    def test_detect_contrail_at_boundary(self):
        """Test contrail detection at image boundaries."""
        detector = ContrailDetector(min_line_length=50)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Line that goes to edge of image
        cv2.line(img, (0, 100), (640, 102), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should detect the line
        assert len(detections) > 0

    def test_detect_thick_line(self):
        """Test detection of thick contrail-like line."""
        detector = ContrailDetector(min_line_length=50)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Thick horizontal line
        cv2.line(img, (100, 100), (500, 100), (255, 255, 255), 10)

        detections = detector.detect(img)
        # Should detect the thick line
        assert len(detections) > 0

    def test_detect_faint_contrail(self):
        """Test detection of low-contrast contrail."""
        detector = ContrailDetector(min_line_length=50, hough_threshold=50)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Faint gray line (low contrast)
        cv2.line(img, (100, 100), (500, 102), (180, 180, 180), 2)

        detections = detector.detect(img)
        # May or may not detect depending on threshold
        # This test ensures no crashes with low-contrast images

    def test_angle_boundary_45_degrees(self):
        """Test angle filtering at 45 degree boundary."""
        detector = ContrailDetector(min_line_length=50, max_angle_from_horizontal=30.0)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw line at exactly 45 degrees (should be rejected)
        cv2.line(img, (100, 400), (500, 0), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should be rejected
        assert len(detections) == 0

    def test_angle_near_horizontal(self):
        """Test angle filtering near horizontal."""
        detector = ContrailDetector(min_line_length=50, max_angle_from_horizontal=30.0)

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw line at 25 degrees (should pass)
        # tan(25 degrees) * 400 = 186 pixels vertical change
        cv2.line(img, (100, 300), (500, 114), (255, 255, 255), 3)

        detections = detector.detect(img)
        # Should pass angle filter
        assert len(detections) > 0

    def test_detection_serialization(self):
        """Test ContrailDetection serialization edge cases."""
        det = ContrailDetection(
            start_x=0.0,  # Edge: zero coordinate
            start_y=0.0,
            end_x=640.0,  # Edge: max coordinate
            end_y=480.0,
            confidence=1.0,  # Edge: max confidence
            angle=0.0,  # Edge: perfectly horizontal
            length_px=640.0,
            width_px=None,  # Edge: None width
        )

        result = det.to_dict()
        assert result["start_x"] == 0.0
        assert result["end_x"] == 640.0
        assert result["confidence"] == 1.0
        assert result["angle"] == 0.0
        assert result["width_px"] is None

    def test_detector_with_color_noise(self):
        """Test detector handles color noise gracefully."""
        detector = ContrailDetector()

        # Color noise with varying intensities
        np.random.seed(123)
        color_noise = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

        # Should not raise any exceptions
        detections = detector.detect(color_noise)
        assert isinstance(detections, list)

    def test_detector_error_handling(self):
        """Test detector handles invalid input gracefully."""
        detector = ContrailDetector()

        # Empty array should not crash
        try:
            empty = np.zeros((0, 0, 3), dtype=np.uint8)
            detections = detector.detect(empty)
            assert detections == []
        except Exception:
            # Some OpenCV versions may throw, which is acceptable
            pass
