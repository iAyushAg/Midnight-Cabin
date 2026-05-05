import os
import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))

IDEA_PATH = PERSISTENT_DIR / "current_idea.json"
VIDEO_DIR = BASE_DIR / "video"
OUTPUT_PATH = VIDEO_DIR / "bg.jpg"

VIDEO_DIR.mkdir(exist_ok=True)

ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

# Fallback to BASE_DIR idea if PERSISTENT_DIR idea doesn't exist
if not IDEA_PATH.exists():
    IDEA_PATH = BASE_DIR / "current_idea.json"

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

layers = " ".join(idea.get("sound_layers", []))
visual = idea.get("visual", "")
primary = idea.get("audio_strategy", {}).get("primary_category", "")

# Build a better query using both visual description and primary category
query = f"{primary.replace('_', ' ')} {visual} night dark cozy cinematic"
# Trim to reasonable length for API
query = " ".join(query.split()[:12])

print("Unsplash query:", query)

url = "https://api.unsplash.com/search/photos"

params = {
    "query": query,
    "orientation": "landscape",
    "per_page": 5,  # fetch 5, pick best one
    "order_by": "relevant"
}

headers = {
    "Authorization": f"Client-ID {ACCESS_KEY}"
}

response = requests.get(url, headers=headers, params=params)
data = response.json()

if "results" in data and len(data["results"]) > 0:
    # Pick darkest image — prefer photos with lower brightness
    # Use the third result if available (usually more atmospheric than #1)
    import random
    results = data["results"]
    # Prefer results beyond first to get variety
    pick = results[min(2, len(results)-1)]
    image_url = pick["urls"]["full"]

    img_data = requests.get(image_url).content

    with open(OUTPUT_PATH, "wb") as f:
        f.write(img_data)

    print("Downloaded image from Unsplash:", image_url)
    print("Photo by:", pick["user"]["name"])
else:
    raise Exception("No image found from Unsplash")