# Camera Tracking Stabilizer

A dead-zone camera tracking system for portrait (9:16) video output. Given per-frame face bounding boxes, the tracker computes a smooth, stable crop position that keeps the speaker's face properly framed within a vertical crop window.

The core algorithm uses a **dead-zone** approach: the crop window only moves when the face exits an inner region (the dead zone). This prevents the crop from chasing every small face movement and produces inherently stable output. When the face does exit the dead zone, an **exponential smoothing** filter produces a gradual, natural-looking pan. Scene cuts and speaker switches trigger an instant snap rather than a smooth pan.

## Quick Start

```bash
python -m venv .venv

# Linux / macOS:
source .venv/bin/activate

# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
```

## Project Structure

```
camera-tracking-test/
├── README.md
├── requirements.txt
├── run.py                       # CLI runner — runs tracker and prints output
├── visualize.py                 # Renders cropped portrait video from tracker output
├── src/
│   ├── __init__.py
│   ├── tracker.py               # Dead-zone tracking algorithm
│   ├── debouncer.py             # Speaker ID debouncer (stub — needs implementation)
│   └── compression.py           # RLE compression utilities
├── tests/
│   ├── __init__.py
│   ├── test_tracker.py
│   └── test_compression.py
└── sample_data/
    ├── clip_a.mp4
    ├── clip_a.json
    ├── clip_b.mp4
    └── clip_b.json
```

## Your Tasks

### 1. Bug Finding and Fixing

There are bugs in `src/tracker.py` that cause the crop output to behave incorrectly. Use the provided tools and sample data to identify the issues, find the root causes, and fix them.

### 2. Feature Implementation

`src/debouncer.py` contains a stub function (`debounce_speaker_ids`) that needs to be implemented. Read the docstring carefully for the full specification.

### 3. Tests

Write regression tests for the bugs you find. Your tests should fail on the original buggy code and pass on your fixed version. Also write tests for your debouncer implementation.

## What to Submit

This repo was provided as a GitHub template. Push your changes to the repo you created from it, then share the link with us. Include a brief writeup (in a NOTES.md, in this README, or in your commit messages) covering:

- What you found (root cause of each bug)
- What you fixed and why
- Any design decisions in your debouncer implementation
- Anything else you noticed or would improve given more time

## Time

Please spend no more than **2-3 hours**. We value a working solution over a perfect one.

## What We're Evaluating

- **Does it work?** Did you ship working fixes and a correct debouncer?
- **Debugging process**: How did you find and diagnose the bugs?
- **Code quality**: Is your code clean, well-tested, and consistent with the existing style?
- **Communication**: Did you document your findings and reasoning?
