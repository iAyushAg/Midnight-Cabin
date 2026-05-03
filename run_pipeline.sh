#!/bin/bash
set -e

echo "Current folder:"
pwd

echo "Project files:"
ls -la

echo "Scripts:"
ls -la scripts

echo "Starting pipeline..."

python3 scripts/generate_idea.py
python3 scripts/generate_visual.py
python3 scripts/generate_audio.py

echo "Audio folder after generation:"
ls -la audio || echo "audio folder missing"

echo "Find WAV files:"
find . -name "*.wav" -print

echo "Creating output folder..."
mkdir -p output

echo "Generating video..."

ffmpeg -y -loop 1 -i video/bg.jpg -i audio/brown_noise.wav \
-vf "scale=2200:-1,zoompan=z='min(zoom+0.00015,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=14400:s=1920x1080:fps=24,format=yuv420p" \
-c:v libx264 -preset veryfast -crf 23 \
-c:a aac -b:a 192k \
-ar 44100 \
-r 24 \
-g 48 \
-shortest \
-movflags +faststart \
output/video.mp4

echo "Video created:"
ls -lh output/

echo "Uploading..."

python3 scripts/upload.py

echo "Pipeline finished"