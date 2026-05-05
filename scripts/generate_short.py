"""
generate_short.py — YouTube Shorts generator for Midnight Cabins

Strategy:
- Rotates 3 hook styles: POV emotional / Educational / Contrast reveal
- Theme-specific start offsets for best-sounding moment
- Audio reveal: fades from 20% to 100% in first 3s for satisfying impact
- Vertical 1080x1920, 30fps, #Shorts format
"""

import json
import os
import random
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")

IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(IDEA_PATH):
    IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

SOURCE_VIDEO = os.path.join(BASE_DIR, "output", "video.mp4")
SHORT_OUTPUT = os.path.join(BASE_DIR, "output", "short.mp4")
VOICEOVER_PATH = os.path.join(BASE_DIR, "output", "voiceover.mp3")
SHORT_ROTATION_FILE = os.path.join(PERSISTENT_DIR, "short_hook_rotation.json")

SHORT_DURATION = 60

# ─────────────────────────────────────────────
# LOAD IDEA
# ─────────────────────────────────────────────
with open(IDEA_PATH) as f:
    idea = json.load(f)

theme = idea.get("theme", "Ambient Soundscape")
layers = idea.get("sound_layers", ["brown_noise"])
primary = idea.get("audio_strategy", {}).get("primary_category", "brown_noise")
mood = idea.get("audio_strategy", {}).get("mood", "calm")
duration_minutes = idea.get("duration_minutes", 480)
duration_label = "10 Hours" if duration_minutes >= 600 else "8 Hours"

print(f"Generating Short for: {theme} ({primary})")

# ─────────────────────────────────────────────
# HOOK ROTATION — cycles POV → Educational → Contrast
# ─────────────────────────────────────────────
HOOK_STYLES = ["pov", "educational", "contrast"]

if os.path.exists(SHORT_ROTATION_FILE):
    with open(SHORT_ROTATION_FILE) as f:
        rotation = json.load(f)
    last_style = rotation.get("last_style", "contrast")
    idx = HOOK_STYLES.index(last_style) if last_style in HOOK_STYLES else -1
    hook_style = HOOK_STYLES[(idx + 1) % len(HOOK_STYLES)]
else:
    hook_style = "pov"

with open(SHORT_ROTATION_FILE, "w") as f:
    json.dump({"last_style": hook_style}, f)

print(f"Hook style this Short: {hook_style}")

# ─────────────────────────────────────────────
# HOOK TEXT per style per theme
# ─────────────────────────────────────────────
POV_HOOKS = {
    "rain":         "POV: It's 3am and your brain finally shuts off 🌧️",
    "fireplace":    "POV: A cozy cabin with nowhere to be 🔥",
    "river":        "POV: You found the perfect spot by the river 🌊",
    "ocean_waves":  "POV: Falling asleep to the ocean for the first time 🌊",
    "soft_wind":    "POV: A midnight breeze through an open window 🍃",
    "night_forest": "POV: Completely alone in a quiet forest at midnight 🌲",
    "brown_noise":  "POV: You finally found something that helps you focus 🧠",
}

EDUCATIONAL_HOOKS = {
    "rain":         "Rain sounds lower cortisol by up to 40% 🌧️",
    "fireplace":    "Fireplace sounds reduce anxiety — here's why 🔥",
    "river":        "Running water sounds are scientifically proven to reduce stress 🌊",
    "ocean_waves":  "Ocean waves match the brain's sleep frequency exactly 🌊",
    "soft_wind":    "Pink noise in wind sounds improves deep sleep quality 🍃",
    "night_forest": "Nature sounds reset your nervous system in minutes 🌲",
    "brown_noise":  "Brown noise changes brain activity in ADHD — here's what it sounds like 🧠",
}

CONTRAST_HOOKS = {
    "rain":         "Your brain before rain sounds vs after 🌧️",
    "fireplace":    "What silence sounds like vs a cozy fireplace 🔥",
    "river":        "Office noise vs river ambience — spot the difference 🌊",
    "ocean_waves":  "Anxious mind vs ocean waves 🌊",
    "soft_wind":    "City noise vs soft wind at midnight 🍃",
    "night_forest": "Insomnia vs forest night sounds 🌲",
    "brown_noise":  "ADHD brain without brown noise vs with it 🧠",
}

hook_maps = {
    "pov": POV_HOOKS,
    "educational": EDUCATIONAL_HOOKS,
    "contrast": CONTRAST_HOOKS,
}

hook_text = hook_maps[hook_style].get(
    primary,
    f"POV: You found the perfect {primary.replace('_', ' ')} ambience 🌙"
)

# ─────────────────────────────────────────────
# VOICEOVER SCRIPT per style
# ─────────────────────────────────────────────
POV_VOICEOVERS = {
    "rain":         f"Gentle rain on a quiet cabin. {duration_label} of uninterrupted sound. No ads. No interruptions. Just rain.",
    "fireplace":    f"A warm fireplace crackling softly. {duration_label} of cozy ambience. No ads. Just warmth.",
    "river":        f"A gentle river, flowing in the distance. {duration_label} of pure nature sound. No ads.",
    "ocean_waves":  f"Ocean waves rolling in slowly. {duration_label} of sleep sound. No ads. No interruptions.",
    "soft_wind":    f"Soft wind through the trees at midnight. {duration_label} of calm. No ads.",
    "night_forest": f"A quiet forest at night. {duration_label} of nature ambience. No ads. Just peace.",
    "brown_noise":  f"Brown noise. The sound ADHD brains need. {duration_label}. No ads. No interruptions.",
}

EDUCATIONAL_VOICEOVERS = {
    "rain":         f"Rain sounds trigger the parasympathetic nervous system — your brain's rest mode. {duration_label} version on our channel.",
    "fireplace":    f"Fireplace sounds lower heart rate and reduce cortisol. {duration_label} version on our channel.",
    "river":        f"Running water sounds reduce stress hormones in minutes. Full {duration_label} on our channel.",
    "ocean_waves":  f"Ocean waves oscillate at the same frequency as sleeping brains. Full {duration_label} on our channel.",
    "soft_wind":    f"Pink noise in wind sounds improves memory consolidation during sleep. Full {duration_label} on our channel.",
    "night_forest": f"Nature sounds activate the brain's default mode — deep rest state. Full {duration_label} on our channel.",
    "brown_noise":  f"Brown noise increases dopamine in prefrontal cortex — exactly what ADHD brains need. Full {duration_label} on our channel.",
}

CONTRAST_VOICEOVERS = {
    "rain":         f"This is {duration_label} of rain. No music. No beats. Just the sound your brain needs to sleep.",
    "fireplace":    f"This is {duration_label} of fireplace. No talking. No ads. Just warmth.",
    "river":        f"This is {duration_label} of river sounds. Pure nature. No interruptions.",
    "ocean_waves":  f"This is {duration_label} of ocean waves. No ads. No sudden changes. Just the ocean.",
    "soft_wind":    f"This is {duration_label} of soft wind. Pure calm. No interruptions.",
    "night_forest": f"This is {duration_label} of forest at night. Pure nature. No ads.",
    "brown_noise":  f"This is {duration_label} of brown noise. Pure focus sound. No music. No ads.",
}

voiceover_maps = {
    "pov": POV_VOICEOVERS,
    "educational": EDUCATIONAL_VOICEOVERS,
    "contrast": CONTRAST_VOICEOVERS,
}

voiceover_text = voiceover_maps[hook_style].get(
    primary,
    f"{theme}. {duration_label} of ambient sound. No ads. No interruptions."
)

cta_text = f"Full {duration_label} on our channel \U0001f514"

# ─────────────────────────────────────────────
# THEME-SPECIFIC START OFFSETS
# Best-sounding moment per theme
# ─────────────────────────────────────────────
START_OFFSETS = {
    "rain":         45,   # rain settles into rhythm at ~45s
    "fireplace":    30,   # crackles most present early on
    "river":        60,   # river flows consistently from 1min
    "ocean_waves":  90,   # waves establish their rhythm by 90s
    "soft_wind":    30,   # wind is fullest early
    "night_forest": 120,  # forest settles after 2min
    "brown_noise":  10,   # brown noise is consistent from the start
}

START_OFFSET = START_OFFSETS.get(primary, 60)
print(f"Starting Short at offset: {START_OFFSET}s")

# ─────────────────────────────────────────────
# GENERATE VOICEOVER via Google Cloud TTS
# ─────────────────────────────────────────────
def generate_voiceover(text, output_path):
    import urllib.request
    import base64

    api_key = os.environ.get("GOOGLE_TTS_API_KEY", "")

    if not api_key:
        print("GOOGLE_TTS_API_KEY not set — skipping voiceover")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "3", "-q:a", "9", "-acodec", "libmp3lame",
            output_path
        ], capture_output=True)
        return False

    payload = json.dumps({
        "input": {"text": text},
        "voice": {
            "languageCode": "en-US",
            "name": "en-US-Standard-C",
            "ssmlGender": "FEMALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 0.85,
            "pitch": -2.5,
        }
    }).encode("utf-8")

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            audio_data = base64.b64decode(result["audioContent"])
            with open(output_path, "wb") as f:
                f.write(audio_data)
            print(f"Voiceover generated: {len(audio_data)} bytes")
            return True
    except Exception as e:
        print(f"TTS failed: {e}")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "3", "-q:a", "9", "-acodec", "libmp3lame",
            output_path
        ], capture_output=True)
        return False

has_voiceover = generate_voiceover(voiceover_text, VOICEOVER_PATH)

def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 3.0

vo_duration = get_duration(VOICEOVER_PATH) if os.path.exists(VOICEOVER_PATH) else 3.0
print(f"Voiceover duration: {vo_duration:.1f}s")

# ─────────────────────────────────────────────
# BUILD FILTER GRAPH
# ─────────────────────────────────────────────
def escape_text(text):
    return (text
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace("\n", "\\n"))

def wrap_text(text, width=24):
    words = text.split()
    lines, current, count = [], [], 0
    for word in words:
        if count + len(word) > width:
            lines.append(" ".join(current))
            current, count = [word], len(word)
        else:
            current.append(word)
            count += len(word) + 1
    if current:
        lines.append(" ".join(current))
    return "\\n".join(lines)

hook_wrapped = escape_text(wrap_text(hook_text, 22))
cta_escaped = escape_text(cta_text)
channel_escaped = escape_text("@midnightcabins")

hook_show_until = min(vo_duration + 2, 9)

# For contrast style — show silence label first 5s, then sound label
if hook_style == "contrast":
    vf = (
        "scale=-2:1920,"
        "crop=1080:1920,"

        # Silence label — first 5 seconds
        "drawtext=text='Before':"
        "fontsize=56:fontcolor=white:"
        "x=(w-text_w)/2:y=h/5:"
        "box=1:boxcolor=black@0.5:boxborderw=18:"
        "enable='lt(t,5)',"

        # Sound label — after 5 seconds
        "drawtext=text='After':"
        "fontsize=56:fontcolor=white:"
        "x=(w-text_w)/2:y=h/5:"
        "box=1:boxcolor=black@0.5:boxborderw=18:"
        "enable='gte(t,5)',"

        # Hook subtext
        f"drawtext=text='{hook_wrapped}':"
        "fontsize=40:fontcolor=white@0.9:"
        "x=(w-text_w)/2:y=h/3:"
        "box=1:boxcolor=black@0.4:boxborderw=14:"
        f"enable='between(t,0,{hook_show_until})',"

        # CTA
        f"drawtext=text='{cta_escaped}':"
        "fontsize=36:fontcolor=white:"
        "x=(w-text_w)/2:y=3*h/4:"
        "box=1:boxcolor=black@0.5:boxborderw=14:"
        f"enable='gte(t,{SHORT_DURATION - 8})',"

        # Channel branding
        f"drawtext=text='{channel_escaped}':"
        "fontsize=28:fontcolor=white@0.65:"
        "x=(w-text_w)/2:y=h-70:"
        "enable='1',"

        "format=yuv420p"
    )
else:
    vf = (
        "scale=-2:1920,"
        "crop=1080:1920,"

        # Hook text — large, centre screen
        f"drawtext=text='{hook_wrapped}':"
        "fontsize=50:fontcolor=white:"
        "x=(w-text_w)/2:y=h/4:"
        "box=1:boxcolor=black@0.45:boxborderw=20:"
        f"enable='between(t,0,{hook_show_until})',"

        # CTA
        f"drawtext=text='{cta_escaped}':"
        "fontsize=36:fontcolor=white:"
        "x=(w-text_w)/2:y=3*h/4:"
        "box=1:boxcolor=black@0.5:boxborderw=14:"
        f"enable='gte(t,{SHORT_DURATION - 8})',"

        # Channel branding
        f"drawtext=text='{channel_escaped}':"
        "fontsize=28:fontcolor=white@0.65:"
        "x=(w-text_w)/2:y=h-70:"
        "enable='1',"

        "format=yuv420p"
    )

# ─────────────────────────────────────────────
# AUDIO — reveal effect + voiceover mix
# Audio fades from 20% to 100% over first 3 seconds
# giving a satisfying "sound reveal" feel
# For contrast style: near-silence for first 5s then full volume
# ─────────────────────────────────────────────
if not os.path.exists(SOURCE_VIDEO):
    raise FileNotFoundError(f"Main video not found: {SOURCE_VIDEO}")

if hook_style == "contrast":
    # Silence (5%) for 5 seconds, then ramp to full
    ambient_af = (
        "volume=enable='lt(t,5)':volume=0.05,"
        "volume=enable='between(t,5,8)':volume='0.05+(t-5)*0.317',"
        "volume=enable='gte(t,8)':volume=1.0"
    )
else:
    # Reveal: 20% → 100% over 3 seconds, then stays full
    ambient_af = (
        "volume=enable='lt(t,3)':volume='0.2+(t/3)*0.8',"
        "volume=enable='gte(t,3)':volume=1.0"
    )

if has_voiceover and os.path.exists(VOICEOVER_PATH):
    filter_complex = (
        f"[0:a]{ambient_af}[ambient];"
        f"[1:a]volume=1.1,adelay=300|300[vo];"
        f"[ambient][vo]amix=inputs=2:duration=first:weights=1 1[audio]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(START_OFFSET),
        "-t", str(SHORT_DURATION),
        "-i", SOURCE_VIDEO,
        "-i", VOICEOVER_PATH,
        "-filter_complex", filter_complex,
        "-vf", vf,
        "-map", "0:v",
        "-map", "[audio]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        "-movflags", "+faststart",
        SHORT_OUTPUT
    ]
else:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(START_OFFSET),
        "-t", str(SHORT_DURATION),
        "-i", SOURCE_VIDEO,
        "-vf", vf,
        "-af", ambient_af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        "-movflags", "+faststart",
        SHORT_OUTPUT
    ]

print(f"Rendering Short ({hook_style} style)...")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("Short render failed:", result.stderr[-800:])
    raise RuntimeError("Short render failed")

print(f"Short rendered successfully: {SHORT_OUTPUT}")

# ─────────────────────────────────────────────
# SAVE METADATA
# ─────────────────────────────────────────────
short_meta = {
    "theme": theme,
    "primary": primary,
    "layers": layers,
    "mood": mood,
    "duration_label": duration_label,
    "hook_style": hook_style,
    "hook_text": hook_text,
    "voiceover_text": voiceover_text,
    "has_voiceover": has_voiceover,
    "start_offset": START_OFFSET,
    "created_at": datetime.now().isoformat(),
}

with open(os.path.join(PERSISTENT_DIR, "current_short.json"), "w") as f:
    json.dump(short_meta, f, indent=2)

print(f"Short metadata saved — style: {hook_style}, offset: {START_OFFSET}s")