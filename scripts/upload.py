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
from youtube_utils import (
    generate_chapters, get_full_tags, pin_comment, post_community_update,
    get_sound_attributions, get_ai_disclosure, get_production_note,
    get_quality_summary, get_playlist_ids_for_idea, add_video_to_playlists,
    send_upload_checklist
)

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
is_flagship = idea.get("is_flagship") or idea.get("content_tier") == "flagship"
production_note = get_production_note("main", is_flagship)
quality_summary = get_quality_summary(idea)

primary_hashtags = {
    "rain":         "#RainSounds #RainSoundsForSleeping #RainSoundsForStudying #RainyNight",
    "river":        "#RiverSounds #WaterSounds #NatureSoundsForSleep #StreamSounds",
    "fireplace":    "#FireplaceSounds #CozySounds #FireplaceAmbience #CracklingFire",
    "ocean_waves":  "#OceanSounds #OceanWaves #BeachSounds #WaveSounds",
    "soft_wind":    "#WindSounds #NightSounds #NatureAmbience #SoftWind",
    "night_forest": "#ForestSounds #NatureSounds #NightForest #CricketSounds",
    "brown_noise":  "#BrownNoise #BrownNoiseADHD #BrownNoiseForFocus #ADHDFocus",
    "thunder":      "#ThunderstormSounds #RainAndThunder #StormSounds #Thunderstorm",
}
sound_hashtags = primary_hashtags.get(primary, "#SleepSounds #AmbientSounds")

description = f"""{primary.replace("_", " ").title()} sounds for sleeping — {duration_label} of pure, steady audio with no music, no talking, and no sudden sounds.

{storyline}

✅ What you get:
• {duration_label} of pure {primary.replace("_", " ")} sounds — no talking, no music
• No vocals, no sudden volume changes
• Safe for overnight playback and all-night listening
• Works with sleep timers and screen-off mode

🎧 Best for:
• Falling asleep to {primary.replace("_", " ")} sounds
• Blocking out background noise while studying or working
• ADHD focus and deep work sessions
• Meditation, anxiety relief, and unwinding

💛 Support the cabin → https://ko-fi.com/midnightcabins
🎵 Listen on Spotify → search "Midnight Cabins" on Spotify

🎵 Sound layers: {", ".join(layers)}
⏱ Duration: {duration_label}

{quality_summary}

📌 Chapters:
{chapters}

{production_note}

{ai_disclosure}

{sound_credits}

{sound_hashtags} #SleepSounds #DeepSleep #AmbientSounds #SleepMusic #RelaxingSounds #FocusMusic #StudyMusic #NatureSounds
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

import time as _time
response = None
for _attempt in range(3):
    try:
        response = request.execute()
        break
    except Exception as _upload_err:
        if _attempt < 2:
            _wait = 30 * (_attempt + 1)
            print(f"Upload attempt {_attempt+1} failed: {_upload_err} — retrying in {_wait}s")
            _time.sleep(_wait)
            request = youtube.videos().insert(
                part="snippet,status",
                body={"snippet": {"title": idea["title"], "description": description, "tags": all_tags, "categoryId": "10"}, "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
                media_body=MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True)
            )
        else:
            raise
if not response:
    raise RuntimeError("Upload failed after 3 attempts")
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
# PLAYLIST FUNNELS
# Adds each video to multiple intent-based playlists: sleep, focus, dark screen, storms, 10h, flagship, etc.
# Playlist IDs can be overridden with PLAYLIST_* env vars in youtube_utils.py.
# ─────────────────────────────────────────────
playlist_ids = get_playlist_ids_for_idea(idea, "main")
added_playlist_ids = add_video_to_playlists(youtube, video_id, playlist_ids)
playlist_id = added_playlist_ids[0] if added_playlist_ids else (playlist_ids[0] if playlist_ids else "")

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
    "playlist_ids": added_playlist_ids,
    "content_tier": idea.get("content_tier", "standard"),
    "is_flagship": bool(is_flagship),
    "flagship_package": idea.get("flagship_package", {}),
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
pin_comment(youtube, video_id, primary, duration_label, layers, idea, "main")

# Post community tab update
post_community_update(youtube, video_id, idea["title"], primary, duration_label)

send_upload_checklist(video_id, idea.get("title", ""), "main")