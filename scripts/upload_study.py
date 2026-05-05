import os
import json
import subprocess
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_utils import generate_chapters, get_full_tags, pin_comment, post_community_update

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
SOURCE_VIDEO = os.path.join(BASE_DIR, "output", "video.mp4")
STUDY_VIDEO = os.path.join(BASE_DIR, "output", "video_study.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")

STUDY_PLAYLIST_ID = "PL1C0d7IpxX4vaGtoLf3zbjOTSIjY_cWVE"

# Pomodoro settings
FOCUS_MINUTES = 25
BREAK_MINUTES = 5
POMODORO_CYCLE = (FOCUS_MINUTES + BREAK_MINUTES) * 60  # seconds per cycle

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
if not creds or not creds.valid:
    raise RuntimeError("Invalid credentials")

youtube = build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
idea_path = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(idea_path):
    idea_path = os.path.join(BASE_DIR, "current_idea.json")

with open(idea_path, "r") as f:
    idea = json.load(f)

if not os.path.exists(SOURCE_VIDEO):
    raise FileNotFoundError(f"Source video not found: {SOURCE_VIDEO}")

duration_minutes = idea.get("duration_minutes", 480)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"
layers = idea.get("sound_layers", [])
primary = idea.get("audio_strategy", {}).get("primary_category", "brown_noise")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
theme = idea.get("theme", "")
duration_seconds = duration_minutes * 60

# ─────────────────────────────────────────────
# RENDER POMODORO OVERLAY VERSION
# Shows: FOCUS 25:00 counting down, then BREAK 5:00
# Subtle text in bottom right corner
# ─────────────────────────────────────────────
print("Rendering Study With Me (Pomodoro) version...")

# ffmpeg drawtext with Pomodoro timer logic
# mod(t, 1800) gives position within 30-min cycle
# First 1500s = focus (25min), last 300s = break (5min)
pomodoro_filter = (
    # Focus phase text
    "drawtext="
    "text='FOCUS':"
    "fontsize=28:"
    "fontcolor=white@0.6:"
    "x=w-tw-30:"
    "y=h-th-60:"
    "enable='lt(mod(t\\,1800)\\,1500)',"

    # Focus countdown timer
    "drawtext="
    "text='%{eif\\:(1500-mod(t\\,1800))/60\\:d\\:2}\\:%{eif\\:mod(1500-mod(t\\,1800)\\,60)\\:d\\:2}':"
    "fontsize=36:"
    "fontcolor=white@0.8:"
    "x=w-tw-30:"
    "y=h-th-28:"
    "enable='lt(mod(t\\,1800)\\,1500)',"

    # Break phase text
    "drawtext="
    "text='BREAK':"
    "fontsize=28:"
    "fontcolor=lightgreen@0.7:"
    "x=w-tw-30:"
    "y=h-th-60:"
    "enable='gte(mod(t\\,1800)\\,1500)',"

    # Break countdown timer
    "drawtext="
    "text='%{eif\\:(1800-mod(t\\,1800))/60\\:d\\:2}\\:%{eif\\:mod(1800-mod(t\\,1800)\\,60)\\:d\\:2}':"
    "fontsize=36:"
    "fontcolor=lightgreen@0.9:"
    "x=w-tw-30:"
    "y=h-th-28:"
    "enable='gte(mod(t\\,1800)\\,1500)',"

    # Pomodoro session counter (top right)
    "drawtext="
    "text='🍅 %{eif\\:floor(t/1800)+1\\:d}':"
    "fontsize=22:"
    "fontcolor=white@0.5:"
    "x=w-tw-30:"
    "y=20"
)

cmd = [
    "ffmpeg", "-y",
    "-i", SOURCE_VIDEO,
    "-vf", f"{pomodoro_filter},format=yuv420p",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
    "-c:a", "copy",
    "-movflags", "+faststart",
    STUDY_VIDEO
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("Pomodoro render failed:", result.stderr[-500:])
    raise RuntimeError("Study video render failed")

print("Study With Me video rendered successfully")

# ─────────────────────────────────────────────
# BUILD TITLE
# ─────────────────────────────────────────────
sound_label = primary.replace("_", " ").title()

if primary == "brown_noise":
    study_title = f"Study With Me | Brown Noise Pomodoro Timer | {duration_label}"
elif primary in ["rain", "river"]:
    study_title = f"Study With Me | {sound_label} + Pomodoro Timer | {duration_label}"
elif primary == "fireplace":
    study_title = f"Study With Me | Cozy Fireplace Pomodoro | {duration_label}"
else:
    study_title = f"Study With Me | {sound_label} Pomodoro Timer | {duration_label}"

if len(study_title) > 90:
    study_title = f"Study With Me Pomodoro Timer | {duration_label} Focus Music"

print(f"Study title: {study_title}")

# ─────────────────────────────────────────────
# DESCRIPTION
# ─────────────────────────────────────────────
description = f"""Study With Me — Pomodoro Timer Edition 🍅

{duration_label} of ambient sound with a built-in Pomodoro timer overlay.

⏱ Pomodoro Method:
• 25 minutes FOCUS — timer counts down in bottom right
• 5 minutes BREAK — green timer appears
• Repeat until your session is done
• Session counter (🍅) tracks your progress

🎵 Background sound: {", ".join(layers)}
🌙 Mood: {mood.capitalize()}

✨ Perfect for:
• Students and exam prep
• Work from home focus sessions
• Deep work and writing
• Anyone who struggles to stay on task

No ads. No interruptions. Just you, your work, and the timer.

📌 How to use:
1. Open your study materials
2. Start the video
3. Work when you see FOCUS, rest when you see BREAK
4. Repeat for as many sessions as you need

🔔 Subscribe for new Study With Me sessions every few days.

#StudyWithMe #Pomodoro #PomodoroTimer #StudyMusic #FocusMusic #StudySession #DeepWork
"""

# ─────────────────────────────────────────────
# TAGS
# ─────────────────────────────────────────────
all_tags = [
    "study with me",
    "pomodoro timer",
    "pomodoro study",
    "study music pomodoro",
    "focus timer",
    "study session",
    f"{duration_label.lower()} study",
    "deep work timer",
    "study with me timer",
    "pomodoro technique",
    "focus music",
    "study music",
    "work with me",
    "productivity timer",
    "ambient study music"
][:15]

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
print("Uploading Study With Me video...")
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": study_title,
            "description": description,
            "tags": all_tags,
            "categoryId": "10"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload(STUDY_VIDEO, chunksize=-1, resumable=True)
)

response = request.execute()
video_id = response["id"]
print(f"Study video uploaded: https://youtube.com/watch?v={video_id}")

# THUMBNAIL
if os.path.exists(THUMBNAIL_FILE):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMBNAIL_FILE)
        ).execute()
        print("Thumbnail uploaded")
    except Exception as e:
        print(f"Thumbnail failed (non-fatal): {e}")

# PLAYLIST
try:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": STUDY_PLAYLIST_ID,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}
            }
        }
    ).execute()
    print(f"Added to Study With Me playlist")
except Exception as e:
    print(f"Playlist failed (non-fatal): {e}")

# HISTORY
record = {
    "video_id": video_id,
    "title": study_title,
    "theme": theme,
    "type": "study_with_me",
    "sound_layers": layers,
    "duration_minutes": duration_minutes,
    "playlist_id": STUDY_PLAYLIST_ID,
    "uploaded_at": datetime.now().isoformat(),
    "privacy_status": "public",
    "performance": {}
}

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
else:
    history = []

history.append(record)
with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

print(f"Study video saved to history: {video_id}")

# Pin comment and community post
pin_comment(youtube, video_id, primary, duration_label, layers)
post_community_update(youtube, video_id, title if "title" in dir() else study_title if "study_title" in dir() else adhd_title if "adhd_title" in dir() else dark_title, primary, duration_label)