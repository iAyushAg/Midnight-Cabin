#!/usr/bin/env python3
"""
generate_short_idea.py — Dedicated idea generator for Shorts

Completely independent from generate_idea.py.
Reads/writes its own files — never touches:
  - current_idea.json       (main pipeline)
  - niche_rotation.json     (main pipeline)
  - video_history.json      (main pipeline reads this; we read it too for anti-repeat but never write it)

Writes:
  - $PERSISTENT_DIR/short_idea.json           — this Short's idea
  - $PERSISTENT_DIR/short_niche_rotation.json — Short's own rotation state
  - $PERSISTENT_DIR/short_used_hooks.json     — hook dedup log

The idea schema is a short-specific subset of the main idea schema —
only the fields generate_short.py and generate_short_audio.py actually need.
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path
from collections import Counter

BASE_DIR       = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))

# Short pipeline owns these files exclusively
SHORT_IDEA_PATH     = Path(os.environ.get("SHORT_IDEA_PATH",
                           str(PERSISTENT_DIR / "short_idea.json")))
SHORT_ROTATION_FILE = Path(os.environ.get("SHORT_ROTATION_FILE",
                           str(PERSISTENT_DIR / "short_niche_rotation.json")))
SHORT_HOOKS_LOG     = PERSISTENT_DIR / "short_used_hooks.json"

# Read-only reference to main history for anti-repeat (never written)
HISTORY_PATH = PERSISTENT_DIR / "video_history.json"

PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# ANTHROPIC CLIENT
# ─────────────────────────────────────────────
from anthropic import Anthropic
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ─────────────────────────────────────────────
# NICHES + SECONDARY LAYERS
# ─────────────────────────────────────────────
NICHES = ["rain", "river", "thunder", "fireplace", "ocean_waves",
          "soft_wind", "night_forest", "brown_noise"]

SECONDARY_BY_PRIMARY = {
    "rain":         ["soft_wind", "thunder", "river"],
    "river":        ["rain", "soft_wind", "night_forest"],
    "thunder":      ["rain", "fireplace"],
    "fireplace":    ["soft_wind", "rain", "night_forest"],
    "ocean_waves":  ["soft_wind", "rain", "thunder"],
    "soft_wind":    ["night_forest", "rain", "river"],
    "night_forest": ["soft_wind", "river", "fireplace"],
    "brown_noise":  ["rain", "soft_wind"],
}

DURATION_OPTIONS = [480, 480, 480, 600, 600, 720]  # minutes — weighted toward 8h

# ─────────────────────────────────────────────
# SHORT'S OWN NICHE ROTATION
# Completely separate from the main pipeline's rotation.
# Rotates through all 8 niches before repeating.
# ─────────────────────────────────────────────
def load_short_rotation():
    try:
        if SHORT_ROTATION_FILE.exists():
            return json.loads(SHORT_ROTATION_FILE.read_text())
    except Exception:
        pass
    return {"queue": [], "used": []}

def save_short_rotation(data):
    SHORT_ROTATION_FILE.write_text(json.dumps(data, indent=2))

rotation = load_short_rotation()
queue = rotation.get("queue", [])

if not queue:
    new_queue = NICHES[:]
    random.shuffle(new_queue)
    last_used = rotation.get("used", [])
    last = last_used[-1] if last_used else None
    if new_queue and new_queue[0] == last and len(new_queue) > 1:
        swap = random.randint(1, len(new_queue) - 1)
        new_queue[0], new_queue[swap] = new_queue[swap], new_queue[0]
    queue = new_queue
    print(f"Short rotation queue rebuilt: {queue}")

primary = queue.pop(0)
used_log = rotation.get("used", [])
used_log.append(primary)
save_short_rotation({"queue": queue, "used": used_log[-20:]})
print(f"Short niche selected: {primary} | Remaining: {queue}")

secondary = random.choice(SECONDARY_BY_PRIMARY.get(primary, ["soft_wind"]))
duration_minutes = random.choice(DURATION_OPTIONS)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"

# ─────────────────────────────────────────────
# ANTI-REPEAT — read recent short ideas and main history
# ─────────────────────────────────────────────
recent_short_titles = set()
recent_short_hooks  = set()

# Load last 10 short ideas
for i in range(1, 11):
    past = PERSISTENT_DIR / f"short_idea_{i}.json"
    if past.exists():
        try:
            d = json.loads(past.read_text())
            t = d.get("title", "")
            h = d.get("hook_text", "")
            if t: recent_short_titles.add(t.lower().strip())
            if h: recent_short_hooks.add(h.lower().strip())
        except Exception:
            pass

# Also check the short hooks log
try:
    if SHORT_HOOKS_LOG.exists():
        hooks_data = json.loads(SHORT_HOOKS_LOG.read_text())
        for niche_hooks in hooks_data.values():
            recent_short_hooks.update(h.lower() for h in niche_hooks[-10:])
except Exception:
    pass

recent_titles_str = (
    "\nAvoid these recent Short titles:\n" +
    "\n".join(f"- {t}" for t in list(recent_short_titles)[:8])
) if recent_short_titles else ""

recent_hooks_str = (
    "\nAvoid these recent hooks:\n" +
    "\n".join(f"- {h}" for h in list(recent_short_hooks)[:10])
) if recent_short_hooks else ""

# ─────────────────────────────────────────────
# SCENE LOCATIONS — Short-specific
# More intimate, more specific than main pipeline scenes
# ─────────────────────────────────────────────
SHORT_SCENES = {
    "rain": [
        "rain on the window at 2am",
        "rain on the roof of a mountain hut",
        "the window beside your bed during a night storm",
        "a cabin porch in the middle of a downpour",
        "rain on the skylight of a dark bedroom",
    ],
    "fireplace": [
        "a fireplace in an old stone cabin",
        "the fire going while the house is quiet",
        "the last fire of winter in a dark room",
        "a wood stove in a remote mountain lodge",
        "firelight in a room where no one is awake",
    ],
    "river": [
        "a river behind a forest cabin at midnight",
        "the sound of water you can hear from your bed",
        "a stream running under an old wooden bridge",
        "the river that runs through the valley at 3am",
        "whitewater in a quiet forest clearing",
    ],
    "ocean_waves": [
        "waves on a dark coastline at midnight",
        "the sound of the sea through an open window",
        "waves on rocks below a cliffside cabin",
        "the ocean at the hour before sunrise",
        "a stormy sea you can hear but not see",
    ],
    "soft_wind": [
        "wind through pine trees at midnight",
        "a forest at 2am when the wind is low",
        "the sound of wind that asks nothing of you",
        "a quiet meadow where only the grass moves",
        "wind through an open window late at night",
    ],
    "night_forest": [
        "a dark forest path at midnight",
        "the forest floor where nothing moves quickly",
        "a clearing in the trees where the sky is visible",
        "deep forest with only small sounds",
        "the edge of the forest where the cabin light ends",
    ],
    "brown_noise": [
        "a dark study where the rain is heavy outside",
        "the room where you finally got things done",
        "late night with something steady playing",
        "the frequency that quiets a loud brain",
        "a room where the thoughts slow down",
    ],
    "thunder": [
        "the cabin window during a violent storm",
        "thunder that shakes the walls at 2am",
        "a storm so heavy you can see lightning",
        "the moment a thunderstorm fully arrives",
        "inside during the storm you can hear from miles away",
    ],
}

scene = random.choice(SHORT_SCENES.get(primary, [f"a quiet {primary} night"]))

# ─────────────────────────────────────────────
# GENERATE IDEA VIA CLAUDE
# ─────────────────────────────────────────────
print(f"Calling Claude for Short idea: {primary} / {scene}")

prompt = f"""You are generating a YouTube Short concept for @midnightcabins — a sleep/focus ambient channel.

The channel's proven formula: "Why your brain loves rain at night" outperforms
"Rain sounds for sleep" by 3-10x. Titles must describe the viewer's internal state,
not the sound.

Niche: {primary.replace("_", " ")}
Scene: {scene}
Secondary sound: {secondary.replace("_", " ")}
Sound layers: [{primary}, {secondary}]
Duration of full video this Short promotes: {duration_label}{recent_titles_str}{recent_hooks_str}

Generate a Short concept with these exact fields:

TITLE (for YouTube upload):
- Uses one of these patterns:
  A) "Why your brain [does X] when [sound] plays | {duration_label}"
  B) "For people who [specific 2am situation] | {duration_label} | [sound]"
  C) "The [sound] that [emotional outcome] | {duration_label}"
- Under 85 characters
- Must contain the sound name
- Must feel written about the viewer, not about the sound

HOOK_TEXT (shown on screen in the Short, max 5 words, no emojis, no punctuation except apostrophes):
- Creates immediate emotional recognition
- Makes the viewer think "that's exactly me"
- NOT a scene description — an internal state

VOICEOVER (spoken, max 35 words):
- Warm, specific, like a friend at midnight
- Must contain the word "your"
- Must end with exactly "Save this for tonight." OR "Save this for 3am."
- No wellness-brand language

THEME (3-5 words, atmospheric):
- Describes the scene, not the sound

Return ONLY this JSON, no markdown:
{{
  "title": "...",
  "hook_text": "...",
  "voiceover": "...",
  "theme": "...",
  "sound_layers": ["{primary}", "{secondary}"],
  "audio_strategy": {{
    "primary_category": "{primary}",
    "secondary_category": "{secondary}",
    "mood": "calm",
    "intensity": "low"
  }},
  "duration_minutes": {duration_minutes},
  "thumbnail_text": "3-4 word emotional phrase in caps e.g. BRAIN FINALLY QUIET"
}}"""

idea = None
try:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        temperature=0.9,
        messages=[{"role": "user", "content": prompt}]
    )
    import re
    text = re.sub(r"```json|```", "", response.content[0].text).strip()
    idea = json.loads(text)
    print(f"Claude idea: {idea.get('title', '?')[:70]}")
except Exception as e:
    print(f"Claude idea generation failed: {e} — using fallback")

# ─────────────────────────────────────────────
# FALLBACK IDEA
# ─────────────────────────────────────────────
FALLBACK_TITLES = {
    "rain":         f"Why your brain loves rain playing all night | {duration_label}",
    "river":        f"Why a river at midnight quiets a loud brain | {duration_label}",
    "fireplace":    f"Why a fire feels like someone is home | {duration_label}",
    "ocean_waves":  f"Why ocean waves are your brain's oldest sleep signal | {duration_label}",
    "soft_wind":    f"For people who need something playing to fall asleep | {duration_label} | Wind",
    "night_forest": f"Why forest sounds feel like nothing needs you | {duration_label}",
    "brown_noise":  f"Why your brain stops scanning when brown noise plays | {duration_label}",
    "thunder":      f"Why thunderstorms feel like permission to stop | {duration_label}",
}
FALLBACK_HOOKS = {
    "rain":         "your brain finally stopped",
    "river":        "the overthinking just stopped",
    "fireplace":    "you have nowhere to be",
    "ocean_waves":  "your body just exhaled",
    "soft_wind":    "nothing needs you right now",
    "night_forest": "the whole world got quiet",
    "brown_noise":  "your brain stopped scanning",
    "thunder":      "you feel cozy and safe",
}
FALLBACK_VOICEOVERS = {
    "rain":         "You know that feeling when the rain starts and your whole body just exhales? That is what this is. Save this for tonight.",
    "river":        "A river does not ask anything of you. It just keeps moving, and your brain finds something to follow that is not your own thoughts. Save this for tonight.",
    "fireplace":    "There is something about a fire that makes your brain think someone is home and you are safe. Save this for tonight.",
    "ocean_waves":  "The ocean has been doing this since before you were born. Arrive, fade, return. Your brain recognises it before you do. Save this for tonight.",
    "soft_wind":    "Wind is the sound of nothing needing you right now. Your nervous system knows the difference. Save this for tonight.",
    "night_forest": "The forest is never completely silent. But nothing in it is demanding your attention. That is what makes it feel safe. Save this for tonight.",
    "brown_noise":  "Your brain is always scanning for threats. Brown noise gives it something consistent to latch onto so it stops. Save this for 3am.",
    "thunder":      "A storm this heavy makes the inside feel even safer. Your body decides you are protected before you think it. Save this for tonight.",
}
FALLBACK_THEMES = {
    "rain":         "Rain on cabin window",
    "river":        "River at midnight",
    "fireplace":    "Fire in the dark",
    "ocean_waves":  "Waves on dark coast",
    "soft_wind":    "Wind through pine trees",
    "night_forest": "Deep forest midnight",
    "brown_noise":  "Dark study late night",
    "thunder":      "Storm on cabin windows",
}

if not idea or not all(k in idea for k in ["title", "hook_text", "voiceover", "theme"]):
    print("Using fallback idea")
    idea = {
        "title":          FALLBACK_TITLES[primary],
        "hook_text":      FALLBACK_HOOKS[primary],
        "voiceover":      FALLBACK_VOICEOVERS[primary],
        "theme":          FALLBACK_THEMES[primary],
        "sound_layers":   [primary, secondary],
        "audio_strategy": {
            "primary_category":   primary,
            "secondary_category": secondary,
            "mood":               "calm",
            "intensity":          "low",
        },
        "duration_minutes": duration_minutes,
        "thumbnail_text": "BRAIN FINALLY QUIET",
    }

# ─────────────────────────────────────────────
# ENRICH IDEA WITH FIELDS generate_short.py NEEDS
# ─────────────────────────────────────────────
idea.setdefault("sound_layers",   [primary, secondary])
idea.setdefault("audio_strategy", {
    "primary_category":   primary,
    "secondary_category": secondary,
    "mood":               "calm",
    "intensity":          "low",
})
idea.setdefault("duration_minutes", duration_minutes)
idea.setdefault("thumbnail_text",  "BRAIN FINALLY QUIET")
idea["is_flagship"]    = False
idea["content_tier"]   = "standard"
idea["flagship_package"] = {"shorts": [], "hero_reason": "Short-only idea"}
idea["storyline"]      = idea.get("theme", scene)
idea["unique_angle"]   = f"Short-native idea for {primary} — not derived from a long-form video"
idea["visual"]         = f"dark {primary} night, cabin atmosphere, no people"
idea["created_at"]     = datetime.now().isoformat()
idea["pipeline"]       = "short_only"  # marker so other scripts can detect this

# ─────────────────────────────────────────────
# SAVE SHORT'S OWN IDEA
# ─────────────────────────────────────────────
SHORT_IDEA_PATH.parent.mkdir(parents=True, exist_ok=True)
SHORT_IDEA_PATH.write_text(json.dumps(idea, indent=2))
print(f"Short idea saved: {SHORT_IDEA_PATH}")
print(f"  Title:    {idea['title'][:70]}")
print(f"  Hook:     {idea['hook_text']}")
print(f"  Niche:    {primary}")

# Archive last 10 short ideas for anti-repeat
import shutil
for i in range(9, 0, -1):
    src = PERSISTENT_DIR / f"short_idea_{i}.json"
    dst = PERSISTENT_DIR / f"short_idea_{i+1}.json"
    if src.exists():
        shutil.copy(src, dst)
if SHORT_IDEA_PATH.exists():
    shutil.copy(SHORT_IDEA_PATH, PERSISTENT_DIR / "short_idea_1.json")

# Update hooks log
try:
    hooks_data = {}
    if SHORT_HOOKS_LOG.exists():
        hooks_data = json.loads(SHORT_HOOKS_LOG.read_text())
    niche_hooks = hooks_data.get(primary, [])
    hook = idea.get("hook_text", "")
    if hook and hook not in niche_hooks:
        niche_hooks.append(hook)
    hooks_data[primary] = niche_hooks[-20:]
    SHORT_HOOKS_LOG.write_text(json.dumps(hooks_data, indent=2))
except Exception:
    pass

print("Short idea generation complete ✅")