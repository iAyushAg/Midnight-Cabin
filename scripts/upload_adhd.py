import os
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from youtube_utils import generate_chapters, get_full_tags, pin_comment, post_community_update, get_sound_attributions, get_ai_disclosure

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")
HISTORY_FILE = os.path.join(PERSISTENT_DIR, "video_history.json")
VIDEO_FILE = os.path.join(BASE_DIR, "output", "video.mp4")
THUMBNAIL_FILE = os.path.join(BASE_DIR, "thumbnail.jpg")

ADHD_PLAYLIST_ID = "PL1C0d7IpxX4urDAwNHXeOWiow5xOTsye3"

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

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Video not found: {VIDEO_FILE}")

duration_minutes = idea.get("duration_minutes", 480)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"
layers = idea.get("sound_layers", [])
primary = idea.get("audio_strategy", {}).get("primary_category", "brown_noise")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
theme = idea.get("theme", "")

# ─────────────────────────────────────────────
# ADHD TITLE — always angle toward focus/ADHD
# ─────────────────────────────────────────────
sound_label = primary.replace("_", " ").title()

# Pick angle based on primary category
if primary == "brown_noise":
    adhd_title = f"Brown Noise for ADHD Focus | {duration_label} No Interruptions"
elif primary in ["rain", "river", "ocean_waves"]:
    adhd_title = f"{sound_label} + Brown Noise for ADHD | {duration_label} Deep Focus"
elif primary == "fireplace":
    adhd_title = f"Fireplace Brown Noise for ADHD Focus | {duration_label}"
else:
    adhd_title = f"Brown Noise & {sound_label} for ADHD | {duration_label} Focus Music"

# Ensure under 90 chars
if len(adhd_title) > 90:
    adhd_title = f"Brown Noise for ADHD Focus | {duration_label}"

print(f"ADHD title: {adhd_title}")

# ─────────────────────────────────────────────
# ADHD DESCRIPTION
# ─────────────────────────────────────────────
sound_credits = get_sound_attributions(PERSISTENT_DIR)
ai_disclosure = get_ai_disclosure()
description = f"""Brown noise and ambient sound specifically mixed for ADHD focus and deep work.

{duration_label} of uninterrupted sound — no music, no beats, no sudden changes that break concentration.

🧠 Why brown noise helps ADHD:
• Masks distracting background sounds
• Provides consistent auditory stimulation
• Helps quiet racing thoughts
• Scientifically linked to improved focus in ADHD brains

🎵 Sound layers: {", ".join(layers)}
🌙 Mood: {mood.capitalize()}
⏱ Duration: {duration_label}

✨ Perfect for:
• ADHD work and study sessions
• Deep focus and flow state
• Blocking office or home distractions
• Reading and writing tasks

No ads. No interruptions. No music — just pure focus sound.

🔔 Subscribe for new ADHD focus sounds every few days.

#ADHD #BrownNoise #FocusMusic #ADHDFocus #DeepWork #StudyMusic #BrownNoiseADHD #FocusSounds

{ai_disclosure}

{sound_credits}
"""

# ─────────────────────────────────────────────
# TAGS
# ─────────────────────────────────────────────
all_tags = [
    "ADHD focus",
    "brown noise ADHD",
    "ADHD brown noise",
    "focus music ADHD",
    "brown noise focus",
    "ADHD study music",
    "deep work music",
    "concentration music",
    "ADHD sounds",
    f"{duration_label.lower()} focus",
    "no interruptions focus",
    "study music no lyrics",
    "brown noise",
    "focus sounds",
    "ADHD tools"
][:15]

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
print("Uploading ADHD video...")
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": adhd_title,
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
print(f"ADHD video uploaded: https://youtube.com/watch?v={video_id}")

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
                "playlistId": ADHD_PLAYLIST_ID,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}
            }
        }
    ).execute()
    print(f"Added to ADHD playlist")
except Exception as e:
    print(f"Playlist failed (non-fatal): {e}")

# HISTORY
record = {
    "video_id": video_id,
    "title": adhd_title,
    "theme": theme,
    "type": "adhd",
    "sound_layers": layers,
    "duration_minutes": duration_minutes,
    "playlist_id": ADHD_PLAYLIST_ID,
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

print(f"ADHD video saved to history: {video_id}")

# Pin comment and community post
pin_comment(youtube, video_id, primary, duration_label, layers)
post_community_update(youtube, video_id, title if "title" in dir() else study_title if "study_title" in dir() else adhd_title if "adhd_title" in dir() else dark_title, primary, duration_label)