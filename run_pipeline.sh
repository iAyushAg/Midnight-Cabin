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
python3 scripts/generate_audio.py

echo "Audio folder after generation:"
ls -la audio || echo "audio folder missing"

echo "Find WAV files:"
find . -name "*.wav" -print