"""
generate_visual.py — AI image generation for Midnight Cabins

Generates a cinematic, atmospheric scene using DALL-E 3
matching the current video theme (rain, fireplace, river, etc.)
Style inspired by Cozy Rain channel — warm, detailed, painterly interiors
"""

import json
import os
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")

IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(IDEA_PATH):
    IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

VIDEO_DIR = BASE_DIR / "video"
VIDEO_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = VIDEO_DIR / "bg.jpg"

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
with open(IDEA_PATH) as f:
    idea = json.load(f)

primary = idea.get("audio_strategy", {}).get("primary_category", "rain")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
theme = idea.get("theme", "Cozy Cabin Ambience")
layers = idea.get("sound_layers", [])

print(f"Generating visual for: {theme} ({primary})")

# ─────────────────────────────────────────────
# SCENE PROMPTS per primary category
# Cozy Rain style — warm, cinematic, detailed interior
# Always includes a window showing weather outside
# Always has warm light sources (fireplace, lanterns, candles)
# ─────────────────────────────────────────────
SCENE_PROMPTS = {
    "rain": (
        "A cozy attic bedroom in a rustic wooden cabin at night. "
        "Large arched windows showing heavy rain falling outside, "
        "rain droplets streaking down the glass. "
        "A stone fireplace with a crackling fire on the right. "
        "Warm lanterns hanging from exposed wooden beams. "
        "A plush bed with rumpled blankets, leather armchair, bookshelves. "
        "A steaming cup of tea on a side table. "
        "Warm amber and deep blue colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "cozy atmosphere, no people."
    ),
    "fireplace": (
        "A grand stone fireplace in a rustic mountain lodge at midnight. "
        "Roaring fire with bright orange flames and glowing embers. "
        "Wooden cabin interior with exposed log walls. "
        "Snow visible through a frost-edged window in the background. "
        "A leather armchair positioned close to the hearth. "
        "Warm amber firelight casting long shadows across the room. "
        "Pine cones, stacked wood, iron fire tools nearby. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "cozy atmosphere, no people."
    ),
    "river": (
        "A wooden cabin porch overlooking a misty mountain river at night. "
        "The river flowing gently between mossy rocks in the moonlight. "
        "Soft lantern light spilling through the cabin window. "
        "Pine forest on both sides of the river, fog rising from the water. "
        "A rocking chair on the porch with a wool blanket. "
        "Stars visible through breaks in the clouds above. "
        "Cool blue and warm amber colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "peaceful atmosphere, no people."
    ),
    "ocean_waves": (
        "A cliffside cottage bedroom overlooking a stormy ocean at night. "
        "Large windows showing waves crashing against dark rocks below. "
        "Moonlight breaking through storm clouds over the sea. "
        "A cozy reading nook with a lit candle and open book. "
        "Weathered wooden interior, nautical details, rope and driftwood accents. "
        "Deep navy blue and warm candlelight colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "moody coastal atmosphere, no people."
    ),
    "soft_wind": (
        "A Japanese-inspired wooden cabin in a bamboo forest at twilight. "
        "Shoji screen windows with silhouettes of bamboo swaying in the breeze. "
        "A simple interior with a futon, paper lanterns glowing softly. "
        "Cherry blossom petals drifting past the window from outside. "
        "A small zen garden visible through the open sliding door. "
        "Pale lavender, deep green, and warm gold colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "tranquil atmosphere, no people."
    ),
    "night_forest": (
        "A glass-walled treehouse deep in an ancient forest at midnight. "
        "Massive oak and pine trees surrounding the structure, moonlight filtering through. "
        "Bioluminescent mushrooms glowing softly on the forest floor below. "
        "Interior with a hammock, fairy lights strung across wooden beams. "
        "An owl perched on a branch just outside the glass. "
        "Fireflies visible in the forest darkness. "
        "Deep forest green, midnight blue, and soft gold colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "magical atmosphere, no people."
    ),
    "brown_noise": (
        "A modern minimalist study in a converted loft apartment at night. "
        "Floor to ceiling industrial windows with rain streaking down the glass. "
        "City lights blurred and glowing in the background beyond the rain. "
        "A clean desk with a warm lamp, open notebook, and steaming coffee. "
        "Exposed brick walls, dark wood shelving with books. "
        "A single candle burning on the windowsill. "
        "Warm amber, charcoal, and deep navy colour palette. "
        "Photorealistic digital painting, cinematic lighting, ultra detailed, "
        "focus atmosphere, no people."
    ),
}

# Add weather-specific enhancements
WEATHER_ADDITIONS = {
    "rain": ", rain on windows, wet glass reflections, dramatic rain outside",
    "thunder": ", lightning visible through windows, dramatic storm outside",
    "fireplace": ", fireplace flames, glowing embers, warm fire light",
    "ocean_waves": ", crashing waves visible, sea spray, stormy ocean",
    "soft_wind": ", gentle breeze, swaying plants, soft movement",
    "night_forest": ", moonlight through trees, forest sounds, peaceful night",
    "brown_noise": ", rain on city windows, urban night lights, focus atmosphere",
    "river": ", flowing water visible, misty river, moonlight on water",
}

base_prompt = SCENE_PROMPTS.get(
    primary,
    (
        "A cozy wooden cabin interior at night. Warm fireplace light. "
        "Rain visible through large windows. Atmospheric and cinematic. "
        "Photorealistic digital painting, ultra detailed, no people."
    )
)

# Add secondary layer context
secondary = idea.get("audio_strategy", {}).get("secondary_category", "")
if secondary and secondary != primary:
    addition = WEATHER_ADDITIONS.get(secondary, "")
    base_prompt += addition

full_prompt = base_prompt + (
    " Style: highly detailed digital art, reminiscent of cozy cabin artwork, "
    "warm cinematic photography, ultra realistic textures, "
    "perfect for a YouTube sleep ambience channel background, "
    "16:9 aspect ratio, no text, no watermarks, no people."
)

print(f"DALL-E prompt length: {len(full_prompt)} chars")

# ─────────────────────────────────────────────
# CALL DALL-E 3
# ─────────────────────────────────────────────
api_key = os.environ.get("OPENAI_API_KEY", "")

if not api_key:
    print("OPENAI_API_KEY not set — falling back to Unsplash")
    # Fallback to Unsplash
    UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    QUERIES = {
        "rain": "dark rainy cabin window night cozy",
        "fireplace": "cozy fireplace cabin night warm",
        "river": "mountain river night forest cabin",
        "ocean_waves": "ocean waves night cliff cottage",
        "soft_wind": "peaceful forest night cabin lantern",
        "night_forest": "dark forest night moonlight trees",
        "brown_noise": "dark study room night city rain",
    }
    query = QUERIES.get(primary, f"cozy cabin {primary} night dark atmospheric")
    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={UNSPLASH_KEY}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    img_url = resp.json()["urls"]["regular"]
    img = requests.get(img_url, timeout=60)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(img.content)
    print(f"Fallback Unsplash image saved: {OUTPUT_PATH}")
else:
    print("Calling DALL-E 3...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "dall-e-3",
        "prompt": full_prompt,
        "n": 1,
        "size": "1792x1024",  # closest to 16:9 widescreen
        "quality": "standard",  # use "hd" for better quality at $0.08/image
        "style": "vivid",  # vivid = more dramatic and cinematic
    }

    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=120
    )

    if resp.status_code != 200:
        print(f"DALL-E failed: {resp.status_code} {resp.text[:300]}")
        raise RuntimeError("DALL-E 3 image generation failed")

    image_url = resp.json()["data"][0]["url"]
    print(f"DALL-E image URL received")

    # Download the image
    img = requests.get(image_url, timeout=60)
    img.raise_for_status()

    with open(OUTPUT_PATH, "wb") as f:
        f.write(img.content)

    print(f"DALL-E 3 image saved: {OUTPUT_PATH}")

# ─────────────────────────────────────────────
# RESIZE TO 1280x720 for ffmpeg
# ─────────────────────────────────────────────
try:
    from PIL import Image
    img = Image.open(OUTPUT_PATH)
    img = img.convert("RGB")
    img = img.resize((1280, 720), Image.LANCZOS)
    img.save(OUTPUT_PATH, "JPEG", quality=95)
    print(f"Image resized to 1280x720: {OUTPUT_PATH}")
except Exception as e:
    print(f"PIL resize failed: {e} — ffmpeg will handle scaling")

# Save visual metadata for pipeline
visual_meta = {
    "primary": primary,
    "theme": theme,
    "prompt_used": full_prompt[:200],
    "source": "dalle3" if api_key else "unsplash",
}
with open(os.path.join(PERSISTENT_DIR, "current_visual.json"), "w") as f:
    json.dump(visual_meta, f, indent=2)

print("Visual generation complete")