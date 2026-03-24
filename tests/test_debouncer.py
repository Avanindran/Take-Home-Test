"""Tests for the speaker ID debouncing module."""

import unittest
from src.debouncer import debounce_speaker_ids


class TestDebouncer(unittest.TestCase):
    """Tests for speaker ID debouncing."""

    def test_empty_input(self):
        """Empty list should return empty result."""
        assert debounce_speaker_ids([]) == []

    def test_none_segments_untouched(self):
        """None segments should never be modified - they represent valid 'no speaker' states."""
        input_ids = [None] * 10 + [0] * 50
        result = debounce_speaker_ids(input_ids, min_hold_frames=15)
        assert result == input_ids

    def test_short_flicker_replacement(self):
        """Short flicker segments should be replaced by surrounding stable ID."""
        # 50 frames of speaker 0, 3 frames of speaker 1 (too short), 50 frames of speaker 0
        input_ids = [0] * 50 + [1] * 3 + [0] * 50
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = [0] * 103  # All should be speaker 0
        assert result == expected

    def test_long_segments_preserved(self):
        """Long segments should be preserved - they represent genuine speaker switches."""
        input_ids = [0] * 50 + [1] * 20 + [0] * 50
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        assert result == input_ids  # Should be unchanged

    def test_multiple_short_flickers(self):
        """Multiple short flickers should all be replaced by the surrounding stable speaker."""
        input_ids = [0] * 30 + [1] * 2 + [2] * 3 + [0] * 30
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = [0] * 65  # All should be speaker 0
        assert result == expected

    def test_short_at_beginning(self):
        """Short segment at beginning should be replaced by next stable ID."""
        input_ids = [1] * 3 + [0] * 50  # 3 frames of speaker 1, then 50 frames of speaker 0
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = [0] * 53  # All should be speaker 0
        assert result == expected

    def test_short_at_end(self):
        """Short segment at end should be replaced by previous stable ID."""
        input_ids = [0] * 50 + [1] * 3  # 50 frames of speaker 0, then 3 frames of speaker 1
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = [0] * 53  # All should be speaker 0
        assert result == expected

    def test_none_separating_segments(self):
        """None segments should separate stable runs they act as natural boundaries."""
        input_ids = [0] * 20 + [None] * 5 + [1] * 3 + [None] * 5 + [0] * 20
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        # The short speaker 1 segment should be replaced, but None segments preserved
        expected = [0] * 20 + [None] * 5 + [0] * 3 + [None] * 5 + [0] * 20
        assert result == expected

    def test_edge_case_single_frame(self):
        """Single frame segments should definitely be replaced since they're clearly noise."""
        input_ids = [0] * 20 + [1] + [0] * 20
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = [0] * 41  # All should be speaker 0
        assert result == expected

    def test_no_stable_neighbors(self):
        """Edge case where short segment has no stable neighbors and should keep original."""
        input_ids = [1] * 3  # Only 3 frames, no stable neighbors
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        # Should keep original since no stable neighbors exist
        assert result == input_ids

    def test_complex_scenario(self):
        """Complex scenario with multiple short segments and None values."""
        input_ids = (
            [0] * 30 +           # Stable speaker 0
            [1] * 2 +            # Short flicker 1
            [None] * 5 +         # No speaker
            [2] * 3 +            # Short flicker 2
            [None] * 3 +         # No speaker
            [0] * 2 +            # Short flicker 0
            [None] * 5 +         # No speaker
            [3] * 25             # Stable speaker 3
        )
        result = debounce_speaker_ids(input_ids, min_hold_frames=10)
        expected = (
            [0] * 30 +           # Stable speaker 0 preserved
            [0] * 2 +            # Short flicker 1 replaced by previous stable 0
            [None] * 5 +         # No speaker preserved
            [0] * 3 +            # Short flicker 2 replaced by previous stable 0
            [None] * 3 +         # No speaker preserved
            [0] * 2 +            # Short flicker 0 replaced by previous stable 0
            [None] * 5 +         # No speaker preserved
            [3] * 25             # Stable speaker 3 preserved
        )
        assert result == expected
