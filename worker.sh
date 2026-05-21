#!/bin/bash

# ─────────────────────────────────────────────────────────
# WORKER — runs two parallel loops:
# 1. Main pipeline (long video) — every 24h
# 2. Short pipeline — 3x per day, every 8h
# ─────────────────────────────────────────────────────────

PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────
notify_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$message" || true
    fi
}

get_sleep_seconds() {
    python3 - << 'PYEOF'
import json, os

PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
DEFAULT_INTERVAL = 48 * 3600  # 48 hours between main videos
BOOST_INTERVAL   = 24 * 3600  # 24 hours if a video hits 500+ views

if not os.path.exists(HISTORY_FILE):
    print(DEFAULT_INTERVAL)
    exit()

with open(HISTORY_FILE) as f:
    try:
        history = json.load(f)
    except Exception:
        print(DEFAULT_INTERVAL)
        exit()

if not history:
    print(DEFAULT_INTERVAL)
    exit()

# Only check long-form videos — a Short with 500 views should not
# trigger faster long-form upload cadence
long_form_types = {"main", "adhd", "dark_screen", "study_with_me"}
long_form = [v for v in history if v.get("type", "main") in long_form_types]
if not long_form:
    print(DEFAULT_INTERVAL)
    exit()
max_views = max(v.get("performance", {}).get("views", 0) for v in long_form[-5:])
if max_views >= 500:
    print(BOOST_INTERVAL)
else:
    print(DEFAULT_INTERVAL)
PYEOF
}

get_wake_time() {
    local sleep_secs="$1"
    python3 - << PYEOF
import datetime
secs = $sleep_secs
wake = datetime.datetime.utcnow() + datetime.timedelta(seconds=secs)
wake_ist = wake + datetime.timedelta(hours=5, minutes=30)
print(wake_ist.strftime("%I:%M %p on %b %d (IST)"))
PYEOF
}

# ─────────────────────────────────────────────────────────
# SHORT LOOP — 3 Shorts per day, every 8 hours
# First Short posts 2h after deploy so it doesn't clash
# with the main video that runs immediately
# ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────
# MAIN LOOP — runs first, then starts Short loop after
# ─────────────────────────────────────────────────────────

SHORT_INTERVAL=43200  # 12 hours between Shorts

while true; do
    echo "Running main pipeline..."
    bash run_pipeline.sh || echo "Main pipeline failed"

    SLEEP_SECS=$(get_sleep_seconds)
    SLEEP_HOURS=$(echo "scale=1; $SLEEP_SECS / 3600" | bc)
    WAKE_TIME=$(get_wake_time "$SLEEP_SECS")

    echo "Sleeping ${SLEEP_HOURS} hours (${SLEEP_SECS}s)... Next video at: ${WAKE_TIME}"
    notify_telegram "😴 Sleeping for ${SLEEP_HOURS}h — next video at ${WAKE_TIME}"

    # One Short per main pipeline cycle — posting too many identical Shorts
    # signals spam to YouTube and suppresses all content on the channel
    echo "Running Short pipeline (post-main)..."
    bash run_short_pipeline.sh || echo "Short pipeline failed (non-fatal)"

    sleep $SLEEP_SECS
done