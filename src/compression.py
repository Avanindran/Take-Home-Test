"""
Run-length encoding utilities for coordinate and frame compression.

These utilities compress frame-by-frame data into compact run-length
encoded representations, reducing storage and making it easier to
identify stable segments vs. transitions.
"""


def compress_crop_coordinates(frame_by_frame_coords, pixel_tolerance=5):
    """
    Compress frame-by-frame crop coordinates into runs of similar values.

    Uses a tolerance to merge coordinates that differ by only a few pixels,
    preventing micro-oscillations from smoothing from creating many
    tiny segments.

    Args:
        frame_by_frame_coords (list): List of (left, right) tuples for each frame.
        pixel_tolerance (int): Maximum pixel difference to consider coordinates "same".
                               Default 5 pixels handles smoothing noise.

    Returns:
        list: List of (left, right, count) tuples, where count is the number of
              consecutive frames that use similar coordinates (within tolerance).
    """
    if not frame_by_frame_coords:
        return []

    def coords_similar(c1, c2, tol):
        """Check if two coordinate pairs are within tolerance."""
        return abs(c1[0] - c2[0]) <= tol and abs(c1[1] - c2[1]) <= tol

    compressed = []
    current_coords = frame_by_frame_coords[0]
    current_count = 1

    for coords in frame_by_frame_coords[1:]:
        if coords_similar(coords, current_coords, pixel_tolerance):
            current_count += 1
        else:
            compressed.append((current_coords[0], current_coords[1], current_count))
            current_coords = coords
            current_count = 1

    compressed.append((current_coords[0], current_coords[1], current_count))
    return compressed


def group_consecutive_frames(frame_indices):
    """
    Group consecutive frame indices into tuples of (start_frame, count).

    Args:
        frame_indices: List of frame indices (e.g., [0, 1, 2, 45, 46, 47, 120, 121, 122])

    Returns:
        List of tuples (start_frame, count) representing consecutive groups
        (e.g., [(0, 3), (45, 3), (120, 3)])
    """
    if not frame_indices:
        return []

    sorted_frames = sorted(frame_indices)
    groups = []

    current_start = sorted_frames[0]
    current_count = 1

    for i in range(1, len(sorted_frames)):
        if sorted_frames[i] == sorted_frames[i - 1] + 1:
            current_count += 1
        else:
            groups.append((current_start, current_count))
            current_start = sorted_frames[i]
            current_count = 1

    groups.append((current_start, current_count))
    return groups
