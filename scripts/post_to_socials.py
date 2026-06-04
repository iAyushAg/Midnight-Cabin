#!/usr/bin/env python3
"""
post_to_socials.py — Midnight Cabin cross-platform auto-poster

Posts every Short to: Instagram Reels, Pinterest, YouTube Shorts (already done)
TikTok removed — banned in India.

Called automatically from run_short_pipeline.sh after upload_short.py.
Also callable manually for challenge Shorts.

PLATFORMS & SETUP:
──────────────────────────────────────────────────────────────────
Instagram Reels INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_ACCOUNT_ID + CLOUDINARY_URL
                developers.facebook.com → create app → Instagram Graph API
                Account must be Creator or Business (not Personal)
                CLOUDINARY_URL format: cloudinary://api_key:api_secret@cloud_name
                Free tier at cloudinary.com is sufficient

Pinterest       PINTEREST_ACCESS_TOKEN + PINTEREST_BOARD_ID
                developers.pinterest.com → create app → request Video Pin scope
                Run: python3 scripts/pinterest_auth.py  (one-time OAuth flow)
                Pinterest is the highest-ROI platform for sleep content:
                Pins are evergreen — a sleep Pin from 2 years ago still gets clicks.
                Sleep boards have 10M+ followers. Board ID is in the board URL.

USAGE:
  # Auto (called by pipeline):
  python3 scripts/post_to_socials.py

  # Manual:
  python3 scripts/post_to_socials.py --file output/short.mp4
  python3 scripts/post_to_socials.py --file output/challenge_short_rain.mp4 --challenge
  python3 scripts/post_to_socials.py --dry-run

ENV VARS IN RAILWAY:
  INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID, CLOUDINARY_URL
  PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

BASE_DIR       = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))
OUTPUT_DIR     = BASE_DIR / "output"

# ─────────────────────────────────────────────
# CREDENTIALS — all from Railway env vars
# ─────────────────────────────────────────────
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID   = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
CLOUDINARY_URL         = os.environ.get("CLOUDINARY_URL", "")

PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_BOARD_ID     = os.environ.get("PINTEREST_BOARD_ID", "")

TELEGRAM_BOT_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID       = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# ARGS
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Cross-post Short to all platforms")
parser.add_argument("--file",      default=None, help="Video file path (default: output/short.mp4)")
parser.add_argument("--challenge", action="store_true", help="Use challenge-format captions")
parser.add_argument("--niche",     default=None, help="Override niche for captions")
parser.add_argument("--dry-run",   action="store_true", help="Print captions, don't post")
args = parser.parse_args()

# ─────────────────────────────────────────────
# LOAD SHORT METADATA
# generate_short.py writes /data/current_short.json after every render
# ─────────────────────────────────────────────
SHORT_META_PATH = PERSISTENT_DIR / "current_short.json"
SHORT_IDEA_PATH = PERSISTENT_DIR / "short_idea.json"

short_meta = {}
if SHORT_META_PATH.exists():
    try:
        short_meta = json.loads(SHORT_META_PATH.read_text())
    except Exception:
        pass

# Also read short_idea.json for richer title/voiceover data
short_idea = {}
if SHORT_IDEA_PATH.exists():
    try:
        short_idea = json.loads(SHORT_IDEA_PATH.read_text())
    except Exception:
        pass

primary        = args.niche or short_meta.get("primary") or short_idea.get("audio_strategy", {}).get("primary_category", "rain")
hook_text      = short_meta.get("hook_text") or short_idea.get("hook_text", "")
voiceover      = short_meta.get("voiceover_text") or short_idea.get("voiceover", "")
hook_style     = short_meta.get("hook_style", "")
duration_label = short_meta.get("duration_label") or short_idea.get("duration_label", "8 Hours")
is_challenge   = args.challenge or hook_style == "countdown"

# Resolve video file
VIDEO_FILE = Path(args.file) if args.file else OUTPUT_DIR / "short.mp4"

if not VIDEO_FILE.exists():
    print(f"❌ Video file not found: {VIDEO_FILE}")
    print("Run the pipeline first or specify --file path/to/short.mp4")
    sys.exit(1)

file_size_mb = VIDEO_FILE.stat().st_size / 1024 / 1024
print(f"Video: {VIDEO_FILE} ({file_size_mb:.1f} MB)")
print(f"Niche: {primary} | Format: {hook_style or 'standard'} | Hook: {hook_text[:50]}")

# ─────────────────────────────────────────────
# DOUBLE-POST GUARD
# Checks if this exact file was already posted to each platform
# ─────────────────────────────────────────────
POST_LOG_PATH = PERSISTENT_DIR / "social_post_log.json"
post_log = []
if POST_LOG_PATH.exists():
    try:
        post_log = json.loads(POST_LOG_PATH.read_text())
    except Exception:
        pass

file_key = str(VIDEO_FILE.resolve())
already_posted_platforms = set()
for entry in post_log:
    if entry.get("file") == file_key:
        for platform in ["instagram", "pinterest"]:
            if entry.get(platform, {}).get("success"):
                already_posted_platforms.add(platform)

if already_posted_platforms:
    print(f"⚠️  Already posted to: {', '.join(already_posted_platforms)} — skipping those")

# ─────────────────────────────────────────────
# CAPTION BUILDER
# Uses actual hook_text and voiceover from the Short's idea
# Platform-specific hashtag sets — different algorithms, different tags
# ─────────────────────────────────────────────
NICHE_EMOJI = {
    "rain": "🌧️", "fireplace": "🔥", "river": "🌿", "ocean_waves": "🌊",
    "soft_wind": "🍃", "night_forest": "🌲", "brown_noise": "🧠", "thunder": "⛈️",
}
emoji = NICHE_EMOJI.get(primary, "🌙")

# Hook line — use actual generated hook, fall back to niche defaults
HOOK_FALLBACKS = {
    "rain": "your brain finally stopped", "fireplace": "you have nowhere to be tonight",
    "river": "the overthinking just stopped", "ocean_waves": "your body just exhaled",
    "soft_wind": "nothing needs you right now", "night_forest": "the whole world got quiet",
    "brown_noise": "your brain stopped scanning", "thunder": "you feel safe and cozy",
}
display_hook = hook_text or HOOK_FALLBACKS.get(primary, "save this for tonight")

# Challenge format overrides
CHALLENGE_HOOKS = {
    "rain": "Try to fall asleep before this ends",
    "fireplace": "Try to fall asleep before this ends",
    "brown_noise": "Try to keep one anxious thought for 28 seconds",
    "ocean_waves": "Try to fall asleep before this ends",
    "river": "Try to fall asleep before this ends",
    "soft_wind": "Try to stay tense while this plays",
    "night_forest": "Try to fall asleep before this ends",
    "thunder": "Try to feel tense during this thunderstorm",
}
if is_challenge:
    display_hook = CHALLENGE_HOOKS.get(primary, "Try to fall asleep before this ends")

# Instagram hashtags — discovery-first, mix of high and niche tags
INSTAGRAM_TAGS = {
    "rain":         "#rainsounds #sleepsounds #asmrsounds #cozytime #sleepaid #anxietyrelief #insomnia #rainyday #ambience #midnight",
    "fireplace":    "#fireplacesounds #cozyhome #hygge #sleepsounds #ambience #wintervibes #cozynights #warmth #cabinlife",
    "river":        "#riversounds #naturetherapy #sleepsounds #ambience #mindfulness #anxietyrelief #naturalsounds #waterasmr",
    "ocean_waves":  "#oceansounds #wavesounds #sleepsounds #beachvibes #naturetherapy #ambience #seasounds #calmdown",
    "soft_wind":    "#windsounds #forestbathing #sleepsounds #ambience #naturetherapy #peacefulplace #mindfulness",
    "night_forest": "#forestsounds #nightnature #sleepsounds #ambience #naturetherapy #wildcalling #crickets #nightvibes",
    "brown_noise":  "#brownnoise #adhdtok #focusmusic #studymusic #anxietyrelief #brainhealth #concentration #whitenoiseapp",
    "thunder":      "#thundersounds #stormchaser #sleepsounds #cozynight #ambience #rainyday #thunderstorm #stormy",
}

# Pinterest tags — keyword-rich, search-optimised (Pinterest is a search engine)
PINTEREST_TAGS = {
    "rain":         "rain sounds for sleep, rain ASMR, sleep sounds, anxiety relief sounds, rainy night cabin",
    "fireplace":    "fireplace sounds sleep, cozy cabin sounds, hygge ambience, sleep sounds, crackling fire",
    "river":        "river sounds sleep, nature sounds for sleep, water sounds anxiety, calming river sounds",
    "ocean_waves":  "ocean sounds sleep, wave sounds for sleeping, beach ambience, sea sounds meditation",
    "soft_wind":    "wind sounds sleep, forest sounds, nature sleep sounds, peaceful night sounds",
    "night_forest": "forest sounds sleep, cricket sounds night, nature ASMR, night sounds for sleeping",
    "brown_noise":  "brown noise sleep, brown noise ADHD, focus sounds, study music noise, anxiety brown noise",
    "thunder":      "thunderstorm sounds sleep, rain and thunder for sleeping, storm sounds ASMR, cozy storm",
}

def build_caption(platform: str) -> str:
    if platform == "instagram":
        if is_challenge:
            body = f"{display_hook} {emoji}\n\nDrop a 🕯️ if you didn't make it.\n\nFull 8-10 hour version at @midnightcabins\n\n"
        else:
            body = f"{display_hook} {emoji}\n\nSave this for tonight.\n\nFull 8-10 hour version at @midnightcabins\n\n"
        return (body + INSTAGRAM_TAGS.get(primary, "#sleepsounds #ambience #cozy #sleep #asmr"))[:2200]

    elif platform == "pinterest":
        # Pinterest pins have a title + description — no hashtags in title
        return None  # handled separately in post_to_pinterest

    return ""

# ─────────────────────────────────────────────
# CLOUDINARY — needed by Instagram
# Free tier: 25GB storage, 25GB bandwidth/month
# Sign up: cloudinary.com
# CLOUDINARY_URL format: cloudinary://api_key:api_secret@cloud_name
# ─────────────────────────────────────────────
def upload_to_cloudinary(video_path: Path) -> str | None:
    if not CLOUDINARY_URL:
        print("CLOUDINARY_URL not set — Instagram posting requires a public URL")
        print("Sign up free at cloudinary.com, then add CLOUDINARY_URL to Railway")
        return None

    try:
        import hashlib
        creds      = CLOUDINARY_URL.replace("cloudinary://", "")
        api_key, rest = creds.split(":", 1)
        api_secret, cloud_name = rest.rsplit("@", 1)

        timestamp  = str(int(time.time()))
        folder     = "midnight_cabin_shorts"
        # Signature must include ALL params being sent, sorted alphabetically
        params_str = f"folder={folder}&timestamp={timestamp}{api_secret}"
        signature  = hashlib.sha1(params_str.encode()).hexdigest()

        with open(video_path, "rb") as f:
            resp = requests.post(
                f"https://api.cloudinary.com/v1_1/{cloud_name}/video/upload",
                data={
                    "api_key":   api_key,
                    "timestamp": timestamp,
                    "signature": signature,
                    "folder":    folder,
                },
                files={"file": f},
                timeout=180,
            )
        resp.raise_for_status()
        url = resp.json().get("secure_url")
        print(f"Cloudinary: uploaded → {url[:80]}...")
        return url
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None


# ─────────────────────────────────────────────
# INSTAGRAM REELS
# Instagram Graph API v21.0
# docs: developers.facebook.com/docs/instagram-api/reference/ig-user/media
# Requires: Creator or Business account (Settings → Account type)
# ─────────────────────────────────────────────
def post_to_instagram(video_path: Path) -> dict:
    if "instagram" in already_posted_platforms:
        return {"success": False, "error": "already posted (skipped)"}
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        return {"success": False, "error": "INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID not set"}

    caption = build_caption("instagram")
    video_url = upload_to_cloudinary(video_path)
    if not video_url:
        return {"success": False, "error": "Cloudinary upload failed — no public URL for Instagram"}

    BASE = f"https://graph.facebook.com/v21.0/{INSTAGRAM_ACCOUNT_ID}"
    P    = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        # Step 1: Create container
        r = requests.post(
            f"{BASE}/media",
            params={**P, "media_type": "REELS", "video_url": video_url,
                    "caption": caption, "share_to_feed": "true"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            return {"success": False, "error": f"Container: {data['error']}"}
        container_id = data["id"]
        print(f"Instagram: container={container_id}")

        # Step 2: Poll until FINISHED
        for attempt in range(20):
            time.sleep(10)
            sr = requests.get(
                f"https://graph.facebook.com/v21.0/{container_id}",
                params={**P, "fields": "status_code,status"}, timeout=30,
            )
            sr.raise_for_status()
            code = sr.json().get("status_code", "")
            print(f"Instagram: container status={code} ({attempt+1}/20)")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                return {"success": False, "error": f"Container {code}: {sr.json()}"}
        else:
            return {"success": False, "error": "Container timed out after 200s"}

        # Step 3: Publish
        pr = requests.post(
            f"{BASE}/media_publish",
            params={**P, "creation_id": container_id}, timeout=30,
        )
        pr.raise_for_status()
        pd = pr.json()
        if "error" in pd:
            return {"success": False, "error": f"Publish: {pd['error']}"}
        return {"success": True, "post_id": str(pd.get("id", "?"))}

    except requests.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ─────────────────────────────────────────────
# PINTEREST VIDEO PIN
#
# Why Pinterest for sleep content:
#   - Pins are EVERGREEN — a pin from 2023 still ranks and drives traffic today
#   - Sleep boards have 10M+ monthly viewers
#   - Pinterest users actively search "rain sounds for sleep" etc.
#   - No algorithm fighting — pins surface in search results indefinitely
#   - Each pin links back to your YouTube channel = direct traffic
#
# Setup (15 minutes):
#   1. developers.pinterest.com → My Apps → Create App
#   2. Request scopes: pins:read, pins:write, boards:read
#   3. Run: python3 scripts/pinterest_auth.py  (one-time OAuth)
#   4. Find your board ID: open your sleep board on Pinterest,
#      the ID is in the URL: pinterest.com/username/board-name/
#      Board ID is numeric — use Pinterest API to list boards:
#      GET https://api.pinterest.com/v5/boards with your token
#   5. Set Railway env vars: PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID
#
# Pinterest Video Pin API:
# docs: developers.pinterest.com/docs/api/v5/#operation/pins/create
# ─────────────────────────────────────────────
def post_to_pinterest(video_path: Path) -> dict:
    if "pinterest" in already_posted_platforms:
        return {"success": False, "error": "already posted (skipped)"}
    if not PINTEREST_ACCESS_TOKEN:
        return {"success": False, "error": "PINTEREST_ACCESS_TOKEN not set"}
    if not PINTEREST_BOARD_ID:
        return {"success": False, "error": "PINTEREST_BOARD_ID not set"}

    # Pinterest needs a public URL — reuse Cloudinary if already uploaded
    # Check if Instagram already uploaded it (saves API calls)
    video_url = upload_to_cloudinary(video_path)
    if not video_url:
        return {"success": False, "error": "Cloudinary upload failed — no public URL for Pinterest"}

    # Pinterest title: 100 char max
    # Description: 500 char max. Keyword-rich for search.
    tags_str = PINTEREST_TAGS.get(primary, "sleep sounds, ambient sounds, relaxing sounds")
    title    = (short_idea.get("title") or display_hook)[:98]
    if len(title) < len(short_idea.get("title", display_hook)):
        title = title.rstrip() + "…"

    description = (
        f"{display_hook} {emoji}\n\n"
        f"Full {duration_label} version on @midnightcabins — no talking, no music.\n\n"
        f"Perfect for: {tags_str}"
    )[:500]

    headers = {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }

    payload = {
        "board_id":   PINTEREST_BOARD_ID,
        "title":      title,
        "description": description,
        "link":       "https://youtube.com/@midnightcabins",
        "media_source": {
            "source_type": "video_url",
            "url":         video_url,
            "cover_image_url": video_url.replace("/upload/", "/upload/so_1/"),
        },
    }

    try:
        r = requests.post(
            "https://api.pinterest.com/v5/pins",
            headers=headers, json=payload, timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if "id" in data:
            pin_url = f"https://pinterest.com/pin/{data['id']}/"
            print(f"Pinterest: pin created → {pin_url}")
            return {"success": True, "pin_id": data["id"], "url": pin_url}
        return {"success": False, "error": f"Unexpected response: {data}"}

    except requests.HTTPError as e:
        err = e.response.text[:200]
        # 403 often means scope not granted — surface clearly
        if e.response.status_code == 403:
            return {"success": False, "error": f"403 Forbidden — check that pins:write scope is granted. {err}"}
        return {"success": False, "error": f"HTTP {e.response.status_code}: {err}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ─────────────────────────────────────────────
# DRY RUN
# ─────────────────────────────────────────────
if args.dry_run:
    print("\n" + "="*55)
    print("DRY RUN — captions that would be posted")
    print("="*55)
    for platform in ["instagram"]:
        print(f"\n── {platform.upper()} ──")
        print(build_caption(platform))
    print(f"\n── PINTEREST ──")
    print(f"Title: {(short_idea.get('title') or display_hook)[:98]}")
    print(f"Tags:  {PINTEREST_TAGS.get(primary, '')}")
    print(f"\nFile: {VIDEO_FILE}")
    print(f"Niche: {primary} | Challenge: {is_challenge}")
    sys.exit(0)


# ─────────────────────────────────────────────
# POST TO ALL PLATFORMS
# ─────────────────────────────────────────────
results = {
    "file":       file_key,
    "posted_at":  datetime.now().isoformat(),
    "niche":      primary,
    "hook_style": hook_style,
    "instagram":  None,
    "pinterest":  None,
}

platforms = [
    ("Instagram", post_to_instagram, "instagram"),
    ("Pinterest", post_to_pinterest, "pinterest"),
]

for name, fn, key in platforms:
    print(f"\n{'='*50}")
    print(f"POSTING TO {name.upper()}")
    print(f"{'='*50}")
    result = fn(VIDEO_FILE)
    results[key] = result
    if result["success"]:
        extra = result.get("video_id") or result.get("post_id") or result.get("pin_id") or ""
        print(f"✅ {name}: posted {f'(id={extra})' if extra else ''}")
    else:
        print(f"❌ {name}: {result['error']}")

# ─────────────────────────────────────────────
# LOG
# ─────────────────────────────────────────────
post_log.append(results)
try:
    POST_LOG_PATH.write_text(json.dumps(post_log, indent=2))
except Exception as e:
    print(f"Log write failed: {e}")

# ─────────────────────────────────────────────
# TELEGRAM SUMMARY
# ─────────────────────────────────────────────
def _status(r):
    if r is None:      return "⏭ skipped"
    if r["success"]:   return "✅ posted"
    err = r.get("error", "failed")
    if "not set" in err or "skipped" in err:
        return "⚙️ not configured"
    return f"❌ {err[:60]}"

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    msg = (
        f"📱 Cross-post complete ({primary} {emoji})\n"
            f"Instagram: {_status(results['instagram'])}\n"
        f"Pinterest: {_status(results['pinterest'])}\n"
        f"File: {VIDEO_FILE.name}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=10,
        )
    except Exception:
        pass

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print(f"\n{'='*55}")
print("CROSS-POST SUMMARY")
print(f"{'='*55}")
for platform in ["instagram", "pinterest"]:
    print(f"  {platform:<12} {_status(results[platform])}")
print(f"\nLog: {POST_LOG_PATH}")