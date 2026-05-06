#!/bin/bash
# ─────────────────────────────────────────────────────────
# test_animation.sh — downloads real video overlays and
# composites them on bg.jpg to preview animation locally
# Run from your Midnight-Cabin project root
# ─────────────────────────────────────────────────────────

set -e
# Stay in current directory — run this from project root

echo "🎬 Animation Test — Midnight Cabins"
echo "────────────────────────────────────"

if [ ! -f "video/bg.jpg" ]; then
    echo "❌ No video/bg.jpg found. Run first:"
    echo "   PERSISTENT_DIR=. python3 scripts/generate_visual.py"
    exit 1
fi

mkdir -p video output

# ─────────────────────────────────────────────────────────
# DOWNLOAD RAIN ON GLASS overlay
# Free from Pixabay — rain streaking down a window
# ─────────────────────────────────────────────────────────
RAIN_VIDEO="video/rain_overlay.mp4"
if [ ! -f "$RAIN_VIDEO" ]; then
    echo "📥 Downloading rain on glass overlay..."
    
    PIXABAY_KEY="55726621-3fc62672f528e610d6419d335"
    if [ -n "$PIXABAY_KEY" ]; then
        RAIN_URL=$(python3 - << PYEOF
import requests
resp = requests.get(
    "https://pixabay.com/api/videos/",
    params={
        "key": "$PIXABAY_KEY",
        "q": "rain window glass drops",
        "per_page": 10,
        "min_duration": 5,
    },
    timeout=30
)
hits = resp.json().get("hits", [])
for hit in hits:
    v = hit.get("videos", {})
    url = v.get("medium", {}).get("url") or v.get("small", {}).get("url", "")
    if url:
        print(url)
        break
PYEOF
)
        if [ -n "$RAIN_URL" ]; then
            curl -sL "$RAIN_URL" -o "$RAIN_VIDEO"
            echo "✅ Rain overlay downloaded"
        else
            echo "⚠️  Pixabay rain not found — using direct URL"
            # Fallback direct URLs from Pixabay free videos
            curl -sL "https://cdn.pixabay.com/video/2016/01/05/1650-150295744_medium.mp4" -o "$RAIN_VIDEO" || true
        fi
    else
        echo "⚠️  No PIXABAY_API_KEY — downloading from direct URL..."
        # Public domain rain video
        curl -sL "https://cdn.pixabay.com/video/2016/01/05/1650-150295744_medium.mp4" -o "$RAIN_VIDEO" || \
        curl -sL "https://www.pexels.com/download/video/3576378/" -o "$RAIN_VIDEO" || true
    fi
fi

# ─────────────────────────────────────────────────────────
# DOWNLOAD FIRE overlay
# ─────────────────────────────────────────────────────────
FIRE_VIDEO="video/fire_overlay.mp4"
if [ ! -f "$FIRE_VIDEO" ]; then
    echo "📥 Downloading fire/fireplace overlay..."
    
    PIXABAY_KEY="${PIXABAY_API_KEY:-}"
    if [ -n "$PIXABAY_KEY" ]; then
        FIRE_URL=$(python3 - << PYEOF
import requests
resp = requests.get(
    "https://pixabay.com/api/videos/",
    params={
        "key": "$PIXABAY_KEY",
        "q": "fireplace fire burning flames",
        "per_page": 10,
        "min_duration": 5,
    },
    timeout=30
)
hits = resp.json().get("hits", [])
for hit in hits:
    v = hit.get("videos", {})
    url = v.get("medium", {}).get("url") or v.get("small", {}).get("url", "")
    if url:
        print(url)
        break
PYEOF
)
        if [ -n "$FIRE_URL" ]; then
            curl -sL "$FIRE_URL" -o "$FIRE_VIDEO"
            echo "✅ Fire overlay downloaded"
        fi
    else
        echo "⚠️  No PIXABAY_API_KEY set"
        echo "   Add PIXABAY_API_KEY=your_key before running"
        echo "   Or manually download a fire video to video/fire_overlay.mp4"
    fi
fi

echo ""
echo "🎞️  Compositing overlays on background image..."

# ─────────────────────────────────────────────────────────
# COMPOSITE — rain on top half + fire bottom-right
# ─────────────────────────────────────────────────────────

HAS_RAIN=false
HAS_FIRE=false
[ -f "$RAIN_VIDEO" ] && HAS_RAIN=true
[ -f "$FIRE_VIDEO" ] && HAS_FIRE=true

if $HAS_RAIN && $HAS_FIRE; then
    echo "Rendering with rain + fire..."
    ffmpeg -y \
        -loop 1 -i video/bg.jpg \
        -stream_loop -1 -i "$RAIN_VIDEO" \
        -stream_loop -1 -i "$FIRE_VIDEO" \
        -t 15 \
        -filter_complex "
            [0:v]scale=1280:720[bg];
            [1:v]scale=1280:360,
                 format=yuva420p,
                 colorchannelmixer=aa=0.35[rain];
            [2:v]scale=320:280,
                 format=yuva420p,
                 colorchannelmixer=aa=0.75[fire];
            [bg][rain]overlay=0:0[v1];
            [v1][fire]overlay=W-w-10:H-h-10[v2];
            [v2]format=yuv420p[out]" \
        -map "[out]" \
        -an \
        -c:v libx264 -preset fast -crf 22 -r 24 \
        output/test_animation.mp4

elif $HAS_RAIN; then
    echo "Rendering with rain only..."
    ffmpeg -y \
        -loop 1 -i video/bg.jpg \
        -stream_loop -1 -i "$RAIN_VIDEO" \
        -t 15 \
        -filter_complex "
            [0:v]scale=1280:720[bg];
            [1:v]scale=1280:400,
                 format=yuva420p,
                 colorchannelmixer=aa=0.35[rain];
            [bg][rain]overlay=0:0[v1];
            [v1]format=yuv420p[out]" \
        -map "[out]" \
        -an \
        -c:v libx264 -preset fast -crf 22 -r 24 \
        output/test_animation.mp4

elif $HAS_FIRE; then
    echo "Rendering with fire only..."
    ffmpeg -y \
        -loop 1 -i video/bg.jpg \
        -stream_loop -1 -i "$FIRE_VIDEO" \
        -t 15 \
        -filter_complex "
            [0:v]scale=1280:720[bg];
            [1:v]scale=320:280,
                 format=yuva420p,
                 colorchannelmixer=aa=0.75[fire];
            [bg][fire]overlay=W-w-10:H-h-10[v1];
            [v1]format=yuv420p[out]" \
        -map "[out]" \
        -an \
        -c:v libx264 -preset fast -crf 22 -r 24 \
        output/test_animation.mp4

else
    echo "❌ No overlay videos available"
    echo "   Set PIXABAY_API_KEY and run again"
    exit 1
fi

echo ""
echo "✅ Animation test rendered: output/test_animation.mp4"
open output/test_animation.mp4