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

# Hotfix: patch generate_idea.py to fix unhashable dict bug
python3 - << 'PATCH'
import re
path = "scripts/generate_idea.py"
with open(path) as f:
    content = f.read()

old = """    scored = [
        (v, v.get("performance", {}).get("views", 0))
        for v in history
        if v.get("performance", {}).get("views", 0) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_performers = [v[0] for v in scored[:3]]
    low_performers = [v[0] for v in scored[-3:] if v[1] > 0]"""

new = """    scored = [
        (i, v.get("performance", {}).get("views", 0))
        for i, v in enumerate(history)
        if v.get("performance", {}).get("views", 0) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_performers = [history[i] for i, _ in scored[:3]]
    low_performers = [history[i] for i, v in scored[-3:] if v > 0]"""

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("Hotfix applied successfully")
else:
    print("Pattern not found — may already be fixed")
PATCH

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
    -vf "format=yuv420p" \
    -c:v libx264 -preset ultrafast -tune stillimage -crf 28 \
    -c:a aac -b:a 128k \
    -ar 44100 \
    -r 1 \
    -movflags +faststart \
    output/video.mp4 || fail "ffmpeg render"

echo "Video created:"
ls -lh output/

# ─────────────────────────────────────────────────────────
# THUMBNAIL + UPLOAD
# ─────────────────────────────────────────────────────────

echo "Uploading..."
python3 scripts/generate_thumbnail.py || echo "Thumbnail generation skipped"

python3 scripts/upload.py || fail "upload"

echo "Pipeline finished"
notify "✅ Midnight Cabin video uploaded successfully!"