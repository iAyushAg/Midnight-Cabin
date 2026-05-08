#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────
# MIDNIGHT CABIN PIPELINE
# ─────────────────────────────────────────────────────────

echo "Starting pipeline..."

export PERSISTENT_DIR="${PERSISTENT_DIR:-/data}"
mkdir -p "$PERSISTENT_DIR"
mkdir -p output audio video audio_samples

fail() {
    echo "❌ Pipeline failed at: $1"
    exit 1
}

notify() {
    MESSAGE="$1"

    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="$MESSAGE" >/dev/null || true
    fi

    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -s -H "Content-Type: application/json" \
            -X POST \
            -d "{\"content\":\"$MESSAGE\"}" \
            "$DISCORD_WEBHOOK_URL" >/dev/null || true
    fi
}

notify "🌙 Midnight Cabin pipeline starting..."

# ─────────────────────────────────────────────────────────
# REFRESH YOUTUBE AUTH FILES FROM ENV IF AVAILABLE
# ─────────────────────────────────────────────────────────
if [ -n "$YOUTUBE_TOKEN_JSON" ]; then
    echo "$YOUTUBE_TOKEN_JSON" > token.json
    cp token.json "$PERSISTENT_DIR/token.json" || true
    echo "Refreshed token.json"
elif [ -f "$PERSISTENT_DIR/token.json" ]; then
    cp "$PERSISTENT_DIR/token.json" token.json
fi

if [ -n "$YOUTUBE_CLIENT_SECRET_JSON" ]; then
    echo "$YOUTUBE_CLIENT_SECRET_JSON" > client_secret.json
    cp client_secret.json "$PERSISTENT_DIR/client_secret.json" || true
    echo "Refreshed client_secret.json"
elif [ -f "$PERSISTENT_DIR/client_secret.json" ]; then
    cp "$PERSISTENT_DIR/client_secret.json" client_secret.json
fi

echo "Persistent dir:"
ls -la "$PERSISTENT_DIR" || true

# ─────────────────────────────────────────────────────────
# CLEAN BAD AUDIO LICENSES IF SCRIPT SUPPORTS IT
# ─────────────────────────────────────────────────────────
python3 - << 'PYEOF' || true
import json, os
from pathlib import Path

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
path = persistent_dir / "audio_attributions.json"

if not path.exists():
    print("No audio_attributions.json to clean")
    raise SystemExit(0)

with open(path) as f:
    data = json.load(f)

if not isinstance(data, list):
    print("audio_attributions.json is not a list, skipping")
    raise SystemExit(0)

before = len(data)
cleaned = [
    item for item in data
    if "by-nc" not in str(item.get("license", "")).lower()
]
after = len(cleaned)

with open(path, "w") as f:
    json.dump(cleaned, f, indent=2)

print(f"Cleaned {before - after} BY-NC sounds")
PYEOF

# ─────────────────────────────────────────────────────────
# COLLECT STATS
# ─────────────────────────────────────────────────────────
python3 scripts/collect_stats.py || echo "Stats collection skipped"

# ─────────────────────────────────────────────────────────
# GENERATE IDEA
# ─────────────────────────────────────────────────────────
python3 scripts/generate_idea.py || fail "generate_idea"

# Copy idea into persistent dir if script wrote local copy only.
if [ -f current_idea.json ]; then
    cp current_idea.json "$PERSISTENT_DIR/current_idea.json" || true
fi

# ─────────────────────────────────────────────────────────
# READ DURATION
# ─────────────────────────────────────────────────────────
DURATION_MINUTES=$(python3 - << 'PYEOF'
import json, os
from pathlib import Path

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
idea_path = persistent_dir / "current_idea.json"

if not idea_path.exists():
    idea_path = Path("current_idea.json")

with open(idea_path) as f:
    idea = json.load(f)

print(int(idea.get("duration_minutes", 480)))
PYEOF
)

DURATION_SECONDS=$((DURATION_MINUTES * 60))

echo "Duration: $DURATION_MINUTES min"

# ─────────────────────────────────────────────────────────
# GENERATE VISUAL
# ─────────────────────────────────────────────────────────
python3 scripts/generate_visual.py || echo "Visual generation failed — continuing with existing image"

echo "Visual folder:"
ls -lh video || true

# ─────────────────────────────────────────────────────────
# FETCH AUDIO
# ─────────────────────────────────────────────────────────
python3 scripts/fetch_freesound.py || fail "fetch_freesound"

# ─────────────────────────────────────────────────────────
# GENERATE AUDIO
# ─────────────────────────────────────────────────────────
python3 scripts/generate_audio.py || fail "generate_audio"

echo "Audio folder:"
ls -lh audio || true

echo "WAV files:"
find . -name "*.wav" || true

# ─────────────────────────────────────────────────────────
# RENDER VIDEO
# Uses generated image with:
# - Replicate animated clip if available
# - otherwise FFmpeg procedural motion
# ─────────────────────────────────────────────────────────
mkdir -p output

ANIMATED_VIDEO="video/bg_animated.mp4"

if [ -f "$ANIMATED_VIDEO" ]; then
    echo "Using animated video..."

    ffmpeg -y \
        -stream_loop -1 -i "$ANIMATED_VIDEO" \
        -stream_loop -1 -i audio/brown_noise.wav \
        -t "$DURATION_SECONDS" \
        -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
        -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
        -c:v libx264 -preset ultrafast -crf 26 \
        -c:a aac -b:a 192k -ar 44100 -r 24 \
        -movflags +faststart \
        output/video.mp4 || fail "ffmpeg render"

    echo "Video rendered from animated clip"

else
    echo "No animated clip — using high-res Pollinations image with procedural motion..."

    IS_DARK_SCREEN=$(python3 - << 'PYEOF'
import json, os
from pathlib import Path

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
idea_path = persistent_dir / "current_idea.json"

if not idea_path.exists():
    idea_path = Path("current_idea.json")

is_dark = False

if idea_path.exists():
    with open(idea_path) as f:
        idea = json.load(f)

    title = idea.get("title", "").lower()
    genre = idea.get("content_genre", "")
    video_type = idea.get("recommended_video_type", "")

    is_dark = (
        genre == "dark_screen_sleep"
        or video_type == "dark_screen"
        or "dark screen" in title
    )

print("1" if is_dark else "0")
PYEOF
)

    if [ "$IS_DARK_SCREEN" = "1" ]; then
        echo "Dark-screen style render: minimal motion, low brightness..."

        ffmpeg -y \
            -loop 1 -i video/bg.jpg \
            -stream_loop -1 -i audio/brown_noise.wav \
            -t "$DURATION_SECONDS" \
            -filter_complex "\
[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,\
eq=brightness=-0.12:contrast=1.05:saturation=0.75,\
zoompan=z='min(zoom+0.000015,1.035)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=24,\
format=yuv420p[v]" \
            -map "[v]" -map 1:a \
            -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
            -c:v libx264 -preset ultrafast -crf 26 \
            -c:a aac -b:a 192k -ar 44100 -r 24 \
            -movflags +faststart \
            output/video.mp4 || fail "ffmpeg render"

    else
        echo "Normal ambience render: slow zoom/pan + rain/fog/light texture..."

        ffmpeg -y \
            -loop 1 -i video/bg.jpg \
            -stream_loop -1 -i audio/brown_noise.wav \
            -f lavfi -i "color=c=white@0.0:s=1920x1080:r=24" \
            -t "$DURATION_SECONDS" \
            -filter_complex "\
[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,\
zoompan=z='min(zoom+0.000035,1.08)':x='iw/2-(iw/zoom/2)+20*sin(on/720)':y='ih/2-(ih/zoom/2)+12*cos(on/900)':d=1:s=1920x1080:fps=24,\
eq=contrast=1.04:saturation=1.06:brightness=0.01,\
noise=alls=3:allf=t+u[base];\
[2:v]format=rgba,\
geq=r='255':g='255':b='255':a='22*between(mod(Y+T*85,95),0,3)'[rain];\
[base][rain]overlay=0:0:format=auto,\
gblur=sigma=0.25,\
drawbox=x=0:y=0:w=iw:h=ih:color=white@0.018*between(mod(t\,17)\,0\,0.18):t=fill,\
format=yuv420p[v]" \
            -map "[v]" -map 1:a \
            -af "equalizer=f=8000:width_type=o:width=2:g=-6,equalizer=f=100:width_type=o:width=2:g=2" \
            -c:v libx264 -preset ultrafast -crf 26 \
            -c:a aac -b:a 192k -ar 44100 -r 24 \
            -movflags +faststart \
            output/video.mp4 || fail "ffmpeg render"
    fi

    echo "Video rendered from high-res image with FFmpeg procedural motion"
fi

echo "Video created:"
ls -lh output || true



# ─────────────────────────────────────────────────────────
# VIDEO TYPE SELECTION
# Supports recommended_video_type from current_idea.json.
# Allows manual override with FORCE_VIDEO_TYPE.
# ─────────────────────────────────────────────────────────
VIDEO_TYPE=$(python3 - << 'PYEOF'
import json, os
from pathlib import Path

forced = os.environ.get("FORCE_VIDEO_TYPE", "").strip()
allowed = {"main", "adhd", "dark_screen", "study_with_me"}

if forced in allowed:
    print(forced)
    raise SystemExit(0)

persistent_dir = Path(os.environ.get("PERSISTENT_DIR", "/data"))
idea_path = persistent_dir / "current_idea.json"

if not idea_path.exists():
    idea_path = Path("current_idea.json")

recommended = ""

if idea_path.exists():
    with open(idea_path) as f:
        idea = json.load(f)

    recommended = idea.get("recommended_video_type", "")

if recommended in allowed:
    print(recommended)
    raise SystemExit(0)

rotation_file = persistent_dir / "video_type_rotation.json"
order = ["main", "adhd", "dark_screen", "study_with_me"]

if rotation_file.exists():
    with open(rotation_file) as f:
        data = json.load(f)

    last = data.get("last_type", "study_with_me")
    idx = order.index(last) if last in order else -1
    next_type = order[(idx + 1) % len(order)]
else:
    next_type = "main"

persistent_dir.mkdir(parents=True, exist_ok=True)

with open(rotation_file, "w") as f:
    json.dump({"last_type": next_type}, f)

print(next_type)
PYEOF
)

echo "This cycle: $VIDEO_TYPE"
notify "🎬 Midnight Cabin — uploading $VIDEO_TYPE video..."

# ─────────────────────────────────────────────────────────
# THUMBNAIL
# ─────────────────────────────────────────────────────────
echo "Generating thumbnail..."
python3 scripts/generate_thumbnail.py || echo "Thumbnail skipped"

# ─────────────────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────────────────
case "$VIDEO_TYPE" in
    main)
        python3 scripts/upload.py || fail "upload main"
        ;;
    adhd)
        python3 scripts/upload_adhd.py || fail "upload adhd"
        ;;
    dark_screen)
        python3 scripts/upload_dark.py || fail "upload dark_screen"
        ;;
    study_with_me)
        python3 scripts/upload_study.py || fail "upload study_with_me"
        ;;
    *)
        echo "Unknown video type: $VIDEO_TYPE"
        fail "video type selection"
        ;;
esac

notify "✅ Midnight Cabin pipeline completed: $VIDEO_TYPE"
echo "Pipeline complete"