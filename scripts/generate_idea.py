import json
import os
import re
from datetime import datetime

from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(BASE_DIR, "video_history.json")
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

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

Your job:
Generate ONE high-quality, unique video idea.

Important variety rules:
- Do NOT default to rain unless it is the suggested primary category.
- Rain can be used, but only occasionally.
- Rotate across rain, river, fireplace, ocean_waves, soft_wind, night_forest, and brown_noise.
- If recent videos used rain, choose a different main category.
- Only use rain in maximum 1 out of every 4 ideas.
- Explore non-rain ideas like ocean waves, fireplace sleep ambience, forest night, soft wind, river stream, and brown noise focus.
- Combine 2–3 sound layers that work well together.
- Keep the soundscape calm, cozy, dark, and suitable for sleep or focus.
- Avoid scary, chaotic, or dramatic themes.
- Avoid repeating exact titles.

High-performing keyword families:
- ocean waves for sleep
- fireplace sounds for sleep
- brown noise for focus
- river sounds for relaxation
- forest night ambience
- wind sounds for sleep
- rain sounds for sleep
- black screen sleep sounds
- deep sleep sounds no ads
- focus sounds no distractions

Title rules:
- Make the title SEO-friendly.
- Include a clear use case: sleep, focus, study, relaxation, or deep sleep.
- Include duration like "10 Hours".
- Keep title under 90 characters.
- Do not mention AI.
- Do not use clickbait.
- Do not use scary words.

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

Structure:
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

response = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt
)

text = response.output_text.strip()

print("RAW OUTPUT:")
print(text)

text = re.sub(r"```json|```", "", text).strip()

match = re.search(r"\{.*\}", text, re.DOTALL)

if not match:
    raise ValueError("No JSON found in model output")

idea = json.loads(match.group(0))
idea["created_at"] = datetime.now().isoformat()

# Safety cleanup
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

# Enforce suggested primary if model keeps overusing rain
primary = idea.get("audio_strategy", {}).get("primary_category")

if suggested_primary != "rain" and primary == "rain":
    idea["audio_strategy"]["primary_category"] = suggested_primary

    if suggested_primary not in idea["sound_layers"]:
        idea["sound_layers"] = ["brown_noise", suggested_primary]

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))