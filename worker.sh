#!/bin/bash

# ─────────────────────────────────────────────────────────
# MIDNIGHT CABIN WORKER
#
# Two completely independent loops running in parallel:
#
#   MAIN LOOP:   Runs run_pipeline.sh every 48h.
#                On a fresh deploy, waits 48h before the
#                first run — so redeploying code fixes
#                never accidentally push a video.
#                Override: set SKIP_MAIN_DELAY=1 in Railway
#                env vars to run immediately on next deploy.
#
#   SHORT LOOP:  Runs run_short_pipeline.sh every 24h.
#                Posts the first Short 30 minutes after
#                deploy — completely unaffected by when
#                the main pipeline runs.
#                Uses previous cycle's audio/visual assets
#                if the main video hasn't generated yet.
#
# Railway env vars:
#   SKIP_MAIN_DELAY=1        — bypass the 48h deploy delay once
#   MAIN_INTERVAL_HOURS=48   — change main pipeline cadence
#   SHORT_INTERVAL_HOURS=24  — change Short cadence
# ─────────────────────────────────────────────────────────

PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"
mkdir -p "$PERSISTENT_DIR"

MAIN_INTERVAL_HOURS="${MAIN_INTERVAL_HOURS:-48}"
SHORT_INTERVAL_HOURS="${SHORT_INTERVAL_HOURS:-24}"
MAIN_INTERVAL=$(( MAIN_INTERVAL_HOURS * 3600 ))
SHORT_INTERVAL=$(( SHORT_INTERVAL_HOURS * 3600 ))

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
notify() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$msg" >/dev/null 2>&1 || true
    fi
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $1"
}

wake_time() {
    # Prints human-readable wake time in IST
    local sleep_secs="$1"
    python3 - << PYEOF
import datetime
wake = datetime.datetime.utcnow() + datetime.timedelta(seconds=$sleep_secs)
ist  = wake + datetime.timedelta(hours=5, minutes=30)
print(ist.strftime("%I:%M %p on %b %d (IST)"))
PYEOF
}

main_interval() {
    # Returns interval in seconds — drops to 24h if a recent video hit 500+ views
    python3 - << 'PYEOF'
import json, os
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
HISTORY_FILE   = os.path.join(PERSISTENT_DIR, "video_history.json")
DEFAULT = int(os.environ.get("MAIN_INTERVAL_HOURS", "48")) * 3600
BOOST   = 24 * 3600

if not os.path.exists(HISTORY_FILE):
    print(DEFAULT); exit()
try:
    history = json.load(open(HISTORY_FILE))
except Exception:
    print(DEFAULT); exit()

long_form_types = {"main", "adhd", "dark_screen", "study_with_me"}
long_form = [v for v in history if v.get("type", "main") in long_form_types]
if not long_form:
    print(DEFAULT); exit()

max_views = max(v.get("performance", {}).get("views", 0) for v in long_form[-5:])
print(BOOST if max_views >= 500 else DEFAULT)
PYEOF
}

# ─────────────────────────────────────────────
# SHORT LOOP — fully independent background process
# Starts after a 30-minute warmup delay so it doesn't
# compete with startup I/O, then runs every 24h.
# ─────────────────────────────────────────────
short_loop() {
    log "Short loop: waiting 30 minutes before first Short..."
    sleep 1800  # 30 min warmup — avoids startup resource clash

    while true; do
        log "Short loop: running Short pipeline..."
        notify "🎬 Short pipeline starting..."
        bash run_short_pipeline.sh && \
            notify "✅ Short posted!" || \
            notify "⚠️ Short pipeline failed (non-fatal)"

        local next_wake
        next_wake=$(wake_time "$SHORT_INTERVAL")
        log "Short loop: sleeping ${SHORT_INTERVAL_HOURS}h — next Short at ${next_wake}"
        notify "😴 Next Short at ${next_wake}"
        sleep "$SHORT_INTERVAL"
    done
}

# ─────────────────────────────────────────────
# MAIN LOOP — delayed on deploy
# ─────────────────────────────────────────────
main_loop() {
    # First run: respect the 48h deploy delay unless overridden
    if [ "${SKIP_MAIN_DELAY:-0}" = "1" ]; then
        log "Main loop: SKIP_MAIN_DELAY=1 — running immediately"
        notify "🚀 SKIP_MAIN_DELAY set — main pipeline starting now..."
    else
        local deploy_wait=$MAIN_INTERVAL
        local next_wake
        next_wake=$(wake_time "$deploy_wait")
        log "Main loop: fresh deploy — waiting ${MAIN_INTERVAL_HOURS}h before first video"
        log "Main loop: first video scheduled at ${next_wake}"
        notify "🌙 Midnight Cabin deployed. First video in ${MAIN_INTERVAL_HOURS}h — at ${next_wake}. Shorts posting independently every ${SHORT_INTERVAL_HOURS}h."
        sleep "$deploy_wait"
    fi

    while true; do
        log "Main loop: running main pipeline..."
        notify "🎬 Main pipeline starting..."
        bash run_pipeline.sh && \
            notify "✅ Main video uploaded!" || \
            notify "❌ Main pipeline failed — check logs"

        local interval
        interval=$(main_interval)
        local sleep_hours
        sleep_hours=$(echo "scale=1; $interval / 3600" | bc)
        local next_wake
        next_wake=$(wake_time "$interval")

        log "Main loop: sleeping ${sleep_hours}h — next video at ${next_wake}"
        notify "😴 Next main video in ${sleep_hours}h — at ${next_wake}"
        sleep "$interval"
    done
}

# ─────────────────────────────────────────────
# START BOTH LOOPS IN PARALLEL
# Short loop runs in the background.
# Main loop runs in the foreground (keeps the worker process alive).
# If either crashes, Railway restarts the worker automatically.
# ─────────────────────────────────────────────
log "Midnight Cabin worker starting..."
log "Main interval: ${MAIN_INTERVAL_HOURS}h | Short interval: ${SHORT_INTERVAL_HOURS}h"
log "Deploy delay: $([ "${SKIP_MAIN_DELAY:-0}" = "1" ] && echo "SKIPPED" || echo "${MAIN_INTERVAL_HOURS}h")"

short_loop &
SHORT_PID=$!
log "Short loop started in background (PID $SHORT_PID)"

main_loop