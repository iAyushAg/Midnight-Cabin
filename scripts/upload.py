import os
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

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
            "privacyStatus": "private"
        }
    },
    media_body=MediaFileUpload("output/video.mp4")
)

response = request.execute()
print(response)