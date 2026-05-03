import os
import json
import base64
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")
VIDEO_DIR = os.path.join(BASE_DIR, "video")

os.makedirs(VIDEO_DIR, exist_ok=True)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

prompt = f"""
Create a dark, cinematic, cozy ambient YouTube background image.

Theme: {idea.get("theme")}
Visual: {idea.get("visual")}

Style:
- realistic cinematic scene
- dark cozy midnight atmosphere
- no people
- no text
- no logos
- suitable for sleep and focus video
- 16:9 YouTube background
"""

result = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1536x1024"
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

output_path = os.path.join(VIDEO_DIR, "bg.jpg")

with open(output_path, "wb") as f:
    f.write(image_bytes)

print("Generated visual:", output_path)