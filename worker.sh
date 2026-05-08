#!/bin/bash

# ─────────────────────────────────────────────────────────
# WORKER — runs two parallel loops:
# 1. Main pipeline long video — every 24h, or every 12h if latest video crosses 500 views
# 2. Short pipeline — every 30 minutes
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
DEFAULT_INTERVAL = 24 * 3600
BOOST_INTERVAL   = 12 * 3600

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

latest = history[-1]
views = latest.get("performance", {}).get("views", 0)

if views >= 500:
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
# SHORT LOOP — every 30 minutes
# First Short posts 10 minutes after deploy so it does not
# clash with the main video pipeline starting immediately.
# ─────────────────────────────────────────────────────────
run_short_loop() {
    local SHORT_INTERVAL=1800  # 30 minutes in seconds
    local INITIAL_OFFSET=600   # 10 minutes before first Short

    echo "Short loop: waiting ${INITIAL_OFFSET}s before first Short..."
    WAKE_TIME=$(get_wake_time $INITIAL_OFFSET)
    notify_telegram "🎬 First Short will post at ${WAKE_TIME}"
    sleep $INITIAL_OFFSET

    while true; do
        echo "Running Short pipeline..."
        bash run_short_pipeline.sh || echo "Short pipeline failed (non-fatal)"

        WAKE_TIME=$(get_wake_time $SHORT_INTERVAL)
        echo "Short loop: sleeping 30 min... Next Short at: ${WAKE_TIME}"
        notify_telegram "🎬 Next Short at ${WAKE_TIME}"
        sleep $SHORT_INTERVAL
    done
}

# Start Short loop in background
run_short_loop &
SHORT_LOOP_PID=$!
echo "Short loop started (PID: $SHORT_LOOP_PID) — Shorts every 30 minutes"

# ─────────────────────────────────────────────────────────
# MAIN LOOP — long video, adaptive cadence
# ─────────────────────────────────────────────────────────
while true; do
    echo "Running main pipeline..."
    bash run_pipeline.sh || echo "Main pipeline failed"

    SLEEP_SECS=$(get_sleep_seconds)
    SLEEP_HOURS=$(echo "scale=1; $SLEEP_SECS / 3600" | bc)
    WAKE_TIME=$(get_wake_time "$SLEEP_SECS")

    echo "Sleeping ${SLEEP_HOURS} hours (${SLEEP_SECS}s)... Next video at: ${WAKE_TIME}"
    notify_telegram "😴 Sleeping for ${SLEEP_HOURS}h — next video at ${WAKE_TIME}"
    sleep "$SLEEP_SECS"
done