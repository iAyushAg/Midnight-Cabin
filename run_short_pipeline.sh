#!/bin/bash

# ─────────────────────────────────────────────────────────
# SHORT PIPELINE — FULLY SELF-CONTAINED
#
# Completely decoupled from the main pipeline.
# Has its own idea, its own audio, its own visual.
# Works correctly even if run_pipeline.sh is disabled forever.
#
# Never reads:  current_idea.json   (main pipeline's idea)
#               current_visual.json (main pipeline's visual)
#               output/video.mp4    (main pipeline's video)
#               niche_rotation.json (main pipeline's rotation)
#
# Owns:  short_idea.json           — this Short's idea
#        short_niche_rotation.json — Short's own niche rotation
#        short_audio.wav           — this Short's audio mix
#        bg_short_animated.mp4     — this Short's portrait visual
#        current_short_visual.json — this Short's visual metadata
#        short.mp4                 — final Short output
# ─────────────────────────────────────────────────────────

set -e

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
    notify_telegram "❌ Short pipeline failed: $1"
    exit 1
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Short pipeline starting..."
notify_telegram "🎬 Short pipeline starting..."

mkdir -p video output audio

# ─────────────────────────────────────────────────────────
# STEP 1 — GENERATE SHORT IDEA
#
# Uses SHORT_IDEA_PATH and SHORT_ROTATION_FILE so it never
# touches the main pipeline's current_idea.json or
# niche_rotation.json. The Short has its own niche rotation
# that advances independently every 12 hours.
# ─────────────────────────────────────────────────────────
log "Generating Short idea..."
SHORT_IDEA_PATH="$PERSISTENT_DIR/short_idea.json" \
SHORT_ROTATION_FILE="$PERSISTENT_DIR/short_niche_rotation.json" \
IDEA_OUTPUT_PATH="$PERSISTENT_DIR/short_idea.json" \
python3 scripts/generate_short_idea.py || fail "generate_short_idea"

# Verify idea was written
if [ ! -f "$PERSISTENT_DIR/short_idea.json" ]; then
    fail "short_idea.json not written"
fi

log "Short idea generated: $(python3 -c "import json; d=json.load(open('$PERSISTENT_DIR/short_idea.json')); print(d.get('title','?')[:60])")"

# ─────────────────────────────────────────────────────────
# STEP 2 — GENERATE SHORT AUDIO
#
# Reads short_idea.json (not current_idea.json).
# Writes audio/short_audio.wav — the Short's own audio mix.
# Duration: 3 minutes (enough for a 28s Short + headroom).
# ─────────────────────────────────────────────────────────
log "Generating Short audio..."
SHORT_AUDIO_MODE=1 \
SHORT_IDEA_PATH="$PERSISTENT_DIR/short_idea.json" \
python3 scripts/generate_short_audio.py || fail "generate_short_audio"

if [ ! -f "audio/short_audio.wav" ]; then
    fail "short_audio.wav not written"
fi

# ─────────────────────────────────────────────────────────
# STEP 3 — GENERATE SHORT VISUAL (PORTRAIT)
#
# Reads short_idea.json (not current_idea.json).
# Fetches niche-matched portrait photo from Pexels/Unsplash/Pixabay.
# Animates with Kling → bg_short_animated.mp4 (9:16 vertical).
# Writes current_short_visual.json (not current_visual.json).
# ─────────────────────────────────────────────────────────
log "Generating Short portrait visual..."
SHORT_IDEA_PATH="$PERSISTENT_DIR/short_idea.json" \
python3 scripts/generate_short_visual.py || {
    log "Short visual generation failed — will use fallback in render step"
}

# ─────────────────────────────────────────────────────────
# STEP 4 — RENDER THE SHORT
#
# Reads short_idea.json for hook text / voiceover / niche.
# Reads audio/short_audio.wav for ambient sound.
# Reads bg_short_animated.mp4 or bg_short.jpg for visuals.
# Writes output/short.mp4
# ─────────────────────────────────────────────────────────
log "Rendering Short..."
SHORT_IDEA_PATH="$PERSISTENT_DIR/short_idea.json" \
python3 scripts/generate_short.py || fail "generate_short"

if [ ! -f "output/short.mp4" ]; then
    fail "output/short.mp4 not written"
fi

# ─────────────────────────────────────────────────────────
# STEP 5 — UPLOAD TO YOUTUBE
# ─────────────────────────────────────────────────────────
log "Uploading Short to YouTube..."
python3 scripts/upload_short.py || fail "upload_short"

# Cross-posting (Instagram/Pinterest) is currently disabled.
# Re-enable by uncommenting the block below once Buffer + Pinterest are configured.
# python3 scripts/post_to_socials.py || log "Cross-posting failed (non-fatal)"

log "Short pipeline complete ✅"
notify_telegram "✅ Short posted!"