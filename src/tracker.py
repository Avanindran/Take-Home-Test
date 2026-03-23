"""
Dead-zone camera tracking for stable crop window positioning.

Computes a stabilized crop window that only moves when the face exits an
inner "dead zone" region. Combined with exponential smoothing, this produces
stable, jitter-free crop coordinates for portrait (9:16) video output.
"""

from src.debouncer import debounce_speaker_ids


def track_face_crop(
    face_bbox_timeline,
    video_width=640,
    video_height=360,
    face_scenes=None,
    speaker_track_ids=None,
    deadzone_ratio=0.10,
    smoothing=0.25,
    pixel_tolerance=3,
    min_speaker_hold_frames=15,
):
    """
    Dead-zone camera tracking for stable crop window positioning.

    Instead of tracking raw face positions (which jitter even with EMA), this
    computes a stabilized crop window that only moves when the face exits an
    inner "dead zone" region. The result is inherently stable output with far
    fewer keyframe entries.

    Args:
        face_bbox_timeline (list): List of (x1, y1, x2, y2) tuples or None per frame.
        video_width (int): Width of video in pixels (default 640).
        video_height (int): Height of video in pixels (default 360).
        face_scenes (list|None): List of (start_frame, end_frame) tuples for scene
            boundaries. Crop snaps instantly at scene cuts.
        speaker_track_ids (list|None): Per-frame active speaker track ID. When the
            track ID changes, the crop snaps instantly (speaker switch = hard cut).
        deadzone_ratio (float): Fraction of crop dimensions for the inner dead zone.
            0.10 means face can move within 10% of crop before triggering movement.
        smoothing (float): Smoothing factor for crop movement (0..1). Higher = faster.
            0.25 gives ~2.5-frame half-life.
        pixel_tolerance (int): RLE compression tolerance in pixels. Tight (3px)
            because the dead zone already eliminates jitter.
        min_speaker_hold_frames (int): Minimum frames a speaker must hold before
            a switch is committed. Shorter segments are treated as noise and
            merged into the surrounding stable speaker. Default 15 (~0.5s at 30fps).

    Returns:
        tuple: (compressed, scene_cuts) where:
            - compressed: List of [crop_x, crop_y, frame_count] entries.
              crop_x, crop_y are stabilized crop window center in pixel space.
              No-face sentinel: [-1, -1, frame_count] (only before first face).
              After first face, no-face gaps hold the last crop position.
            - scene_cuts: List of frame indices where the crop snapped due to a
              scene boundary or speaker switch (hard cut, no easing).
    """
    if not face_bbox_timeline:
        return [], []

    # Debounce rapid speaker-ID flickers before processing
    if speaker_track_ids and min_speaker_hold_frames > 1:
        speaker_track_ids = debounce_speaker_ids(
            speaker_track_ids, min_hold_frames=min_speaker_hold_frames
        )

    # 9:16 crop dimensions within the video frame
    crop_w = video_height * 9.0 / 16.0
    crop_h = float(video_height)

    # Dead zone: inner region where face movement doesn't trigger crop movement
    dz_half_w = crop_w * deadzone_ratio / 2.0
    dz_half_h = crop_h * deadzone_ratio / 2.0

    # Clamp bounds for crop center
    min_cx = crop_w / 2.0
    max_cx = video_width - crop_w / 2.0
    min_cy = crop_h / 2.0
    max_cy = video_height - crop_h / 2.0

    # Build scene boundary set for O(1) lookup
    scene_starts = set()
    if face_scenes:
        for start, _end in face_scenes:
            scene_starts.add(start)

    def clamp_crop(cx, cy):
        cx = max(min_cx, min(max_cx, cx))
        cy = max(min_cy, min(max_cy, cy))
        return cx, cy

    def bbox_center(bbox):
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    # Per-frame crop position computation
    per_frame = []
    scene_cut_frames = []
    crop_cx, crop_cy = None, None
    initialized = False
    prev_track_id = None

    for frame_idx, bbox in enumerate(face_bbox_timeline):
        face = bbox_center(bbox)
        is_scene_boundary = frame_idx in scene_starts

        # Detect speaker switch: track ID changed from previous frame
        is_speaker_switch = False
        if speaker_track_ids and frame_idx < len(speaker_track_ids):
            cur_track_id = speaker_track_ids[frame_idx]
            if (
                initialized
                and cur_track_id is not None
                and prev_track_id is not None
                and cur_track_id != prev_track_id
            ):
                is_speaker_switch = True
            if cur_track_id is not None:
                prev_track_id = cur_track_id

        should_snap = is_scene_boundary or is_speaker_switch

        if face is None:
            # No face detected
            if not initialized:
                per_frame.append((-1.0, -1.0))
            else:
                per_frame.append((crop_cx, crop_cy))
            continue

        if not initialized:
            # First face ever: snap instantly
            crop_cx, crop_cy = clamp_crop(face[0], face[1])
            initialized = True
            per_frame.append((crop_cx, crop_cy))
            continue

        if should_snap:
            scene_cut_frames.append(frame_idx)

        face_x, face_y = face

        # Check if face is within dead zone
        dx = face_x - crop_cx
        dy = face_y - crop_cy

        need_move_x = abs(dx) > 0
        need_move_y = abs(dy) > 0

        if not need_move_x and not need_move_y:
            # Face within dead zone — hold position
            per_frame.append((crop_cx, crop_cy))
            continue

        # Face exited dead zone — smooth move toward target
        target_cx = crop_cx
        target_cy = crop_cy

        if need_move_x:
            if dx > 0:
                target_cx = face_x - dz_half_w
            else:
                target_cx = face_x + dz_half_w

        if need_move_y:
            if dy > 0:
                target_cy = face_y - dz_half_h
            else:
                target_cy = face_y + dz_half_h

        crop_cx += smoothing * (target_cx - crop_cx)
        crop_cy += smoothing * (target_cy - crop_cy)
        crop_cx, crop_cy = clamp_crop(crop_cx, crop_cy)
        per_frame.append((crop_cx, crop_cy))

    # RLE-compress per-frame positions
    def coords_close(a, b, tol):
        return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol

    compressed = []
    current = per_frame[0]
    count = 1

    for pos in per_frame[1:]:
        if coords_close(pos, current, pixel_tolerance):
            count += 1
        else:
            compressed.append([current[0], current[1], count])
            current = pos
            count = 1

    compressed.append([current[0], current[1], count])
    return compressed, scene_cut_frames
