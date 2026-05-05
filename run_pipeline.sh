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
    local message="$1"
    notify_discord "$message"
    notify_telegram "$message"
}

fail() {
    local step="$1"
    notify "❌ Midnight Cabin pipeline FAILED at step: $step"
    exit 1
}

# ─────────────────────────────────────────────────────────
# START
# ─────────────────────────────────────────────────────────

echo "Current folder:"
pwd

echo "Project files:"
ls -la

echo "Scripts:"
ls -la scripts

notify "🌙 Midnight Cabin pipeline starting..."

# ─────────────────────────────────────────────────────────
# PERSISTENT DIR SETUP
# Copies credentials to /data on first run so they survive redeployments
# ─────────────────────────────────────────────────────────
PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"
mkdir -p "$PERSISTENT_DIR"

# Always overwrite token.json from repo if present — ensures fresh scopes on redeploy
if [ -f "token.json" ]; then
    cp token.json "$PERSISTENT_DIR/token.json"
    echo "Refreshed token.json in $PERSISTENT_DIR from repo"
fi

if [ -f "client_secret.json" ]; then
    cp client_secret.json "$PERSISTENT_DIR/client_secret.json"
    echo "Refreshed client_secret.json in $PERSISTENT_DIR from repo"
fi

if [ ! -f "$PERSISTENT_DIR/video_history.json" ]; then
    echo "[]" > "$PERSISTENT_DIR/video_history.json"
    echo "Initialized empty video_history.json in $PERSISTENT_DIR"
fi

echo "Persistent dir contents:"
ls -la "$PERSISTENT_DIR"

echo "Starting pipeline..."

python3 scripts/collect_stats.py || echo "Stats collection skipped"

python3 scripts/generate_idea.py || fail "generate_idea"

python3 scripts/generate_visual.py || echo "Visual generation skipped"

python3 scripts/fetch_freesound.py || echo "Freesound fetch skipped"

python3 scripts/generate_audio.py || fail "generate_audio"

echo "Audio folder after generation:"
ls -la audio || echo "audio folder missing"

echo "Find WAV files:"
find . -name "*.wav" -print

# ─────────────────────────────────────────────────────────
# READ DURATION FROM IDEA JSON
# ─────────────────────────────────────────────────────────

DURATION_MINUTES=$(python3 -c "
import json
with open('current_idea.json') as f:
    idea = json.load(f)
print(idea.get('duration_minutes', 480))
")

DURATION_SECONDS=$((DURATION_MINUTES * 60))
echo "Video duration: ${DURATION_MINUTES} minutes (${DURATION_SECONDS} seconds)"

# ─────────────────────────────────────────────────────────
# RENDER VIDEO — static image, ultrafast preset, 1fps
# No zoompan — cuts render time from 16+ hours to ~30 mins
# ─────────────────────────────────────────────────────────

echo "Creating output folder..."
mkdir -p output

echo "Generating video..."
ffmpeg -y \
    -loop 1 -i video/bg.jpg \
    -stream_loop -1 -i audio/brown_noise.wav \
    -t "$DURATION_SECONDS" \
    -vf "scale=1380:776,crop=1280:720:'(iw-ow)/2*sin(t/300)+(iw-ow)/2':'(ih-oh)/2',drawtext=text='Now Playing  •  No Ads  •  No Interruptions':fontsize=24:fontcolor=white@0.85:x=40:y=h-th-40:enable='between(t,0,8)',format=yuv420p" \
    -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
    -c:v libx264 -preset ultrafast -tune stillimage -crf 28 \
    -c:a aac -b:a 192k \
    -ar 44100 \
    -r 1 \
    -movflags +faststart \
    output/video.mp4 || fail "ffmpeg render"

echo "Video created:"
ls -lh output/

# Dark screen render happens only when rotation picks dark_screen type
# See UPLOAD section below

# ─────────────────────────────────────────────────────────
# ROTATION — pick which video type to upload this cycle
# Rotates: main → adhd → dark_screen → study_with_me → main...
# ─────────────────────────────────────────────────────────

ROTATION_FILE="${PERSISTENT_DIR}/video_type_rotation.json"
ROTATION_ORDER='["main", "adhd", "dark_screen", "study_with_me"]'

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

# Save next type
with open(rotation_file, "w") as f:
    json.dump({"last_type": next_type}, f)

print(next_type)
PYEOF
)

echo "This cycle video type: $VIDEO_TYPE"
notify "🎬 Midnight Cabin — rendering $VIDEO_TYPE video..."

# ─────────────────────────────────────────────────────────
# THUMBNAIL — always generate
# ─────────────────────────────────────────────────────────
echo "Generating thumbnail..."
python3 scripts/generate_thumbnail.py || echo "Thumbnail generation skipped"

# ─────────────────────────────────────────────────────────
# UPLOAD — based on rotation type
# ─────────────────────────────────────────────────────────

if [ "$VIDEO_TYPE" = "main" ]; then
    echo "Uploading main sleep video..."
    python3 scripts/upload.py || fail "upload"

elif [ "$VIDEO_TYPE" = "dark_screen" ]; then
    echo "Rendering dark screen version..."
    ffmpeg -y \
        -f lavfi -i color=c=black:size=1280x720:rate=1 \
        -stream_loop -1 -i audio/brown_noise.wav \
        -t "$DURATION_SECONDS" \
        -vf "format=yuv420p" \
        -c:v libx264 -preset ultrafast -tune stillimage -crf 28 \
        -c:a aac -b:a 192k \
        -ar 44100 \
        -r 1 \
        -movflags +faststart \
        output/video_dark.mp4 || fail "dark screen render"
    echo "Uploading dark screen video..."
    python3 scripts/upload_dark.py || fail "upload"

elif [ "$VIDEO_TYPE" = "adhd" ]; then
    echo "Uploading ADHD focus video..."
    python3 scripts/upload_adhd.py || fail "upload"

elif [ "$VIDEO_TYPE" = "study_with_me" ]; then
    echo "Rendering Study With Me (Pomodoro) version..."
    python3 scripts/upload_study.py || fail "upload"
fi

echo "Pipeline finished — uploaded: $VIDEO_TYPE"
notify "✅ Midnight Cabin — $VIDEO_TYPE video uploaded successfully!"