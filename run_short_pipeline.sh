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

# Check if main video exists — need it for the Short
if [ ! -f "output/video.mp4" ]; then
    echo "No main video found — running audio generation first..."

    # Need at minimum an idea and audio to make a Short
    # Check if current_idea.json exists in persistent dir
    if [ ! -f "$PERSISTENT_DIR/current_idea.json" ]; then
        echo "No current idea found — Short pipeline skipped"
        notify_telegram "⚠️ Short skipped — no main video available yet"
        exit 0
    fi

    # Generate audio and a minimal video for the Short
    python3 scripts/generate_audio.py || fail "generate_audio for short"

    mkdir -p output

    DURATION_SECONDS=180  # 3 min minimal video for Short source

    if [ -f "video/bg.jpg" ]; then
        ffmpeg -y \
            -loop 1 -i video/bg.jpg \
            -stream_loop -1 -i audio/brown_noise.wav \
            -t "$DURATION_SECONDS" \
            -vf "scale=1280:720,format=yuv420p" \
            -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -b:a 128k \
            -r 30 \
            -movflags +faststart \
            output/video.mp4 || fail "minimal video render"
    else
        # Pure audio Short — black background
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

# Generate the Short
python3 scripts/generate_short.py || fail "generate_short"

# Retention / audio quality gate for Shorts
if [ "${SKIP_QUALITY_GATE:-0}" != "1" ] && [ -f "output/short.mp4" ]; then
    python3 scripts/quality_gate.py --video output/short.mp4 --type short --expected-minutes 1 --sample-seconds 60 || fail "quality_gate_short"
fi

# Upload the Short
python3 scripts/upload_short.py || fail "upload_short"

echo "Short pipeline complete"