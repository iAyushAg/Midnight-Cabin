#!/bin/bash

# ─────────────────────────────────────────────────────────
# ADAPTIVE CADENCE WORKER
#
# Base interval: 24 hours
# If latest video has 500+ views: post every 12h (boost)
# If latest video has 0–50 views: slow down to every 36h
# Otherwise: stay at 24h
# ─────────────────────────────────────────────────────────

get_sleep_seconds() {
    python3 - <<'EOF'
import json, os

HISTORY_FILE = "video_history.json"
DEFAULT_INTERVAL = 24 * 3600   # 24 hours
BOOST_INTERVAL   = 12 * 3600   # 12 hours — if performing well
SLOW_INTERVAL    = 36 * 3600   # 36 hours — if underperforming

if not os.path.exists(HISTORY_FILE):
    print(DEFAULT_INTERVAL)
    exit()

with open(HISTORY_FILE) as f:
    history = json.load(f)

if not history:
    print(DEFAULT_INTERVAL)
    exit()

latest = history[-1]
views = latest.get("performance", {}).get("views", 0)

if views >= 500:
    print(BOOST_INTERVAL)
elif views <= 50 and len(history) >= 3:
    # Only slow down once we have some data, not from the start
    print(SLOW_INTERVAL)
else:
    print(DEFAULT_INTERVAL)
EOF
}

while true
do
    echo "Running pipeline..."
    bash run_pipeline.sh || echo "Pipeline failed"

    SLEEP_SECS=$(get_sleep_seconds)
    SLEEP_HOURS=$(echo "scale=1; $SLEEP_SECS / 3600" | bc)
    echo "Sleeping ${SLEEP_HOURS} hours (${SLEEP_SECS}s) based on channel performance..."
    sleep "$SLEEP_SECS"
done
