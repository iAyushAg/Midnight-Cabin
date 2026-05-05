#!/bin/bash

# ─────────────────────────────────────────────────────────
# ADAPTIVE CADENCE WORKER
#
# Default: 24 hours
# If latest video >= 500 views: post every 12h (boost)
# Never slows down below 24h — always maintain posting volume
# ─────────────────────────────────────────────────────────

PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"

get_sleep_seconds() {
    python3 - << 'PYEOF'
import json, os

PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
DEFAULT_INTERVAL = 24 * 3600   # 24 hours
BOOST_INTERVAL   = 12 * 3600   # 12 hours — if performing well

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

# Only boost if genuinely performing well
# Never slow down — always post at least every 24 hours
if views >= 500:
    print(BOOST_INTERVAL)
else:
    print(DEFAULT_INTERVAL)
PYEOF
}

while true
do
    echo "Running pipeline..."
    bash run_pipeline.sh || echo "Pipeline failed"

    SLEEP_SECS=$(get_sleep_seconds)
    SLEEP_HOURS=$(echo "scale=1; $SLEEP_SECS / 3600" | bc)
    echo "Sleeping ${SLEEP_HOURS} hours (${SLEEP_SECS}s)..."
    sleep "$SLEEP_SECS"
done