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

if "rain" in title or "rain" in layers:
    main_text = "RAIN\nSLEEP"
    sub_text = "10 HOURS • NO ADS"
elif "brown_noise" in layers or "brown noise" in title or "focus" in title:
    main_text = "DEEP\nFOCUS"
    sub_text = "10 HOURS • NO DISTRACTIONS"
elif "fireplace" in title or "fireplace" in layers:
    main_text = "COZY\nFIRE"
    sub_text = "10 HOURS • DEEP SLEEP"
elif "ocean" in title or "ocean" in layers:
    main_text = "OCEAN\nCALM"
    sub_text = "10 HOURS • SLEEP & RELAX"
elif "river" in title or "river" in layers:
    main_text = "RIVER\nSLEEP"
    sub_text = "10 HOURS • RELAXING WATER"
elif "wind" in title or "soft_wind" in layers:
    main_text = "SOFT\nWIND"
    sub_text = "10 HOURS • SLEEP SOUNDS"
else:
    main_text = "DEEP\nSLEEP"
    sub_text = "10 HOURS • SLEEP & FOCUS"

if not BG_PATH.exists():
    raise FileNotFoundError("Missing video/bg.jpg")

img = Image.open(BG_PATH).convert("RGB")

# Crop 16:9
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

# Cinematic look
img = ImageEnhance.Contrast(img).enhance(1.18)
img = ImageEnhance.Color(img).enhance(0.88)
img = img.filter(ImageFilter.SHARPEN)

# Dark overlay
overlay = Image.new("RGB", img.size, (0, 0, 0))
img = Image.blend(img, overlay, 0.34)

draw = ImageDraw.Draw(img)

try:
    font_main = ImageFont.truetype("DejaVuSans-Bold.ttf", 112)
    font_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
except:
    font_main = ImageFont.load_default()
    font_sub = ImageFont.load_default()

# Left text panel gradient
panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
panel_draw = ImageDraw.Draw(panel)

for x in range(0, 620):
    alpha = int(190 * (1 - x / 620))
    panel_draw.line([(x, 0), (x, 720)], fill=(0, 0, 0, alpha))

img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
draw = ImageDraw.Draw(img)

# Main text
x = 58
y = 330
shadow = 8

for i, line in enumerate(main_text.split("\n")):
    yy = y + i * 112

    draw.text((x + shadow, yy + shadow), line, font=font_main, fill=(0, 0, 0))
    draw.text((x, yy), line, font=font_main, fill=(255, 255, 255))

# Subtitle pill
pill_x, pill_y = 58, 610
pill_w, pill_h = 520, 58

draw.rounded_rectangle(
    [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
    radius=18,
    fill=(10, 10, 10)
)

draw.text(
    (pill_x + 24, pill_y + 9),
    sub_text,
    font=font_sub,
    fill=(235, 235, 235)
)

img.save(THUMBNAIL_PATH, "JPEG", quality=88, optimize=True)

print("Generated thumbnail:", THUMBNAIL_PATH)
print("Main text:", main_text.replace("\n", " "))