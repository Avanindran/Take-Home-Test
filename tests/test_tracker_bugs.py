"""Tests for bug fixes in the face tracking module."""

from src.tracker import track_face_crop


class TestTrackerBugFixes:
    """Tests for specific bug fixes in track_face_crop."""

    def test_dead_zone_prevents_unnecessary_movement(self):
        """Test that dead zone prevents crop movement for small face movements.
        
        This test verifies that the fixed dead zone logic actually works.
        Before the fix, ANY face movement would trigger crop movement.
        After the fix, only movements that exit the dead zone should trigger movement.
        """
        # Create a scenario where face moves within dead zone
        # Face centered at (320, 180), dead zone should be around this area
        video_width, video_height = 640, 360
        crop_w = video_height * 9.0 / 16.0  # 202.5
        crop_h = float(video_height)  # 360
        dz_half_w = crop_w * 0.10 / 2.0  # 10.125
        dz_half_h = crop_h * 0.10 / 2.0  # 18.0
        
        # Face moves within dead zone (small movements around center)
        center_x, center_y = 320, 180
        bboxes = [
            (center_x - 50, center_y - 50, center_x + 50, center_y + 50),  # Frame 0
            (center_x - 45, center_y - 45, center_x + 55, center_y + 55),  # Frame 1 - small move
            (center_x - 55, center_y - 55, center_x + 45, center_y + 45),  # Frame 2 - small move
        ]
        
        compressed, scene_cuts = track_face_crop(
            bboxes, 
            video_width=video_width, 
            video_height=video_height,
            deadzone_ratio=0.10
        )
        
        # Should have minimal movement or single segment due to dead zone
        assert len(compressed) <= 2  # At most 2 segments for 3 frames
        assert scene_cuts == []

    def test_dead_zone_triggers_movement_when_exited(self):
        """Test that dead zone triggers movement when face exits the zone.
        
        This verifies that the dead zone isn't too aggressive - when the face
        actually moves significantly, the crop should follow.
        """
        video_width, video_height = 640, 360
        center_x, center_y = 320, 180
        
        # Face starts in center, then moves significantly outside dead zone
        bboxes = [
            (center_x - 50, center_y - 50, center_x + 50, center_y + 50),  # Frame 0 - center
            (center_x + 100, center_y - 50, center_x + 200, center_y + 50),  # Frame 1 - moved right
        ]
        
        compressed, scene_cuts = track_face_crop(
            bboxes, 
            video_width=video_width, 
            video_height=video_height,
            deadzone_ratio=0.10
        )
        
        # Should have movement due to exiting dead zone
        assert len(compressed) >= 2  # At least 2 segments for movement
        assert scene_cuts == []

    def test_no_face_before_first_detection_sentinel(self):
        """Test that frames with None bbox before first face return (-1, -1) sentinel.
        
        This ensures the special case handling for no-face frames before the first
        face detection works correctly.
        """
        bboxes = [None, None, None, (300, 160, 340, 200), (300, 160, 340, 200)]
        compressed, scene_cuts = track_face_crop(bboxes, video_width=640, video_height=360)

        # First segment should be the no-face sentinel
        assert compressed[0][0] == -1
        assert compressed[0][1] == -1
        assert compressed[0][2] == 3  # 3 no-face frames
        assert scene_cuts == []

    def test_no_face_after_first_detection_holds_position(self):
        """Test that no-face gaps after first detection hold the last crop position.
        
        After the first face is detected, subsequent no-face frames should maintain
        the last known crop position, not revert to the (-1, -1) sentinel.
        """
        bboxes = [(300, 160, 340, 200), (300, 160, 340, 200), None, None, None]
        compressed, scene_cuts = track_face_crop(bboxes, video_width=640, video_height=360)

        # Should not have (-1, -1) sentinel after first face detection
        for segment in compressed:
            assert not (segment[0] == -1 and segment[1] == -1), "No (-1, -1) sentinel after first face"

    def test_scene_boundary_triggers_snap(self):
        """Test that scene boundaries trigger instant crop snap.
        
        Scene cuts should cause immediate crop position changes without smoothing,
        creating a hard cut effect.
        """
        bboxes = [(300, 160, 340, 200)] * 10 + [(400, 160, 440, 200)] * 10
        face_scenes = [(0, 9), (10, 19)]  # Scene boundary at frame 10
        
        compressed, scene_cuts = track_face_crop(
            bboxes, 
            video_width=640, 
            video_height=360,
            face_scenes=face_scenes
        )
        
        # Should have scene cut at frame 10
        assert 10 in scene_cuts

    def test_speaker_switch_triggers_snap(self):
        """Test that speaker ID changes trigger instant crop snap.
        
        When the active speaker changes, the crop should snap immediately to
        handle the transition between different speakers.
        """
        bboxes = [(300, 160, 340, 200)] * 20
        speaker_ids = [0] * 10 + [1] * 10  # Speaker switch at frame 10
        
        compressed, scene_cuts = track_face_crop(
            bboxes, 
            video_width=640, 
            video_height=360,
            speaker_track_ids=speaker_ids
        )
        
        # Should have scene cut at frame 10 due to speaker switch
        assert 10 in scene_cuts

    def test_first_face_snaps_instantly(self):
        """Test that first face detection snaps crop instantly.
        
        The first face detected should immediately set the crop position without
        any smoothing delay to avoid initial instability.
        """
        bboxes = [None, None, None, (300, 160, 340, 200)]  # First face at frame 3
        compressed, scene_cuts = track_face_crop(bboxes, video_width=640, video_height=360)

        # Should have no smoothing for first face detection
        # The crop should be exactly at the face center
        face_center_x = (300 + 340) / 2.0
        face_center_y = (160 + 200) / 2.0
        
        # Find the segment that contains frame 3
        frame_offset = 0
        for segment in compressed:
            if frame_offset <= 3 < frame_offset + segment[2]:
                # Check if crop position is close to face center (allowing for clamping)
                assert abs(segment[0] - face_center_x) < 1.0, f"Crop X {segment[0]} not close to face center X {face_center_x}"
                assert abs(segment[1] - face_center_y) < 1.0, f"Crop Y {segment[1]} not close to face center Y {face_center_y}"
                break
            frame_offset += segment[2]
        else:
            assert False, "Could not find segment containing frame 3"

    def test_smoothing_applies_after_dead_zone_exit(self):
        """Test that exponential smoothing is applied when face exits dead zone.
        
        When the face moves enough to exit the dead zone, the crop should follow
        with smooth, gradual movement rather than jumping immediately.
        """
        video_width, video_height = 640, 360
        center_x, center_y = 320, 180
        
        # Face moves significantly outside dead zone
        bboxes = [
            (center_x - 50, center_y - 50, center_x + 50, center_y + 50),  # Frame 0 - center
            (center_x + 200, center_y - 50, center_x + 300, center_y + 50),  # Frame 1 - moved far right
            (center_x + 200, center_y - 50, center_x + 300, center_y + 50),  # Frame 2 - stays
        ]
        
        compressed, scene_cuts = track_face_crop(
            bboxes, 
            video_width=video_width, 
            video_height=video_height,
            deadzone_ratio=0.10,
            smoothing=0.25
        )
        
        # Should have multiple segments showing gradual movement
        assert len(compressed) >= 2
        assert scene_cuts == []
