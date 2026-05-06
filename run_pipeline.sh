#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

notify_discord() {
    local message="$1"
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -s -X POST "$DISCORD_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"$message\"}" || true
    fi
}

notify_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$message" || true
    fi
}

notify() {
    notify_discord "$1"
    notify_telegram "$1"
}

fail() {
    notify "❌ Midnight Cabin pipeline FAILED at step: $1"
    exit 1
}

# ─────────────────────────────────────────────────────────
# START
# ─────────────────────────────────────────────────────────
echo "Current folder:"; pwd
echo "Project files:"; ls -la
echo "Scripts:"; ls -la scripts

notify "🌙 Midnight Cabin pipeline starting..."

# ─────────────────────────────────────────────────────────
# PERSISTENT DIR SETUP
# ─────────────────────────────────────────────────────────
PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"
mkdir -p "$PERSISTENT_DIR"

if [ -f "token.json" ]; then
    cp token.json "$PERSISTENT_DIR/token.json"
    echo "Refreshed token.json"
fi

if [ -f "client_secret.json" ]; then
    cp client_secret.json "$PERSISTENT_DIR/client_secret.json"
    echo "Refreshed client_secret.json"
fi

if [ ! -f "$PERSISTENT_DIR/video_history.json" ]; then
    echo "[]" > "$PERSISTENT_DIR/video_history.json"
fi

echo "Persistent dir:"; ls -la "$PERSISTENT_DIR"

# ─────────────────────────────────────────────────────────
# CLEANUP BY-NC sounds
# ─────────────────────────────────────────────────────────
python3 - << 'PYEOF'
import json, os
attr_path = os.path.join(os.environ.get("PERSISTENT_DIR", "/data"), "audio_attributions.json")
nc_licenses = {
    "Attribution NonCommercial",
    "http://creativecommons.org/licenses/by-nc/3.0/",
    "http://creativecommons.org/licenses/by-nc/4.0/",
    "https://creativecommons.org/licenses/by-nc/3.0/",
    "https://creativecommons.org/licenses/by-nc/4.0/",
}
removed = 0
if os.path.exists(attr_path):
    with open(attr_path) as f:
        attributions = json.load(f)
    clean = []
    for item in attributions:
        if item.get("license") in nc_licenses:
            local_path = item.get("local_path", "")
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
                removed += 1
        else:
            clean.append(item)
    with open(attr_path, "w") as f:
        json.dump(clean, f, indent=2)
print(f"Cleaned {removed} BY-NC sounds")
PYEOF

echo "Starting pipeline..."

python3 scripts/collect_stats.py || echo "Stats collection skipped"
python3 scripts/generate_idea.py || fail "generate_idea"
python3 scripts/generate_visual.py || echo "Visual generation skipped"
python3 scripts/fetch_freesound.py || echo "Freesound fetch skipped"
python3 scripts/generate_audio.py || fail "generate_audio"

echo "Audio folder:"; ls -la audio || echo "audio folder missing"
echo "WAV files:"; find . -name "*.wav" -print

# ─────────────────────────────────────────────────────────
# READ DURATION + PRIMARY CATEGORY FROM PERSISTENT DIR
# ─────────────────────────────────────────────────────────
DURATION_MINUTES=$(python3 - << 'PYEOF'
import json, os
path = os.path.join(os.environ.get("PERSISTENT_DIR", "/data"), "current_idea.json")
if not os.path.exists(path):
    path = "current_idea.json"
with open(path) as f:
    idea = json.load(f)
print(idea.get("duration_minutes", 480))
PYEOF
)

PRIMARY=$(python3 - << 'PYEOF'
import json, os
path = os.path.join(os.environ.get("PERSISTENT_DIR", "/data"), "current_idea.json")
if not os.path.exists(path):
    path = "current_idea.json"
with open(path) as f:
    idea = json.load(f)
print(idea.get("audio_strategy", {}).get("primary_category", "rain"))
PYEOF
)

DURATION_SECONDS=$((DURATION_MINUTES * 60))
echo "Duration: ${DURATION_MINUTES} min | Primary: ${PRIMARY}"

# ─────────────────────────────────────────────────────────
# DOWNLOAD FIRE OVERLAY from Pixabay (for fireplace themes)
# ─────────────────────────────────────────────────────────
FIRE_OVERLAY=""
if [ "$PRIMARY" = "fireplace" ]; then
    FIRE_PATH="video/fire_overlay.mp4"
    if [ ! -f "$FIRE_PATH" ]; then
        echo "Downloading fire overlay..."
        PIXABAY_KEY="${PIXABAY_API_KEY:-}"
        if [ -n "$PIXABAY_KEY" ]; then
            FIRE_URL=$(python3 - << PYEOF
import requests, json
resp = requests.get(
    "https://pixabay.com/api/videos/",
    params={"key": "$PIXABAY_KEY", "q": "fireplace crackling fire", "per_page": 5},
    timeout=30
)
hits = resp.json().get("hits", [])
if hits:
    videos = hits[0].get("videos", {})
    url = videos.get("medium", {}).get("url") or videos.get("small", {}).get("url", "")
    print(url)
PYEOF
)
            if [ -n "$FIRE_URL" ]; then
                curl -sL "$FIRE_URL" -o "$FIRE_PATH" && echo "Fire overlay downloaded"
            fi
        fi
    fi
    if [ -f "$FIRE_PATH" ]; then
        FIRE_OVERLAY="$FIRE_PATH"
    fi
fi

# ─────────────────────────────────────────────────────────
# RENDER VIDEO
# ─────────────────────────────────────────────────────────
mkdir -p output

# ─────────────────────────────────────────────────────────

mkdir -p output

# ─────────────────────────────────────────────────────────
# RENDER VIDEO
# Uses Replicate animated clip if available (bg_animated.mp4)
# Falls back to static image with slow pan
# ─────────────────────────────────────────────────────────
ANIMATED_VIDEO="video/bg_animated.mp4"

if [ -f "$ANIMATED_VIDEO" ]; then
    echo "Using Replicate animated video..."
    # Loop the animated clip for full duration
    ffmpeg -y \
        -stream_loop -1 -i "$ANIMATED_VIDEO" \
        -stream_loop -1 -i audio/brown_noise.wav \
        -t "$DURATION_SECONDS" \
        -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
        -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
        -c:v libx264 -preset ultrafast -crf 28 \
        -c:a aac -b:a 192k -ar 44100 -r 24 \
        -movflags +faststart \
        output/video.mp4 || fail "ffmpeg render"
    echo "Video rendered from animated clip"

else
    echo "No animated clip — using static image with slow pan..."
    ffmpeg -y \
        -loop 1 -i video/bg.jpg \
        -stream_loop -1 -i audio/brown_noise.wav \
        -t "$DURATION_SECONDS" \
        -vf "scale=1380:776,crop=1280:720:'(iw-ow)/2*sin(t/300)+(iw-ow)/2':'(ih-oh)/2',format=yuv420p" \
        -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
        -c:v libx264 -preset ultrafast -crf 28 \
        -c:a aac -b:a 192k -ar 44100 -r 24 \
        -movflags +faststart \
        output/video.mp4 || fail "ffmpeg render"
    echo "Video rendered from static image"
fi

echo "Video created:"; ls -lh output/

# ─────────────────────────────────────────────────────────
# RETENTION / AUDIO QUALITY GATE
# Stops broken renders and writes /data/quality_gate_report.json.
# Set STRICT_QUALITY_GATE=1 to fail on warnings too.
# Set SKIP_QUALITY_GATE=1 to bypass during experiments.
# ─────────────────────────────────────────────────────────
if [ "${SKIP_QUALITY_GATE:-0}" != "1" ]; then
    python3 scripts/quality_gate.py --video output/video.mp4 --type main --expected-minutes "$DURATION_MINUTES" || fail "quality_gate"
else
    echo "Quality gate skipped by SKIP_QUALITY_GATE=1"
fi

# ROTATION — main → adhd → dark_screen → study_with_me
# ─────────────────────────────────────────────────────────
VIDEO_TYPE=$(python3 - << 'PYEOF'
import json, os
rotation_file = os.environ.get("PERSISTENT_DIR", "/data") + "/video_type_rotation.json"
order = ["main", "adhd", "dark_screen", "study_with_me"]
if os.path.exists(rotation_file):
    with open(rotation_file) as f:
        data = json.load(f)
    last = data.get("last_type", "study_with_me")
    idx = order.index(last) if last in order else -1
    next_type = order[(idx + 1) % len(order)]
else:
    next_type = "main"
with open(rotation_file, "w") as f:
    json.dump({"last_type": next_type}, f)
print(next_type)
PYEOF
)

echo "This cycle: $VIDEO_TYPE"
notify "🎬 Midnight Cabin — uploading $VIDEO_TYPE video..."

# ─────────────────────────────────────────────────────────
# THUMBNAIL
# ─────────────────────────────────────────────────────────
echo "Generating thumbnail..."
python3 scripts/generate_thumbnail.py || echo "Thumbnail skipped"

# ─────────────────────────────────────────────────────────
# UPLOAD based on rotation
# ─────────────────────────────────────────────────────────
if [ "$VIDEO_TYPE" = "main" ]; then
    python3 scripts/upload.py || fail "upload"

elif [ "$VIDEO_TYPE" = "dark_screen" ]; then
    ffmpeg -y \
        -f lavfi -i color=c=black:size=1280x720:rate=1 \
        -stream_loop -1 -i audio/brown_noise.wav \
        -t "$DURATION_SECONDS" \
        -vf "format=yuv420p" \
        -c:v libx264 -preset ultrafast -crf 28 \
        -c:a aac -b:a 192k -ar 44100 -r 1 \
        -movflags +faststart \
        output/video_dark.mp4 || fail "dark screen render"
    if [ "${SKIP_QUALITY_GATE:-0}" != "1" ]; then
        python3 scripts/quality_gate.py --video output/video_dark.mp4 --type dark_screen --expected-minutes "$DURATION_MINUTES" || fail "quality_gate_dark"
    fi
    python3 scripts/upload_dark.py || fail "upload"

elif [ "$VIDEO_TYPE" = "adhd" ]; then
    python3 scripts/upload_adhd.py || fail "upload"

elif [ "$VIDEO_TYPE" = "study_with_me" ]; then
    python3 scripts/upload_study.py || fail "upload"
fi

echo "Pipeline finished — uploaded: $VIDEO_TYPE"
notify "✅ Midnight Cabin — $VIDEO_TYPE video uploaded successfully!"