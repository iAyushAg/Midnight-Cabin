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

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"
HISTORY_FILE = "video_history.json"
VIDEO_FILE = "output/video.mp4"
THUMBNAIL_FILE = "thumbnail.jpg"

creds = None

if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

if not creds or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        SCOPES
    )

    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message=""
    )

    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

with open("current_idea.json", "r") as f:
    idea = json.load(f)

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Video file not found: {VIDEO_FILE}")

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": idea["title"],
            "description": (
                f"{idea['theme']}\n\n"
                "Relaxing soundscape for sleep, focus, studying, and deep work.\n\n"
                "Best used for sleeping, relaxation, meditation, reading, studying, "
                "deep work, and reducing background distractions."
            ),
            "tags": [
                "sleep sounds",
                "rain sounds",
                "focus music",
                "brown noise",
                "ambient sounds",
                "relaxing sounds",
                "study sounds",
                "deep sleep",
                "white noise",
                "nature sounds"
            ],
            "categoryId": "10"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload(
        VIDEO_FILE,
        chunksize=-1,
        resumable=True
    )
)

response = request.execute()

print("Upload response:")
print(response)

video_id = response["id"]

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

record = {
    "video_id": video_id,
    "title": idea.get("title"),
    "theme": idea.get("theme"),
    "sound_layers": idea.get("sound_layers", []),
    "visual": idea.get("visual"),
    "duration_minutes": idea.get("duration_minutes"),
    "audio_strategy": idea.get("audio_strategy", {}),
    "learning_reason": idea.get("learning_reason"),
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