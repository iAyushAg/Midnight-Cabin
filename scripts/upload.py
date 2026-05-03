import os
import json
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
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

youtube = build("youtube", "v3", credentials=creds)

with open("current_idea.json", "r") as f:
    idea = json.load(f)

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": idea["title"],
            "description": f"{idea['theme']}\n\nRelaxing soundscape for sleep, focus, studying, and deep work.",
            "tags": ["sleep", "focus", "ambient", "brown noise", "relaxing sounds"],
            "categoryId": "10"
        },
        "status": {
            "privacyStatus": "public"
        }
    },
    media_body=MediaFileUpload("output/video.mp4")
)

import os
from datetime import datetime

history_path = "video_history.json"

record = {
    "video_id": response["id"],
    "title": idea["title"],
    "theme": idea["theme"],
    "sound_layers": idea["sound_layers"],
    "visual": idea["visual"],
    "uploaded_at": datetime.now().isoformat(),
    "performance": {}
}

if os.path.exists(history_path):
    with open(history_path, "r") as f:
        history = json.load(f)
else:
    history = []

history.append(record)

with open(history_path, "w") as f:
    json.dump(history, f, indent=2)