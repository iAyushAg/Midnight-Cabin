import json
import os
from datetime import datetime
from openai import OpenAI

client = OpenAI(api_key="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")

AVAILABLE_AUDIO = {
    "rain": [
        "rain_heavy.wav",
        "rain_light.wav",
        "rain_medium.wav",
        "rain_window_light.wav"
    ],
    "river": [
        "river_thunder_medium.mp3"
    ],
    "thunder": [
        "thunder_medium.wav"
    ]
}

prompt = f"""
You are the idea agent for a YouTube channel called Midnight Cabin.

The channel creates long sleep/focus soundscape videos.

Available audio categories:
{json.dumps(AVAILABLE_AUDIO, indent=2)}

Generate ONE fresh video idea.

Return ONLY valid JSON with this exact structure:
{{
  "theme": "...",
  "title": "...",
  "sound_layers": ["brown_noise", "..."],
  "visual": "...",
  "duration_minutes": 60,
  "audio_strategy": {{
    "primary_category": "...",
    "secondary_category": "...",
    "mood": "...",
    "intensity": "low/medium/high"
  }}
}}

Rules:
- Use only these sound layer names: brown_noise, rain, river, thunder, fireplace, ocean_waves, soft_wind, night_forest
- Prefer combinations that fit sleep, focus, study, relaxation
- Do not make scary titles
- Titles should be YouTube-friendly and under 75 characters
- Pick ideas suitable for dark, cozy, faceless ambient videos
"""
import re

response = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt
)

text = response.output_text.strip()

print("RAW OUTPUT:\n", text)

# Extract JSON safely
match = re.search(r"\{.*\}", text, re.DOTALL)

if not match:
    raise ValueError("No JSON found in model output")

json_text = match.group(0)

idea = json.loads(json_text)

idea["created_at"] = datetime.now().isoformat()

with open("current_idea.json", "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))