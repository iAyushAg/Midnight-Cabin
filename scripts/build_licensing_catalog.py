#!/usr/bin/env python3
"""
build_licensing_catalog.py — Midnight Cabin Audio Licensing Catalog Builder

Reads video_history.json and generates:
  1. /data/licensing_catalog.json  — machine-readable asset register
  2. /data/licensing_catalog.csv   — spreadsheet for outreach
  3. /data/licensing_pitch.txt     — ready-to-send email pitch template

Add this to your pipeline: run after collect_stats.py in run_pipeline.sh
  python3 scripts/build_licensing_catalog.py

The catalog becomes your sales asset when you hit 50K subscribers.
Each entry is a licensable audio product with:
  - Unique asset ID
  - Niche / mood / duration
  - YouTube performance (views, watch hours)
  - Suggested license tiers (sync, background, app integration)
  - YouTube URL for preview
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path

PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))
HISTORY_FILE = PERSISTENT_DIR / "video_history.json"
CATALOG_JSON = PERSISTENT_DIR / "licensing_catalog.json"
CATALOG_CSV  = PERSISTENT_DIR / "licensing_catalog.csv"
PITCH_FILE   = PERSISTENT_DIR / "licensing_pitch.txt"

# ─────────────────────────────────────────────
# LOAD HISTORY
# ─────────────────────────────────────────────
if not HISTORY_FILE.exists():
    print("No video_history.json found — run the main pipeline first.")
    raise SystemExit(0)

with open(HISTORY_FILE) as f:
    history = json.load(f)

if not history:
    print("History is empty.")
    raise SystemExit(0)

# ─────────────────────────────────────────────
# LICENSE TIER PRICING
# Based on industry standard rates for ambient/sleep audio
# Tiered by subscriber count — update CHANNEL_SUBS env var as you grow
# ─────────────────────────────────────────────
CHANNEL_SUBS = int(os.environ.get("CHANNEL_SUBS", "0"))

def get_license_tiers(views, duration_minutes, primary, channel_subs):
    """
    Return suggested license pricing for this asset.
    Prices scale with audience size and track performance.
    """
    # Base rates (at <10K subs — proof of concept pricing)
    # These increase as channel grows — update CHANNEL_SUBS
    if channel_subs >= 500_000:
        base_sync   = 2500
        base_bg     = 800
        base_app    = 15000
        base_excl   = 50000
    elif channel_subs >= 100_000:
        base_sync   = 800
        base_bg     = 250
        base_app    = 5000
        base_excl   = 20000
    elif channel_subs >= 50_000:
        base_sync   = 300
        base_bg     = 100
        base_app    = 2000
        base_excl   = 8000
    elif channel_subs >= 10_000:
        base_sync   = 100
        base_bg     = 35
        base_app    = 500
        base_excl   = 2000
    else:
        # Current stage — proof of concept pricing to start conversations
        base_sync   = 50
        base_bg     = 15
        base_app    = 200
        base_excl   = 800

    # Performance multiplier: high-view tracks command premium
    if views >= 1_000_000:
        mult = 3.0
    elif views >= 100_000:
        mult = 2.0
    elif views >= 10_000:
        mult = 1.5
    elif views >= 1_000:
        mult = 1.2
    else:
        mult = 1.0

    # Duration premium: 8h+ tracks are uniquely valuable to sleep apps
    if duration_minutes >= 480:
        duration_mult = 1.5
    elif duration_minutes >= 120:
        duration_mult = 1.2
    else:
        duration_mult = 1.0

    return {
        "sync_license_usd":         round(base_sync   * mult),
        "background_license_usd":   round(base_bg     * mult),
        "app_integration_usd":      round(base_app    * mult * duration_mult),
        "exclusive_buyout_usd":     round(base_excl   * mult * duration_mult),
        "note": "Prices scale with channel size. Update CHANNEL_SUBS env var as you grow."
    }

# ─────────────────────────────────────────────
# MOOD / USE-CASE TAGS
# For app licensing search and filtering
# ─────────────────────────────────────────────
MOOD_TAGS = {
    "rain":         ["sleep", "anxiety-relief", "focus", "cozy", "white-noise", "study"],
    "fireplace":    ["sleep", "cozy", "relaxation", "meditation", "winter"],
    "brown_noise":  ["focus", "adhd", "productivity", "sleep", "tinnitus-masking", "study"],
    "ocean_waves":  ["sleep", "meditation", "relaxation", "beach", "anxiety-relief"],
    "river":        ["sleep", "focus", "nature", "relaxation", "meditation"],
    "soft_wind":    ["sleep", "relaxation", "meditation", "nature", "gentle"],
    "night_forest": ["sleep", "meditation", "nature", "relaxation", "grounding"],
    "thunder":      ["sleep", "cozy", "white-noise", "rain", "storm"],
}

TARGET_APPS = {
    "rain":         ["Calm", "Headspace", "Sleep Cycle", "BetterSleep", "Endel", "Pzizz"],
    "fireplace":    ["Calm", "BetterSleep", "Endel", "Noisli", "myNoise"],
    "brown_noise":  ["Brain.fm", "Focus@Will", "Endel", "Noisli", "Flow (Finish Line Labs)"],
    "ocean_waves":  ["Calm", "Headspace", "BetterSleep", "Sleep Cycle", "Pzizz"],
    "river":        ["Calm", "myNoise", "BetterSleep", "Noisli", "Endel"],
    "soft_wind":    ["Calm", "BetterSleep", "myNoise", "Noisli"],
    "night_forest": ["Calm", "Headspace", "myNoise", "BetterSleep"],
    "thunder":      ["Calm", "BetterSleep", "myNoise", "Noisli", "Sleep Cycle"],
}

# ─────────────────────────────────────────────
# BUILD CATALOG
# ─────────────────────────────────────────────
catalog = []
asset_num = 1

for item in history:
    video_id    = item.get("video_id", "")
    title       = item.get("title", "Untitled")
    primary     = item.get("audio_strategy", {}).get("primary_category", "")
    layers      = item.get("sound_layers", [])
    duration_m  = item.get("duration_minutes", 0)
    uploaded_at = item.get("uploaded_at", "")
    video_type  = item.get("type", "main")
    perf        = item.get("performance", {})
    views       = perf.get("views", 0)
    likes       = perf.get("likes", 0)
    watch_hours = round(views * (duration_m / 60) * 0.35, 1)  # est. 35% avg completion

    # Skip Shorts for licensing (too short for app integration)
    if video_type == "short" or duration_m < 60:
        continue

    asset_id = f"MC-{asset_num:04d}"
    asset_num += 1

    youtube_url = f"https://youtube.com/watch?v={video_id}" if video_id else ""

    tiers = get_license_tiers(views, duration_m, primary, CHANNEL_SUBS)
    mood  = MOOD_TAGS.get(primary, ["sleep", "relaxation"])
    apps  = TARGET_APPS.get(primary, ["Calm", "BetterSleep"])

    entry = {
        "asset_id":             asset_id,
        "title":                title,
        "youtube_url":          youtube_url,
        "primary_sound":        primary,
        "sound_layers":         layers,
        "duration_minutes":     duration_m,
        "duration_label":       f"{duration_m // 60}h" if duration_m >= 60 else f"{duration_m}m",
        "mood_tags":            mood,
        "use_cases":            mood[:3],
        "target_apps":          apps,
        "performance": {
            "views":                views,
            "likes":                likes,
            "est_watch_hours":      watch_hours,
        },
        "license_tiers":        tiers,
        "uploaded_at":          uploaded_at,
        "is_flagship":          item.get("is_flagship", False),
    }
    catalog.append(entry)

# Sort by views descending (best performers first — lead with strength in outreach)
catalog.sort(key=lambda x: x["performance"]["views"], reverse=True)

# ─────────────────────────────────────────────
# SAVE JSON
# ─────────────────────────────────────────────
catalog_output = {
    "channel": "Midnight Cabin (@midnightcabins)",
    "generated_at": datetime.now().isoformat(),
    "channel_subscribers": CHANNEL_SUBS,
    "total_assets": len(catalog),
    "total_duration_hours": round(sum(e["duration_minutes"] for e in catalog) / 60, 1),
    "total_views": sum(e["performance"]["views"] for e in catalog),
    "total_est_watch_hours": round(sum(e["performance"]["est_watch_hours"] for e in catalog), 0),
    "assets": catalog,
}

PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

with open(CATALOG_JSON, "w") as f:
    json.dump(catalog_output, f, indent=2)

print(f"Catalog JSON saved: {CATALOG_JSON}")

# ─────────────────────────────────────────────
# SAVE CSV (for spreadsheet / outreach)
# ─────────────────────────────────────────────
CSV_FIELDS = [
    "asset_id", "title", "primary_sound", "duration_label",
    "views", "est_watch_hours", "mood_tags",
    "app_integration_usd", "sync_license_usd", "exclusive_buyout_usd",
    "target_apps", "youtube_url",
]

with open(CATALOG_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for e in catalog:
        writer.writerow({
            "asset_id":             e["asset_id"],
            "title":                e["title"],
            "primary_sound":        e["primary_sound"],
            "duration_label":       e["duration_label"],
            "views":                e["performance"]["views"],
            "est_watch_hours":      e["performance"]["est_watch_hours"],
            "mood_tags":            ", ".join(e["mood_tags"]),
            "app_integration_usd":  e["license_tiers"]["app_integration_usd"],
            "sync_license_usd":     e["license_tiers"]["sync_license_usd"],
            "exclusive_buyout_usd": e["license_tiers"]["exclusive_buyout_usd"],
            "target_apps":          ", ".join(e["target_apps"][:3]),
            "youtube_url":          e["youtube_url"],
        })

print(f"Catalog CSV saved: {CATALOG_CSV}")

# ─────────────────────────────────────────────
# GENERATE PITCH EMAIL TEMPLATE
# ─────────────────────────────────────────────
top_asset      = catalog[0] if catalog else {}
top_title      = top_asset.get("title", "our top sleep soundscape")
top_views      = top_asset.get("performance", {}).get("views", 0)
top_url        = top_asset.get("youtube_url", "")
total_assets   = len(catalog)
total_hours    = catalog_output["total_duration_hours"]
total_views    = catalog_output["total_views"]
rain_assets    = sum(1 for e in catalog if e["primary_sound"] == "rain")
noise_assets   = sum(1 for e in catalog if e["primary_sound"] == "brown_noise")
fire_assets    = sum(1 for e in catalog if e["primary_sound"] == "fireplace")

# Find best app_integration price for the outreach
best_app_price = max((e["license_tiers"]["app_integration_usd"] for e in catalog), default=200)

pitch = f"""
MIDNIGHT CABIN — AUDIO LICENSING CATALOG
Generated: {datetime.now().strftime('%B %d, %Y')}
Channel: @midnightcabins | youtube.com/@midnightcabins
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CATALOG OVERVIEW
  Total licensable tracks:   {total_assets}
  Total audio hours:         {total_hours}h
  Total YouTube views:       {total_views:,}
  Rain sound tracks:         {rain_assets}
  Brown noise / focus:       {noise_assets}
  Fireplace / cozy:          {fire_assets}

TOP PERFORMING ASSET
  "{top_title}"
  Views: {top_views:,}
  Preview: {top_url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTREACH EMAIL TEMPLATE (send when you hit 50K subs)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subject: Sleep audio licensing — {total_hours}h of ambient content for [App Name]

Hi [Name],

I run Midnight Cabin (@midnightcabins on YouTube) — a sleep and focus ambient 
channel with [X] subscribers and [X] monthly views.

I noticed [App Name] uses ambient sleep audio, and I wanted to reach out about 
licensing our catalog directly.

We have {total_assets} tracks across {total_hours} total hours, covering:
  • Rain / thunderstorm sounds ({rain_assets} tracks)
  • Brown noise / focus sounds ({noise_assets} tracks, popular with ADHD users)
  • Fireplace / cozy ambience ({fire_assets} tracks)
  • Ocean waves, river, forest night sounds

Our top track: "{top_title}" — {top_views:,} views on YouTube.
Preview: {top_url}

What we offer:
  • App integration license (exclusive in-app use): from ${best_app_price}/track
  • Background license (non-exclusive): from ${max(15, best_app_price // 14)}/track
  • Full catalog license (all {total_assets} tracks, perpetual): available on request

Every track is:
  ✓ 8–10 hours, continuous (no loops, no sudden changes)
  ✓ Mixed and EQ'd specifically for sleep and focus contexts
  ✓ AI-assisted production — no musician royalties or third-party clearance needed
  ✓ Available as WAV masters (not just YouTube streams)

Would you be open to a 15-minute call this week?
Happy to send over the full catalog CSV with previews.

Best,
[Your name]
Midnight Cabin
@midnightcabins
[email] | [phone optional]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TARGET COMPANIES FOR OUTREACH
(Research contact via LinkedIn — look for "Content Partnerships" or "Audio Lead")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIER 1 — Large apps (higher rates, harder to get in):
  • Calm (calm.com) — largest sleep app, licenses extensively
  • Headspace (headspace.com) — focus and sleep, strong brown noise demand
  • Sleep Cycle (sleepcycle.com) — uses ambient audio as sleep aids

TIER 2 — Mid-size apps (more accessible, faster decisions):
  • BetterSleep (bettersleep.com) — specifically ambient and ASMR
  • Endel (endel.io) — AI-adaptive audio, licenses source material
  • Pzizz (pzizz.com) — sleep and focus, known to work with indie creators

TIER 3 — Niche apps (smaller deals, but easier to land):
  • myNoise (mynoise.net) — curated ambient sound, creator-friendly
  • Noisli (noisli.com) — background noise for work, licenses audio
  • Brain.fm (brain.fm) — focus audio, brown noise especially relevant

WHEN TO START OUTREACH: When channel hits 50,000 subscribers.
Before that, build the catalog and perfect the pitch.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FILES
  Full catalog (JSON): {CATALOG_JSON}
  Spreadsheet (CSV):   {CATALOG_CSV}
  This pitch:          {PITCH_FILE}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

with open(PITCH_FILE, "w", encoding="utf-8") as f:
    f.write(pitch)

print(f"Pitch template saved: {PITCH_FILE}")
print(pitch)