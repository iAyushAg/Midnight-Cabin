import os
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
HISTORY_FILE = os.path.join(BASE_DIR, "video_history.json")
VIDEO_FILE = os.path.join(BASE_DIR, "output", "video.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
creds = None

if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

if not creds or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="")
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
with open(os.path.join(BASE_DIR, "current_idea.json"), "r") as f:
    idea = json.load(f)

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Video file not found: {VIDEO_FILE}")

duration_minutes = idea.get("duration_minutes", 60)
duration_label = "3 Hours" if duration_minutes >= 180 else "1 Hour"

# ─────────────────────────────────────────────
# BUILD TAGS — SEO-aware, duration-aware
# ─────────────────────────────────────────────
base_tags = [
    "sleep sounds",
    "focus music",
    "brown noise",
    "ambient sounds",
    "relaxing sounds",
    "study sounds",
    "deep sleep",
    "white noise",
    "nature sounds",
    f"{duration_label.lower()} sleep",
    f"{duration_label.lower()} focus"
]

theme_tags = {
    "rain": ["rain sounds", "rain for sleep", "rainy night ambience"],
    "river": ["river sounds", "river ambience", "stream sounds"],
    "fireplace": ["fireplace sounds", "crackling fire", "cozy fireplace"],
    "ocean_waves": ["ocean sounds", "wave sounds", "ocean for sleep"],
    "soft_wind": ["wind sounds", "night wind", "wind ambience"],
    "night_forest": ["forest sounds", "forest ambience", "night forest"],
    "brown_noise": ["brown noise", "brown noise sleep", "brown noise focus"],
}

layers = idea.get("sound_layers", [])
extra_tags = []
for layer in layers:
    extra_tags.extend(theme_tags.get(layer, []))

all_tags = list(dict.fromkeys(base_tags + extra_tags))[:15]  # YouTube tag limit ~500 chars

# ─────────────────────────────────────────────
# BUILD DESCRIPTION
# ─────────────────────────────────────────────
theme = idea.get("theme", "")
primary = idea.get("audio_strategy", {}).get("primary_category", "").replace("_", " ")
mood = idea.get("audio_strategy", {}).get("mood", "calm")

description = f"""{theme}

{duration_label} of uninterrupted {primary} sounds for sleep, relaxation, and deep focus.

✨ Perfect for:
• Falling asleep faster
• Study sessions & deep work
• Meditation & mindfulness
• Reading & unwinding
• Background ambience

🎵 Sound layers: {", ".join(layers)}
🌙 Mood: {mood.capitalize()}

No ads. No interruptions. Just pure ambient sound.

🔔 Subscribe for new ambient soundscapes every few days.

#SleepSounds #AmbientSounds #BrownNoise #Relaxation #FocusMusic
"""

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": idea["title"],
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
print("Upload response:")
print(response)

video_id = response["id"]

# ─────────────────────────────────────────────
# THUMBNAIL
# ─────────────────────────────────────────────
if os.path.exists(THUMBNAIL_FILE):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMBNAIL_FILE)
        ).execute()
        print("Thumbnail uploaded")
    except Exception as e:
        print("Thumbnail upload failed:", e)
else:
    print("No thumbnail found, skipping thumbnail upload")

# ─────────────────────────────────────────────
# SAVE TO HISTORY (includes thumbnail variant for A/B)
# ─────────────────────────────────────────────
record = {
    "video_id": video_id,
    "title": idea.get("title"),
    "theme": idea.get("theme"),
    "sound_layers": idea.get("sound_layers", []),
    "visual": idea.get("visual"),
    "duration_minutes": idea.get("duration_minutes"),
    "audio_strategy": idea.get("audio_strategy", {}),
    "learning_reason": idea.get("learning_reason"),
    "thumbnail_variant": idea.get("thumbnail_variant", "A"),  # for A/B tracking
    "uploaded_at": datetime.now().isoformat(),
    "privacy_status": "public",
    "thumbnail_uploaded": os.path.exists(THUMBNAIL_FILE),
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

print("Saved video to history:", video_id)
print(f"Thumbnail variant used: {record['thumbnail_variant']}")
