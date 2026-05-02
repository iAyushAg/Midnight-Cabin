

ffmpeg -y -loop 1 -i video/bg.jpg -i audio/brown_noise.wav \
-vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p" \
-c:v libx264 -preset ultrafast -crf 28 \
-c:a aac -b:a 128k \
-r 24 \
-shortest \
-movflags +faststart \
output/video.mp4