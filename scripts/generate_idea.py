import json
import os
import re
from datetime import datetime, timedelta

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

# ─────────────────────────────────────────────
# 1. LOAD HISTORY
# ─────────────────────────────────────────────
if os.path.exists(HISTORY_PATH):
    with open(HISTORY_PATH, "r") as f:
        history = json.load(f)
else:
    history = []

recent_results = history[-20:]

CONTENT_BUCKETS = [
    "river", "fireplace", "ocean_waves",
    "soft_wind", "night_forest", "brown_noise", "rain"
]

# ─────────────────────────────────────────────
# 2. THEME BLACKOUT — skip themes used in last 30 days
# ─────────────────────────────────────────────
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
    print("All themes blacked out — resetting blackout")
    available_buckets = CONTENT_BUCKETS

used_primary = []
for item in recent_results:
    primary = item.get("audio_strategy", {}).get("primary_category")
    if primary:
        used_primary.append(primary)

import random as _random

if used_primary:
    min_count = min(used_primary.count(c) for c in available_buckets)
    least_used = [c for c in available_buckets if used_primary.count(c) == min_count]
    # Shuffle least-used so we don't always pick the same one when counts are tied
    _random.shuffle(least_used)
    suggested_primary = least_used[0]
else:
    # No history — pick randomly so rain isn't always first
    suggested_primary = _random.choice(available_buckets)

# Hard rule — never pick the same category as the last video
last_primary = history[-1].get("audio_strategy", {}).get("primary_category") if history else None
if suggested_primary == last_primary and len(available_buckets) > 1:
    remaining = [b for b in available_buckets if b != last_primary]
    import random as _r
    suggested_primary = _r.choice(remaining)
    print(f"Avoided repeating last category ({last_primary}), switched to: {suggested_primary}")

print("Suggested primary category:", suggested_primary)

# ─────────────────────────────────────────────
# 3. VIDEO LENGTH — alternate between 8h and 10h
# ─────────────────────────────────────────────
last_duration = history[-1].get("duration_minutes", 480) if history else 480
next_duration_minutes = 600 if last_duration <= 480 else 480
duration_label = "10 Hours" if next_duration_minutes == 600 else "8 Hours"
print(f"Next video duration: {duration_label} ({next_duration_minutes} min)")

# ─────────────────────────────────────────────
# 4. YOUTUBE TREND DATA
# ─────────────────────────────────────────────
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
        f"{suggested_primary.replace('_', ' ')} sleep",
        "ambient sleep sounds",
        "brown noise focus",
    ]

    for seed in seed_terms[:3]:
        response = youtube.search().list(
            part="snippet",
            q=seed,
            type="video",
            order="viewCount",
            videoCategoryId="10",
            maxResults=5
        ).execute()

        for item in response.get("items", []):
            trending_keywords.append(item["snippet"]["title"])

    print("Trending titles found:", len(trending_keywords))

except Exception as e:
    print("YouTube trend fetch failed (non-fatal):", e)

# ─────────────────────────────────────────────
# 5. CHANNEL PERFORMANCE
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# 6. CALL CLAUDE
# ─────────────────────────────────────────────
prompt = f"""
You are the Idea Agent for a YouTube channel called Midnight Cabin.

The channel creates long sleep, relaxation, and focus soundscape videos.

Available sound categories:
- rain, river, thunder, fireplace, ocean_waves, soft_wind, night_forest, brown_noise

=== THEME BLACKOUT ===
These primary categories were used in the last 30 days — DO NOT use them as primary:
{list(blacked_out_themes)}

=== VIDEO LENGTH ===
This video must be: {duration_label}
Include "{duration_label}" in the title (not "10 Hours" if it's 8 Hours).

=== YOUTUBE TRENDING TITLES (for keyword inspiration) ===
{json.dumps(trending_keywords[:10], indent=2)}

=== TOP PERFORMING VIDEOS ===
{json.dumps([{{"title": v.get("title"), "views": v.get("performance", {{}}).get("views", 0)}} for v in top_performers], indent=2)}

=== LOW PERFORMING VIDEOS ===
{json.dumps([{{"title": v.get("title"), "views": v.get("performance", {{}}).get("views", 0)}} for v in low_performers], indent=2)}

=== SUGGESTED PRIMARY CATEGORY ===
{suggested_primary}

Generate ONE high-quality, unique video idea.

Rules:
- Primary category MUST be: {suggested_primary}
- Use 2-3 sound layers that work well together
- Always include brown_noise unless it conflicts
- Keep it calm, cozy, dark, suitable for sleep or focus
- Title must be SEO-friendly, under 90 characters, include "{duration_label}"
- Return ONLY valid JSON — no markdown, no explanation, no duplicate keys

JSON structure (return exactly this, no extra fields outside it):
{{
  "theme": "...",
  "title": "...",
  "sound_layers": ["brown_noise", "..."],
  "visual": "...",
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

def safe_parse_json(text):
    """Robustly extract and parse the first valid JSON object from text."""
    # Remove markdown fences
    text = re.sub(r"```json|```", "", text).strip()

    # Find the outermost {} block
    start = text.find("{")
    if start == -1:
        return None

    # Walk to find matching closing brace
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

    json_str = text[start:end + 1]

    # Fix common Claude mistakes:
    # 1. Remove duplicate keys by keeping last occurrence
    # 2. Fix trailing commas before }
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        # Try removing lines with obvious syntax errors
        lines = json_str.split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip orphaned lines that aren't valid JSON structure
            if stripped and not stripped.startswith('"') and stripped not in ["{", "}", "[", "]", ","]:
                if not any(stripped.startswith(c) for c in ['"', '{', '}', '[', ']']):
                    print(f"Skipping malformed line: {line}")
                    continue
            clean_lines.append(line)
        try:
            return json.loads("\n".join(clean_lines))
        except Exception:
            return None

idea = None

try:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        temperature=0.8,
        messages=[{"role": "user", "content": prompt}]
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
    idea = {
        "theme": f"{suggested_primary.replace('_', ' ').title()} Sleep Ambience",
        "title": f"{duration_label} {suggested_primary.replace('_', ' ').title()} for Sleep & Focus",
        "sound_layers": ["brown_noise", suggested_primary],
        "visual": f"dark cozy {suggested_primary.replace('_', ' ')} ambience, no people",
        "duration_minutes": next_duration_minutes,
        "audio_strategy": {
            "primary_category": suggested_primary,
            "secondary_category": "brown_noise",
            "mood": "calm",
            "intensity": "low"
        },
        "learning_reason": "Fallback idea — Claude API unavailable or returned unparseable JSON."
    }

# ─────────────────────────────────────────────
# 7. VALIDATE + SAVE
# ─────────────────────────────────────────────
idea["created_at"] = datetime.now().isoformat()
idea["duration_minutes"] = next_duration_minutes  # enforce regardless of Claude output

allowed_layers = {
    "rain", "river", "thunder", "fireplace",
    "ocean_waves", "soft_wind", "night_forest", "brown_noise"
}
idea["sound_layers"] = [l for l in idea.get("sound_layers", []) if l in allowed_layers]

if not idea["sound_layers"]:
    idea["sound_layers"] = ["brown_noise", suggested_primary]

if "brown_noise" not in idea["sound_layers"]:
    idea["sound_layers"].insert(0, "brown_noise")

os.makedirs(PERSISTENT_DIR, exist_ok=True)

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print("\nFinal idea saved:")
print(json.dumps(idea, indent=2))