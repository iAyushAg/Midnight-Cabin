#!/usr/bin/env python3
"""
generate_visual.py

Pollinations-first visual pipeline for Midnight Cabin.

What this does:
1. Uses Pollinations as the primary image generator.
2. Requests high-res 1920x1080 images first.
3. Falls back to 1280x720 if Pollinations keeps rate-limiting.
4. Rejects tiny / low-quality images under the configured file-size threshold.
5. Retries with different seeds.
6. Handles Pollinations 429 rate limits with exponential backoff.
7. Prevents black-screen prompts unless the video type is actually dark_screen.
8. Writes visual metadata for quality_gate.py.
"""

import json
import os
import random
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))

IDEA_PATH = PERSISTENT_DIR / "current_idea.json"
if not IDEA_PATH.exists():
    IDEA_PATH = BASE_DIR / "current_idea.json"

VIDEO_DIR = BASE_DIR / "video"
VIDEO_DIR.mkdir(exist_ok=True)

BG_IMAGE = VIDEO_DIR / "bg.jpg"
BG_ANIMATED = VIDEO_DIR / "bg_animated.mp4"
VISUAL_META_PATH = PERSISTENT_DIR / "current_visual.json"

POLLINATIONS_WIDTH = int(os.environ.get("POLLINATIONS_WIDTH", "1920"))
POLLINATIONS_HEIGHT = int(os.environ.get("POLLINATIONS_HEIGHT", "1080"))
POLLINATIONS_RETRIES = int(os.environ.get("POLLINATIONS_RETRIES", "5"))

# Start with 300 KB because Pollinations can return compressed images.
# You can raise this to 400000 or 500000 once you confirm reliable outputs.
MIN_POLLINATIONS_IMAGE_BYTES = int(
    os.environ.get("MIN_POLLINATIONS_IMAGE_BYTES", "300000")
)

POLLINATIONS_MODEL = os.environ.get("POLLINATIONS_MODEL", "flux")
POLLINATIONS_ENHANCE = os.environ.get("POLLINATIONS_ENHANCE", "true")
POLLINATIONS_NOLOGO = os.environ.get("POLLINATIONS_NOLOGO", "true")


# Remove stale animated clip so old animations do not accidentally get reused.
if BG_ANIMATED.exists():
    BG_ANIMATED.unlink()


def load_idea() -> dict:
    if not IDEA_PATH.exists():
        raise FileNotFoundError(f"Could not find current_idea.json at {IDEA_PATH}")

    with open(IDEA_PATH) as f:
        return json.load(f)


idea = load_idea()

theme = idea.get("theme", "Cozy Cabin Ambience")
title = idea.get("title", "")
primary = idea.get("audio_strategy", {}).get("primary_category", "rain")
secondary = idea.get("audio_strategy", {}).get("secondary_category", "")
layers = idea.get("sound_layers", [])
visual = idea.get("visual", "")
content_genre = idea.get("content_genre", "")
recommended_video_type = idea.get("recommended_video_type", "main")

is_dark_screen = (
    recommended_video_type == "dark_screen"
    or content_genre == "dark_screen_sleep"
    or "dark screen" in title.lower()
)

print(f"Generating visual for: {theme} ({primary})")
print(
    f"Video type: {recommended_video_type} | "
    f"Genre: {content_genre} | "
    f"Dark screen: {is_dark_screen}"
)


SCENE_PROMPTS = {
    "rain": (
        "cozy attic bedroom inside a rustic wooden cabin at night, "
        "large rain-streaked window with pine forest outside, "
        "warm amber lantern light, soft bed with blankets, old wooden beams, "
        "visible rain droplets on glass, calm cinematic sleep ambience, "
        "high detail, realistic digital painting, no people, no text, no watermark"
    ),
    "fireplace": (
        "snowed-in rustic forest lodge interior at night, "
        "large stone fireplace with warm orange flames, soft blankets, wooden floor, "
        "frosted windows showing gentle snowfall outside, cozy winter cabin mood, "
        "high detail, realistic digital painting, no people, no text, no watermark"
    ),
    "river": (
        "wooden riverside cabin porch at night, "
        "moonlit river flowing below, mist over water, pine forest, warm cabin window light, "
        "quiet protected sleep ambience, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
    "ocean_waves": (
        "lighthouse cabin bedroom on a rocky coast at night, "
        "large window facing dark ocean waves, moonlight on water, warm candlelight inside, "
        "cozy coastal sleep ambience, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
    "soft_wind": (
        "quiet wooden cabin in a forest at night, "
        "soft wind moving trees outside, warm window glow, simple bed, candles, wooden beams, "
        "peaceful sleep ambience, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
    "night_forest": (
        "glass-walled forest cabin at midnight, "
        "dark pine trees outside, moonlight, warm fireplace glow inside, soft blankets, "
        "calm forest sleep ambience, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
    "brown_noise": (
        "warm wooden cabin study room at night, "
        "desk lamp, notebook, bookshelves, rain on window, cozy focus ambience, "
        "minimalist but warm, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
    "thunder": (
        "cozy cabin porch during a distant thunderstorm at night, "
        "covered wooden porch, rain visible in warm light, distant storm clouds, "
        "subtle lightning glow far away, safe sheltered feeling, cabin window warm amber, "
        "cinematic storm sleep ambience, high detail, realistic digital painting, "
        "no people, no text, no watermark"
    ),
}


DARK_SCREEN_PROMPT = (
    "almost black screen sleep ambience, extremely dark cabin window silhouette, "
    "barely visible rain reflections, tiny warm cabin light far in distance, "
    "minimal visual detail, dark screen for overnight sleep, "
    "no people, no text, no watermark"
)


def build_prompt() -> str:
    if is_dark_screen:
        base = DARK_SCREEN_PROMPT
    else:
        base = SCENE_PROMPTS.get(primary, SCENE_PROMPTS["rain"])

        if secondary and secondary != primary:
            additions = {
                "rain": " additional visible rain on glass,",
                "fireplace": " small warm fireplace glow,",
                "thunder": " distant soft lightning glow outside,",
                "river": " moonlit river visible outside,",
                "ocean_waves": " ocean waves visible through window,",
                "soft_wind": " trees gently bending in wind outside,",
            }
            base += additions.get(secondary, "")

        if visual:
            cleaned_visual = str(visual)

            black_phrases = [
                "true black screen after 10 seconds",
                "black screen after 10 seconds",
                "screen stays black",
                "very dark overall—true black screen",
                "very dark overall - true black screen",
            ]

            for phrase in black_phrases:
                cleaned_visual = cleaned_visual.replace(phrase, "")

            # Keep this short because Pollinations uses the prompt in the URL.
            base += f" {cleaned_visual[:180]}"

    # Shorter style prompt to avoid giant URLs and 429 / request issues.
    style = (
        " premium cinematic cozy cabin ambience, warm amber light, deep soft shadows, "
        "realistic, high detail, 16:9 widescreen, no people, no text, no watermark, "
        "not blurry, not pixelated, not cartoon"
    )

    return base + style


FULL_PROMPT = build_prompt()
print(f"Prompt: {FULL_PROMPT[:220]}...")


def pollinations_url(prompt: str, seed: int, width: int, height: int) -> str:
    encoded = quote(prompt)
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}"
        f"&height={height}"
        f"&seed={seed}"
        f"&model={POLLINATIONS_MODEL}"
        f"&enhance={POLLINATIONS_ENHANCE}"
        f"&nologo={POLLINATIONS_NOLOGO}"
    )


def validate_image(path: Path, min_bytes: int = MIN_POLLINATIONS_IMAGE_BYTES) -> dict:
    size = path.stat().st_size

    if size < min_bytes:
        raise ValueError(
            f"Image too small: {size // 1024}KB. "
            f"Minimum is {min_bytes // 1024}KB."
        )

    with Image.open(path) as img:
        width, height = img.size

    if width < 1280 or height < 720:
        raise ValueError(f"Image dimensions too small: {width}x{height}")

    return {
        "size_bytes": size,
        "width": width,
        "height": height,
    }


def normalize_to_16x9(source_path: Path, output_path: Path, width: int, height: int) -> None:
    with Image.open(source_path) as img:
        img = img.convert("RGB")

        target_ratio = width / height
        img_ratio = img.width / img.height

        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        elif img_ratio < target_ratio:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))

        img = img.resize((width, height), Image.LANCZOS)
        img.save(output_path, "JPEG", quality=95, optimize=True)


def get_wait_seconds_for_429(resp: requests.Response, attempt: int) -> int:
    retry_after = resp.headers.get("Retry-After")

    if retry_after and retry_after.isdigit():
        return int(retry_after)

    # 30s, 60s, 120s, 240s, 240s
    return min(30 * (2 ** (attempt - 1)), 240)


def download_pollinations_image() -> dict:
    last_error = None

    # Try high-res first. If Pollinations keeps rate-limiting,
    # fall back to 1280x720 so the pipeline still has a chance to complete.
    size_plan = [
        (POLLINATIONS_WIDTH, POLLINATIONS_HEIGHT),
        (1280, 720),
    ]

    for width, height in size_plan:
        print(f"Pollinations size plan: {width}x{height}")

        # 1280x720 outputs are often more compressed, so use a slightly lower
        # minimum threshold for the fallback size.
        if width < 1920:
            min_bytes_for_this_size = min(MIN_POLLINATIONS_IMAGE_BYTES, 250000)
        else:
            min_bytes_for_this_size = MIN_POLLINATIONS_IMAGE_BYTES

        for attempt in range(1, POLLINATIONS_RETRIES + 1):
            seed = random.randint(1, 999_999_999)
            url = pollinations_url(FULL_PROMPT, seed, width, height)

            print(
                f"Calling Pollinations attempt {attempt}/{POLLINATIONS_RETRIES} "
                f"seed={seed} size={width}x{height}..."
            )

            tmp_path = BG_IMAGE.with_suffix(".tmp.jpg")

            try:
                resp = requests.get(
                    url,
                    timeout=240,
                    headers={
                        "User-Agent": "MidnightCabin/1.0 ambience-video-generator"
                    },
                )

                if resp.status_code == 429:
                    wait_seconds = get_wait_seconds_for_429(resp, attempt)
                    last_error = RuntimeError(
                        f"Pollinations rate limited with 429. "
                        f"Waited {wait_seconds}s before retry."
                    )
                    print(f"Pollinations 429 rate limit. Waiting {wait_seconds}s...")
                    time.sleep(wait_seconds)
                    continue

                resp.raise_for_status()

                with open(tmp_path, "wb") as f:
                    f.write(resp.content)

                raw_info = validate_image(tmp_path, min_bytes_for_this_size)

                normalize_to_16x9(tmp_path, BG_IMAGE, width, height)
                tmp_path.unlink(missing_ok=True)

                final_info = validate_image(BG_IMAGE, min_bytes_for_this_size)
                final_info["raw_size_bytes"] = raw_info["size_bytes"]
                final_info["raw_width"] = raw_info["width"]
                final_info["raw_height"] = raw_info["height"]
                final_info["seed"] = seed
                final_info["attempt"] = attempt
                final_info["requested_width"] = width
                final_info["requested_height"] = height
                final_info["min_image_bytes_used"] = min_bytes_for_this_size

                print(
                    "Pollinations image accepted: "
                    f"{final_info['width']}x{final_info['height']}, "
                    f"{final_info['size_bytes'] // 1024}KB"
                )

                return final_info

            except Exception as exc:
                last_error = exc
                print(f"Pollinations attempt {attempt} rejected: {exc}")
                tmp_path.unlink(missing_ok=True)

                # Non-429 errors get a smaller wait.
                time.sleep(min(5 * attempt, 30))

        print(f"Pollinations failed for size {width}x{height}; trying next size if available.")

    raise RuntimeError(
        f"Pollinations failed after all size plans and retries. Last error: {last_error}"
    )


try:
    image_info = download_pollinations_image()
except Exception as exc:
    print(f"❌ Visual generation failed: {exc}")
    sys.exit(1)


visual_meta = {
    "source": "pollinations",
    "model": POLLINATIONS_MODEL,
    "theme": theme,
    "title": title,
    "primary": primary,
    "secondary": secondary,
    "content_genre": content_genre,
    "recommended_video_type": recommended_video_type,
    "is_dark_screen": is_dark_screen,
    "has_animation": False,
    "motion_style": "ffmpeg_procedural_motion",
    "image_path": str(BG_IMAGE),
    "image_width": image_info["width"],
    "image_height": image_info["height"],
    "image_size_bytes": image_info["size_bytes"],
    "raw_image_width": image_info.get("raw_width"),
    "raw_image_height": image_info.get("raw_height"),
    "raw_image_size_bytes": image_info.get("raw_size_bytes"),
    "pollinations_seed": image_info["seed"],
    "pollinations_attempt": image_info["attempt"],
    "requested_width": image_info.get("requested_width"),
    "requested_height": image_info.get("requested_height"),
    "min_image_bytes": image_info.get("min_image_bytes_used", MIN_POLLINATIONS_IMAGE_BYTES),
    "prompt": FULL_PROMPT,
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

with open(VISUAL_META_PATH, "w") as f:
    json.dump(visual_meta, f, indent=2)

print(f"✅ Pollinations image ready: {BG_IMAGE}")
print(f"Visual metadata saved: {VISUAL_META_PATH}")
print("Visual generation complete")