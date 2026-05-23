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
    "rain":         "static camera, raindrops streaming down glass, fireplace flames flickering, all objects frozen, seamless loop",
    "fireplace":    "static camera, fireplace flames dancing upward, embers glowing, smoke wisping, all objects frozen, seamless loop",
    "river":        "static camera, water flowing downward over rocks, mist drifting, moonlight shimmering, all objects frozen, seamless loop",
    "ocean_waves":  "static camera, waves rolling and crashing, white foam forming, all objects frozen, seamless loop",
    "soft_wind":    "static camera, tree branches swaying gently, leaves rustling slowly, all objects frozen, seamless loop",
    "night_forest": "static camera, fireflies blinking and drifting, fairy lights twinkling, all objects frozen, seamless loop",
    "brown_noise":  "static camera, raindrops on window glass, candle flame wavering gently, all objects frozen, seamless loop",
    "thunder":      "static camera, heavy rain on glass, brief lightning flash, fireplace blazing, all objects frozen, seamless loop",
}

NEGATIVE_PROMPT = (
    "camera movement, camera pan, camera zoom, camera drift, "
    "people, faces, hands, text, watermark, logo, "
    "distortion, warping, flickering artifacts"
)

animation_success = False

if SHORT_BG_IMAGE.exists() and KLING_ACCESS_KEY and KLING_SECRET_KEY:
    anim_prompt = VERTICAL_ANIMATION_PROMPTS.get(
        primary,
        "static camera, subtle ambient motion, atmospheric movement, seamless loop"
    )

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

        payload = {
            "model_name":      "kling-v1-5",
            "image":           img_b64,
            "prompt":          anim_prompt,
            "negative_prompt": NEGATIVE_PROMPT + ", camera pan, camera zoom, camera rotation",
            "cfg_scale":       0.6,
            "mode":            "std",
            "duration":        "5",
        }

        resp = requests.post("https://api.klingai.com/v1/videos/image2video",
                             headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") != 0:
            raise RuntimeError(f"Kling error: {result.get('message')}")

        task_id = result["data"]["task_id"]
        print(f"Kling vertical task: {task_id}")

        start = time.time()
        while time.time() - start < 300:
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
    "model":             "kling-v1-5" if animation_success else "static",
}
with open(str(SHORT_VISUAL_META), "w") as f:
    json.dump(meta, f, indent=2)

print(f"Short visual complete — animated={animation_success}, portrait=True")