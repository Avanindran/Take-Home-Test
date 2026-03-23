#!/usr/bin/env python3
"""
CLI runner for the camera tracking stabilizer.

Usage:
    python run.py sample_data/clip_a.json
    python run.py sample_data/clip_b.json --verbose
"""

import argparse
import json
import sys

from src.tracker import track_face_crop


def load_data(path):
    """Load face tracking data from a JSON file."""
    with open(path) as f:
        return json.load(f)


def print_summary(compressed, scene_cuts, total_frames):
    """Print a summary of the tracking output."""
    print(f"\n{'=' * 60}")
    print(f"  Total frames processed:    {total_frames}")
    print(f"  Compressed segments:       {len(compressed)}")
    print(f"  Compression ratio:         {total_frames / max(len(compressed), 1):.1f}x")
    print(f"  Scene cuts detected:       {len(scene_cuts)}")
    if scene_cuts:
        print(f"  Scene cut frames:          {scene_cuts}")
    print(f"{'=' * 60}")

    if compressed:
        print("\n  First 5 segments:")
        for i, seg in enumerate(compressed[:5]):
            print(f"    [{i:3d}] crop=({seg[0]:7.1f}, {seg[1]:7.1f})  frames={seg[2]}")

        if len(compressed) > 10:
            print("    ...")
            print("\n  Last 5 segments:")
            for i, seg in enumerate(compressed[-5:], len(compressed) - 5):
                print(f"    [{i:3d}] crop=({seg[0]:7.1f}, {seg[1]:7.1f})  frames={seg[2]}")
        elif len(compressed) > 5:
            print("\n  Remaining segments:")
            for i, seg in enumerate(compressed[5:], 5):
                print(f"    [{i:3d}] crop=({seg[0]:7.1f}, {seg[1]:7.1f})  frames={seg[2]}")
    print()


def print_verbose(compressed):
    """Print all segments in detail."""
    print("\n  All segments:")
    frame_offset = 0
    for i, seg in enumerate(compressed):
        print(
            f"    [{i:3d}] frames {frame_offset:4d}-{frame_offset + seg[2] - 1:4d}  "
            f"crop=({seg[0]:7.1f}, {seg[1]:7.1f})  count={seg[2]}"
        )
        frame_offset += seg[2]
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run camera tracking stabilizer on face bbox data"
    )
    parser.add_argument("input", help="Path to input JSON file")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print all segments"
    )
    parser.add_argument(
        "--compare", "-c", help="Path to expected output JSON for comparison"
    )
    args = parser.parse_args()

    # Load input data
    try:
        data = load_data(args.input)
    except FileNotFoundError:
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.input}: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert bbox lists to tuples (JSON gives us lists)
    bboxes = [tuple(b) if b is not None else None for b in data["face_bbox_timeline"]]
    face_scenes = [tuple(s) for s in data.get("face_scenes", [])] if data.get("face_scenes") else None
    speaker_ids = data.get("speaker_track_ids")

    total_frames = len(bboxes)
    print(f"\nProcessing: {args.input}")
    print(f"  Frames: {total_frames}, Video: {data['video_width']}x{data['video_height']}")
    if data.get("description"):
        print(f"  Scenario: {data['description']}")

    # Run tracker
    try:
        compressed, scene_cuts = track_face_crop(
            bboxes,
            video_width=data["video_width"],
            video_height=data["video_height"],
            face_scenes=face_scenes,
            speaker_track_ids=speaker_ids,
        )
    except NotImplementedError:
        print("  Note: debouncer not implemented, running without speaker debouncing...")
        compressed, scene_cuts = track_face_crop(
            bboxes,
            video_width=data["video_width"],
            video_height=data["video_height"],
            face_scenes=face_scenes,
            speaker_track_ids=speaker_ids,
            min_speaker_hold_frames=0,
        )

    # Display results
    print_summary(compressed, scene_cuts, total_frames)

    if args.verbose:
        print_verbose(compressed)

    # Compare with expected output if provided
    if args.compare:
        try:
            with open(args.compare) as f:
                expected = json.load(f)
            expected_compressed = expected.get("compressed", [])

            if len(compressed) != len(expected_compressed):
                print(f"  DIFF: Segment count differs: got {len(compressed)}, expected {len(expected_compressed)}")
            else:
                diffs = 0
                for i, (got, exp) in enumerate(zip(compressed, expected_compressed)):
                    if abs(got[0] - exp[0]) > 3 or abs(got[1] - exp[1]) > 3 or got[2] != exp[2]:
                        if diffs < 10:
                            print(
                                f"  DIFF at segment {i}: "
                                f"got ({got[0]:.1f}, {got[1]:.1f}, {got[2]}) "
                                f"expected ({exp[0]:.1f}, {exp[1]:.1f}, {exp[2]})"
                            )
                        diffs += 1
                if diffs == 0:
                    print("  MATCH: Output matches expected values")
                else:
                    print(f"  Total differences: {diffs}")
        except FileNotFoundError:
            print(f"  Warning: Expected output file not found: {args.compare}")


if __name__ == "__main__":
    main()
