"""
upload_short.py — uploads output/short.mp4 as a YouTube Short
"""

import os
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")
SHORT_FILE = os.path.join(BASE_DIR, "output", "short.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
META_FILE = os.path.join(PERSISTENT_DIR, "current_short.json")

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
# LOAD SHORT METADATA
# ─────────────────────────────────────────────
if not os.path.exists(META_FILE):
    raise FileNotFoundError(f"Short metadata not found: {META_FILE}")

with open(META_FILE) as f:
    meta = json.load(f)

if not os.path.exists(SHORT_FILE):
    raise FileNotFoundError(f"Short video not found: {SHORT_FILE}")

theme = meta.get("theme", "Ambient Soundscape")
primary = meta.get("primary", "brown_noise")
layers = meta.get("layers", [])
mood = meta.get("mood", "calm")
duration_label = meta.get("duration_label", "8 Hours")
hook_text = meta.get("hook_text", "")
hook_style = meta.get("hook_style", "pov")

# ─────────────────────────────────────────────
# BUILD SHORT TITLE — varies by hook style
# ─────────────────────────────────────────────
POV_TITLES = {
    "rain":         "Rain sounds for when you can't sleep 🌧️ #Shorts",
    "fireplace":    "Cozy fireplace vibes at midnight 🔥 #Shorts",
    "river":        "River sounds to calm your mind 🌊 #Shorts",
    "ocean_waves":  "Ocean waves sleep sounds 🌊 #Shorts",
    "soft_wind":    "Soft wind ambience at midnight 🍃 #Shorts",
    "night_forest": "Forest night sounds for deep sleep 🌲 #Shorts",
    "brown_noise":  "Brown noise for ADHD focus 🧠 #Shorts",
}

EDUCATIONAL_TITLES = {
    "rain":         "Why rain sounds help you sleep faster 🌧️ #Shorts",
    "fireplace":    "Why fireplace sounds reduce anxiety 🔥 #Shorts",
    "river":        "Why river sounds lower stress hormones 🌊 #Shorts",
    "ocean_waves":  "Why ocean waves match your sleep frequency 🌊 #Shorts",
    "soft_wind":    "Why wind sounds improve deep sleep 🍃 #Shorts",
    "night_forest": "Why nature sounds reset your nervous system 🌲 #Shorts",
    "brown_noise":  "Why brown noise helps ADHD brains focus 🧠 #Shorts",
}

CONTRAST_TITLES = {
    "rain":         "Your brain before vs after rain sounds 🌧️ #Shorts",
    "fireplace":    "Silence vs fireplace ambience 🔥 #Shorts",
    "river":        "Stressed vs calm — river sounds 🌊 #Shorts",
    "ocean_waves":  "Anxious vs peaceful — ocean waves 🌊 #Shorts",
    "soft_wind":    "City noise vs midnight wind 🍃 #Shorts",
    "night_forest": "Insomnia vs forest night sounds 🌲 #Shorts",
    "brown_noise":  "ADHD without vs with brown noise 🧠 #Shorts",
}

title_maps = {
    "pov": POV_TITLES,
    "educational": EDUCATIONAL_TITLES,
    "contrast": CONTRAST_TITLES,
}

title = title_maps.get(hook_style, POV_TITLES).get(
    primary,
    f"{theme} | 60 Second Preview #Shorts"
)

# ─────────────────────────────────────────────
# BUILD DESCRIPTION
# ─────────────────────────────────────────────
description = f"""{hook_text}

60 seconds of {primary.replace('_', ' ')} ambience — {mood} mood.

🎵 Full {duration_label} version on our channel with no ads, no interruptions.

👉 Subscribe @midnightcabins for daily sleep & focus soundscapes.

#Shorts #SleepSounds #AmbientSounds #{primary.replace('_', '').title()} #Relaxation #{'ADHD' if primary == 'brown_noise' else 'Sleep'}
"""

# ─────────────────────────────────────────────
# TAGS
# ─────────────────────────────────────────────
tags = [
    "shorts",
    "sleep sounds shorts",
    "ambient shorts",
    primary.replace("_", " "),
    f"{primary.replace('_', ' ')} sounds",
    "relaxing sounds",
    "sleep",
    "study music shorts",
    "brown noise",
    "ASMR shorts",
    "calm sounds",
    "midnight cabins",
][:15]

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
print(f"Uploading Short: {title}")

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "10",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    },
    media_body=MediaFileUpload(SHORT_FILE, chunksize=-1, resumable=True)
)

response = request.execute()
video_id = response["id"]
print(f"Short uploaded: https://youtube.com/shorts/{video_id}")

# THUMBNAIL
if os.path.exists(THUMBNAIL_FILE):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMBNAIL_FILE)
        ).execute()
        print("Thumbnail uploaded to Short")
    except Exception as e:
        print(f"Thumbnail failed (non-fatal): {e}")

# ─────────────────────────────────────────────
# SAVE TO HISTORY
# ─────────────────────────────────────────────
record = {
    "video_id": video_id,
    "title": title,
    "theme": theme,
    "type": "short",
    "primary": primary,
    "sound_layers": layers,
    "uploaded_at": datetime.now().isoformat(),
    "privacy_status": "public",
    "performance": {}
}

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE) as f:
        history = json.load(f)
else:
    history = []

history.append(record)
with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

# TELEGRAM NOTIFICATION
try:
    import requests as _req
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        msg = f"🎬 Short uploaded!\nhttps://youtube.com/shorts/{video_id}\n\nTitle: {title}"
        _req.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": msg},
            timeout=10
        )
except Exception:
    pass

print(f"Short saved to history: {video_id}")