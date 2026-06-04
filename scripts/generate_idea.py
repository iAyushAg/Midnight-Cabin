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
    "soft_wind", "night_forest"
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
    # brown_noise removed from rotation — never use as primary or secondary
    return False


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
    
def repair_and_validate_idea(idea, fallback_context):
    """Ensure the final idea has a clean, predictable structure.

    Claude sometimes returns malformed or partially nested JSON.
    This function normalizes the recovered object before saving it.
    """
    if not isinstance(idea, dict):
        idea = {}

    suggested_primary = fallback_context["suggested_primary"]
    secondary_hint = fallback_context["secondary_hint"]
    scene_hint = fallback_context["scene_hint"]
    duration_label = fallback_context["duration_label"]
    next_duration_minutes = fallback_context["next_duration_minutes"]
    content_tier = fallback_context["content_tier"]
    is_flagship = fallback_context["is_flagship"]

    # If fields accidentally landed inside audio_strategy, pull them back out.
    audio_strategy = idea.get("audio_strategy", {})
    if not isinstance(audio_strategy, dict):
        audio_strategy = {}

    misplaced_top_level_fields = [
        "unique_angle",
        "first_30_seconds",
        "retention_hook",
        "storyline",
        "visual",
        "thumbnail_text",
        "learning_reason",
    ]

    for key in misplaced_top_level_fields:
        if not idea.get(key) and audio_strategy.get(key):
            idea[key] = audio_strategy.pop(key)

    # Normalize sound_layers
    raw_layers = idea.get("sound_layers", [])
    if not isinstance(raw_layers, list):
        raw_layers = []

    allowed_layers = set(CONTENT_BUCKETS)
    layers = [str(layer) for layer in raw_layers if str(layer) in allowed_layers]

    if suggested_primary not in layers:
        layers.insert(0, suggested_primary)

    secondary = audio_strategy.get("secondary_category") or secondary_hint
    if secondary in allowed_layers and secondary not in layers and len(layers) < 3:
        layers.append(secondary)

    idea["sound_layers"] = layers[:3]

    # Normalize audio strategy
    idea["audio_strategy"] = {
        "primary_category": suggested_primary,
        "secondary_category": next((l for l in idea["sound_layers"] if l != suggested_primary), secondary_hint),
        "mood": audio_strategy.get("mood", "calm"),
        "intensity": audio_strategy.get("intensity", "low"),
    }

    # Normalize title
    title = str(idea.get("title", "")).strip()
    # Accept emotional titles that don't use pipe separators — they're intentional.
    # Only reject if: empty, too long, or missing the duration label entirely.
    if not title or len(title) > 95 or duration_label not in title:
        utility = "Deep Sleep"
        sound_name = suggested_primary.replace("_", " ")
        title = f"Why your brain loves {sound_name} at night | {duration_label}"

    idea["title"] = title[:90].rstrip(" |-")

    # Required text fields
    idea["theme"] = str(idea.get("theme") or f"{scene_hint} {suggested_primary.replace('_', ' ').title()}").strip()

    idea["storyline"] = str(
        idea.get("storyline")
        or f"You are inside a quiet {scene_hint.lower()} as the outside world softens into a steady, calming soundscape."
    ).strip()

    idea["unique_angle"] = str(
        idea.get("unique_angle")
        or f"A specific {scene_hint.lower()} setting with a {suggested_primary.replace('_', ' ')}-first mix instead of a generic sleep loop."
    ).strip()

    idea["first_30_seconds"] = str(
        idea.get("first_30_seconds")
        or "A gentle fade-in, clear primary sound identity, and no sudden volume changes."
    ).strip()

    idea["retention_hook"] = str(
        idea.get("retention_hook")
        or "The mix stays stable and low-distraction for overnight listening or long focus sessions."
    ).strip()

    idea["visual"] = str(
        idea.get("visual")
        or f"dark cozy {scene_hint.lower()}, cinematic low light, no people, slow atmospheric movement"
    ).strip()

    idea["thumbnail_text"] = str(
        idea.get("thumbnail_text")
        or extract_scene_from_title(idea["title"]).upper()[:22]
    ).strip()

    idea["learning_reason"] = str(
        idea.get("learning_reason")
        or "Generated to improve variety while staying inside the Midnight Cabin sleep/focus identity."
    ).strip()

    # Flagship package repair
    flagship_package = idea.get("flagship_package", {})
    if not isinstance(flagship_package, dict):
        flagship_package = {}

    shorts = flagship_package.get("shorts", [])
    if not isinstance(shorts, list):
        shorts = []

    while len(shorts) < 3:
        shorts.append("Save this soundscape for tonight.")

    idea["flagship_package"] = {
        "hero_reason": str(
            flagship_package.get("hero_reason")
            or ("Weekly flagship concept" if is_flagship else "Standard upload")
        ),
        "shorts": [str(s) for s in shorts[:3]],
    }

    idea["duration_minutes"] = next_duration_minutes
    idea["content_tier"] = content_tier
    idea["is_flagship"] = bool(is_flagship)
    idea["created_at"] = datetime.now().isoformat()

    return idea


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

# ─────────────────────────────────────────────
# STRICT ROUND-ROBIN NICHE ROTATION
# Tracks which niche was used per pipeline RUN (not per upload record).
# Each run writes one entry to niche_rotation.json regardless of how many
# upload types (main/adhd/dark_screen/study) are produced from that run.
# This prevents rain from dominating just because it got 4 history records
# in one cycle.
# ─────────────────────────────────────────────
ROTATION_FILE = os.path.join(PERSISTENT_DIR, "niche_rotation.json")

def load_rotation():
    try:
        if os.path.exists(ROTATION_FILE):
            with open(ROTATION_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"queue": [], "used": []}

def save_rotation(data):
    with open(ROTATION_FILE, "w") as f:
        json.dump(data, f, indent=2)

rotation = load_rotation()
queue = rotation.get("queue", [])

# Rebuild queue whenever it runs dry — shuffle for variety
if not queue:
    new_queue = CONTENT_BUCKETS[:]
    random.shuffle(new_queue)
    # Never start with the same niche that just ran
    last_used = rotation.get("used", [])
    last_primary_used = last_used[-1] if last_used else None
    if new_queue and new_queue[0] == last_primary_used and len(new_queue) > 1:
        swap_idx = random.randint(1, len(new_queue) - 1)
        new_queue[0], new_queue[swap_idx] = new_queue[swap_idx], new_queue[0]
    queue = new_queue
    print(f"Rotation queue exhausted — rebuilt: {queue}")

suggested_primary = queue.pop(0)

# Save updated rotation state
used_log = rotation.get("used", [])
used_log.append(suggested_primary)
used_log = used_log[-20:]  # keep last 20 only
save_rotation({"queue": queue, "used": used_log})

blacked_out_themes = set()  # kept for prompt context only — no longer drives selection
print(f"Niche rotation selected: {suggested_primary}")
print(f"Remaining in queue: {queue}")

include_brown_noise = should_use_brown_noise(suggested_primary, recent_results)
scene_hint = pick_unused_scene(recent_scenes)
secondary_hint = random.choice(SECONDARY_BY_PRIMARY.get(suggested_primary, ["soft_wind"]))

print("Suggested primary category:", suggested_primary)
print("Scene hint:", scene_hint)
print("Include brown noise:", include_brown_noise)
print("Content tier:", content_tier)

# Video length: 8 hours drives 8x the watch time per view toward YPP (4,000 hr threshold).
# Flagship videos get 10 hours for maximum watch time. Standard = 8 hours.
next_duration_minutes = 600 if is_flagship else 480
duration_label = "10 Hours" if next_duration_minutes >= 600 else "8 Hours"
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

# brown_noise removed from all content — not used as primary or secondary layer

prompt = f"""
You are the Idea Agent for a YouTube channel called Midnight Cabin.

The channel creates long sleep, relaxation, and focus soundscape videos. The goal is to build a monetization-ready catalog that feels curated, original, and intentional rather than mass-produced.

Available sound categories:
- rain, river, thunder, fireplace, ocean_waves, soft_wind, night_forest

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
Note: brown_noise is NOT used on this channel. Never include it in sound_layers.

Generate ONE high-quality, unique video idea.

=== CONTENT TIER ===
This upload is: {content_tier.upper()}
If FLAGSHIP, make it feel like a weekly hero asset: more cinematic, more specific, more memorable, and strong enough to create 3 Shorts from.
If STANDARD, keep it high quality but simpler and repeatable.

CRITICAL — This channel has under 100 subscribers. YouTube will NOT recommend it.
The ONLY path to views is: (1) search traffic from emotionally specific queries, and
(2) Shorts virality from titles that feel personally written about the viewer.

TITLE RULES (the most important part — read carefully):
The channel's top-performing video is "Why your brain loves rain at night" — this
outsperforms all other videos by 3-10x. Study this pattern. Every title must feel like
it was written about the viewer specifically, not about the sound.

PSYCHOLOGICAL TITLE FORMULA — choose ONE of these three patterns:
  Pattern A — "Why your brain [does X] when [sound] plays | {duration_label}"
  Pattern B — "For people who [specific relatable situation] | {duration_label} | [sound]"
  Pattern C — "The [sound] that [emotional outcome] | {duration_label} | No music"

GOOD title examples (these patterns):
- "Why your brain finally quiets down when rain plays | {duration_label}"
- "For people who can't sleep without something playing | {duration_label} | Rain"
- "For people whose brain won't stop replaying conversations at 3am | {duration_label}"
- "The rain sound that makes your body think it's safe | {duration_label}"
- "The fireplace sound that feels like someone is home | {duration_label}"
- "Why ocean waves are the oldest sleep signal your brain knows | {duration_label}"
- "What happens to your brain when a river plays all night | {duration_label}"

BAD titles (commodity — never use these patterns):
- "Rain Sounds for Sleeping | 8 Hours | No Music No Talking"  ← generic utility label
- "Fireplace Crackling for Sleep | 8 Hours"  ← zero emotional pull
- "Midnight Cabin Ambience | 10 Hours"  ← branding over emotion

Rules:
- Under 90 characters. Include "{duration_label}" exactly.
- Must contain the sound name (rain/fireplace/ocean/river/wind/forest/thunder)
- Must feel like it was written about a specific person at a specific emotional moment
- Do NOT repeat any recent title.
- If flagship: go deeper — more specific emotional situation, more curiosity pull

THUMBNAIL TEXT: A 2-4 word EMOTIONAL PHRASE (not just the sound name).
- GOOD: "BRAIN FINALLY QUIET", "3AM THOUGHTS", "FEELS LIKE SAFE", "ANXIETY OFF"
- BAD: "MIDNIGHT CABIN", "DEEP SLEEP", "8 HOURS"

Other rules:
- Use 2-3 sound layers total
- No medical claims — use "many listeners find..." or "can help create..."
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
    title_sound = suggested_primary.replace("_", " ").title()
    _fallback_titles = {
        "rain":         f"Why your brain loves rain playing all night | {duration_label}",
        "river":        f"Why a river playing all night quiets a loud brain | {duration_label}",
        "fireplace":    f"Why a crackling fire feels like someone is home | {duration_label}",
        "ocean_waves":  f"Why ocean waves are the oldest sleep signal your brain knows | {duration_label}",
        "soft_wind":    f"For people who need something playing to fall asleep | {duration_label} | Wind",
        "night_forest": f"Why forest sounds at night feel like nothing needs you | {duration_label}",
        "thunder":      f"Why thunderstorms feel like permission to stop doing things | {duration_label}",
    }
    _fallback_thumbs = {
        "rain": "RAIN SOUNDS", "river": "RIVER SOUNDS", "fireplace": "FIREPLACE",
        "ocean_waves": "OCEAN WAVES", "soft_wind": "WIND SOUNDS",
        "night_forest": "FOREST NIGHT", "thunder": "THUNDERSTORM",
    }
    idea = {
        "theme": f"{title_sound} Sleep Sounds",
        "title": _fallback_titles.get(suggested_primary, f"{title_sound} Sounds for Sleep | {duration_label} | No Music"),
        "storyline": f"Steady {suggested_primary.replace('_', ' ')} sounds play continuously for {duration_label}. No music, no talking, no sudden changes.",
        "unique_angle": f"Targets the search query '{suggested_primary.replace('_', ' ')} sounds for sleeping {duration_label.lower()}'.",
        "first_30_seconds": "Immediate fade-in of the primary sound — no intro, no music, just the sound.",
        "retention_hook": "Consistent, continuous audio with no sudden changes, safe for overnight playback.",
        "sound_layers": layer_list[:3],
        "visual": f"dark cozy cabin interior, {suggested_primary.replace('_', ' ')} visible outside window, warm amber light, no people",
        "thumbnail_text": _fallback_thumbs.get(suggested_primary, title_sound.upper()),
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

# ─────────────────────────────────────────────
# REPAIR, VALIDATE, AND SAVE
# ─────────────────────────────────────────────
fallback_context = {
    "suggested_primary": suggested_primary,
    "secondary_hint": secondary_hint,
    "scene_hint": scene_hint,
    "duration_label": duration_label,
    "next_duration_minutes": next_duration_minutes,
    "content_tier": content_tier,
    "is_flagship": is_flagship,
}

idea = repair_and_validate_idea(idea, fallback_context)

# Avoid reusing exact recent layer combination when possible.
combo = normalize_layers(idea.get("sound_layers", []))
if recent_layer_combos.get(combo, 0) > 0:
    layers = idea.get("sound_layers", [])
    alternatives = [
        x for x in SECONDARY_BY_PRIMARY.get(suggested_primary, [])
        if x not in layers
    ]

    if alternatives:
        if len(layers) >= 2:
            layers[-1] = random.choice(alternatives)
        else:
            layers.append(random.choice(alternatives))

        idea["sound_layers"] = layers[:3]
        idea["audio_strategy"]["secondary_category"] = next(
            (l for l in idea["sound_layers"] if l != suggested_primary),
            secondary_hint
        )

# Final title uniqueness guard
title = str(idea.get("title", "")).strip()
if normalize_title(title) in recent_titles:
    sound_name = suggested_primary.replace("_", " ")
    emotional_fallbacks = [
        f"Why your brain finally rests when {sound_name} plays | {duration_label}",
        f"For people whose brain won't stop at night | {duration_label} | {sound_name.title()}",
        f"What {sound_name} does to a busy brain after midnight | {duration_label}",
    ]
    import hashlib as _hs
    idx = int(_hs.md5(title.encode()).hexdigest(), 16) % len(emotional_fallbacks)
    idea["title"] = emotional_fallbacks[idx][:90].rstrip(" |-")

os.makedirs(PERSISTENT_DIR, exist_ok=True)

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print("\nFinal idea saved:")
print(json.dumps(idea, indent=2))

# Verify saved JSON can be loaded cleanly.
with open(IDEA_PATH, "r") as f:
    verified = json.load(f)

required_fields = [
    "theme",
    "title",
    "storyline",
    "unique_angle",
    "first_30_seconds",
    "retention_hook",
    "sound_layers",
    "visual",
    "thumbnail_text",
    "duration_minutes",
    "audio_strategy",
    "learning_reason",
]

missing = [field for field in required_fields if field not in verified]
if missing:
    raise RuntimeError(f"Final idea missing required fields: {missing}")

print("Final idea JSON verified successfully")