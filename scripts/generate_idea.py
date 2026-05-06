import json
import os
import random
import re
from datetime import datetime, timedelta
from collections import Counter

from anthropic import Anthropic
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")

HISTORY_PATH = os.path.join(PERSISTENT_DIR, "video_history.json")
IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
TOKEN_FILE = os.path.join(PERSISTENT_DIR, "token.json")

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Content-quality goals for faster monetization readiness:
# 1. No duplicate titles/concepts in the recent catalog.
# 2. Scene-first, specific titles instead of generic sound names.
# 3. Brown noise is used selectively, not in every upload.
# 4. Every idea includes a unique angle and first-30-second viewer promise.
# 5. Descriptions and thumbnails get stronger scene metadata downstream.
BROWN_NOISE_TARGET_RATIO = float(os.environ.get("BROWN_NOISE_TARGET_RATIO", "0.55"))
RECENT_WINDOW = int(os.environ.get("CONTENT_RECENT_WINDOW", "20"))
FLAGSHIP_INTERVAL_DAYS = int(os.environ.get("FLAGSHIP_INTERVAL_DAYS", "7"))
FORCE_FLAGSHIP = os.environ.get("FORCE_FLAGSHIP", "").lower() in {"1", "true", "yes"}
DISABLE_FLAGSHIP = os.environ.get("DISABLE_FLAGSHIP", "").lower() in {"1", "true", "yes"}

CONTENT_BUCKETS = [
    "rain", "river", "thunder", "fireplace", "ocean_waves",
    "soft_wind", "night_forest", "brown_noise"
]

SCENE_LOCATIONS = [
    "Mountain Cabin Roof",
    "Foggy Riverside Cabin",
    "Snowed-In Forest Lodge",
    "Attic Bedroom Window",
    "Lakeside Cabin at 3AM",
    "Old Library Fireplace",
    "Rainy Pine Forest Hideaway",
    "Dark Cabin Porch",
    "Moonlit Ocean Cabin",
    "Remote Study Room",
    "Storm Window Bedroom",
    "Deep Forest Loft",
]

SECONDARY_BY_PRIMARY = {
    "rain": ["soft_wind", "thunder", "night_forest"],
    "river": ["rain", "night_forest", "soft_wind"],
    "thunder": ["rain", "soft_wind"],
    "fireplace": ["soft_wind", "rain", "night_forest"],
    "ocean_waves": ["soft_wind", "rain"],
    "soft_wind": ["night_forest", "rain", "fireplace"],
    "night_forest": ["soft_wind", "river", "rain"],
    "brown_noise": ["rain", "fireplace", "soft_wind"],
}


def load_json(path, fallback):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as exc:
        print(f"Failed to load {path}: {exc}")
    return fallback


def normalize_title(title):
    return re.sub(r"\s+", " ", str(title).strip().lower())


def normalize_layers(layers):
    return tuple(sorted(str(layer) for layer in layers if layer))


def extract_scene_from_title(title):
    title = str(title or "")
    if "|" in title:
        return title.split("|", 1)[0].strip().lower()
    return title.strip().lower()


def pick_unused_scene(recent_scenes):
    choices = [s for s in SCENE_LOCATIONS if s.lower() not in recent_scenes]
    return random.choice(choices or SCENE_LOCATIONS)


def should_use_brown_noise(primary, recent_items):
    if primary == "brown_noise":
        return True
    if not recent_items:
        return random.random() < BROWN_NOISE_TARGET_RATIO
    uses = sum(1 for item in recent_items if "brown_noise" in item.get("sound_layers", []))
    ratio = uses / max(len(recent_items), 1)
    return ratio < BROWN_NOISE_TARGET_RATIO


def should_make_flagship(history):
    """Create one higher-effort hero concept roughly once per week."""
    if DISABLE_FLAGSHIP:
        return False
    if FORCE_FLAGSHIP:
        return True
    cutoff = datetime.now() - timedelta(days=FLAGSHIP_INTERVAL_DAYS)
    for item in reversed(history):
        if not (item.get("is_flagship") or item.get("content_tier") == "flagship"):
            continue
        try:
            uploaded_at = datetime.fromisoformat(str(item.get("uploaded_at", "")))
        except Exception:
            continue
        if uploaded_at >= cutoff:
            return False
    return True


def safe_parse_json(text):
    """Robustly extract and parse the first valid JSON object from model text."""
    text = re.sub(r"```json|```", "", text).strip()
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        return None

    json_str = re.sub(r",\s*([}\]])", r"\1", text[start:end + 1])
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}")
        return None


history = load_json(HISTORY_PATH, [])
recent_results = history[-RECENT_WINDOW:]
is_flagship = should_make_flagship(history)
content_tier = "flagship" if is_flagship else "standard"

recent_titles = {normalize_title(v.get("title", "")) for v in recent_results}
recent_scenes = {extract_scene_from_title(v.get("title", "")) for v in recent_results}
recent_layer_combos = Counter(normalize_layers(v.get("sound_layers", [])) for v in recent_results)
recent_primary_counts = Counter(
    v.get("audio_strategy", {}).get("primary_category") for v in recent_results
    if v.get("audio_strategy", {}).get("primary_category")
)

# Theme blackout: avoid primaries used in the last 30 days when possible.
BLACKOUT_DAYS = 30
cutoff = datetime.now() - timedelta(days=BLACKOUT_DAYS)
blacked_out_themes = set()
for item in history:
    uploaded_at = item.get("uploaded_at", "")
    try:
        upload_date = datetime.fromisoformat(uploaded_at)
    except Exception:
        continue
    if upload_date >= cutoff:
        primary = item.get("audio_strategy", {}).get("primary_category")
        if primary:
            blacked_out_themes.add(primary)

print("Blacked out themes (used in last 30 days):", blacked_out_themes)

available_buckets = [b for b in CONTENT_BUCKETS if b not in blacked_out_themes]
if not available_buckets:
    print("All themes blacked out - resetting blackout")
    available_buckets = CONTENT_BUCKETS[:]

min_count = min((recent_primary_counts.get(c, 0) for c in available_buckets), default=0)
least_used = [c for c in available_buckets if recent_primary_counts.get(c, 0) == min_count]
random.shuffle(least_used)
suggested_primary = least_used[0] if least_used else random.choice(CONTENT_BUCKETS)

last_primary = history[-1].get("audio_strategy", {}).get("primary_category") if history else None
if suggested_primary == last_primary and len(available_buckets) > 1:
    remaining = [b for b in available_buckets if b != last_primary]
    suggested_primary = random.choice(remaining)
    print(f"Avoided repeating last category ({last_primary}), switched to: {suggested_primary}")

include_brown_noise = should_use_brown_noise(suggested_primary, recent_results)
scene_hint = pick_unused_scene(recent_scenes)
secondary_hint = random.choice(SECONDARY_BY_PRIMARY.get(suggested_primary, ["soft_wind"]))

print("Suggested primary category:", suggested_primary)
print("Scene hint:", scene_hint)
print("Include brown noise:", include_brown_noise)
print("Content tier:", content_tier)

# Video length: alternate between 8h and 10h.
last_duration = history[-1].get("duration_minutes", 480) if history else 480
next_duration_minutes = 600 if last_duration <= 480 else 480
duration_label = "10 Hours" if next_duration_minutes == 600 else "8 Hours"
print(f"Next video duration: {duration_label} ({next_duration_minutes} min)")

# Optional YouTube trend inspiration.
trending_keywords = []
try:
    creds = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        ["https://www.googleapis.com/auth/youtube.readonly"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    youtube = build("youtube", "v3", credentials=creds)
    seed_terms = [
        f"{suggested_primary.replace('_', ' ')} sleep ambience",
        "cabin sleep ambience",
        "dark screen sleep sounds",
    ]

    for seed in seed_terms:
        response = youtube.search().list(
            part="snippet",
            q=seed,
            type="video",
            order="viewCount",
            videoCategoryId="10",
            maxResults=5,
        ).execute()
        for item in response.get("items", []):
            trending_keywords.append(item["snippet"]["title"])

    print("Trending titles found:", len(trending_keywords))
except Exception as e:
    print("YouTube trend fetch failed (non-fatal):", e)

# Performance context.
top_performers = []
low_performers = []
if history:
    scored = [
        (i, v.get("performance", {}).get("views", 0))
        for i, v in enumerate(history)
        if v.get("performance", {}).get("views", 0) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_performers = [history[i] for i, _ in scored[:3]]
    low_performers = [history[i] for i, v in scored[-3:] if v > 0]

top_performers_json = json.dumps(
    [{"title": str(v.get("title", "")), "views": int(v.get("performance", {}).get("views", 0))}
     for v in top_performers],
    indent=2,
)
low_performers_json = json.dumps(
    [{"title": str(v.get("title", "")), "views": int(v.get("performance", {}).get("views", 0))}
     for v in low_performers],
    indent=2,
)
recent_titles_json = json.dumps([v.get("title", "") for v in recent_results[-12:]], indent=2)
recent_combos_json = json.dumps([
    {"primary": v.get("audio_strategy", {}).get("primary_category"), "layers": v.get("sound_layers", [])}
    for v in recent_results[-12:]
], indent=2)

brown_noise_rule = (
    "Include brown_noise only if it genuinely improves the concept. Do NOT force it."
    if not include_brown_noise
    else "You MAY include brown_noise, but only as a subtle supporting layer if it fits."
)

prompt = f"""
You are the Idea Agent for a YouTube channel called Midnight Cabin.

The channel creates long sleep, relaxation, and focus soundscape videos. The goal is to build a monetization-ready catalog that feels curated, original, and intentional rather than mass-produced.

Available sound categories:
- rain, river, thunder, fireplace, ocean_waves, soft_wind, night_forest, brown_noise

=== THEME BLACKOUT ===
These primary categories were used in the last 30 days. Avoid them as primary unless no alternative exists:
{list(blacked_out_themes)}

=== RECENT TITLES TO AVOID ===
{recent_titles_json}

=== RECENT SOUND COMBOS TO AVOID COPYING ===
{recent_combos_json}

=== VIDEO LENGTH ===
This video must be: {duration_label}
Include exactly "{duration_label}" in the title.

=== YOUTUBE TRENDING TITLES (keyword inspiration only, do not copy) ===
{json.dumps(trending_keywords[:10], indent=2)}

=== TOP PERFORMING VIDEOS ===
{top_performers_json}

=== LOW PERFORMING VIDEOS ===
{low_performers_json}

=== REQUIRED CREATIVE DIRECTION ===
Primary category MUST be: {suggested_primary}
Suggested scene location: {scene_hint}
Suggested secondary sound: {secondary_hint}
Brown noise rule: {brown_noise_rule}

Generate ONE high-quality, unique video idea.

=== CONTENT TIER ===
This upload is: {content_tier.upper()}
If FLAGSHIP, make it feel like a weekly hero asset: more cinematic, more specific, more memorable, and strong enough to create 3 Shorts from.
If STANDARD, keep it high quality but simpler and repeatable.

Hard rules:
- Do NOT repeat or closely paraphrase any recent title.
- Do NOT reuse the same sound combination as a recent video.
- Title must be scene-first, not sound-first.
- Title format: "[Specific Place/Event] | [Utility Keyword] | [Duration]"
- Good examples: "Rain on a Mountain Cabin Roof | Deep Sleep | 10 Hours", "Snowstorm Outside an Old Library | Fireplace Sleep | 8 Hours"
- Bad examples: "Gentle Rain and River Sounds for Deep Sleep", "Relaxing Sleep Sounds", "Brown Noise for Sleep"
- Title must be under 90 characters.
- Use 2-3 sound layers total.
- Keep it calm, cozy, dark, and suitable for sleep or focus.
- The first 30 seconds must feel premium immediately: gentle fade-in, clear sound identity, no jarring moments.
- Use the channel name exactly as "Midnight Cabin" when needed.
- Avoid promises like "no ads". Use "uninterrupted", "no vocals", "no sudden sounds", or "no mid-roll interruptions" instead.
- Do not make medical claims. Use soft phrasing such as "many listeners use this for..." or "can help create a steadier background..."
- Return ONLY valid JSON. No markdown, no explanation, no duplicate keys.

JSON structure (return exactly this, no extra fields outside it):
{{
  "theme": "...",
  "title": "...",
  "storyline": "2-3 immersive sentences in second person. Make the viewer feel inside this exact scene.",
  "unique_angle": "What makes this video meaningfully different from recent uploads?",
  "first_30_seconds": "What the viewer hears/sees immediately after clicking.",
  "retention_hook": "Why someone would keep this playing for hours.",
  "sound_layers": ["...", "..."],
  "visual": "specific, cinematic visual scene with lighting and location details",
  "thumbnail_text": "2-4 word emotional thumbnail phrase",
  "content_tier": "{content_tier}",
  "is_flagship": {str(is_flagship).lower()},
  "flagship_package": {{
    "hero_reason": "If flagship, why this deserves flagship treatment. If standard, say standard upload.",
    "shorts": [
      "Short idea 1: emotional POV",
      "Short idea 2: calming observation",
      "Short idea 3: save/use-case angle"
    ]
  }},
  "duration_minutes": {next_duration_minutes},
  "audio_strategy": {{
    "primary_category": "{suggested_primary}",
    "secondary_category": "...",
    "mood": "...",
    "intensity": "low/medium/high"
  }},
  "learning_reason": "..."
}}
"""

idea = None
try:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        temperature=0.95,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    print("RAW CLAUDE OUTPUT:")
    print(text)
    idea = safe_parse_json(text)
    if not idea:
        raise ValueError("Could not parse valid JSON from Claude output")
    print("Successfully parsed idea:", idea.get("title"))
except Exception as e:
    print("Claude idea generation failed, using fallback:", e)
    idea = None

if not idea:
    layer_list = [suggested_primary, secondary_hint]
    if include_brown_noise and "brown_noise" not in layer_list:
        layer_list.append("brown_noise")
    title_sound = suggested_primary.replace("_", " ").title()
    idea = {
        "theme": f"{scene_hint} {title_sound} Ambience",
        "title": f"{scene_hint} | {title_sound} Sleep | {duration_label}",
        "storyline": f"You are tucked inside the {scene_hint.lower()} while the outside world fades into a slow, steady hush. The sound stays soft and predictable, giving your mind one quiet place to rest.",
        "unique_angle": f"A specific {scene_hint.lower()} setting with a {suggested_primary.replace('_', ' ')}-first mix instead of a generic sleep sound loop.",
        "first_30_seconds": "A gentle fade-in, clear primary sound identity, and no sudden volume changes.",
        "retention_hook": "The mix stays stable and low-distraction for overnight listening or long focus sessions.",
        "sound_layers": layer_list[:3],
        "visual": f"dark cozy {scene_hint.lower()}, cinematic low light, no people, slow atmospheric movement",
        "thumbnail_text": scene_hint.split()[0].upper() + " CABIN",
        "content_tier": content_tier,
        "is_flagship": is_flagship,
        "flagship_package": {
            "hero_reason": "Weekly flagship concept" if is_flagship else "Standard upload",
            "shorts": [
                "Emotional POV of the room",
                "Soft observation about steady sound",
                "Save this for tonight angle",
            ],
        },
        "duration_minutes": next_duration_minutes,
        "audio_strategy": {
            "primary_category": suggested_primary,
            "secondary_category": secondary_hint,
            "mood": "calm",
            "intensity": "low",
        },
        "learning_reason": "Fallback idea that prioritizes a specific scene, a distinct sound mix, and low-distraction retention.",
    }

# Validate and save.
idea["created_at"] = datetime.now().isoformat()
idea["duration_minutes"] = next_duration_minutes
allowed_layers = set(CONTENT_BUCKETS)

layers = [l for l in idea.get("sound_layers", []) if l in allowed_layers]
if suggested_primary not in layers:
    layers.insert(0, suggested_primary)

# Brown noise is selective: keep it if primary, if explicitly allowed, or if the concept already depends on it.
if suggested_primary != "brown_noise" and not include_brown_noise:
    layers = [l for l in layers if l != "brown_noise"]
elif include_brown_noise and "brown_noise" not in layers and len(layers) < 3:
    layers.append("brown_noise")

# Avoid reusing an exact recent layer combination when possible.
combo = normalize_layers(layers)
if recent_layer_combos.get(combo, 0) > 0:
    alternatives = [x for x in SECONDARY_BY_PRIMARY.get(suggested_primary, []) if x not in layers]
    if alternatives:
        if len(layers) >= 2:
            layers[-1] = random.choice(alternatives)
        else:
            layers.append(random.choice(alternatives))

idea["sound_layers"] = layers[:3]

# Force primary category and basic metadata consistency.
idea.setdefault("audio_strategy", {})
idea["audio_strategy"]["primary_category"] = suggested_primary
if not idea["audio_strategy"].get("secondary_category"):
    idea["audio_strategy"]["secondary_category"] = next((l for l in idea["sound_layers"] if l != suggested_primary), "")

# Title guardrails: scene-first, unique, contains duration, under 90 chars.
title = str(idea.get("title", "")).strip()
if duration_label not in title:
    title = f"{title} | {duration_label}".strip(" |")
if normalize_title(title) in recent_titles or len(title) > 90 or "|" not in title:
    scene = pick_unused_scene(recent_scenes)
    utility = "Deep Sleep" if suggested_primary != "brown_noise" else "Focus Sound"
    title = f"{scene} | {utility} | {duration_label}"
idea["title"] = title[:90].rstrip(" |-")

idea.setdefault("storyline", "You are inside a quiet cabin as the outside world softens into a steady, calming soundscape.")
idea.setdefault("unique_angle", "A more specific scene and sound mix than a generic ambient loop.")
idea.setdefault("first_30_seconds", "Gentle fade-in, immediate atmosphere, and no sudden sounds.")
idea.setdefault("retention_hook", "Stable, low-distraction sound designed for long listening sessions.")
idea["content_tier"] = content_tier
idea["is_flagship"] = bool(is_flagship)
idea.setdefault("flagship_package", {
    "hero_reason": "Weekly flagship concept" if is_flagship else "Standard upload",
    "shorts": [
        "Emotional POV of the scene",
        "Soft credible observation about the sound",
        "Save this for tonight/use later angle",
    ],
})
idea.setdefault("thumbnail_text", extract_scene_from_title(idea["title"]).upper()[:22])

os.makedirs(PERSISTENT_DIR, exist_ok=True)
with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print("\nFinal idea saved:")
print(json.dumps(idea, indent=2))
