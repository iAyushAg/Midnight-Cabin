#!/bin/bash
set -e

echo "Starting pipeline..."

python3 scripts/generate_idea.py
python3 scripts/generate_audio.py

mkdir -p output

ffmpeg -y -loop 1 -i video/bg.jpg -i audio/brown_noise.wav \
-filter_complex "zoompan=z='min(zoom+0.0005,1.1)':d=125" \
-c:v libx264 -preset fast -crf 23 \
-c:a aac -b:a 192k \
-ar 44100 \
-pix_fmt yuv420p \
-r 30 \
-g 60 \
-shortest \
-movflags +faststart \
output/video.mp4

ls -lh output/video.mp4

python3 scripts/upload.py

echo "Pipeline finished"