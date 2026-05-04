import os
import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IDEA_PATH = BASE_DIR / "current_idea.json"
VIDEO_DIR = BASE_DIR / "video"
OUTPUT_PATH = VIDEO_DIR / "bg.jpg"

VIDEO_DIR.mkdir(exist_ok=True)

ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

layers = " ".join(idea.get("sound_layers", []))
visual = idea.get("visual", "")

query = f"{visual} night dark cozy cinematic"

print("Unsplash query:", query)

url = "https://api.unsplash.com/search/photos"

params = {
    "query": query,
    "orientation": "landscape",
    "per_page": 1
}

headers = {
    "Authorization": f"Client-ID {ACCESS_KEY}"
}

response = requests.get(url, headers=headers, params=params)

data = response.json()

if "results" in data and len(data["results"]) > 0:
    image_url = data["results"][0]["urls"]["full"]

    img_data = requests.get(image_url).content

    with open(OUTPUT_PATH, "wb") as f:
        f.write(img_data)

    print("Downloaded image from Unsplash:", image_url)
else:
    raise Exception("No image found from Unsplash")