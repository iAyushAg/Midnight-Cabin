import json
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_FILE = "token.json"
HISTORY_FILE = "video_history.json"

creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

if creds.expired and creds.refresh_token:
    creds.refresh(Request())

youtube = build("youtube", "v3", credentials=creds)

with open(HISTORY_FILE, "r") as f:
    history = json.load(f)

for item in history:
    video_id = item["video_id"]

    request = youtube.videos().list(
        part="statistics,status",
        id=video_id
    )

    response = request.execute()
    videos = response.get("items", [])

    if not videos:
        continue

    stats = videos[0].get("statistics", {})
    status = videos[0].get("status", {})

    item["performance"] = {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "privacy_status": status.get("privacyStatus")
    }

with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

print("Updated video stats")