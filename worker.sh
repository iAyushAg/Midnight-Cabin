#!/bin/bash

# ─────────────────────────────────────────────────────────
# WORKER — runs two parallel loops:
# 1. Main pipeline (long video) — every 24h
# 2. Short pipeline — every 24h, offset by 12h
# ─────────────────────────────────────────────────────────

PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"

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

# ─────────────────────────────────────────────────────────
# SHORT LOOP — runs in background, offset by 12 hours
# so Shorts post midway between main videos
# ─────────────────────────────────────────────────────────
run_short_loop() {
    echo "Short loop: sleeping 12h offset before first Short..."
    sleep 43200  # 12 hours offset

    while true; do
        echo "Running Short pipeline..."
        bash run_short_pipeline.sh || echo "Short pipeline failed (non-fatal)"
        echo "Short loop: sleeping 24h..."
        sleep 86400
    done
}

# Start Short loop in background
run_short_loop &
SHORT_LOOP_PID=$!
echo "Short loop started (PID: $SHORT_LOOP_PID)"

# ─────────────────────────────────────────────────────────
# MAIN LOOP — long video, adaptive cadence
# ─────────────────────────────────────────────────────────
while true; do
    echo "Running main pipeline..."
    bash run_pipeline.sh || echo "Main pipeline failed"

    SLEEP_SECS=$(get_sleep_seconds)
    SLEEP_HOURS=$(echo "scale=1; $SLEEP_SECS / 3600" | bc)
    echo "Sleeping ${SLEEP_HOURS} hours (${SLEEP_SECS}s)..."
    sleep "$SLEEP_SECS"
done