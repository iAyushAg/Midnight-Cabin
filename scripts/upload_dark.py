import os
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")
CLIENT_SECRET_FILE = os.path.join(PERSISTENT_DIR, "client_secret.json")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
VIDEO_FILE = os.path.join(BASE_DIR, "output", "video_dark.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")

DARK_SCREEN_PLAYLIST_ID = "PL1C0d7IpxX4tlvxdvXDlQmIHhs0VwxEKi"

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
if not creds or not creds.valid:
    raise RuntimeError("Invalid credentials — re-authenticate locally first")

youtube = build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
idea_path = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(idea_path):
    idea_path = os.path.join(BASE_DIR, "current_idea.json")

with open(idea_path, "r") as f:
    idea = json.load(f)

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Dark screen video not found: {VIDEO_FILE}")

duration_minutes = idea.get("duration_minutes", 480)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"
layers = idea.get("sound_layers", [])
primary = idea.get("audio_strategy", {}).get("primary_category", "brown_noise")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
theme = idea.get("theme", "")

# ─────────────────────────────────────────────
# BUILD DARK SCREEN TITLE
# ─────────────────────────────────────────────
original_title = idea.get("title", "")

# Remove existing duration label and add dark screen suffix
base_title = original_title
for label in ["10 Hours", "8 Hours", "10 hours", "8 hours"]:
    base_title = base_title.replace(label, "").strip()
base_title = base_title.strip("| -–").strip()

dark_title = f"{base_title} | {duration_label} Dark Screen"

# Ensure under 90 chars
if len(dark_title) > 90:
    dark_title = f"{duration_label} {primary.replace('_', ' ').title()} Dark Screen Sleep"

print(f"Dark screen title: {dark_title}")

# ─────────────────────────────────────────────
# BUILD DARK SCREEN DESCRIPTION
# ─────────────────────────────────────────────
description = f"""{theme} — Dark Screen Version

{duration_label} of uninterrupted {primary.replace('_', ' ')} sounds for deep sleep — with a completely black screen so your device won't disturb your rest.

🌑 Dark screen — no light, no distractions
🎵 Sound layers: {", ".join(layers)}
🌙 Mood: {mood.capitalize()}
⏱ Duration: {duration_label}

✨ Perfect for:
• Sleeping with your phone or TV on
• People sensitive to screen light at night
• ASMR and relaxation without visual stimulation
• Overnight background ambience

No ads. No interruptions. Screen stays black.

🔔 Subscribe for new dark screen soundscapes every few days.

#DarkScreen #BlackScreen #SleepSounds #BrownNoise #AmbientSounds #SleepMusic
"""

# ─────────────────────────────────────────────
# BUILD TAGS
# ─────────────────────────────────────────────
base_tags = [
    "dark screen",
    "black screen",
    "sleep sounds dark screen",
    "brown noise dark screen",
    f"{duration_label.lower()} dark screen",
    f"{duration_label.lower()} sleep",
    "sleep sounds",
    "ambient sounds",
    "no ads sleep",
    "screen off sleep sounds",
]

theme_tags = {
    "rain":         ["rain dark screen", "rain sounds black screen"],
    "river":        ["river sounds dark screen", "stream dark screen"],
    "fireplace":    ["fireplace dark screen", "fire sounds black screen"],
    "ocean_waves":  ["ocean dark screen", "waves black screen"],
    "soft_wind":    ["wind sounds dark screen"],
    "night_forest": ["forest sounds dark screen"],
    "brown_noise":  ["brown noise dark screen", "brown noise black screen"],
}

extra_tags = []
for layer in layers:
    extra_tags.extend(theme_tags.get(layer, []))

all_tags = list(dict.fromkeys(base_tags + extra_tags))[:15]

# ─────────────────────────────────────────────
# UPLOAD DARK SCREEN VIDEO
# ─────────────────────────────────────────────
print("Uploading dark screen video...")
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": dark_title,
            "description": description,
            "tags": all_tags,
            "categoryId": "10"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True)
)

response = request.execute()
video_id = response["id"]
print(f"Dark screen video uploaded: https://youtube.com/watch?v={video_id}")

# ─────────────────────────────────────────────
# THUMBNAIL — reuse main video thumbnail
# ─────────────────────────────────────────────
if os.path.exists(THUMBNAIL_FILE):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMBNAIL_FILE)
        ).execute()
        print("Thumbnail uploaded to dark screen video")
    except Exception as e:
        print(f"Thumbnail upload failed (non-fatal): {e}")

# ─────────────────────────────────────────────
# PLAYLIST ASSIGNMENT — dark screen playlist
# ─────────────────────────────────────────────
try:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": DARK_SCREEN_PLAYLIST_ID,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    print(f"Added to dark screen playlist: {DARK_SCREEN_PLAYLIST_ID}")
except Exception as e:
    print(f"Playlist assignment failed (non-fatal): {e}")

# ─────────────────────────────────────────────
# SAVE TO HISTORY
# ─────────────────────────────────────────────
record = {
    "video_id": video_id,
    "title": dark_title,
    "theme": theme,
    "type": "dark_screen",
    "sound_layers": layers,
    "duration_minutes": duration_minutes,
    "audio_strategy": idea.get("audio_strategy", {}),
    "playlist_id": DARK_SCREEN_PLAYLIST_ID,
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

print(f"Dark screen video saved to history: {video_id}")
print(f"Title: {dark_title}")