#!/bin/bash
set -e

echo "Current folder:"
pwd

echo "Project files:"
ls -la

echo "Scripts:"
ls -la scripts

echo "Starting pipeline..."


python3 scripts/collect_stats.py || echo "Stats collection skipped"
python3 scripts/generate_idea.py
python3 scripts/generate_visual.py || echo "Visual generation skipped"
python3 scripts/fetch_freesound.py || echo "Freesound fetch skipped"
python3 scripts/generate_audio.py

echo "Audio folder after generation:"
ls -la audio || echo "audio folder missing"

echo "Find WAV files:"
find . -name "*.wav" -print
echo "Creating output folder..."
mkdir -p output

echo "Generating video..."

ffmpeg -y -loop 1 -i video/bg.jpg -stream_loop 4 -i audio/brown_noise.wav \
-t 600 \
-vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p" \
-c:v libx264 -preset ultrafast -crf 28 \
-c:a aac -b:a 128k \
-ar 44100 \
-r 15 \
-g 30 \
-movflags +faststart \
output/video.mp4

echo "Video created:"
ls -lh output/

echo "Uploading..."
python3 scripts/generate_thumbnail.py

python3 scripts/upload.py

echo "Pipeline finished"