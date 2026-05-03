import os
import json
import base64
from pathlib import Path
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
IDEA_PATH = BASE_DIR / "current_idea.json"
THUMBNAIL_PATH = BASE_DIR / "thumbnail.jpg"

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

prompt = f"""
Create a high-click YouTube thumbnail background for a sleep/focus soundscape channel.

Theme: {idea.get("theme")}
Visual: {idea.get("visual")}

Style:
- dark cinematic cozy cabin ambience
- strong focal point
- warm window glow or moonlight
- dramatic but calm
- no people, no faces
- no logos
- no text
- high contrast
- suitable for rain/sleep/focus ambience
"""

result = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1536x1024"
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

raw_path = BASE_DIR / "thumbnail_raw.png"

with open(raw_path, "wb") as f:
    f.write(image_bytes)

img = Image.open(raw_path).convert("RGB")

# Crop to 16:9
w, h = img.size
target_ratio = 16 / 9
current_ratio = w / h

if current_ratio > target_ratio:
    new_w = int(h * target_ratio)
    left = (w - new_w) // 2
    img = img.crop((left, 0, left + new_w, h))
else:
    new_h = int(w / target_ratio)
    top = (h - new_h) // 2
    img = img.crop((0, top, w, top + new_h))

img = img.resize((1280, 720))

draw = ImageDraw.Draw(img)

title = idea.get("title", "Sleep Sounds")
short_text = title.split(" for ")[0][:28].upper()

# dark gradient overlay
overlay = Image.new("RGB", img.size, (0, 0, 0))
img = Image.blend(img, overlay, 0.22)
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    small_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
except:
    font = ImageFont.load_default()
    small_font = ImageFont.load_default()

# text shadow
x, y = 60, 470
draw.text((x + 4, y + 4), short_text, font=font, fill=(0, 0, 0))
draw.text((x, y), short_text, font=font, fill=(255, 255, 255))

draw.text((60, 565), "10 HOURS • SLEEP & FOCUS", font=small_font, fill=(230, 230, 230))

img.save(THUMBNAIL_PATH, "JPEG", quality=88, optimize=True)

print("Generated thumbnail:", THUMBNAIL_PATH)