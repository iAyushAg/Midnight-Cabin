import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

BASE_DIR = Path(__file__).resolve().parent.parent
IDEA_PATH = BASE_DIR / "current_idea.json"
BG_PATH = BASE_DIR / "video" / "bg.jpg"
THUMBNAIL_PATH = BASE_DIR / "thumbnail.jpg"

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

title = idea.get("title", "").lower()
layers = " ".join(idea.get("sound_layers", [])).lower()

# 🔥 Decide thumbnail text (VERY IMPORTANT)
if "rain" in title or "rain" in layers:
    main_text = "RAIN\nSLEEP"
elif "brown_noise" in layers or "focus" in title:
    main_text = "DEEP\nFOCUS"
elif "fireplace" in layers:
    main_text = "COZY\nFIRE"
elif "ocean" in layers:
    main_text = "OCEAN\nCALM"
elif "river" in layers:
    main_text = "RIVER\nSLEEP"
elif "wind" in layers:
    main_text = "SOFT\nWIND"
else:
    main_text = "DEEP\nSLEEP"

sub_text = "10 HOURS • NO ADS"

if not BG_PATH.exists():
    raise FileNotFoundError("Missing video/bg.jpg")

# Load base image
img = Image.open(BG_PATH).convert("RGB")

# 🔧 Crop to 16:9
w, h = img.size
target_ratio = 16 / 9

if w / h > target_ratio:
    new_w = int(h * target_ratio)
    left = (w - new_w) // 2
    img = img.crop((left, 0, left + new_w, h))
else:
    new_h = int(w / target_ratio)
    top = (h - new_h) // 2
    img = img.crop((0, top, w, top + new_h))

img = img.resize((1280, 720))

# 🎨 Cinematic enhancement
img = ImageEnhance.Contrast(img).enhance(1.2)
img = ImageEnhance.Color(img).enhance(0.9)
img = img.filter(ImageFilter.SHARPEN)

# 🌑 Dark overlay
overlay = Image.new("RGB", img.size, (0, 0, 0))
img = Image.blend(img, overlay, 0.35)

# 🎭 Left gradient (for text clarity)
gradient = Image.new("L", (1280, 720), 0)
for x in range(600):
    value = int(255 * (1 - x / 600))
    for y in range(720):
        gradient.putpixel((x, y), value)

gradient = gradient.convert("RGB")
img = Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), gradient)

draw = ImageDraw.Draw(img)

# 🔤 Fonts
try:
    font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 110)
    font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
except:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

# ✍️ Draw main text
x = 60
y = 320
shadow = 8

for i, line in enumerate(main_text.split("\n")):
    yy = y + i * 110

    # shadow
    draw.text((x + shadow, yy + shadow), line, font=font_big, fill=(0, 0, 0))
    # main text
    draw.text((x, yy), line, font=font_big, fill=(255, 255, 255))

# 🧾 Bottom label
draw.text((60, 620), sub_text, font=font_small, fill=(230, 230, 230))

# 💾 Save
img.save(THUMBNAIL_PATH, "JPEG", quality=88, optimize=True)

print("Thumbnail created from bg.jpg")