"""Speaker ID debouncing for stable camera tracking.

Removes rapid speaker-ID bounces that cause jarring crop window snaps.
"""


def debounce_speaker_ids(speaker_track_ids, min_hold_frames=15):
    """
    Remove rapid speaker-ID bounces shorter than min_hold_frames.

    Speaker detection sometimes flickers the active-speaker label during
    crosstalk or brief classification uncertainty, producing 1-10 frame
    segments that cause jarring rapid-fire crop snaps. This pre-filter
    replaces those short segments with the surrounding stable speaker ID
    so the downstream dead-zone tracker never sees them.
    
    Algorithm:
      1. Run-length encode the raw IDs into (track_id, start, length) runs.
      2. For any run shorter than min_hold_frames, replace it with the
         previous stable run's ID (or the next stable run if it's the first).
      3. Expand back to a per-frame list.

    Args:
        speaker_track_ids: Per-frame list of speaker IDs (int or None).
            None means no speaker detected at that frame.
        min_hold_frames: Minimum frames a speaker must hold to be "stable".

    Returns:
        Same-length list with short flicker runs replaced by nearest stable ID.
        None segments are never modified.
    """
    if not speaker_track_ids:
        return speaker_track_ids
    
    # First, let's run-length encode to group consecutive identical IDs
    # This makes it easier to identify and process short flicker segments
    runs = []
    current_id = speaker_track_ids[0]
    current_start = 0
    current_length = 1
    
    for i in range(1, len(speaker_track_ids)):
        if speaker_track_ids[i] == current_id:
            current_length += 1
        else:
            runs.append((current_id, current_start, current_length))
            current_id = speaker_track_ids[i]
            current_start = i
            current_length = 1
    
    # Don't forget the last run
    runs.append((current_id, current_start, current_length))
    
    # Now process each run to remove short flickers
    processed_runs = []
    i = 0
    while i < len(runs):
        track_id, start, length = runs[i]
        
        # If this run is long enough or is None, keep it as-is
        if length >= min_hold_frames or track_id is None:
            processed_runs.append((track_id, start, length))
            i += 1
        else:
            # This run is too short - need to merge it with surrounding stable runs
            # Let's find the nearest stable speaker ID to replace this flicker
            
            # Look backwards for a stable run (non-None and long enough)
            prev_stable_id = None
            for j in range(i - 1, -1, -1):
                prev_id, _, prev_length = runs[j]
                if prev_id is not None and prev_length >= min_hold_frames:
                    prev_stable_id = prev_id
                    break
            
            # Look forwards for a stable run
            next_stable_id = None
            for j in range(i + 1, len(runs)):
                next_id, _, next_length = runs[j]
                if next_id is not None and next_length >= min_hold_frames:
                    next_stable_id = next_id
                    break
            
            # Decide which stable ID to use for replacement
            replacement_id = None
            if prev_stable_id is not None:
                replacement_id = prev_stable_id
            elif next_stable_id is not None:
                replacement_id = next_stable_id
            # If no stable neighbors exist, keep the original (edge case)
            else:
                processed_runs.append((track_id, start, length))
                i += 1
                continue
            
            # Now merge this short run with any surrounding runs of the same replacement ID
            merge_start = start
            merge_length = length
            
            # Look backwards for runs with the same replacement ID
            j = i - 1
            while j >= 0:
                prev_id, prev_start, prev_length = runs[j]
                if prev_id == replacement_id:
                    merge_start = prev_start
                    merge_length += prev_length
                    j -= 1
                else:
                    break
            
            # Look forwards for runs with the same replacement ID
            k = i + 1
            while k < len(runs):
                next_id, next_start, next_length = runs[k]
                if next_id == replacement_id:
                    merge_length += next_length
                    k += 1
                else:
                    break
            
            # Add the merged run with the replacement ID
            processed_runs.append((replacement_id, merge_start, merge_length))
            
            # Skip all the runs we just processed
            i = k
    
    # Finally, expand back to a per-frame list
    result = [None] * len(speaker_track_ids)
    for track_id, start, length in processed_runs:
        for j in range(start, start + length):
            result[j] = track_id
    
    return result