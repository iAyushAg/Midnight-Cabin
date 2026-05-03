import json
import os
import re
from datetime import datetime
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(BASE_DIR, "video_history.json")
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

AVAILABLE_AUDIO = {
    "rain": [
        "rain_heavy.wav",
        "rain_light.wav",
        "rain_medium.wav",
        "rain_window_light.wav"
    ],
    "river": [
        "river_thunder_medium.wav"
    ],
    "thunder": [
        "thunder_medium.wav"
    ],
    "brown_noise": [
        "procedural_brown_noise"
    ]
}

if os.path.exists(HISTORY_PATH):
    with open(HISTORY_PATH, "r") as f:
        history = json.load(f)
else:
    history = []

recent_results = history[-20:]

prompt = f"""
You are the Idea Agent for a faceless YouTube channel called Midnight Cabin.

The channel creates long sleep, relaxation, and focus soundscape videos.

Available audio categories and files:
{json.dumps(AVAILABLE_AUDIO, indent=2)}

Past video performance:
{json.dumps(recent_results, indent=2)}

Your job:
Generate ONE fresh video idea using the available audio categories.

Use past performance to improve future ideas:
- Prefer themes, sound layers, and moods similar to higher-performing videos.
- Avoid repeating exact titles.
- Avoid themes similar to videos with low views.
- If there is not enough history yet, create a high-quality sleep/focus idea using rain, river, thunder, and brown_noise.
- Keep the idea calm, cozy, dark, and suitable for sleep or focus.

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

Return this exact JSON structure:
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
    "intensity": "low"
  }},
  "learning_reason": "Short explanation of why this idea was chosen based on available history."
}}

Rules:
- Allowed sound_layers only: brown_noise, rain, river, thunder, fireplace, ocean_waves, soft_wind, night_forest
- Use only sound layers that match available audio when possible.
- Titles must be YouTube-friendly and under 75 characters.
- Avoid scary wording.
- Avoid clickbait.
- Do not mention AI.
- Do not use people, faces, or characters in the visual.
- Visual should describe a dark cozy ambient scene.
"""

response = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt
)

text = response.output_text.strip()

print("RAW OUTPUT:")
print(text)

# Remove markdown if present
text = re.sub(r"```json|```", "", text).strip()

match = re.search(r"\{.*\}", text, re.DOTALL)

if not match:
    raise ValueError("No JSON found")

idea = json.loads(match.group(0))
idea["created_at"] = datetime.now().isoformat()

with open(IDEA_PATH, "w") as f:
    json.dump(idea, f, indent=2)

print(json.dumps(idea, indent=2))