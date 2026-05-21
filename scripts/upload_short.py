"""
upload_short.py — uploads output/short.mp4 as a YouTube Short
"""

import os
import json
import random
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
# ─────────────────────────────────────────────
# TITLE POOLS — multiple titles per niche per style
# Rotated via short_title_rotation.json to prevent repeats
# ─────────────────────────────────────────────
TITLE_POOLS = {
    "pov": {
        "rain":         [
            "Rain sounds for when you can't sleep 🌧️ #Shorts",
            "This is what rain sounds like at 2am 🌧️ #Shorts",
            "Rain at midnight hits different 🌧️ #Shorts",
            "POV: The rain finally arrived 🌧️ #Shorts",
            "When rain is the only sound you need 🌧️ #Shorts",
        ],
        "fireplace":    [
            "Cozy fireplace vibes at midnight 🔥 #Shorts",
            "POV: Nowhere else to be tonight 🔥 #Shorts",
            "Fireplace sounds for when you can't sleep 🔥 #Shorts",
            "This is what a cabin fire sounds like 🔥 #Shorts",
            "When the fire is the only light on 🔥 #Shorts",
        ],
        "river":        [
            "River sounds to calm your mind 🌊 #Shorts",
            "POV: You can hear water outside 🌊 #Shorts",
            "This river sound will slow your thoughts 🌊 #Shorts",
            "River at midnight — uninterrupted 🌊 #Shorts",
            "When flowing water is all you need 🌊 #Shorts",
        ],
        "ocean_waves":  [
            "Ocean waves sleep sounds 🌊 #Shorts",
            "POV: The ocean keeps breathing for you 🌊 #Shorts",
            "This is what falling asleep by the ocean sounds like 🌊 #Shorts",
            "Ocean waves at midnight — no music 🌊 #Shorts",
            "When the tide becomes your heartbeat 🌊 #Shorts",
        ],
        "soft_wind":    [
            "Soft wind ambience at midnight 🍃 #Shorts",
            "POV: Midnight wind through the trees 🍃 #Shorts",
            "Wind sounds for when you can't switch off 🍃 #Shorts",
            "This is what the forest sounds like at 3am 🍃 #Shorts",
            "When wind is the softest sound in the world 🍃 #Shorts",
        ],
        "night_forest": [
            "Forest night sounds for deep sleep 🌲 #Shorts",
            "POV: The forest is completely still 🌲 #Shorts",
            "This is what midnight in a forest sounds like 🌲 #Shorts",
            "Forest ambience for when sleep won't come 🌲 #Shorts",
            "When nature sounds quieter than your thoughts 🌲 #Shorts",
        ],
        "brown_noise":  [
            "Brown noise for ADHD focus 🧠 #Shorts",
            "POV: Your thoughts finally get quieter 🧠 #Shorts",
            "This sound helps ADHD brains focus 🧠 #Shorts",
            "Brown noise hits different when you're overwhelmed 🧠 #Shorts",
            "When your brain needs one steady sound 🧠 #Shorts",
        ],
    },
    "educational": {
        "rain":         [
            "Why rain sounds help you sleep faster 🌧️ #Shorts",
            "What rain actually does to your brain 🌧️ #Shorts",
            "The science behind rain sounds and sleep 🌧️ #Shorts",
            "Why your brain loves rain at night 🌧️ #Shorts",
            "Rain sounds don't just relax you — here's why 🌧️ #Shorts",
        ],
        "fireplace":    [
            "Why fireplace sounds reduce anxiety 🔥 #Shorts",
            "What crackling fire does to your nervous system 🔥 #Shorts",
            "The science behind why fire sounds calm you 🔥 #Shorts",
            "Why your brain finds fire sounds comforting 🔥 #Shorts",
            "Fireplace sounds and cortisol — the connection 🔥 #Shorts",
        ],
        "river":        [
            "Why river sounds lower stress hormones 🌊 #Shorts",
            "What flowing water does to your brain at night 🌊 #Shorts",
            "The science behind river sounds and sleep 🌊 #Shorts",
            "Why pink noise in rivers helps you fall asleep 🌊 #Shorts",
            "River sounds activate this part of your brain 🌊 #Shorts",
        ],
        "ocean_waves":  [
            "Why ocean waves match your sleep frequency 🌊 #Shorts",
            "What the ocean does to your breathing rate 🌊 #Shorts",
            "The science behind ocean waves and deep sleep 🌊 #Shorts",
            "Why 12 waves per minute is the magic number 🌊 #Shorts",
            "Ocean waves and your nervous system — explained 🌊 #Shorts",
        ],
        "soft_wind":    [
            "Why wind sounds improve deep sleep 🍃 #Shorts",
            "What pink noise in wind does to your memory 🍃 #Shorts",
            "The science behind wind sounds and rest 🍃 #Shorts",
            "Why soft wind is better than white noise 🍃 #Shorts",
            "Wind sounds activate your rest-and-digest system 🍃 #Shorts",
        ],
        "night_forest": [
            "Why nature sounds reset your nervous system 🌲 #Shorts",
            "What forest sounds do to your threat response 🌲 #Shorts",
            "The science behind nature sounds and anxiety 🌲 #Shorts",
            "Why your brain trusts forest sounds at night 🌲 #Shorts",
            "Forest ambience lowers cortisol — here's how 🌲 #Shorts",
        ],
        "brown_noise":  [
            "Why brown noise helps ADHD brains focus 🧠 #Shorts",
            "What brown noise does to your prefrontal cortex 🧠 #Shorts",
            "The science behind brown noise and ADHD 🧠 #Shorts",
            "Why brown noise works better than white noise 🧠 #Shorts",
            "Brown noise shifts your brain into focus mode 🧠 #Shorts",
        ],
    },
}

# ─────────────────────────────────────────────
# TITLE ROTATION — pick unused title, track in persistent file
# ─────────────────────────────────────────────
TITLE_ROTATION_FILE = os.path.join(PERSISTENT_DIR, "short_title_rotation.json")

def pick_title(primary, hook_style):
    pool = TITLE_POOLS.get(hook_style, TITLE_POOLS["pov"]).get(
        primary,
        [f"{primary.replace('_', ' ').title()} sounds | 60 sec preview #Shorts"]
    )

    used_titles = {}
    if os.path.exists(TITLE_ROTATION_FILE):
        try:
            with open(TITLE_ROTATION_FILE) as f:
                used_titles = json.load(f)
        except Exception:
            pass

    key = f"{hook_style}_{primary}"
    used = set(used_titles.get(key, []))
    available = [t for t in pool if t not in used]

    if not available:
        # All used — reset this niche/style combo
        available = pool
        used = set()

    title = random.choice(available)
    used.add(title)
    used_titles[key] = list(used)

    try:
        with open(TITLE_ROTATION_FILE, "w") as f:
            json.dump(used_titles, f, indent=2)
    except Exception:
        pass

    return title

title = pick_title(primary, hook_style)

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