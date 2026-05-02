import os
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

scopes = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", scopes
)
creds = flow.run_local_server(port=0)

youtube = build("youtube", "v3", credentials=creds)
with open("current_idea.json", "r") as f:
    idea = json.load(f)
    
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
           "title": idea["title"],
           "description": f"{idea['theme']}\n\nRelaxing soundscape for sleep, focus, studying, and deep work.",
            "tags": ["sleep", "focus"],
            "categoryId": "10"
        },
        "status": {"privacyStatus": "public"}
    },
    media_body=MediaFileUpload("output/video.mp4")
)

response = request.execute()
print(response)