#!/usr/bin/env python3
"""
Visualization tool for the camera tracking stabilizer.

Takes a video file and its corresponding sample data JSON, runs the tracker,
and renders the cropped portrait output as a video. Useful for visually
verifying that the dead-zone tracking produces smooth, stable output.

Usage:
    python visualize.py sample_data/clip_a.mp4 sample_data/clip_a.json
    python visualize.py sample_data/clip_b.mp4 sample_data/clip_b.json -o output.mp4
    python visualize.py sample_data/clip_a.mp4 sample_data/clip_a.json --show-frame-number
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import cv2

from src.tracker import track_face_crop


def load_data(path):
    """Load face tracking data from a JSON file."""
    with open(path) as f:
        return json.load(f)


def decompress_rle(compressed):
    """
    Decompress RLE-encoded crop coordinates to per-frame values.

    Args:
        compressed: List of [crop_cx, crop_cy, frame_count] entries.

    Returns:
        List of (crop_cx, crop_cy) tuples, one per frame.
    """
    per_frame = []
    for cx, cy, count in compressed:
        for _ in range(count):
            per_frame.append((cx, cy))
    return per_frame


def parse_resolution(resolution_str):
    """
    Parse a resolution string like '720x1280' into (width, height).

    Args:
        resolution_str: String in 'WIDTHxHEIGHT' format.

    Returns:
        Tuple of (width, height) as integers.
    """
    parts = resolution_str.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid resolution format: {resolution_str!r} (expected WxH)")
    return int(parts[0]), int(parts[1])


def crop_frame(frame, crop_pos, crop_w, crop_h, center_cx, center_cy,
               scale_x, scale_y, vid_width, vid_height, out_w, out_h,
               show_frame_number, frame_idx):
    """Extract and resize a single crop from a video frame."""
    crop_cx, crop_cy = crop_pos

    if crop_cx < 0 and crop_cy < 0:
        crop_cx = center_cx
        crop_cy = center_cy
    else:
        crop_cx *= scale_x
        crop_cy *= scale_y

    left = max(0.0, min(crop_cx - crop_w / 2.0, vid_width - crop_w))
    top = max(0.0, min(crop_cy - crop_h / 2.0, vid_height - crop_h))

    x1 = max(0, int(round(left)))
    y1 = max(0, int(round(top)))
    x2 = min(vid_width, int(round(left + crop_w)))
    y2 = min(vid_height, int(round(top + crop_h)))

    cropped = frame[y1:y2, x1:x2]
    resized = cv2.resize(cropped, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

    if show_frame_number:
        text = f"Frame {frame_idx}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = out_w / 720.0
        thickness = max(1, int(2 * font_scale))
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = out_w - text_size[0] - 10
        text_y = text_size[1] + 10
        cv2.rectangle(
            resized,
            (text_x - 5, text_y - text_size[1] - 5),
            (text_x + text_size[0] + 5, text_y + 5),
            (0, 0, 0), -1,
        )
        cv2.putText(resized, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

    return resized


def main():
    parser = argparse.ArgumentParser(
        description="Visualize camera tracking by rendering cropped portrait video"
    )
    parser.add_argument("video", help="Path to input video file (MP4)")
    parser.add_argument("data", help="Path to sample data JSON file")
    parser.add_argument(
        "--output", "-o", default="output.mp4", help="Output MP4 path (default: output.mp4)"
    )
    parser.add_argument(
        "--resolution",
        default="720x1280",
        help="Output portrait resolution as WxH (default: 720x1280)",
    )
    parser.add_argument(
        "--show-frame-number",
        action="store_true",
        help="Overlay frame number on each output frame (useful for debugging)",
    )
    args = parser.parse_args()

    try:
        out_w, out_h = parse_resolution(args.resolution)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = load_data(args.data)
    except FileNotFoundError:
        print(f"Error: File not found: {args.data}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.data}: {e}", file=sys.stderr)
        sys.exit(1)

    json_width = data["video_width"]
    json_height = data["video_height"]

    bboxes = [tuple(b) if b is not None else None for b in data["face_bbox_timeline"]]
    face_scenes = (
        [tuple(s) for s in data["face_scenes"]] if data.get("face_scenes") else None
    )
    speaker_ids = data.get("speaker_track_ids")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {args.video}", file=sys.stderr)
        sys.exit(1)

    vid_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    vid_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\nVideo:  {args.video}")
    print(f"  Resolution: {vid_width}x{vid_height}, FPS: {fps:.2f}, Frames: {vid_frame_count}")
    print(f"  JSON dimensions: {json_width}x{json_height}, Bbox entries: {len(bboxes)}")

    scale_x = vid_width / json_width
    scale_y = vid_height / json_height
    if abs(scale_x - 1.0) > 0.001 or abs(scale_y - 1.0) > 0.001:
        print(f"  Scale factors: x={scale_x:.4f}, y={scale_y:.4f}")

    print(f"\nRunning tracker...")
    try:
        compressed, scene_cuts = track_face_crop(
            bboxes, video_width=json_width, video_height=json_height,
            face_scenes=face_scenes, speaker_track_ids=speaker_ids,
        )
    except NotImplementedError:
        print("  Note: debouncer not implemented, running without speaker debouncing...")
        compressed, scene_cuts = track_face_crop(
            bboxes, video_width=json_width, video_height=json_height,
            face_scenes=face_scenes, speaker_track_ids=speaker_ids,
            min_speaker_hold_frames=0,
        )

    print(f"  Compressed segments: {len(compressed)}")
    print(f"  Scene cuts: {len(scene_cuts)}")

    per_frame_crops = decompress_rle(compressed)

    crop_w = vid_height * 9.0 / 16.0
    crop_h = float(vid_height)
    center_cx = vid_width / 2.0
    center_cy = vid_height / 2.0
    frames_to_process = min(vid_frame_count, len(per_frame_crops))

    # Step 1: Write cropped frames to a temp AVI using OpenCV
    # XVID + AVI is the most reliable codec across all platforms
    tmp_fd, tmp_video = tempfile.mkstemp(suffix=".avi")
    os.close(tmp_fd)

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        # Fallback: try mp4v
        os.remove(tmp_video)
        tmp_fd, tmp_video = tempfile.mkstemp(suffix=".mp4")
        os.close(tmp_fd)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_video, fourcc, fps, (out_w, out_h))
    if not writer.isOpened():
        print(f"Error: Cannot create output video", file=sys.stderr)
        os.remove(tmp_video)
        cap.release()
        sys.exit(1)

    print(f"\nRendering to {args.output} ({out_w}x{out_h})...")

    frame_idx = 0
    try:
        while frame_idx < frames_to_process:
            ret, frame = cap.read()
            if not ret:
                break
            resized = crop_frame(
                frame, per_frame_crops[frame_idx], crop_w, crop_h,
                center_cx, center_cy, scale_x, scale_y,
                vid_width, vid_height, out_w, out_h,
                args.show_frame_number, frame_idx,
            )
            writer.write(resized)
            frame_idx += 1
            if frame_idx % 100 == 0:
                print(f"  Processed {frame_idx}/{frames_to_process} frames...")
    except KeyboardInterrupt:
        print(f"\n  Interrupted at frame {frame_idx}.")
    finally:
        cap.release()
        writer.release()

    print(f"  Wrote {frame_idx} frames.")

    # Step 2: Use FFmpeg to re-encode to h264 + mux audio from source
    if shutil.which("ffmpeg"):
        print(f"  Adding audio from {args.video}...")
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_video,
                "-i", args.video,
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0?",
                "-shortest",
                args.output,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.remove(tmp_video)
        if result.returncode != 0:
            print(f"  Warning: FFmpeg failed. Output saved without audio.")
            # Re-render without audio as fallback
            os.rename(tmp_video, args.output) if os.path.exists(tmp_video) else None
    else:
        # No FFmpeg — just rename the temp file
        os.rename(tmp_video, args.output)
        ext = os.path.splitext(args.output)[1]
        if ext != os.path.splitext(tmp_video)[1]:
            print(f"  Note: output is AVI format (ffmpeg not found for mp4 conversion)")

    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
