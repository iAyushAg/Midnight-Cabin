#!/usr/bin/env python3
"""
generate_short_visual.py — Dedicated visual generator for Shorts

Why this exists separately from generate_visual.py:
  - Shorts are 9:16 vertical. The main pipeline generates 16:9 landscape
    video and crops it to vertical — losing the edges of every image.
  - This script fetches portrait-oriented photos from Pexels/Unsplash,
    generates a 9:16 image (720x1280 or 1080x1920), and sends it to
    Kling for vertical animation — producing a bg_short_animated.mp4
    that fills the Short frame perfectly with no cropping artifacts.
  - Visual variety: the Short uses a completely different image from
    the main video even when they share the same niche.

Output:
  video/bg_short_animated.mp4   — vertical animated clip for Shorts
  video/bg_short.jpg            — source portrait image
  /data/current_short_visual.json

Called from run_short_pipeline.sh before generate_short.py.
"""

import base64
import hashlib
import hmac
import json
import os
import random
import time
import requests
from pathlib import Path

BASE_DIR      = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))
VIDEO_DIR     = BASE_DIR / "video"
LIBRARY_DIR   = VIDEO_DIR / "library"

# Read SHORT_IDEA_PATH env var (set by run_short_pipeline.sh)
_short_idea_env = os.environ.get("SHORT_IDEA_PATH", "")
IDEA_PATH = Path(_short_idea_env) if _short_idea_env else PERSISTENT_DIR / "short_idea.json"
if not IDEA_PATH.exists():
    IDEA_PATH = PERSISTENT_DIR / "current_idea.json"
if not IDEA_PATH.exists():
    IDEA_PATH = BASE_DIR / "current_idea.json"

SHORT_BG_IMAGE   = VIDEO_DIR / "bg_short.jpg"
SHORT_BG_VIDEO   = VIDEO_DIR / "bg_short_animated.mp4"
SHORT_VISUAL_META = PERSISTENT_DIR / "current_short_visual.json"

VIDEO_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
with open(IDEA_PATH) as f:
    idea = json.load(f)

primary = idea.get("audio_strategy", {}).get("primary_category") or idea.get("sound_layers", ["rain"])[0]
theme   = idea.get("theme", "Cozy Cabin Ambience")
print(f"Generating Short visual for: {theme} ({primary})")

# ─────────────────────────────────────────────
# PORTRAIT PHOTO QUERIES
# Different from main pipeline — these are portrait-oriented
# searches that produce tall images with strong vertical composition.
# ─────────────────────────────────────────────
PORTRAIT_QUERIES = {
    "rain": [
        "rain window portrait night interior",
        "rainy window dark cozy vertical",
        "raindrops glass window dark night portrait",
        "cabin window rain night tall",
    ],
    "fireplace": [
        "fireplace warm glow dark room vertical",
        "cozy fireplace night portrait",
        "fire flames dark interior portrait",
        "fireplace cabin night tall composition",
    ],
    "river": [
        "waterfall forest night vertical",
        "river forest night portrait tall",
        "mountain stream dark forest vertical",
        "waterfall mist night portrait",
    ],
    "ocean_waves": [
        "ocean cliff night vertical portrait",
        "dark ocean waves tall composition",
        "sea coast night portrait dramatic",
        "ocean storm vertical dark",
    ],
    "soft_wind": [
        "forest trees night vertical portrait",
        "misty forest path vertical night",
        "tall trees night fog portrait",
        "forest moonlight vertical tall",
    ],
    "night_forest": [
        "dark forest night vertical portrait",
        "forest fireflies night tall",
        "pine forest midnight vertical",
        "enchanted forest night tall portrait",
    ],
    "brown_noise": [
        "desk lamp night rain portrait",
        "study room night vertical dark",
        "reading lamp night rain window portrait",
        "cozy desk night dark vertical",
    ],
    "thunder": [
        "lightning storm night vertical dramatic",
        "thunderstorm dark sky vertical portrait",
        "storm lightning tall composition night",
        "dramatic lightning night portrait",
    ],
}

def image_is_bright_enough(image_path: Path, min_brightness: int = 25) -> bool:
    """Check average brightness of image. Reject if too dark to be usable."""
    try:
        from PIL import Image as PILImage
        import numpy as np
        with PILImage.open(image_path) as img:
            # Convert to grayscale and check mean pixel value (0=black, 255=white)
            gray = img.convert("L").resize((64, 64))  # small for speed
            brightness = np.array(gray).mean()
            if brightness < min_brightness:
                print(f"  ⚠️  {image_path.name} too dark (brightness={brightness:.0f}<{min_brightness}) — skipping")
                return False
            return True
    except Exception:
        return True  # if check fails, allow the image

# ─────────────────────────────────────────────
# STEP 1 — CHECK LOCAL PORTRAIT LIBRARY
# video/library/{primary}/portrait/*.jpg
# Falls back to API if empty.
# ─────────────────────────────────────────────
def pick_portrait_from_library(primary):
    portrait_dir = LIBRARY_DIR / primary / "portrait"
    if not portrait_dir.exists():
        return None
    images = list(portrait_dir.glob("*.jpg")) + list(portrait_dir.glob("*.jpeg")) + list(portrait_dir.glob("*.png"))
    if not images:
        return None

    # Filter out images that are too dark to be usable
    # night_forest portraits especially can be near-black
    bright_images = [i for i in images if image_is_bright_enough(i, min_brightness=30)]
    if not bright_images:
        print(f"  ⚠️  All {primary} portrait images too dark — falling through to API")
        return None
    images = bright_images

    used_path = PERSISTENT_DIR / "used_short_images.json"
    used_map = {}
    try:
        if used_path.exists():
            with open(used_path) as f: used_map = json.load(f)
    except Exception: pass
    used = set(used_map.get(primary, []))
    available = [i for i in images if i.name not in used] or images
    chosen = random.choice(available)
    used.add(chosen.name)
    used_map[primary] = list(used)
    try:
        with open(used_path, "w") as f: json.dump(used_map, f, indent=2)
    except Exception: pass
    print(f"Portrait library image: {chosen.name}")
    return chosen

# ─────────────────────────────────────────────
# STEP 2 — FETCH PORTRAIT PHOTO FROM API
# ─────────────────────────────────────────────
def fetch_portrait_photo(primary, output_path):
    queries = PORTRAIT_QUERIES.get(primary, [f"{primary} night vertical portrait"])
    query   = random.choice(queries)
    print(f"Portrait photo search: '{query}'")

    # Pexels first for portrait (better portrait collection than Unsplash)
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    if pexels_key:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "orientation": "portrait", "size": "large", "per_page": 15},
                headers={"Authorization": pexels_key},
                timeout=20,
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                photo = random.choice(photos[:10])
                pr = requests.get(photo["src"]["large2x"], timeout=60, stream=True)
                pr.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in pr.iter_content(8192): f.write(chunk)
                size = os.path.getsize(output_path)
                if size > 50000:
                    print(f"Pexels portrait saved ({size//1024}KB) by {photo.get('photographer','?')}")
                    return True
        except Exception as e:
            print(f"Pexels portrait failed: {e}")

    # Unsplash portrait fallback
    unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if unsplash_key:
        try:
            r = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"query": query, "orientation": "portrait", "content_filter": "high"},
                headers={"Authorization": f"Client-ID {unsplash_key}"},
                timeout=20,
            )
            r.raise_for_status()
            photo_url = r.json()["urls"]["regular"]
            pr = requests.get(photo_url, timeout=60, stream=True)
            pr.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in pr.iter_content(8192): f.write(chunk)
            size = os.path.getsize(output_path)
            if size > 50000:
                print(f"Unsplash portrait saved ({size//1024}KB)")
                return True
        except Exception as e:
            print(f"Unsplash portrait failed: {e}")


    # Pixabay API (portrait orientation)
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    if pixabay_key:
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key":         pixabay_key,
                    "q":           query,
                    "image_type":  "photo",
                    "orientation": "vertical",
                    "min_width":   720,
                    "min_height":  1080,
                    "per_page":    15,
                    "order":       "popular",
                    "safesearch":  "true",
                },
                timeout=20,
            )
            r.raise_for_status()
            hits = r.json().get("hits", [])
            if hits:
                hit = random.choice(hits[:10])
                photo_url = hit.get("largeImageURL") or hit.get("webformatURL")
                pr = requests.get(photo_url, timeout=60, stream=True)
                pr.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in pr.iter_content(8192): f.write(chunk)
                size = os.path.getsize(output_path)
                if size > 50000:
                    print(f"Pixabay portrait saved ({size//1024}KB)")
                    return True
        except Exception as e:
            print(f"Pixabay portrait failed: {e}")
    else:
        print("PIXABAY_API_KEY not set — skipping Pixabay")

    # Pollinations portrait last resort
    PORTRAIT_PROMPTS = {
        "rain":         "rain window dark night interior tall portrait vertical cozy cabin warm light cinematic no people no text",
        "fireplace":    "fireplace warm glow dark interior portrait vertical cozy night cinematic no people no text",
        "river":        "waterfall forest night mist tall portrait vertical cinematic no people no text",
        "ocean_waves":  "ocean cliff night dramatic tall portrait vertical dark waves cinematic no people no text",
        "soft_wind":    "tall pine forest night moonlight portrait vertical mist cinematic no people no text",
        "night_forest": "dark forest night fireflies tall portrait vertical cinematic no people no text",
        "brown_noise":  "study room desk lamp night rain portrait vertical dark warm cinematic no people no text",
        "thunder":      "lightning storm night vertical portrait dramatic dark cinematic no people no text",
    }
    prompt = PORTRAIT_PROMPTS.get(primary, f"cozy {primary} night portrait vertical cinematic no people no text")
    prompt += " masterpiece 8k"
    try:
        from urllib.parse import quote as _q
        seed = int(time.time()) % 999999
        url = (f"https://image.pollinations.ai/prompt/{_q(prompt)}"
               f"?width=720&height=1280&seed={seed}&model=flux&nologo=true&enhance=true")
        print("Pollinations portrait last resort...")
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(8192): f.write(chunk)
        size = os.path.getsize(output_path)
        if size > 10000:
            print(f"Pollinations portrait saved: {size//1024}KB")
            return True
    except Exception as e:
        print(f"Pollinations portrait failed: {e}")

    return False

# ─────────────────────────────────────────────
# STEP 3 — GET THE IMAGE
# ─────────────────────────────────────────────
image_path = pick_portrait_from_library(primary)

if image_path:
    import shutil
    shutil.copy(str(image_path), str(SHORT_BG_IMAGE))
    print(f"Library portrait copied: {SHORT_BG_IMAGE}")
else:
    print(f"No portrait library image — fetching from API...")
    success = fetch_portrait_photo(primary, str(SHORT_BG_IMAGE))
    if not success:
        print("All portrait sources failed — falling back to landscape bg.jpg crop")
        landscape_bg = VIDEO_DIR / "bg.jpg"
        if landscape_bg.exists():
            import shutil, subprocess
            # Crop centre column of landscape to portrait
            subprocess.run([
                "ffmpeg", "-y", "-i", str(landscape_bg),
                "-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0",
                str(SHORT_BG_IMAGE)
            ], capture_output=True)
            print(f"Landscape fallback cropped to portrait")
        else:
            print("No fallback image available — Short will use source video")

# Ensure portrait dimensions (pad/crop to 1080x1920 if needed)
if SHORT_BG_IMAGE.exists():
    try:
        from PIL import Image as PILImage
        img = PILImage.open(str(SHORT_BG_IMAGE)).convert("RGB")
        w, h = img.size
        # If landscape, crop to portrait
        if w > h:
            left = (w - h * 9 // 16) // 2
            img = img.crop((left, 0, left + h * 9 // 16, h))
        # Resize to 1080x1920
        img = img.resize((1080, 1920), PILImage.LANCZOS)
        img.save(str(SHORT_BG_IMAGE), "JPEG", quality=95)
        print(f"Portrait image prepared: 1080x1920")
    except Exception as e:
        print(f"PIL resize failed: {e}")

# ─────────────────────────────────────────────
# STEP 4 — ANIMATE WITH KLING (vertical)
# ─────────────────────────────────────────────
KLING_ACCESS_KEY = os.environ.get("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY = os.environ.get("KLING_SECRET_KEY", "")

VERTICAL_ANIMATION_PROMPTS = {
    # Rain library: cabin interiors with arched windows showing rainy view + fireplace + lanterns + candles + mug
    #          OR outdoor scenes (misty cabin exterior, Asian roof with heavy rain, lakeside in mist, rainy cafe terrace)
    "rain": (
        "if there is a window: rain falling outside the window, raindrops sliding down glass panes, "
        "wet view of trees and mountains through window, "
        "if this is an outdoor scene: rain falling visibly from the sky onto roof tiles, leaves, ground, "
        "raindrops bouncing on wet surfaces, water dripping from edges, "
        "if any candle is visible: flame flickering gently, "
        "if any fireplace is visible: orange flames dancing, embers glowing, "
        "if any lantern is visible: warm light pulsing, "
        "if any mug or cup is visible: faint steam rising, "
        "if there is mist in the scene: mist drifting slowly, "
        "all furniture, beds, books, rugs, walls completely still, "
        "no rain falling indoors, no motion on solid objects, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Fireplace library: cabin interiors with stone fireplace + armchair + lamp + lantern + snow outside window
    #          OR pure indoor fireplace scenes (some with people — avoid)
    "fireplace": (
        "fire flames dancing and flickering vigorously in the fireplace or hearth, "
        "burning logs glowing with shifting orange embers, "
        "ember sparks drifting upward in warm air currents, "
        "warm golden light pulsing across the room, "
        "if any candle is visible: small flame wavering, "
        "if any lantern is visible: warm light pulsing softly, "
        "if any window shows outdoor scene: snow falling outside, "
        "if any mug is visible: faint steam rising upward, "
        "armchairs, sofas, tables, bookshelves, rugs, walls completely still, "
        "any person in the scene completely frozen and motionless, "
        "any chandelier or hanging light hangs perfectly still, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # River library: cabin porches with river outside + fireplace through window + lanterns
    #          OR pure outdoor rapids (rocks, ferns, flowing water)
    "river": (
        "river or stream water flowing naturally over rocks, "
        "white water cascading and forming small rapids, "
        "ripples spreading on the water surface, "
        "if mist is visible above water: mist drifting slowly upward, "
        "if there are ferns or leaves visible: very gentle swaying in the breeze, "
        "if a porch lantern is visible: warm flame flickering, "
        "if a fireplace is visible through a window: flames dancing inside, "
        "if moonlight is on the water: light shimmering on ripples, "
        "rocks, porch boards, rocking chair, mountains, tree trunks completely still, "
        "only water and mist move, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Ocean library: PNGs = cabin interior with bay window view of stormy ocean + fireplace + bed
    #          OR pure outdoor cliff with crashing waves on rocks
    "ocean_waves": (
        "if there is a window with ocean view: waves rolling and crashing against rocks outside, "
        "if this is an outdoor scene: waves rolling toward shore and breaking on rocks, "
        "white foam forming and spreading across the water surface, "
        "spray rising into the air from breaking waves, "
        "distant waves cresting on the horizon, "
        "if moon is visible: moonlight shimmering on the water, "
        "if any candle is visible on a windowsill: flame flickering, "
        "if any fireplace is visible: flames dancing, "
        "bed, blankets, walls, ceiling, rocks, vegetation completely still, "
        "only water and indoor flames move, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Soft_wind library: Japanese-style rooms with bamboo forest outside, paper lanterns, fireplace, zen garden
    "soft_wind": (
        "if bamboo or trees are visible outside: bamboo stalks and leaves swaying gently in a soft breeze, "
        "if cherry blossom petals are visible: petals drifting slowly through the air, "
        "if any paper lantern is visible: warm light pulsing softly, candle inside flickering, "
        "if any fireplace is visible: flames dancing quietly, "
        "if any curtain or fabric is visible: subtle movement in the wind, "
        "very gentle atmospheric motion overall, "
        "tatami floors, beds, futons, walls, zen garden rocks, sand patterns, lanterns completely still, "
        "no shaking, peaceful calm atmosphere, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Night_forest library: PNGs = glass treehouse with bioluminescent mushrooms + fairy lights + hammock + fireplace
    #              OR pure outdoor — stars through trees, dark forest paths
    "night_forest": (
        "if fireflies or glowing dots are visible: blinking and floating gently throughout the scene, "
        "if fairy lights are visible: twinkling softly, "
        "if bioluminescent mushrooms are visible: gentle blue glow pulsing, "
        "if trees or leaves are visible: very subtle swaying in soft breeze, "
        "if stars are visible: extremely subtle twinkle, "
        "if any fireplace is visible: flames dancing warmly, "
        "if mist is between trees: slow drifting motion, "
        "hammock, bed, bookshelves, tree trunks, rocks, paths completely still, "
        "magical peaceful atmosphere, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Brown_noise library: indoor study/desk with rainy window + city skyline + desk lamp + book + mug + candle + fireplace
    "brown_noise": (
        "if a window shows rain: raindrops sliding down the glass, light rain on outdoor window, "
        "if a city skyline is visible through the window: distant city lights twinkling and pulsing softly, "
        "if a desk lamp or bulb is visible: warm filament glow pulsing very gently, "
        "if a candle is visible: small flame wavering softly, "
        "if a mug is visible on the desk: thin steam rising gently from the cup, "
        "if a fireplace is visible: flames dancing quietly, "
        "very subtle calm motion overall, "
        "desk, open book, chair, bookshelves, walls, plants completely still, "
        "calm focused study atmosphere, minimal motion, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),

    # Thunder library: indoor study (same as brown_noise) with rainy window + city + fireplace + desk + candle
    "thunder": (
        "heavy rain falling outside the window, raindrops streaming down the glass intensely, "
        "occasional bright lightning flashing briefly across the night sky outside, "
        "if a city skyline is visible: lights pulsing more intensely during lightning flashes, "
        "if a fireplace is visible: flames flickering more vigorously during the storm, "
        "if a candle is visible: flame wavering with each lightning flash, "
        "if a desk lamp is visible: warm bulb steady but pulsing slightly during flashes, "
        "if a mug is visible: gentle steam rising, "
        "indoor furniture, desk, books, chair, bookshelves, walls completely still, "
        "storm intense outside, peaceful focused interior, "
        "cinematic, static camera, seamless loop, photorealistic"
    ),
}

NEGATIVE_PROMPT = (
    # Camera
    "fast camera movement, camera panning, camera zooming, camera rotating, "
    "shaky camera, dolly motion, parallax shift, "
    # People (some library images have people)
    "people moving, faces, hands moving, body movement, animated people, "
    "person walking, head turning, eyes blinking, "
    # Watermarks (some library images have watermarks)
    "text overlays, watermark animating, watermark moving, logo animating, "
    "signature changing, captions, subtitles, "
    # Physics-violating motion
    "rain falling indoors, rain inside a room, water inside walls, "
    "snow indoors, snow inside, "
    "furniture moving, beds shifting, sofas moving, armchairs rotating, "
    "books moving, bookshelves shifting, "
    "walls warping, ceiling moving, floors warping, rugs floating, "
    "tables wobbling, chairs moving, picture frames swinging, "
    "chandeliers swinging wildly, lanterns swinging wildly, "
    "tree trunks bending, rocks moving, mountains shifting, "
    # AI artifacts
    "distortion, warping, melting, morphing, flickering artifacts, "
    "abrupt motion, glitches, double exposure, blurry, low quality, "
    "extra limbs, deformed objects, broken geometry"
)

animation_success = False

# ─────────────────────────────────────────────
# AUTO-PROMPT VIA CLAUDE VISION
#
# Look at the actual image and generate a Kling prompt tailored
# to exactly what's in it. This handles all 91+ library images
# automatically and works for new images added later.
#
# Falls back to per-niche default if API call fails.
# Cost: ~$0.001 per Short with Claude Haiku.
# ─────────────────────────────────────────────
def generate_per_image_prompt(image_path: Path, niche: str) -> str:
    """Use Claude vision to generate a Kling animation prompt tailored to this exact image."""
    import hashlib

    # Check cache first — keyed by image content hash
    cache_file = PERSISTENT_DIR / "kling_prompt_cache.json"
    cache = {}
    try:
        if cache_file.exists():
            with open(cache_file) as f: cache = json.load(f)
    except Exception:
        pass

    with open(image_path, "rb") as f:
        img_data = f.read()
    img_hash = hashlib.sha256(img_data).hexdigest()[:16]

    if img_hash in cache:
        print(f"📝 Using cached prompt for {image_path.name}")
        return cache[img_hash]

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        print("ANTHROPIC_API_KEY not set — using fallback niche prompt")
        return VERTICAL_ANIMATION_PROMPTS.get(niche, "subtle ambient motion, seamless loop")

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=anthropic_key)

        img_b64 = base64.b64encode(img_data).decode()
        ext = image_path.suffix.lower()
        media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        instruction = f"""You are writing a Kling AI animation prompt for this exact image.
This will be a 5-second looping background for a YouTube Short about {niche.replace('_', ' ')} sounds.

LOOK AT THE IMAGE CAREFULLY. Identify every element that exists in it.

Write a Kling prompt that animates ONLY what makes physical sense:

MOTION rules (must respect physics):
- Rain/snow ONLY outside windows or in outdoor scenes — NEVER on indoor furniture
- Water flows downhill, not upward
- Indoor flames (fireplace, candle, lantern, lamp bulb) can flicker
- Steam rises from mugs/cups only if you see a mug/cup
- Stars twinkle very subtly if visible
- City lights pulse very subtly if visible through window
- Mist/fog drifts slowly horizontally
- Leaves/branches sway gently if outdoor or visible outside window
- Fireflies/bioluminescence pulse if you see glowing dots

STILL rules (these MUST NOT move):
- Beds, blankets, pillows, books, bookshelves, walls, ceilings, floors, rugs
- Furniture, chairs, tables, sofas, armchairs
- Mountains, rocks, tree trunks, buildings
- Any people, faces, hands (freeze them)
- Hanging lanterns/chandeliers (only their flame inside, not the lantern body)

Output format: comma-separated list of motion instructions, then "still:" followed by what doesn't move.
Maximum 90 words. No preamble. No explanation. Output the prompt directly.

Example output for a cabin interior with rainy window:
"rain falling outside arched window, raindrops sliding down glass, fireplace flames dancing in stone hearth on right, candle flames flickering on windowsill, lantern flames pulsing softly, steam rising from mug on floor, still: bed, blankets, books, bookshelves, walls, ceiling, rug, leather sofa, picture frame, hanging lantern bodies, cinematic static camera seamless loop"

Now write the prompt for THIS image:"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64,
                    }},
                    {"type": "text", "text": instruction},
                ],
            }],
        )

        prompt = response.content[0].text.strip()
        # Strip quotes if Claude wrapped output in them
        if prompt.startswith('"') and prompt.endswith('"'):
            prompt = prompt[1:-1]
        # Ensure it ends with cinematic loop instruction
        if "seamless loop" not in prompt.lower():
            prompt += ", cinematic, static camera, seamless loop"
        if "photorealistic" not in prompt.lower():
            prompt += ", photorealistic"

        print(f"📝 Auto-generated prompt ({len(prompt)} chars):")
        print(f"   {prompt[:200]}{'...' if len(prompt) > 200 else ''}")

        # Save to cache so future runs with same image skip the API call
        try:
            cache[img_hash] = prompt
            # Keep cache size reasonable — drop oldest if over 200 entries
            if len(cache) > 200:
                cache = dict(list(cache.items())[-200:])
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as ce:
            print(f"   (cache write failed: {ce})")

        return prompt

    except Exception as e:
        print(f"⚠️ Claude vision call failed: {e}")
        print(f"   Falling back to niche default prompt")
        return VERTICAL_ANIMATION_PROMPTS.get(niche, "subtle ambient motion, seamless loop")


if SHORT_BG_IMAGE.exists() and KLING_ACCESS_KEY and KLING_SECRET_KEY:
    # Generate per-image prompt via Claude vision
    print("Analysing image to generate tailored Kling prompt...")
    anim_prompt = generate_per_image_prompt(SHORT_BG_IMAGE, primary)

    def kling_jwt(ak, sk):
        h = base64.urlsafe_b64encode(json.dumps({"alg":"HS256","typ":"JWT"}).encode()).rstrip(b'=').decode()
        p = base64.urlsafe_b64encode(json.dumps({"iss":ak,"exp":int(time.time())+1800,"nbf":int(time.time())-5}).encode()).rstrip(b'=').decode()
        sig = base64.urlsafe_b64encode(hmac.new(sk.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
        return f"{h}.{p}.{sig}"

    try:
        token   = kling_jwt(KLING_ACCESS_KEY, KLING_SECRET_KEY)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        with open(str(SHORT_BG_IMAGE), "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        # KLING MODEL STRATEGY:
        # v2-master costs ~5x credits of v1-6. With only 18 credits left,
        # use v1-6-standard which still has good motion quality.
        # Switch back to v2-master when credits are replenished.
        payload = {
            "model_name":      "kling-v1-6",
            "image":           img_b64,
            "prompt":          anim_prompt,
            "negative_prompt": NEGATIVE_PROMPT + ", camera pan, camera zoom, camera rotation",
            "duration":        "8",
            "mode":            "std",
        }

        # Submit with retry on 429 (rate limit) — exponential backoff up to 3 attempts
        # Wait times: 60s, 120s, 240s — total 7 minutes worst case
        resp = None
        for attempt in range(3):
            resp = requests.post("https://api.klingai.com/v1/videos/image2video",
                                 headers=headers, json=payload, timeout=30)
            if resp.status_code == 429:
                wait = 60 * (2 ** attempt)
                print(f"Kling rate-limited (429). Retry {attempt+1}/3 in {wait}s...")
                time.sleep(wait)
                # Refresh JWT before retry — could be expired by now
                token = kling_jwt(KLING_ACCESS_KEY, KLING_SECRET_KEY)
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                continue
            break

        resp.raise_for_status()
        result = resp.json()

        if result.get("code") != 0:
            raise RuntimeError(f"Kling error: {result.get('message')}")

        task_id = result["data"]["task_id"]
        print(f"Kling vertical task: {task_id}")

        start = time.time()
        # Kling v2 Master + 10s duration can take 5-8 minutes
        # Timeout set to 10 minutes to be safe
        while time.time() - start < 600:
            time.sleep(8)
            poll = requests.get(f"https://api.klingai.com/v1/videos/image2video/{task_id}",
                                headers=headers, timeout=30)
            poll.raise_for_status()
            status = poll.json()
            task_status = status["data"]["task_status"]
            print(f"Kling: {task_status} ({int(time.time()-start)}s)")

            if task_status == "succeed":
                videos = status["data"]["task_result"].get("videos", [])
                if videos:
                    vid = requests.get(videos[0]["url"], timeout=120)
                    vid.raise_for_status()
                    with open(str(SHORT_BG_VIDEO), "wb") as f:
                        f.write(vid.content)
                    # Copy to persistent dir
                    import shutil
                    shutil.copy(str(SHORT_BG_VIDEO), str(PERSISTENT_DIR / "bg_short_animated.mp4"))
                    print(f"Short vertical animation saved: {SHORT_BG_VIDEO}")
                    animation_success = True
                    break
            elif task_status == "failed":
                raise RuntimeError(f"Kling failed: {status['data'].get('task_status_msg','')}")

    except Exception as e:
        print(f"Kling vertical animation failed: {e}")
        # CRITICAL: delete stale persistent animation so generate_short.py
        # doesn't reuse the PREVIOUS run's animation for the wrong niche
        stale_persistent = PERSISTENT_DIR / "bg_short_animated.mp4"
        if stale_persistent.exists():
            stale_persistent.unlink()
            print(f"   Deleted stale persistent animation: {stale_persistent}")
        stale_app = SHORT_BG_VIDEO
        if stale_app.exists():
            stale_app.unlink()
            print(f"   Deleted stale app animation: {stale_app}")
else:
    if not (KLING_ACCESS_KEY and KLING_SECRET_KEY):
        print("Kling keys not set — skipping Short animation")

# ─────────────────────────────────────────────
# SAVE METADATA
# ─────────────────────────────────────────────
meta = {
    "primary":           primary,
    "primary_category":  primary,
    "theme":             theme,
    "has_animation":     animation_success,
    "source":            "kling" if animation_success else "static",
    "image_source":      "library_portrait" if image_path else "api_portrait",
    "portrait":          True,
    "model":             "kling-v1-6" if animation_success else "static",
}
with open(str(SHORT_VISUAL_META), "w") as f:
    json.dump(meta, f, indent=2)

print(f"Short visual complete — animated={animation_success}, portrait=True")