import os
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_utils import generate_chapters, get_full_tags, pin_comment, post_community_update, get_sound_attributions, get_ai_disclosure

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",          # full management — needed for playlists + end screens
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")
CLIENT_SECRET_FILE = os.path.join(PERSISTENT_DIR, "client_secret.json")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
VIDEO_FILE = os.path.join(BASE_DIR, "output", "video.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")

# ─────────────────────────────────────────────
# PLAYLIST MAP — category → playlist ID
# ─────────────────────────────────────────────
PLAYLIST_MAP = {
    "rain":         "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "river":        "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "ocean_waves":  "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "fireplace":    "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "thunder":      "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "night_forest": "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "soft_wind":    "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",  # Deep Sleep Sounds
    "brown_noise":  "PL1C0d7IpxX4voVewbgJZoQjizPugYaM0n",  # Focus & Study
}

# Best performing video ID for end screen
BEST_VIDEO_ID = "xRj8cDUHCxg"

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
# Read from persistent dir — falls back to BASE_DIR if not found
idea_path = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(idea_path):
    idea_path = os.path.join(BASE_DIR, "current_idea.json")
with open(idea_path, "r") as f:
    idea = json.load(f)

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Video file not found: {VIDEO_FILE}")

duration_minutes = idea.get("duration_minutes", 480)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"
duration_seconds = duration_minutes * 60

layers = idea.get("sound_layers", [])
primary = idea.get("audio_strategy", {}).get("primary_category", "brown_noise")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
theme = idea.get("theme", "")

# ─────────────────────────────────────────────
# BUILD TAGS
# ─────────────────────────────────────────────
all_tags = get_full_tags(primary, layers, duration_label, "main")

# ─────────────────────────────────────────────
# BUILD DESCRIPTION
# ─────────────────────────────────────────────
chapters = generate_chapters(duration_minutes, layers, primary)
sound_credits = get_sound_attributions(PERSISTENT_DIR)
ai_disclosure = get_ai_disclosure()
# Get storyline from idea (scene-setting story)
storyline = idea.get("storyline", "")

description = f"""{storyline}

{duration_label} of uninterrupted {primary.replace("_", " ")} sounds for deep sleep, relaxation, and focused work. No mid-roll interruptions, no vocals, no sudden sounds.

Best for:
• Falling asleep faster on a restless night
• Study sessions, deep work, and ADHD focus
• Meditation, mindfulness, and unwinding
• Reading, journaling, and creative work
• Background ambience while working from home

Whether you're in London, New York, Sydney, or Mumbai — let this play quietly in the background tonight.

🎵 Sound layers: {", ".join(layers)}
🌙 Mood: {mood.capitalize()}
⏱ Duration: {duration_label}

Subscribe @midnightcabins for new Midnight Cabin soundscapes.

📌 Chapters:
{chapters}

{ai_disclosure}

{sound_credits}

#SleepSounds #AmbientSounds #BrownNoise #Relaxation #FocusMusic #DeepSleep #SleepMusic #RainSounds #StudyMusic #ADHDFocus
"""

# ─────────────────────────────────────────────
# UPLOAD VIDEO
# ─────────────────────────────────────────────
print("Uploading video...")
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
print("Upload response:", response)
video_id = response["id"]
print(f"Video uploaded: https://youtube.com/watch?v={video_id}")

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
    print("No thumbnail found, skipping")

# ─────────────────────────────────────────────
# PLAYLIST ASSIGNMENT
# Auto-assigns to the right playlist based on primary category
# Falls back to Deep Sleep Sounds if category not found
# ─────────────────────────────────────────────
playlist_id = PLAYLIST_MAP.get(primary, "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k")

try:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    print(f"Added to playlist: {playlist_id}")
except Exception as e:
    print(f"Playlist assignment failed (non-fatal): {e}")

# ─────────────────────────────────────────────
# END SCREENS
# YouTube's end screen API (part=endscreen) is not available
# via the public Data API — it's YouTube Studio only.
# Add end screens manually in YouTube Studio for each video:
# Edit video → End screen → Add element → Subscribe + Video
# ─────────────────────────────────────────────
print(f"Reminder: Add end screen manually in YouTube Studio for video {video_id}")

# ─────────────────────────────────────────────
# SAVE TO HISTORY
# ─────────────────────────────────────────────
record = {
    "video_id": video_id,
    "title": idea.get("title"),
    "theme": idea.get("theme"),
    "sound_layers": layers,
    "visual": idea.get("visual"),
    "duration_minutes": duration_minutes,
    "audio_strategy": idea.get("audio_strategy", {}),
    "learning_reason": idea.get("learning_reason"),
    "thumbnail_variant": idea.get("thumbnail_variant", "A"),
    "playlist_id": playlist_id,
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

print("Saved to history:", video_id)
print(f"Thumbnail variant: {record['thumbnail_variant']}")
print(f"Playlist: {playlist_id}")

# Post a comment on the video (pin manually in YouTube Studio)
pin_comment(youtube, video_id, primary, duration_label, layers)

# Post community tab update
post_community_update(youtube, video_id, idea["title"], primary, duration_label)

# Send Telegram reminder to pin the comment
try:
    import requests as _req
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        msg = f"📌 Pin the comment on your new video:\nhttps://studio.youtube.com/video/{video_id}/comments"
        _req.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                  data={"chat_id": chat_id, "text": msg}, timeout=10)
except Exception:
    pass