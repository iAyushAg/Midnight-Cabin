"""
generate_visual.py

Pipeline:
1. Generate base image via Pollinations.ai (free)
   - DALL-E 3 if OPENAI_API_KEY available
   - Pollinations.ai as free fallback
2. Animate via Replicate Wan I2V (image to video)
   - Produces a 3-5 second looping video clip
   - ffmpeg loops this clip for the full 8/10 hour video
3. Save animated clip to video/bg_animated.mp4
   - Falls back to static image if Replicate fails
"""

import json
import os
import time
import requests
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).parent.parent
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")

IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(IDEA_PATH):
    IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

VIDEO_DIR = BASE_DIR / "video"
VIDEO_DIR.mkdir(exist_ok=True)
BG_IMAGE = VIDEO_DIR / "bg.jpg"
BG_VIDEO = VIDEO_DIR / "bg_animated.mp4"

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
with open(IDEA_PATH) as f:
    idea = json.load(f)

primary = idea.get("audio_strategy", {}).get("primary_category", "rain")
secondary = idea.get("audio_strategy", {}).get("secondary_category", "")
theme = idea.get("theme", "Cozy Cabin Ambience")
layers = idea.get("sound_layers", [])

print(f"Generating visual for: {theme} ({primary})")

# ─────────────────────────────────────────────
# IMAGE PROMPTS
# Fixed layout: fireplace bottom-right, windows top-centre
# Rain/fire explicitly described so AI bakes them in
# ─────────────────────────────────────────────
SCENE_PROMPTS = {
    "rain": (
        "cozy attic bedroom rustic wooden cabin at night, "
        "large arched window top centre covered in rain streaks and water droplets on glass, "
        "dark stormy rainy sky and trees barely visible through heavily rain-streaked window, "
        "stone fireplace bottom right with tall bright orange crackling flames and glowing red embers, "
        "warm amber lanterns hanging from exposed wooden ceiling beams, "
        "plush bed with rumpled blankets centre, leather armchair left, "
        "bookshelves filled with books, steaming mug on wooden side table, "
        "deep blue rainy atmosphere outside warm amber glow inside, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "fireplace": (
        "grand rustic stone fireplace bottom right with tall roaring orange and yellow flames, "
        "bright glowing red and orange embers, fire clearly visible with dancing flame tips, "
        "warm amber firelight spilling across stone floor and log cabin walls, "
        "mountain lodge interior midnight, frosted window top left showing snowfall outside, "
        "leather armchair positioned close to hearth, exposed log walls, "
        "stacked firewood and pine cones beside fireplace, "
        "deep warm amber and dark shadow contrast, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "river": (
        "wooden cabin porch overlooking moonlit mountain river at night, "
        "river water flowing with visible ripples between mossy rocks in lower half of image, "
        "silver moonlight reflecting on moving water surface, mist rising from river, "
        "cabin interior with warm lantern light visible through window top right, "
        "pine forest on both banks, small stone fireplace glowing bottom right corner, "
        "cool moonlit blue and warm amber contrast, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "ocean_waves": (
        "cliffside stone cottage bedroom at stormy night, "
        "large window top centre showing ocean waves crashing on dark rocks below, "
        "white foam spray on wave crests, turbulent dark water, moonlight breaking through clouds, "
        "stone fireplace with small bright fire bottom right, lit candle on windowsill, "
        "weathered wood interior with nautical rope and driftwood details, "
        "deep navy and candlelight amber palette, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "soft_wind": (
        "japanese wooden cabin in bamboo forest at twilight, "
        "shoji screen windows with bamboo grove visible outside swaying in gentle breeze, "
        "cherry blossom petals drifting in the air outside, "
        "warm paper lanterns glowing inside, simple futon on tatami mat, "
        "small stone fireplace with glowing embers bottom right, "
        "pale lavender sky deep green bamboo warm gold lantern light, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "night_forest": (
        "magical glass-walled treehouse deep in ancient forest at midnight, "
        "massive oak and pine trees surrounding structure, silver moonlight filtering through glass walls, "
        "fireplace with warm orange glowing fire bottom right corner clearly visible, "
        "fairy lights strung across exposed wooden beams, hammock in corner, "
        "bioluminescent blue-green mushrooms glowing on dark forest floor below, "
        "fireflies as tiny golden lights floating in dark forest, "
        "deep forest green midnight blue warm gold palette, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "brown_noise": (
        "modern minimalist loft study at night, "
        "floor to ceiling industrial windows top half covered in rain streaks showing blurred city lights, "
        "warm desk lamp casting golden circle of light on clean desk, "
        "open notebook and steaming coffee mug on desk, "
        "small stone fireplace with bright orange fire bottom right, "
        "single candle flame on windowsill, "
        "exposed brick walls dark wood shelving filled with books, "
        "warm amber charcoal and deep navy palette, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
    "thunder": (
        "cozy rustic cabin living room during violent thunderstorm at night, "
        "large windows top showing lightning illuminating dark stormy sky, "
        "heavy rain streaming down window glass, dramatic lightning bolt visible outside, "
        "roaring stone fireplace bottom right with tall bright orange flames and glowing embers, "
        "thick wool blankets on armchair, dramatic contrast of storm outside and warmth inside, "
        "deep midnight blue dramatic lightning and warm amber firelight, "
        "cinematic digital painting, photorealistic, ultra detailed, no people, no text, no watermark"
    ),
}

base_prompt = SCENE_PROMPTS.get(
    primary,
    "cozy wooden cabin interior night, fireplace bottom right, "
    "large window showing rain outside, warm amber light, "
    "cinematic digital art, ultra detailed, no people, no text"
)

if secondary and secondary != primary:
    additions = {
        "rain": ", rain visible on windows",
        "fireplace": ", fireplace flames bottom right",
        "thunder": ", lightning through windows",
        "river": ", river visible outside",
        "ocean_waves": ", ocean waves through window",
    }
    base_prompt += additions.get(secondary, "")

style_suffix = ", masterpiece, best quality, 8k uhd, cinematic lighting, award winning digital art"
full_prompt = base_prompt + style_suffix

print(f"Prompt: {full_prompt[:100]}...")

# ─────────────────────────────────────────────
# ANIMATION PROMPT per theme
# Describes what should move in the scene
# ─────────────────────────────────────────────
# Animation prompts — describe ONLY the motion, not the scene
# The image itself is the visual anchor for Wan I2V
# Short and specific works better than long descriptions
ANIMATION_PROMPTS = {
    "rain": (
        "heavy raindrops streaming down window glass, "
        "rain falling outside visible through window, "
        "fireplace fire flickering with dancing orange flames and glowing red embers, "
        "warm amber light from fire pulsing gently on walls, "
        "all furniture books and objects completely motionless"
    ),
    "fireplace": (
        "fireplace fire burning with tall flickering orange and yellow flames, "
        "bright glowing embers crackling, "
        "warm amber firelight dancing on stone walls and floor, "
        "wisps of smoke rising slowly from flames, "
        "all furniture and objects completely motionless"
    ),
    "river": (
        "river water flowing smoothly with rippling surface catching moonlight, "
        "gentle mist rising from water surface, "
        "fireplace fire flickering with orange flames, "
        "moonlight shimmer on moving water, "
        "cabin interior completely still and motionless"
    ),
    "ocean_waves": (
        "ocean waves rolling and breaking on rocks below, "
        "white foam and spray on wave crests, "
        "water surface heaving with swells, "
        "fireplace fire flickering orange and warm, "
        "candlelight flame gently wavering, "
        "all interior objects completely still"
    ),
    "soft_wind": (
        "bamboo gently swaying and rustling in soft breeze, "
        "cherry blossom petals slowly drifting through air, "
        "paper lanterns swaying slightly, casting moving light, "
        "interior objects completely still"
    ),
    "night_forest": (
        "fireflies slowly drifting and blinking in dark forest, "
        "fireplace fire flickering with warm orange glow, "
        "fairy lights gently twinkling, "
        "tree branches barely moving, "
        "interior completely still"
    ),
    "brown_noise": (
        "raindrops streaming down window glass, "
        "blurred city lights glimmering through wet glass, "
        "fireplace fire flickering with small orange flames, "
        "candle flame wavering gently, "
        "desk and all objects completely motionless"
    ),
    "thunder": (
        "heavy rain streaming violently down window glass, "
        "brief bright lightning flash outside illuminating stormy sky, "
        "fireplace fire blazing with tall vigorous flames, "
        "dramatic flickering firelight on walls, "
        "all interior objects motionless"
    ),
}

animation_prompt = ANIMATION_PROMPTS.get(
    primary,
    "subtle ambient motion, fireplace flickering, atmospheric movement"
)

# ─────────────────────────────────────────────
# STEP 1 — GENERATE BASE IMAGE
# ─────────────────────────────────────────────
def generate_image():
    # Try DALL-E 3 first
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            print("Trying DALL-E 3...")
            resp = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "dall-e-3", "prompt": full_prompt, "n": 1,
                      "size": "1792x1024", "quality": "standard", "style": "vivid"},
                timeout=120
            )
            if resp.status_code == 200:
                img_url = resp.json()["data"][0]["url"]
                img = requests.get(img_url, timeout=60)
                img.raise_for_status()
                with open(BG_IMAGE, "wb") as f:
                    f.write(img.content)
                print("DALL-E 3 image saved")
                return True
            else:
                print(f"DALL-E failed ({resp.status_code}) — trying Pollinations")
        except Exception as e:
            print(f"DALL-E error: {e}")

    # Pollinations.ai (free)
    try:
        print("Calling Pollinations.ai...")
        encoded = quote(full_prompt)
        seed = abs(hash(theme)) % 999999
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1280&height=720&seed={seed}&model=flux&nologo=true&enhance=true")
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(BG_IMAGE, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        size = os.path.getsize(BG_IMAGE)
        if size < 10000:
            print(f"Pollinations returned tiny file ({size}b) — may be error")
            return False
        print(f"Pollinations image saved: {size//1024}KB")
        return True
    except Exception as e:
        print(f"Pollinations failed: {e}")

    # Unsplash fallback
    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if unsplash_key:
        try:
            queries = {
                "rain": "dark rainy cabin window night cozy",
                "fireplace": "cozy fireplace cabin night warm",
                "river": "mountain river night forest cabin",
                "ocean_waves": "ocean waves night cliff cottage",
                "soft_wind": "peaceful forest night cabin lantern",
                "night_forest": "dark forest night moonlight trees",
                "brown_noise": "dark study room night city rain",
                "thunder": "stormy night cabin lightning window",
            }
            query = queries.get(primary, f"cozy cabin {primary} night")
            resp = requests.get(
                f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={unsplash_key}",
                timeout=30
            )
            resp.raise_for_status()
            img = requests.get(resp.json()["urls"]["regular"], timeout=60)
            with open(BG_IMAGE, "wb") as f:
                f.write(img.content)
            print("Unsplash fallback saved")
            return True
        except Exception as e:
            print(f"Unsplash failed: {e}")

    return False

image_ok = generate_image()

# Resize to 1280x720
if image_ok and os.path.exists(BG_IMAGE):
    try:
        from PIL import Image
        img = Image.open(BG_IMAGE).convert("RGB")
        img = img.resize((1280, 720), Image.LANCZOS)
        img.save(BG_IMAGE, "JPEG", quality=95)
        print(f"Resized to 1280x720")
    except Exception as e:
        print(f"PIL resize failed: {e}")

# ─────────────────────────────────────────────
# STEP 2 — ANIMATE via Replicate Wan I2V
# ─────────────────────────────────────────────
replicate_key = os.environ.get("REPLICATE_API_KEY", "")

if not replicate_key:
    print("REPLICATE_API_KEY not set — using static image")
elif not image_ok:
    print("No base image — skipping animation")
else:
    try:
        import base64
        print("Animating with Replicate Wan I2V...")

        # Read image as base64
        with open(BG_IMAGE, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        img_data_url = f"data:image/jpeg;base64,{img_b64}"

        # Using replicate Python client

        # Use replicate Python client with explicit token
        import replicate as _replicate
        client = _replicate.Client(api_token=replicate_key)

        # wan-2.2-i2v-fast: cheapest + fastest, 10M+ runs, ~$0.04/video
        print("Sending to Replicate (wan-video/wan-2.2-i2v-fast)...")

        with open(BG_IMAGE, "rb") as img_file:
            output = client.run(
                "wan-video/wan-2.2-i2v-fast",
                input={
                    "image": img_file,
                    "prompt": animation_prompt,
                    "negative_prompt": (
                        "camera pan, camera zoom, camera rotation, camera movement, "
                        "rain indoors, rain on bed, rain on ceiling, rain on furniture, rain on floor, "
                        "snow indoors, water indoors, "
                        "people, faces, hands, human figures, "
                        "text, watermark, logo, "
                        "distortion, warping, morphing, melting, "
                        "flickering artifacts, color shifts, overexposure, "
                        "blurry, low quality, pixelated"
                    ),
                    "num_frames": 81,   # minimum for wan-2.2-i2v-fast (~5s at 16fps)
                    "frames_per_second": 16,
                }
            )

        # output is a URL string
        video_url = str(output) if not isinstance(output, list) else str(output[0])
        print(f"Animation complete — downloading from: {video_url[:60]}...")

        vid = requests.get(video_url, timeout=120)
        vid.raise_for_status()
        with open(BG_VIDEO, "wb") as f:
            f.write(vid.content)
        print(f"Animated video saved: {os.path.getsize(BG_VIDEO)//1024}KB")

    except Exception as e:
        print(f"Replicate animation failed: {e} — using static image")

# Save metadata
visual_meta = {
    "primary": primary,
    "theme": theme,
    "has_animation": os.path.exists(str(BG_VIDEO)),
    "source": "dalle3" if os.environ.get("OPENAI_API_KEY") else "pollinations",
}
with open(os.path.join(PERSISTENT_DIR, "current_visual.json"), "w") as f:
    json.dump(visual_meta, f, indent=2)

if os.path.exists(str(BG_VIDEO)):
    print(f"✅ Animated video ready: {BG_VIDEO}")
else:
    print(f"✅ Static image ready: {BG_IMAGE} (no animation)")

print("Visual generation complete")