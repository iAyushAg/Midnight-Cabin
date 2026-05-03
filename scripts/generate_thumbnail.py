import os
import json
import base64
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
IDEA_PATH = BASE_DIR / "current_idea.json"
THUMBNAIL_PATH = BASE_DIR / "thumbnail.jpg"
RAW_PATH = BASE_DIR / "thumbnail_raw.png"

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

title = idea.get("title", "")
theme = idea.get("theme", "")
visual = idea.get("visual", "")
layers = idea.get("sound_layers", [])

title_lower = title.lower()
layers_text = " ".join(layers).lower()

if "rain" in title_lower or "rain" in layers_text:
    thumbnail_text = "RAIN SLEEP"
    visual_style = "dark rainy cabin window, warm yellow light inside, cold blue rain outside"
elif "brown noise" in title_lower or "focus" in title_lower:
    thumbnail_text = "DEEP FOCUS"
    visual_style = "dark minimal cozy desk room, soft warm lamp, calm deep focus atmosphere"
elif "black screen" in title_lower:
    thumbnail_text = "FALL ASLEEP"
    visual_style = "almost black background, subtle soft glow, minimal calm sleep ambience"
elif "fireplace" in title_lower or "fireplace" in layers_text:
    thumbnail_text = "COZY SLEEP"
    visual_style = "warm fireplace in dark cozy cabin, soft orange glow, peaceful winter night"
elif "ocean" in title_lower or "ocean" in layers_text:
    thumbnail_text = "OCEAN CALM"
    visual_style = "dark ocean waves at night, moonlight reflection, calm cinematic atmosphere"
else:
    thumbnail_text = "DEEP SLEEP"
    visual_style = "dark cozy midnight cabin, soft warm glow, calm sleep ambience"

prompt = f"""
Create a high-click YouTube thumbnail background for a sleep/focus soundscape channel.

Video theme: {theme}
Video visual: {visual}
Required style: {visual_style}

Thumbnail requirements:
- 16:9 YouTube thumbnail composition
- dark cinematic cozy ambience
- strong single focal point on the right side
- empty/darker space on the left side for large text
- warm glow, moonlight, or window light contrast
- minimal clutter
- no people
- no faces
- no logos
- no text
- no watermark
- emotional feeling: safe, cozy, sleepy, quiet, nighttime
- high contrast, professional YouTube thumbnail look
"""

result = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1536x1024"
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

with open(RAW_PATH, "wb") as f:
    f.write(image_bytes)

img = Image.open(RAW_PATH).convert("RGB")

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

# Slight cinematic sharpen/contrast feel
img = img.filter(ImageFilter.SHARPEN)

# Dark overlay for text readability
overlay = Image.new("RGB", img.size, (0, 0, 0))
img = Image.blend(img, overlay, 0.28)

draw = ImageDraw.Draw(img)

try:
    font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 92)
    font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
except:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Wrap big text into two lines if needed
words = thumbnail_text.split()
if len(words) >= 2:
    line1 = words[0]
    line2 = " ".join(words[1:])
else:
    line1 = thumbnail_text
    line2 = ""

x = 58
y = 410

# Draw strong shadow
shadow_offset = 7

draw.text(
    (x + shadow_offset, y + shadow_offset),
    line1,
    font=font_big,
    fill=(0, 0, 0)
)
draw.text(
    (x, y),
    line1,
    font=font_big,
    fill=(255, 255, 255)
)

if line2:
    y2 = y + 92
    draw.text(
        (x + shadow_offset, y2 + shadow_offset),
        line2,
        font=font_big,
        fill=(0, 0, 0)
    )
    draw.text(
        (x, y2),
        line2,
        font=font_big,
        fill=(255, 255, 255)
    )

# Small duration hook
small_text = "10 HOURS • SLEEP & FOCUS"
small_y = 625

draw.text(
    (x + 4, small_y + 4),
    small_text,
    font=font_small,
    fill=(0, 0, 0)
)
draw.text(
    (x, small_y),
    small_text,
    font=font_small,
    fill=(230, 230, 230)
)

# Save under 2MB for YouTube
img.save(THUMBNAIL_PATH, "JPEG", quality=86, optimize=True)

print("Generated thumbnail:", THUMBNAIL_PATH)
print("Thumbnail text:", thumbnail_text)