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

Your job:
Generate ONE high-quality, unique video idea.

Guidelines:
- Combine 2–3 sound layers that work well together.
- Prefer calm, relaxing, dark, cozy themes.
- Avoid repetition of past titles.
- Avoid overly complex or chaotic combinations.
- Think like a top YouTube ambient channel.
- Use past performance to make better choices.
- If there is not enough performance data yet, create a strong sleep/focus idea.

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

Structure:
{{
  "theme": "...",
  "title": "...",
  "sound_layers": ["brown_noise", "..."],
  "visual": "...",
  "duration_minutes": 10,
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

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))