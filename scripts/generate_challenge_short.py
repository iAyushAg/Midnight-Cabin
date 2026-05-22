#!/usr/bin/env python3
"""
generate_challenge_short.py — Midnight Cabin "Challenge Short" Generator

This script creates a single viral-engineered Short with:
- Visible countdown timer burning on screen
- Hook: "Try to fall asleep before this ends"
- Participation mechanic that drives saves, shares, and comments
- Engineered for 500K–5M views based on the challenge format's track record

Run this ONCE manually per niche, then post to:
  1. YouTube Shorts
  2. TikTok (same file)
  3. Instagram Reels (same file)

Usage:
  python3 scripts/generate_challenge_short.py --niche rain --duration 28
  python3 scripts/generate_challenge_short.py --niche brown_noise --duration 28
  python3 scripts/generate_challenge_short.py --niche fireplace --duration 28

Output: output/challenge_short_<niche>.mp4
"""

import argparse
import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_DIR = BASE_DIR / "video"
LIBRARY_DIR = VIDEO_DIR / "library"

OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# ARGUMENT PARSING
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Generate a viral challenge Short")
parser.add_argument("--niche", default="rain",
    choices=["rain", "fireplace", "brown_noise", "ocean_waves", "river", "soft_wind", "night_forest", "thunder"],
    help="Sound niche for this challenge Short")
parser.add_argument("--duration", type=int, default=28,
    help="Short duration in seconds (default 28 — under 30s gets stronger algo push)")
parser.add_argument("--source-video", default=None,
    help="Path to source video (uses bg_animated.mp4 or library image if not specified)")
args = parser.parse_args()

NICHE = args.niche
DURATION = args.duration
OUTPUT_FILE = str(OUTPUT_DIR / f"challenge_short_{NICHE}.mp4")

print(f"Generating Challenge Short: niche={NICHE}, duration={DURATION}s")
print(f"Output: {OUTPUT_FILE}")

# ─────────────────────────────────────────────
# CHALLENGE HOOKS — per niche
# Each has a primary challenge hook and an alternate
# The format: "(verb) before this ends" = participation bait
# ─────────────────────────────────────────────
CHALLENGE_HOOKS = {
    "rain": [
        "Try to fall asleep before this ends",
        "Stay awake for all 28 seconds. Go.",
        "Bet you close your eyes before it ends",
    ],
    "fireplace": [
        "Try to fall asleep before this ends",
        "See if you can stay tense listening to this",
        "Bet you feel safer before this ends",
    ],
    "brown_noise": [
        "Try to keep one anxious thought for 28 seconds",
        "Bet your brain goes quiet before this ends",
        "Try to stay stressed while this plays",
    ],
    "ocean_waves": [
        "Try to fall asleep before this ends",
        "Count how many breaths you take. Bet it slows.",
        "Try to stay tense for all 28 seconds",
    ],
    "river": [
        "Try to fall asleep before this ends",
        "Try to keep a worried thought for 28 seconds",
        "Bet your shoulders drop before this ends",
    ],
    "soft_wind": [
        "Try to fall asleep before this ends",
        "Try to stay anxious for all 28 seconds",
        "Bet you exhale before this ends",
    ],
    "night_forest": [
        "Try to fall asleep before this ends",
        "Try to feel unsafe listening to this",
        "Bet your body relaxes before it ends",
    ],
    "thunder": [
        "Try to fall asleep before this ends",
        "Bet you feel cozy before this ends",
        "Try to feel tense during a thunderstorm",
    ],
}

# Bottom CTA — drives saves and comments
BOTTOM_CTAS = {
    "rain": "Save for 3am",
    "fireplace": "Save for tonight",
    "brown_noise": "Save when brain's loud",
    "ocean_waves": "Save for tonight",
    "river": "Save for 3am",
    "soft_wind": "Save for tonight",
    "night_forest": "Save for tonight",
    "thunder": "Save for tonight",
}

# Comment bait — shown at second 20, drives engagement signal
COMMENT_BAITS = {
    "rain": "Reply: did you make it?",
    "fireplace": "Comment: made it or fell asleep?",
    "brown_noise": "Comment: thoughts gone yet?",
    "ocean_waves": "Comment: made it or gone?",
    "river": "Comment: did you make it?",
    "soft_wind": "Comment: still awake?",
    "night_forest": "Comment: made it?",
    "thunder": "Comment: cozy yet?",
}

hook_text = CHALLENGE_HOOKS[NICHE][0]
bottom_cta = BOTTOM_CTAS[NICHE]
comment_bait = COMMENT_BAITS[NICHE]

print(f"Hook: {hook_text}")
print(f"CTA: {bottom_cta}")

# ─────────────────────────────────────────────
# FIND VIDEO SOURCE
# ─────────────────────────────────────────────
def find_source_video():
    # 1. Explicit path
    if args.source_video and os.path.exists(args.source_video):
        return args.source_video, True

    # 2. Animated bg (niche-matched)
    visual_meta_path = PERSISTENT_DIR / "current_visual.json"
    animated_niche = None
    if visual_meta_path.exists():
        try:
            with open(visual_meta_path) as f:
                vm = json.load(f)
            animated_niche = vm.get("primary") or vm.get("primary_category")
        except Exception:
            pass

    for bg_path in [BASE_DIR / "video" / "bg_animated.mp4",
                    PERSISTENT_DIR / "bg_animated.mp4"]:
        if bg_path.exists() and (animated_niche is None or animated_niche == NICHE):
            print(f"Using animated bg: {bg_path}")
            return str(bg_path), True

    # 3. Library still image for this niche
    niche_folder = LIBRARY_DIR / NICHE
    search_dirs = [niche_folder, LIBRARY_DIR]
    for folder in search_dirs:
        if folder.exists():
            images = list(folder.glob("*.jpg")) + list(folder.glob("*.jpeg")) + list(folder.glob("*.png"))
            if images:
                img = random.choice(images)
                print(f"Using library image: {img}")
                return str(img), False  # needs loop conversion

    # 4. bg.jpg fallback
    bg_jpg = VIDEO_DIR / "bg.jpg"
    if bg_jpg.exists():
        print("Using bg.jpg fallback")
        return str(bg_jpg), False

    # 5. Main output video
    main_video = OUTPUT_DIR / "video.mp4"
    if main_video.exists():
        print("Using main output video")
        return str(main_video), True

    raise FileNotFoundError(
        "No video source found. Run the main pipeline first, or place an image in video/library/{niche}/\n"
        "You can also specify --source-video /path/to/video.mp4"
    )

raw_source, is_video = find_source_video()

# If source is a still image, convert to a loopable short video
if not is_video:
    TEMP_VIDEO = str(OUTPUT_DIR / f"challenge_bg_{NICHE}.mp4")
    print(f"Converting still image to video: {raw_source}")

    # Niche colour grades
    NICHE_GRADE = {
        "rain":         "eq=contrast=1.05:saturation=0.75:brightness=-0.04,colorbalance=bs=0.04",
        "fireplace":    "eq=contrast=1.08:saturation=1.15:brightness=0.02,colorbalance=rs=0.06",
        "river":        "eq=contrast=1.04:saturation=0.85:brightness=-0.02,colorbalance=gs=0.03",
        "ocean_waves":  "eq=contrast=1.06:saturation=0.80:brightness=-0.03,colorbalance=bs=0.03",
        "soft_wind":    "eq=contrast=1.03:saturation=0.90:brightness=-0.01",
        "night_forest": "eq=contrast=1.05:saturation=0.80:brightness=-0.04,colorbalance=gs=0.02",
        "brown_noise":  "eq=contrast=1.04:saturation=0.65:brightness=-0.03",
        "thunder":      "eq=contrast=1.10:saturation=0.60:brightness=-0.06,colorbalance=bs=0.03",
    }
    grade = NICHE_GRADE.get(NICHE, "eq=contrast=1.04:saturation=0.85")

    r = subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", raw_source,
        "-t", str(DURATION + 5),
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{grade},format=yuv420p",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-r", "30",
        TEMP_VIDEO
    ], capture_output=True, text=True)

    if r.returncode != 0:
        print("Image-to-video conversion failed:", r.stderr[-500:])
        sys.exit(1)

    VIDEO_SOURCE = TEMP_VIDEO
else:
    VIDEO_SOURCE = raw_source

# ─────────────────────────────────────────────
# FIND AUDIO SOURCE
# ─────────────────────────────────────────────
MAIN_VIDEO = OUTPUT_DIR / "video.mp4"
if not MAIN_VIDEO.exists():
    print("WARNING: No main video.mp4 found for audio. The Short will be silent.")
    print("Run the main pipeline first to generate audio, then re-run this script.")
    AUDIO_SOURCE = None
else:
    AUDIO_SOURCE = str(MAIN_VIDEO)

# Good start offset per niche (avoid silence at beginning)
START_OFFSETS = {
    "rain": 45, "fireplace": 30, "river": 60,
    "ocean_waves": 90, "soft_wind": 30, "night_forest": 90,
    "brown_noise": 10, "thunder": 45,
}
START = START_OFFSETS.get(NICHE, 45)

# ─────────────────────────────────────────────
# FONT
# ─────────────────────────────────────────────
def find_font():
    system = platform.system()
    if system == "Darwin":
        for p in [
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Verdana.ttf",
        ]:
            if os.path.exists(p): return p
    else:
        for p in [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            if os.path.exists(p): return p
    return ""

FONT = find_font()
font_attr = f":fontfile='{FONT.replace(':', chr(92)+':').replace(chr(39), chr(92)+chr(39))}'" if FONT else ""
print(f"Font: {FONT or 'ffmpeg default'}")

# ─────────────────────────────────────────────
# FFMPEG DRAWTEXT — the magic
#
# Layout (top to bottom on 1080x1920):
#   y=120   — challenge hook text (large, bold)
#   y=center — countdown timer (massive, impossible to ignore)
#   y=3h/4  — comment bait (appears at t=20s)
#   y=h-90  — bottom CTA (save trigger)
#   y=h-45  — channel handle
#
# The timer uses ffmpeg's built-in `%{pts}` expression to show
# DURATION minus elapsed time = countdown
# ─────────────────────────────────────────────

def esc(text):
    """Escape text for ffmpeg drawtext filter."""
    return (text
        .replace("\\", "\\\\")
        .replace("'",  "\\'")
        .replace(":", "\\:")
        .replace("%",  "\\%"))

hook_esc    = esc(hook_text)
cta_esc     = esc(bottom_cta)
bait_esc    = esc(comment_bait)
handle_esc  = esc("@midnightcabins")

# Countdown: shows remaining seconds as integer
# pts\:0 gives elapsed seconds from clip start
# We subtract from DURATION to count DOWN
timer_expr  = f"{DURATION}-trunc(t)"

# Comment bait appears at t=20, fades in over 1s
# alpha = min(1, max(0, t-20))
bait_alpha  = "if(gte(t\\,20)\\,min(1\\,(t-20))\\,0)"

# Hook fades out after t=5 (viewer has read it, timer takes over attention)
hook_alpha  = "if(lte(t\\,4)\\,1\\,if(lte(t\\,6)\\,max(0\\,(6-t)/2)\\,0))"

niche_grade = {
    "rain":         "eq=contrast=1.05:saturation=0.75:brightness=-0.04,colorbalance=bs=0.04",
    "fireplace":    "eq=contrast=1.08:saturation=1.15:brightness=0.02,colorbalance=rs=0.06",
    "river":        "eq=contrast=1.04:saturation=0.85:brightness=-0.02,colorbalance=gs=0.03",
    "ocean_waves":  "eq=contrast=1.06:saturation=0.80:brightness=-0.03,colorbalance=bs=0.03",
    "soft_wind":    "eq=contrast=1.03:saturation=0.90:brightness=-0.01",
    "night_forest": "eq=contrast=1.05:saturation=0.80:brightness=-0.04,colorbalance=gs=0.02",
    "brown_noise":  "eq=contrast=1.04:saturation=0.65:brightness=-0.03",
    "thunder":      "eq=contrast=1.10:saturation=0.60:brightness=-0.06,colorbalance=bs=0.03",
}.get(NICHE, "eq=contrast=1.04:saturation=0.85")

# Build the full video filter chain
vf_parts = [
    "scale=1080:1920:force_original_aspect_ratio=increase",
    "crop=1080:1920",
    niche_grade,
    # Challenge hook — fades out after 6s
    (f"drawtext=text='{hook_esc}'{font_attr}"
     f":fontsize=52:fontcolor=white"
     f":x=(w-text_w)/2:y=120"
     f":box=1:boxcolor=black@0.5:boxborderw=20"
     f":alpha='{hook_alpha}'"),
    # COUNTDOWN TIMER — the centrepiece, massive and unmissable
    (f"drawtext=text='%{{eif\\:{timer_expr}\\:d\\:2}}'{font_attr}"
     f":fontsize=220:fontcolor=white"
     f":x=(w-text_w)/2:y=(h-text_h)/2-80"
     f":box=1:boxcolor=black@0.25:boxborderw=30"
     f":shadowx=4:shadowy=4:shadowcolor=black@0.6"),
    # Comment bait — appears at 20s
    (f"drawtext=text='{bait_esc}'{font_attr}"
     f":fontsize=38:fontcolor=white@0.9"
     f":x=(w-text_w)/2:y=3*h/4"
     f":box=1:boxcolor=black@0.4:boxborderw=14"
     f":alpha='{bait_alpha}'"),
    # Save CTA — visible throughout
    (f"drawtext=text='{cta_esc}'{font_attr}"
     f":fontsize=42:fontcolor=white"
     f":x=(w-text_w)/2:y=h-160"
     f":box=1:boxcolor=black@0.5:boxborderw=16"),
    # Channel handle
    (f"drawtext=text='{handle_esc}'{font_attr}"
     f":fontsize=28:fontcolor=white@0.6"
     f":x=(w-text_w)/2:y=h-65"),
    "format=yuv420p",
]
vf = ",".join(vf_parts)

# ─────────────────────────────────────────────
# NICHE AUDIO EQ
# ─────────────────────────────────────────────
NICHE_EQ = {
    "rain":         "equalizer=f=200:width_type=o:width=2:g=1,equalizer=f=8000:width_type=o:width=2:g=-3",
    "fireplace":    "equalizer=f=100:width_type=o:width=2:g=3,equalizer=f=6000:width_type=o:width=2:g=-4",
    "river":        "equalizer=f=500:width_type=o:width=2:g=2,equalizer=f=8000:width_type=o:width=2:g=-2",
    "ocean_waves":  "equalizer=f=150:width_type=o:width=2:g=2,equalizer=f=7000:width_type=o:width=2:g=-3",
    "soft_wind":    "equalizer=f=300:width_type=o:width=2:g=1,equalizer=f=9000:width_type=o:width=2:g=-2",
    "night_forest": "equalizer=f=400:width_type=o:width=2:g=2,equalizer=f=8000:width_type=o:width=2:g=-2",
    "brown_noise":  "equalizer=f=100:width_type=o:width=2:g=2,equalizer=f=5000:width_type=o:width=2:g=-1",
    "thunder":      "equalizer=f=80:width_type=o:width=2:g=4,equalizer=f=8000:width_type=o:width=2:g=-5",
}
eq = NICHE_EQ.get(NICHE, "")
af = f"afade=t=in:st=0:d=1.5,{eq},volume=0.6" if eq else "afade=t=in:st=0:d=1.5,volume=0.6"

# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────
print(f"Rendering challenge Short ({DURATION}s)...")

if AUDIO_SOURCE:
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", VIDEO_SOURCE,
        "-ss", str(START), "-t", str(DURATION), "-i", AUDIO_SOURCE,
        "-t", str(DURATION),
        "-vf", vf,
        "-map", "0:v",
        "-map", "1:a",
        "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30", "-movflags", "+faststart",
        OUTPUT_FILE,
    ]
else:
    # Silent version — still useful for visual review
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", VIDEO_SOURCE,
        "-t", str(DURATION),
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-r", "30", "-movflags", "+faststart",
        OUTPUT_FILE,
    ]

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print("Render FAILED:")
    print(result.stderr[-1000:])
    sys.exit(1)

size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
print(f"\nChallenge Short rendered successfully!")
print(f"  File: {OUTPUT_FILE}")
print(f"  Size: {size_mb:.1f} MB")
print(f"  Duration: {DURATION}s")

# ─────────────────────────────────────────────
# UPLOAD INSTRUCTIONS
# ─────────────────────────────────────────────
TITLES = {
    "rain":         "Try to fall asleep before this ends 🌧️ #Shorts",
    "fireplace":    "Try to fall asleep before this ends 🔥 #Shorts",
    "brown_noise":  "Try to keep one anxious thought for 28 seconds 🧠 #Shorts",
    "ocean_waves":  "Try to fall asleep before this ends 🌊 #Shorts",
    "river":        "Try to fall asleep before this ends 🌊 #Shorts",
    "soft_wind":    "Try to stay tense while this plays 🍃 #Shorts",
    "night_forest": "Try to fall asleep before this ends 🌲 #Shorts",
    "thunder":      "Try to fall asleep before this ends ⛈️ #Shorts",
}

DESCRIPTIONS = {
    "rain": (
        "Drop a 🕯️ if you didn't make it.\n\n"
        "Full 8-10 hour version on @midnightcabins — no interruptions, no sudden sounds.\n\n"
        "#rain #sleepsounds #asmr #rainasmr #sleeptok #cozy #cozysounds #ambience"
    ),
    "fireplace": (
        "Drop a 🕯️ if you didn't make it.\n\n"
        "Full 8-10 hour version on @midnightcabins — no interruptions.\n\n"
        "#fireplace #cozy #sleepsounds #asmr #cozysounds #cabin #ambience"
    ),
    "brown_noise": (
        "Drop a 🕯️ if your brain went quiet.\n\n"
        "Full 8-10 hour version on @midnightcabins — for focus, sleep, or just turning the volume down.\n\n"
        "#brownnoise #adhd #focussounds #anxiety #studysounds #brainhacks"
    ),
    "ocean_waves": (
        "Drop a 🕯️ if you didn't make it.\n\n"
        "Full 8-10 hour version on @midnightcabins — no interruptions.\n\n"
        "#oceansounds #sleepsounds #waves #asmr #relaxing #ambience"
    ),
}

title = TITLES.get(NICHE, f"Try to fall asleep before this ends #Shorts")
description = DESCRIPTIONS.get(NICHE, (
    "Drop a 🕯️ if you didn't make it.\n\n"
    "Full 8-10 hour version on @midnightcabins — no interruptions, no sudden sounds.\n\n"
    "#sleepsounds #asmr #ambience #relaxing #cozy"
))

print("\n" + "="*60)
print("UPLOAD CHECKLIST")
print("="*60)
print(f"\n1. YOUTUBE SHORTS")
print(f"   Title: {title}")
print(f"   Description:\n{description}")
print(f"\n   After upload:")
print(f"   - Post this as pinned comment:")
print(f"     'Drop a 🕯️ below if you didn't make it. I read every one.'")
print(f"\n2. TIKTOK (same file, same title)")
print(f"   Add TikTok-specific hashtags:")
print(f"   #fyp #sleeptok #cozytok #asmr #sleephack")
print(f"\n3. INSTAGRAM REELS (same file)")
print(f"   Caption: same as YouTube description + #reels")
print(f"\n4. TIMING: Post all three within 30 minutes of each other")
print(f"   Best time: 9–11pm your audience's local time")
print(f"\nFile ready: {OUTPUT_FILE}")