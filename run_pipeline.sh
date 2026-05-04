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
print(idea.get('duration_minutes', 60))
")

DURATION_SECONDS=$((DURATION_MINUTES * 60))
echo "Video duration: ${DURATION_MINUTES} minutes (${DURATION_SECONDS} seconds)"

# ─────────────────────────────────────────────────────────
# RENDER VIDEO
# ─────────────────────────────────────────────────────────

echo "Creating output folder..."
mkdir -p output

echo "Generating video..."
ffmpeg -y \
    -loop 1 -i video/bg.jpg \
    -stream_loop -1 -i audio/brown_noise.wav \
    -t "$DURATION_SECONDS" \
    -vf "zoompan=z='min(zoom+0.0003,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1280x720,format=yuv420p" \
    -c:v libx264 -preset slow -crf 26 \
    -c:a aac -b:a 128k \
    -ar 44100 \
    -r 24 \
    -g 48 \
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
