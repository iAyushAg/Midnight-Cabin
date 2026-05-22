#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────
# SHORT PIPELINE
# Runs independently from main pipeline
# Generates and uploads a 60-second YouTube Short daily
# ─────────────────────────────────────────────────────────

PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"

notify_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$message" || true
    fi
}

fail() {
    notify_telegram "❌ Short pipeline failed at: $1"
    exit 1
}

echo "Starting Short pipeline..."
notify_telegram "🎬 Generating YouTube Short..."

# ─────────────────────────────────────────────────────────
# STEP 1 — RESTORE VISUAL ASSETS FROM PERSISTENT DIR
# Ephemeral filesystem resets on every deploy.
# bg_animated.mp4 and bg.jpg live in /data (persistent).
# Copy them back into the working directory before anything
# else runs — generate_short.py and the ffmpeg fallback
# both need them to be at video/ paths.
# ─────────────────────────────────────────────────────────
mkdir -p video output

if [ ! -f "video/bg_animated.mp4" ] && [ -f "$PERSISTENT_DIR/bg_animated.mp4" ]; then
    echo "Restoring bg_animated.mp4 from persistent dir..."
    cp "$PERSISTENT_DIR/bg_animated.mp4" video/bg_animated.mp4
fi

if [ ! -f "video/bg.jpg" ] && [ -f "$PERSISTENT_DIR/bg.jpg" ]; then
    echo "Restoring bg.jpg from persistent dir..."
    cp "$PERSISTENT_DIR/bg.jpg" video/bg.jpg
fi

# ─────────────────────────────────────────────────────────
# STEP 2 — GENERATE FRESH IDEA, NICHE-LOCKED TO VISUAL
#
# Key constraint: generate_short.py only uses bg_animated.mp4
# if the idea's primary niche matches what the visual was made
# for (stored in current_visual.json). If there's a mismatch
# it falls back to library images or the source video.
#
# Strategy: read the niche of the available animated visual
# first, then override the niche rotation so the fresh idea
# is always compatible with what we can actually show.
# This gives us fresh hook text + voiceover + title every
# run, while guaranteeing the visual asset will be used.
#
# If no visual metadata exists (first ever deploy), let
# generate_idea.py pick freely — it will use whatever
# visual asset it finds.
# ─────────────────────────────────────────────────────────
AVAILABLE_NICHE=$(python3 - << 'PYEOF'
import json, os
from pathlib import Path

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
visual_meta = persistent_dir / "current_visual.json"

if not visual_meta.exists():
    print("")
    exit()

try:
    with open(visual_meta) as f:
        vm = json.load(f)
    niche = vm.get("primary") or vm.get("primary_category") or ""
    valid = {"rain","river","thunder","fireplace","ocean_waves",
             "soft_wind","night_forest","brown_noise"}
    print(niche if niche in valid else "")
except Exception:
    print("")
PYEOF
)

if [ -n "$AVAILABLE_NICHE" ]; then
    echo "Visual asset niche: $AVAILABLE_NICHE — locking idea generation to match"
    # Inject the niche into the rotation queue so generate_idea.py
    # picks it as the next primary. We prepend it to the queue
    # rather than overwriting, so the rotation recovers naturally.
    python3 - << PYEOF
import json, os
from pathlib import Path

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
rotation_file  = persistent_dir / "niche_rotation.json"
niche = "$AVAILABLE_NICHE"

rotation = {"queue": [], "used": []}
try:
    if rotation_file.exists():
        with open(rotation_file) as f:
            rotation = json.load(f)
except Exception:
    pass

queue = rotation.get("queue", [])
# Remove it if it's already in the queue to avoid duplicates
queue = [n for n in queue if n != niche]
# Put it at the front so it's picked next
queue.insert(0, niche)
rotation["queue"] = queue

with open(rotation_file, "w") as f:
    json.dump(rotation, f, indent=2)

print(f"Rotation queue primed with: {niche}")
PYEOF
else
    echo "No visual metadata found — letting idea generation pick freely"
fi

echo "Generating fresh idea for Short..."
python3 scripts/generate_idea.py || {
    echo "Idea generation failed — using existing idea if available"
    # Don't exit — if current_idea.json exists in /data we can still proceed
}

# ─────────────────────────────────────────────────────────
# STEP 3 — ENSURE AUDIO SOURCE EXISTS
# Shorts pull audio from output/video.mp4.
# If the main video hasn't run yet (fresh deploy or 48h
# delay not elapsed), build a minimal 3-minute source
# video from the restored visual assets.
# ─────────────────────────────────────────────────────────
if [ ! -f "output/video.mp4" ]; then
    echo "No main video found — building minimal audio source for Short..."

    if [ ! -f "$PERSISTENT_DIR/current_idea.json" ]; then
        echo "No idea available — Short pipeline cannot run yet"
        notify_telegram "⚠️ Short skipped — no idea available yet (first deploy?)"
        exit 0
    fi

    python3 scripts/generate_audio.py || fail "generate_audio for short"

    DURATION_SECONDS=180

    if [ -f "video/bg_animated.mp4" ]; then
        echo "Building minimal source from animated background..."
        ffmpeg -y \
            -stream_loop -1 -i video/bg_animated.mp4 \
            -stream_loop -1 -i audio/brown_noise.wav \
            -t "$DURATION_SECONDS" \
            -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
            -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -b:a 128k \
            -r 30 -movflags +faststart \
            output/video.mp4 || fail "minimal video render (animated)"

    elif [ -f "video/bg.jpg" ]; then
        echo "Building minimal source from still image..."
        ffmpeg -y \
            -loop 1 -i video/bg.jpg \
            -stream_loop -1 -i audio/brown_noise.wav \
            -t "$DURATION_SECONDS" \
            -vf "scale=1280:720,format=yuv420p" \
            -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -b:a 128k \
            -r 30 -movflags +faststart \
            output/video.mp4 || fail "minimal video render (image)"

    else
        echo "No visual asset found — using black background (audio only)"
        ffmpeg -y \
            -f lavfi -i color=c=black:size=1280x720:rate=30 \
            -stream_loop -1 -i audio/brown_noise.wav \
            -t "$DURATION_SECONDS" \
            -vf "format=yuv420p" \
            -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -b:a 128k \
            -movflags +faststart \
            output/video.mp4 || fail "black video render"
    fi
fi

# ─────────────────────────────────────────────────────────
# STEP 4 — GENERATE AND UPLOAD THE SHORT
# ─────────────────────────────────────────────────────────
python3 scripts/generate_short.py || fail "generate_short"
python3 scripts/upload_short.py   || fail "upload_short"

echo "Short pipeline complete"