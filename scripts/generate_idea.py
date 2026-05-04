import json
import os
import re
from datetime import datetime

from anthropic import Anthropic

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(BASE_DIR, "video_history.json")
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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

used_primary = []

for item in recent_results:
    strategy = item.get("audio_strategy", {})
    primary = strategy.get("primary_category")
    if primary:
        used_primary.append(primary)

if used_primary:
    min_count = min([used_primary.count(c) for c in CONTENT_BUCKETS])
    least_used = [
        category for category in CONTENT_BUCKETS
        if used_primary.count(category) == min_count
    ]
    suggested_primary = least_used[0]
else:
    suggested_primary = "ocean_waves"

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

Past video performance:
{json.dumps(recent_results, indent=2)}

Suggested primary category for this video:
{suggested_primary}

Generate ONE high-quality, unique video idea.

Rules:
- Do NOT default to rain unless it is the suggested primary category.
- Rotate across rain, river, fireplace, ocean_waves, soft_wind, night_forest, and brown_noise.
- Use 2–3 sound layers that work well together.
- Always include brown_noise unless it conflicts with the theme.
- Keep it calm, cozy, dark, and suitable for sleep or focus.
- Avoid scary, chaotic, dramatic, or clickbait wording.
- Avoid repeating exact titles.
- Title must be SEO-friendly, under 90 characters, and include "10 Hours".

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

JSON structure:
{{
  "theme": "...",
  "title": "...",
  "sound_layers": ["brown_noise", "..."],
  "visual": "...",
  "duration_minutes": 600,
  "audio_strategy": {{
    "primary_category": "...",
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
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
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
        "title": f"10 Hours {suggested_primary.replace('_', ' ').title()} for Sleep & Focus",
        "sound_layers": ["brown_noise", suggested_primary],
        "visual": f"dark cozy {suggested_primary.replace('_', ' ')} ambience, no people",
        "duration_minutes": 600,
        "audio_strategy": {
            "primary_category": suggested_primary,
            "secondary_category": "brown_noise",
            "mood": "calm",
            "intensity": "low"
        },
        "learning_reason": "Fallback idea used because Claude API was unavailable."
    }

idea["created_at"] = datetime.now().isoformat()

allowed_layers = {
    "rain",
    "river",
    "thunder",
    "fireplace",
    "ocean_waves",
    "soft_wind",
    "night_forest",
    "brown_noise"
}

idea["sound_layers"] = [
    layer for layer in idea.get("sound_layers", [])
    if layer in allowed_layers
]

if not idea["sound_layers"]:
    idea["sound_layers"] = ["brown_noise", suggested_primary]

if "brown_noise" not in idea["sound_layers"]:
    idea["sound_layers"].insert(0, "brown_noise")

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))