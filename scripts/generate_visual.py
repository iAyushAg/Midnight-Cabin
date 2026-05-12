"""
generate_visual.py

Pipeline:
1. Read primary theme from current_idea.json
2. Pick a random image from video/library/{primary}/
3. Send to Kling API for animation
4. Download animated clip to video/bg_animated.mp4

Falls back to:
- Pollinations.ai if no local image found
- Static image if Kling fails
"""

import json
import os
import time
import random
import base64
import hmac
import hashlib
import requests
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).parent.parent
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")

IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(IDEA_PATH):
    IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

VIDEO_DIR = BASE_DIR / "video"
LIBRARY_DIR = VIDEO_DIR / "library"
BG_IMAGE = VIDEO_DIR / "bg.jpg"
BG_VIDEO = VIDEO_DIR / "bg_animated.mp4"

VIDEO_DIR.mkdir(exist_ok=True)
LIBRARY_DIR.mkdir(exist_ok=True)

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
# ANIMATION PROMPTS per theme
# Focused on motion only — image is the anchor
# ─────────────────────────────────────────────
# Animation prompts — motion only, no camera movement
# Key principle: ONLY natural elements move (rain, fire, water)
# Camera is completely locked — no pan, zoom, or drift
ANIMATION_PROMPTS = {
    "rain": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only raindrops streaming down window glass are moving, "
        "only fireplace flames flickering with orange and red glow, "
        "warm amber firelight gently pulsing on walls and ceiling, "
        "all furniture bed pillows books lamps completely frozen and still, "
        "perfectly seamless loop"
    ),
    "fireplace": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only fireplace flames flickering and dancing with orange yellow glow, "
        "only glowing red hot embers crackling and shifting, "
        "only wisps of smoke rising slowly from fire, "
        "warm amber firelight pulsing softly on stone walls, "
        "all furniture objects decorations completely frozen still, "
        "perfectly seamless loop"
    ),
    "river": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only river water flowing and rippling over rocks, "
        "only gentle mist drifting slowly above water surface, "
        "only moonlight shimmer moving on water, "
        "only fireplace flames flickering softly, "
        "all cabin interior objects completely frozen still, "
        "perfectly seamless loop"
    ),
    "ocean_waves": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only ocean waves rolling and crashing on rocks, "
        "only white sea foam forming and dissolving, "
        "only water surface heaving with swells, "
        "only fireplace flames flickering and candlelight wavering, "
        "all interior furniture objects completely frozen still, "
        "perfectly seamless loop"
    ),
    "soft_wind": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only bamboo stalks swaying gently in breeze, "
        "only cherry blossom petals drifting slowly through air, "
        "only paper lanterns swaying very slightly, "
        "all interior floor objects furniture completely frozen still, "
        "perfectly seamless loop"
    ),
    "night_forest": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only fireflies blinking and drifting in dark forest, "
        "only fireplace flames flickering with warm amber glow, "
        "only fairy lights twinkling gently, "
        "all cabin interior trees bark completely frozen still, "
        "perfectly seamless loop"
    ),
    "brown_noise": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only raindrops streaming down window glass, "
        "only city lights shimmering through wet glass, "
        "only fireplace flames flickering softly, "
        "only candle flame wavering very gently, "
        "desk lamp notebook coffee cup all completely frozen still, "
        "perfectly seamless loop"
    ),
    "thunder": (
        "static locked camera, fixed viewpoint, no camera movement whatsoever, "
        "only heavy rain streaming violently down window glass, "
        "only single brief lightning flash illuminating sky, "
        "only fireplace flames blazing and dancing dramatically, "
        "all interior furniture objects completely frozen still, "
        "perfectly seamless loop"
    ),
}

NEGATIVE_PROMPT = (
    "camera pan, camera zoom, camera rotation, camera movement, "
    "rain indoors, rain on bed, rain on ceiling, rain on furniture, rain on floor, "
    "snow indoors, water indoors, "
    "people, faces, hands, human figures, "
    "text, watermark, logo, "
    "distortion, warping, morphing, melting, "
    "flickering artifacts, color shifts, overexposure, "
    "blurry, low quality, pixelated"
)

animation_prompt = ANIMATION_PROMPTS.get(
    primary,
    "subtle ambient motion, fireplace flickering, atmospheric movement, interior motionless"
)

# Add secondary layer context
if secondary and secondary != primary:
    additions = {
        "rain": ", rain streaming down window glass",
        "fireplace": ", fireplace flames flickering",
        "river": ", river water rippling",
        "ocean_waves": ", waves moving outside",
    }
    animation_prompt += additions.get(secondary, "")

# ─────────────────────────────────────────────
# STEP 1 — PICK IMAGE FROM LOCAL LIBRARY
# video/library/{primary}/*.jpg or *.png
# Falls back to Pollinations if library empty
# ─────────────────────────────────────────────
def pick_library_image(primary):
    """Pick a random image from the local library for this theme."""
    theme_dir = LIBRARY_DIR / primary
    if not theme_dir.exists():
        print(f"No library folder found: {theme_dir}")
        return None

    images = list(theme_dir.glob("*.jpg")) + \
             list(theme_dir.glob("*.jpeg")) + \
             list(theme_dir.glob("*.png"))

    if not images:
        print(f"No images in library for: {primary}")
        return None

    chosen = random.choice(images)
    print(f"Selected from library: {chosen.name}")
    return chosen

def download_pollinations_fallback(primary, output_path):
    """Generate image from Pollinations.ai as fallback."""
    PROMPTS = {
        "rain": (
            "cozy attic bedroom rustic wooden cabin at night, "
            "large arched window filled with heavy rainfall dark stormy sky outside, "
            "raindrops on glass, stone fireplace bright orange flames bottom right, "
            "warm amber lanterns wooden beams, plush bed rumpled blankets, "
            "bookshelves, steaming mug, deep blue and amber palette, "
            "cinematic digital painting, photorealistic, ultra detailed, no people, no text"
        ),
        "fireplace": (
            "grand stone fireplace roaring orange fire bottom right, "
            "mountain lodge interior night, frost window showing snow, "
            "leather armchair, exposed log walls, warm amber glow, "
            "cinematic digital painting, photorealistic, ultra detailed, no people, no text"
        ),
        "river": (
            "wooden cabin porch moonlit mountain river at night, "
            "river flowing over rocks bottom half, mist rising, "
            "warm lantern light through window, pine forest both sides, "
            "cool blue and warm amber, cinematic digital painting, no people, no text"
        ),
        "ocean_waves": (
            "cliffside cottage bedroom stormy ocean at night, "
            "large window showing waves crashing on rocks, "
            "fireplace small fire bottom right, candle on windowsill, "
            "deep navy candlelight, cinematic digital painting, no people, no text"
        ),
        "soft_wind": (
            "japanese cabin bamboo forest twilight, "
            "shoji windows showing swaying bamboo, paper lanterns glowing, "
            "small fireplace embers bottom right, cherry blossom petals, "
            "pale lavender deep green gold, cinematic digital painting, no people, no text"
        ),
        "night_forest": (
            "glass treehouse deep forest midnight, "
            "moonlight through glass walls, fireplace glowing bottom right, "
            "fairy lights wooden beams, bioluminescent mushrooms, "
            "forest green midnight blue gold, cinematic digital painting, no people, no text"
        ),
        "brown_noise": (
            "modern loft study night, floor to ceiling windows rain on city glass, "
            "warm desk lamp open notebook coffee, "
            "small fireplace bottom right candle, exposed brick dark wood, "
            "warm amber charcoal navy, cinematic digital painting, no people, no text"
        ),
        "thunder": (
            "cozy cabin living room violent thunderstorm, "
            "windows showing lightning storm dark sky rain, "
            "roaring fireplace bright flames bottom right, "
            "thick blankets armchair, deep blue amber dramatic, "
            "cinematic digital painting, no people, no text"
        ),
    }
    prompt = PROMPTS.get(primary, f"cozy cabin {primary} night cinematic, no people, no text")
    prompt += ", masterpiece, best quality, 8k uhd, cinematic lighting"

    try:
        encoded = quote(prompt)
        seed = abs(hash(theme)) % 999999
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1280&height=720&seed={seed}&model=flux&nologo=true&enhance=true")
        print("Calling Pollinations.ai fallback...")
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        size = os.path.getsize(output_path)
        if size < 10000:
            print(f"Pollinations returned tiny file ({size}b)")
            return False
        print(f"Pollinations image saved: {size//1024}KB")
        return True
    except Exception as e:
        print(f"Pollinations failed: {e}")
        return False

# Pick image
image_path = pick_library_image(primary)

if image_path:
    # Copy to bg.jpg
    import shutil
    shutil.copy(str(image_path), str(BG_IMAGE))
    print(f"Library image copied to: {BG_IMAGE}")
else:
    # Fallback to Pollinations
    print(f"No library image for {primary} — generating with Pollinations...")
    success = download_pollinations_fallback(primary, str(BG_IMAGE))
    if not success:
        print("Pollinations failed — no background image available")
        image_path = None

# Resize to 1280x720
if os.path.exists(str(BG_IMAGE)):
    try:
        from PIL import Image as PILImage
        img = PILImage.open(str(BG_IMAGE)).convert("RGB")
        img = img.resize((1280, 720), PILImage.LANCZOS)
        img.save(str(BG_IMAGE), "JPEG", quality=95)
        print(f"Resized to 1280x720")
    except Exception as e:
        print(f"PIL resize failed: {e}")

# ─────────────────────────────────────────────
# STEP 2 — ANIMATE VIA KLING API
# Official Kling API: app.klingai.com/global/dev
# Requires KLING_ACCESS_KEY + KLING_SECRET_KEY
# Falls back to Replicate if Kling not configured
# ─────────────────────────────────────────────
KLING_ACCESS_KEY = os.environ.get("KLING_ACCESS_KEY", "")
KLING_SECRET_KEY = os.environ.get("KLING_SECRET_KEY", "")
REPLICATE_KEY = os.environ.get("REPLICATE_API_KEY", "")

def generate_kling_jwt(access_key, secret_key):
    """Generate JWT token for Kling API authentication."""
    import time
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b'=').decode()

    payload = base64.urlsafe_b64encode(
        json.dumps({
            "iss": access_key,
            "exp": int(time.time()) + 1800,  # 30 min expiry
            "nbf": int(time.time()) - 5
        }).encode()
    ).rstrip(b'=').decode()

    signature_input = f"{header}.{payload}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret_key.encode(), signature_input, hashlib.sha256).digest()
    ).rstrip(b'=').decode()

    return f"{header}.{payload}.{signature}"

def animate_with_kling(image_path, prompt, negative_prompt):
    """Animate image using official Kling API."""
    print("Animating with Kling API...")

    token = generate_kling_jwt(KLING_ACCESS_KEY, KLING_SECRET_KEY)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Convert image to base64
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Submit task
    payload = {
        "model_name": "kling-v1-5",  # v1.5 has better motion control than v1
        "image": img_b64,
        "prompt": prompt,
        "negative_prompt": negative_prompt + (
            ", camera pan, camera zoom, camera rotation, camera drift, "
            "camera movement, viewpoint change, perspective shift, "
            "dolly shot, tracking shot, handheld camera, "
            "scene transition, cut, fade, dissolve"
        ),
        "cfg_scale": 0.6,    # higher = follows prompt more strictly
        "mode": "std",
        "duration": "5",     # 5 seconds
    }

    resp = requests.post(
        "https://api.klingai.com/v1/videos/image2video",
        headers=headers,
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        raise RuntimeError(f"Kling API error: {result.get('message', 'unknown')}")

    task_id = result["data"]["task_id"]
    print(f"Kling task submitted: {task_id}")

    # Poll for completion
    max_wait = 300
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(8)
        poll = requests.get(
            f"https://api.klingai.com/v1/videos/image2video/{task_id}",
            headers=headers,
            timeout=30
        )
        poll.raise_for_status()
        status = poll.json()

        if status.get("code") != 0:
            raise RuntimeError(f"Kling poll error: {status.get('message')}")

        task_status = status["data"]["task_status"]
        print(f"Kling status: {task_status} ({int(time.time()-start)}s)")

        if task_status == "succeed":
            videos = status["data"]["task_result"].get("videos", [])
            if videos:
                video_url = videos[0]["url"]
                print(f"Downloading animated video...")
                vid = requests.get(video_url, timeout=120)
                vid.raise_for_status()
                with open(str(BG_VIDEO), "wb") as f:
                    f.write(vid.content)
                print(f"Animated video saved: {os.path.getsize(str(BG_VIDEO))//1024}KB")
                return True
        elif task_status == "failed":
            raise RuntimeError(f"Kling task failed: {status['data'].get('task_status_msg', '')}")

    raise RuntimeError("Kling timed out after 5 minutes")

def animate_with_replicate(image_path, prompt):
    """Fallback: animate with Replicate Wan I2V."""
    try:
        import replicate as _replicate
        client = _replicate.Client(api_token=REPLICATE_KEY)
        print("Animating with Replicate fallback...")

        with open(image_path, "rb") as img_file:
            output = client.run(
                "wan-video/wan-2.2-i2v-fast",
                input={
                    "image": img_file,
                    "prompt": prompt,
                    "negative_prompt": NEGATIVE_PROMPT,
                    "num_frames": 81,
                    "frames_per_second": 16,
                    "resolution": "480p",
                    "aspect_ratio": "16:9",
                    "sample_shift": 16,
                    "go_fast": True,
                }
            )

        video_url = str(output) if not isinstance(output, list) else str(output[0])
        vid = requests.get(video_url, timeout=120)
        vid.raise_for_status()
        with open(str(BG_VIDEO), "wb") as f:
            f.write(vid.content)
        print(f"Replicate video saved: {os.path.getsize(str(BG_VIDEO))//1024}KB")
        return True
    except Exception as e:
        print(f"Replicate failed: {e}")
        return False

# Attempt animation
animation_success = False

if os.path.exists(str(BG_IMAGE)):
    if KLING_ACCESS_KEY and KLING_SECRET_KEY:
        try:
            animation_success = animate_with_kling(
                str(BG_IMAGE), animation_prompt, NEGATIVE_PROMPT
            )
        except Exception as e:
            print(f"Kling failed: {e} — trying Replicate")

    if not animation_success and REPLICATE_KEY:
        animation_success = animate_with_replicate(str(BG_IMAGE), animation_prompt)

    if not animation_success:
        print("No animation API available — using static image")
else:
    print("No background image — skipping animation")

# Save metadata
visual_meta = {
    "primary": primary,
    "theme": theme,
    "has_animation": animation_success,
    "source": "kling" if (animation_success and KLING_ACCESS_KEY) else
              "replicate" if animation_success else "static",
    "image_source": "library" if (image_path and image_path != BG_IMAGE) else "pollinations",
}
with open(os.path.join(PERSISTENT_DIR, "current_visual.json"), "w") as f:
    json.dump(visual_meta, f, indent=2)

if animation_success:
    # Copy to persistent dir so Short pipeline finds it after redeploy
    import shutil as _shutil
    persistent_anim = os.path.join(PERSISTENT_DIR, "bg_animated.mp4")
    _shutil.copy(str(BG_VIDEO), persistent_anim)
    print(f"✅ Animated video ready: {BG_VIDEO}")
    print(f"✅ Saved to persistent dir: {persistent_anim}")
else:
    print(f"✅ Static image ready: {BG_IMAGE}")

print("Visual generation complete")