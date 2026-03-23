"""Basic tests for the compression utilities."""

from src.compression import compress_crop_coordinates, group_consecutive_frames


class TestCompressCropCoordinates:
    """Tests for coordinate compression."""

    def test_compress_identical_coords(self):
        """Same coordinates compress to a single entry."""
        coords = [(100, 200)] * 50
        result = compress_crop_coordinates(coords, pixel_tolerance=5)
        assert len(result) == 1
        assert result[0] == (100, 200, 50)

    def test_compress_different_coords(self):
        """Different coordinates produce multiple entries."""
        coords = [(100, 200)] * 20 + [(300, 400)] * 20
        result = compress_crop_coordinates(coords, pixel_tolerance=5)
        assert len(result) == 2
        assert result[0] == (100, 200, 20)
        assert result[1] == (300, 400, 20)


class TestGroupConsecutiveFrames:
    """Tests for frame grouping."""

    def test_empty_input(self):
        """Empty list returns empty result."""
        assert group_consecutive_frames([]) == []

    def test_consecutive_frames(self):
        """Consecutive frames are grouped together."""
        result = group_consecutive_frames([0, 1, 2, 3, 4])
        assert result == [(0, 5)]

    def test_non_consecutive_frames(self):
        """Non-consecutive frames produce separate groups."""
        result = group_consecutive_frames([0, 1, 2, 10, 11, 12])
        assert result == [(0, 3), (10, 3)]
