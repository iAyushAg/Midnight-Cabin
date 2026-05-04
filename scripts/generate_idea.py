import json
import os
import re
from datetime import datetime, timedelta

from anthropic import Anthropic
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(BASE_DIR, "video_history.json")
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

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
    "rain",
    "river",
    "fireplace",
    "ocean_waves",
    "soft_wind",
    "night_forest",
    "brown_noise"
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

# Pick least-used among available
used_primary = []
for item in recent_results:
    strategy = item.get("audio_strategy", {})
    primary = strategy.get("primary_category")
    if primary:
        used_primary.append(primary)

if used_primary:
    min_count = min(used_primary.count(c) for c in available_buckets)
    least_used = [c for c in available_buckets if used_primary.count(c) == min_count]
    suggested_primary = least_used[0]
else:
    suggested_primary = available_buckets[0]

print("Suggested primary category:", suggested_primary)

# ─────────────────────────────────────────────
# 3. VIDEO LENGTH — alternate between 1h and 3h
#    Use 3h if last video was 1h, else 1h
# ─────────────────────────────────────────────
last_duration = history[-1].get("duration_minutes", 60) if history else 60
next_duration_minutes = 180 if last_duration <= 60 else 60
duration_label = "3 Hours" if next_duration_minutes == 180 else "1 Hour"

print(f"Next video duration: {duration_label} ({next_duration_minutes} min)")

# ─────────────────────────────────────────────
# 4. YOUTUBE TREND DATA — pull high-value search keywords
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
        "relaxing sounds for sleep",
        "brown noise focus",
        "nature sounds relaxation"
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
            title = item["snippet"]["title"]
            trending_keywords.append(title)

    print("Trending titles found:", len(trending_keywords))

except Exception as e:
    print("YouTube trend fetch failed (non-fatal):", e)

# ─────────────────────────────────────────────
# 5. CHANNEL PERFORMANCE — best/worst videos
# ─────────────────────────────────────────────
top_performers = []
low_performers = []

if history:
    scored = [
        (v, v.get("performance", {}).get("views", 0))
        for v in history
        if v.get("performance", {}).get("views", 0) > 0
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_performers = [v[0] for v in scored[:3]]
    low_performers = [v[0] for v in scored[-3:] if v[1] > 0]

# ─────────────────────────────────────────────
# 6. BUILD PROMPT & CALL CLAUDE
# ─────────────────────────────────────────────
prompt = f"""
You are the Idea Agent for a YouTube channel called Midnight Cabin.

The channel creates long sleep, relaxation, and focus soundscape videos.

Available sound categories:
- rain
- river
- thunder
- fireplace
- ocean_waves
- soft_wind
- night_forest
- brown_noise

=== THEME BLACKOUT ===
These primary categories were used in the last 30 days — DO NOT use them as primary:
{list(blacked_out_themes)}

=== VIDEO LENGTH ===
This video must be: {duration_label}
Include "{duration_label}" in the title (not "10 Hours").

=== YOUTUBE TRENDING TITLES (for keyword inspiration) ===
{json.dumps(trending_keywords[:10], indent=2)}
Use these to understand what keywords and phrasing are working right now.
Do NOT copy titles directly — extract the SEO patterns and apply them freshly.

=== TOP PERFORMING VIDEOS (themes/styles to lean into) ===
{json.dumps([{{"title": v.get("title"), "theme": v.get("theme"), "views": v.get("performance", {{}}).get("views", 0)}} for v in top_performers], indent=2)}

=== LOW PERFORMING VIDEOS (themes/styles to avoid) ===
{json.dumps([{{"title": v.get("title"), "theme": v.get("theme"), "views": v.get("performance", {{}}).get("views", 0)}} for v in low_performers], indent=2)}

=== SUGGESTED PRIMARY CATEGORY ===
{suggested_primary}

Generate ONE high-quality, unique video idea.

Rules:
- Primary category MUST be: {suggested_primary}
- Do NOT use any blacked-out categories as primary.
- Use 2–3 sound layers that work well together.
- Always include brown_noise unless it conflicts with the theme.
- Keep it calm, cozy, dark, suitable for sleep or focus.
- Avoid scary, chaotic, dramatic, or clickbait wording.
- Avoid repeating exact titles from history.
- Title must be SEO-friendly, under 90 characters, and include "{duration_label}".
- Use trending keyword patterns where they naturally fit.

Return ONLY valid JSON. No markdown. No explanations.

JSON structure:
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

try:
    message = client.messages.create(
        model="claude-3-5-haiku-latest",
        max_tokens=700,
        temperature=0.8,
        messages=[{"role": "user", "content": prompt}]
    )

    text = message.content[0].text.strip()
    print("RAW CLAUDE OUTPUT:")
    print(text)

    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON found in Claude output")

    idea = json.loads(match.group(0))

except Exception as e:
    print("Claude idea generation failed, using fallback:", e)
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
        "learning_reason": "Fallback idea used because Claude API was unavailable."
    }

idea["created_at"] = datetime.now().isoformat()
idea["duration_minutes"] = next_duration_minutes  # enforce regardless of Claude output

# Validate sound layers
allowed_layers = {
    "rain", "river", "thunder", "fireplace",
    "ocean_waves", "soft_wind", "night_forest", "brown_noise"
}
idea["sound_layers"] = [l for l in idea.get("sound_layers", []) if l in allowed_layers]

if not idea["sound_layers"]:
    idea["sound_layers"] = ["brown_noise", suggested_primary]

if "brown_noise" not in idea["sound_layers"]:
    idea["sound_layers"].insert(0, "brown_noise")

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))
