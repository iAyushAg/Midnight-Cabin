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
import platform
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

def strip_emojis(text):
    """Remove emojis — ffmpeg drawtext doesn't support them without emoji font."""
    import re
    emoji_pattern = re.compile(
        "["
        "😀-🙏"
        "🌀-🗿"
        "🚀-🛿"
        "🇠-🇿"
        "✀-➿"
        "🤀-🧿"
        "☀-⛿"
        "🨀-🩯"
        "🩰-🫿"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()

print(f"Generating Short for: {theme} ({primary})")

# ─────────────────────────────────────────────
# HOOK ROTATION — cycles POV → Educational → Contrast
# ─────────────────────────────────────────────
HOOK_STYLES = ["pov", "educational"]

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
# VOICEOVER SCRIPT per style — 3 variants each, rotated automatically
# ─────────────────────────────────────────────

# Load voiceover rotation index
VO_ROTATION_FILE = os.path.join(PERSISTENT_DIR, "short_vo_rotation.json")
if os.path.exists(VO_ROTATION_FILE):
    with open(VO_ROTATION_FILE) as f:
        vo_data = json.load(f)
    vo_index = vo_data.get("index", 0)
else:
    vo_index = 0

next_vo_index = (vo_index + 1) % 3
with open(VO_ROTATION_FILE, "w") as f:
    json.dump({"index": next_vo_index}, f)

POV_VOICEOVERS = {
    "rain": [
        f"Your brain never fully switches off during sleep. It keeps listening — waiting for something to change. Rain gives it something steady. Nothing sudden. Nothing alarming. {duration_label} of quiet, consistent sound. Subscribe to Midnight Cabins for more.",
        f"Rain does not ask anything of you. It just falls. Steady, patient, unbroken. Your mind has nothing to react to — and that is exactly the point. {duration_label} of rain. Subscribe to Midnight Cabins for more.",
        f"There is a reason rain puts people to sleep. It fills the silence with something alive but predictable. Safe. Your nervous system exhales. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "fireplace": [
        f"For thousands of years, the crackle of fire meant safety and shelter. Your nervous system still remembers. {duration_label} of fireplace ambience. Subscribe to Midnight Cabins for more.",
        f"Fire is one of the oldest sounds humans have ever known. Warmth. Safety. Nowhere to be. Your body still reads it that way. {duration_label} of cozy fireplace ambience. Subscribe to Midnight Cabins for more.",
        f"A crackling fireplace is not just relaxing — it is ancestral. Your nervous system was built around this sound. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "river": [
        f"Moving water produces pink noise — frequencies that mirror your brain's own resting rhythms. Your mind recognises it. Slows down. {duration_label} of river sound. Subscribe to Midnight Cabins for more.",
        f"A river does not stop. Does not speed up. Does not startle. It just flows. Your mind finds the same rhythm. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Before cities, before noise, the sound of running water meant fresh water, safety, rest. Your brain still knows this. {duration_label} of river ambience. Subscribe to Midnight Cabins for more.",
    ],
    "ocean_waves": [
        f"Ocean waves repeat at twelve cycles per minute — matching the breathing rate of a sleeping person. Your body already knows this rhythm. {duration_label} of ocean ambience. Subscribe to Midnight Cabins for more.",
        f"The ocean breathes slower than you do. And when you listen long enough — so do you. {duration_label} of ocean waves. Subscribe to Midnight Cabins for more.",
        f"Wave after wave. Predictable. Patient. Endless. Your nervous system stops bracing for the next thing. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "soft_wind": [
        f"Wind at night signals stillness. No storms. No sudden changes. Your nervous system reads this as safety. {duration_label} of soft wind. Subscribe to Midnight Cabins for more.",
        f"Soft wind is the sound of the world at rest. Trees breathing. Nothing urgent. Nothing coming. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"A gentle breeze through the trees at midnight. The world settling. Your body doing the same. {duration_label} of wind ambience. Subscribe to Midnight Cabins for more.",
    ],
    "night_forest": [
        f"Forest sounds at night are an ecosystem at rest. Your brain evolved inside these sounds. {duration_label} of night forest ambience. Subscribe to Midnight Cabins for more.",
        f"Insects. Distant water. Leaves. A forest at night is never silent — but every sound means safety. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Your nervous system was built inside forests like this one. These sounds are not just calming. They are home. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "brown_noise": [
        f"Sudden sounds during sleep trigger micro-arousals — brief shifts toward lighter sleep you will not remember, but that silently fragment your rest. Brown noise raises the baseline, so nothing stands out. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Brown noise is not music. It is designed to give your brain something steady to hold onto — so it stops scanning for threats. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Your ADHD brain is not broken. It is under-stimulated. Brown noise fills that gap — quietly, consistently, without asking for your attention. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
}

EDUCATIONAL_VOICEOVERS = {
    "rain": [
        f"Your brain does not fully switch off during sleep. The auditory system keeps monitoring for sudden changes. Rain raises the baseline sound, so nothing stands out. Sleep stays deeper. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Did you know rain sounds reduce cortisol — the stress hormone — within minutes of listening? Your body does not need to be told to relax. It just does. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"The parasympathetic nervous system — your rest mode — is directly triggered by steady ambient sounds like rain. Heart rate slows. Breathing deepens. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "fireplace": [
        f"Warm crackling sounds activate the parasympathetic nervous system — your body's rest mode. Heart rate slows. Cortisol drops. {duration_label} of fireplace ambience. Subscribe to Midnight Cabins for more.",
        f"Research shows that exposure to fireplace sounds measurably lowers blood pressure. The effect begins within two minutes. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"The irregular crackle of fire keeps your auditory cortex gently engaged — just enough to quiet intrusive thoughts. Not enough to keep you awake. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "river": [
        f"Running water produces pink noise. Studies show it increases slow-wave sleep — the deepest, most restorative stage. {duration_label} of river sound. Subscribe to Midnight Cabins for more.",
        f"Pink noise — the frequency pattern of flowing water — has been shown to improve memory consolidation during sleep by up to 25 percent. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Your brain enters its deepest sleep stages more easily when background sound is steady and natural. River sounds are among the most effective. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "ocean_waves": [
        f"Ocean waves oscillate at twelve cycles per minute — identical to the breathing rate of someone in deep sleep. Your body synchronises without effort. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Entrainment — the brain's tendency to sync with rhythmic patterns — is why ocean waves help you fall asleep faster than almost any other sound. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Studies show people fall asleep 40 percent faster when exposed to ocean sounds compared to silence. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "soft_wind": [
        f"Pink noise in wind is linked to better memory consolidation during sleep. Your brain does not just rest — it recovers. {duration_label} of soft wind. Subscribe to Midnight Cabins for more.",
        f"Soft wind sounds activate the default mode network — the brain state responsible for deep rest and processing. You are not just sleeping. You are recovering. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Wind sounds reduce hyperarousal — the state of being too alert to sleep. Your nervous system stops scanning. Your thoughts stop looping. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "night_forest": [
        f"Nature sounds activate your brain's default mode network — the state responsible for deep rest and mental recovery. {duration_label} of forest night ambience. Subscribe to Midnight Cabins for more.",
        f"Exposure to natural sounds reduces activity in the brain's threat-detection centre by up to 30 percent. Your body stops bracing. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"The Japanese practice of forest bathing — shinrin-yoku — reduces cortisol, lowers blood pressure, and improves sleep quality. These sounds do the same. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
    "brown_noise": [
        f"Brown noise raises the room's baseline sound floor. When background is steady, sudden noises stand out less. Your brain stops bracing. Essential for ADHD. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"Brown noise shifts activity to the prefrontal cortex — the part of the ADHD brain that struggles most with focus and impulse control. {duration_label}. Subscribe to Midnight Cabins for more.",
        f"During sleep, your auditory system monitors for change. Brown noise removes the contrast between silence and sudden sound — so your brain stops monitoring. {duration_label}. Subscribe to Midnight Cabins for more.",
    ],
}

voiceover_maps = {
    "pov": POV_VOICEOVERS,
    "educational": EDUCATIONAL_VOICEOVERS,
}

# Pick variant based on rotation index
variants = voiceover_maps[hook_style].get(
    primary,
    [f"{theme}. {duration_label} of ambient sound. No ads. Subscribe to Midnight Cabins for more."]
)
voiceover_text = variants[vo_index % len(variants)]


cta_text = f"Full {duration_label} on our channel - Subscribe!"

# Strip emojis for drawtext (ffmpeg default font doesn't support emoji)
hook_text_display = strip_emojis(hook_text)
cta_text_display = strip_emojis(cta_text)

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
    import urllib.error
    import base64
    import ssl

    # Fix macOS SSL cert verification
    ssl_context = ssl.create_default_context()
    try:
        import certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

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
            "name": "en-US-Neural2-F",  # warm, natural female voice
            "ssmlGender": "FEMALE"
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 0.95,
            "pitch": -1.0,
        }
    }).encode("utf-8")

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as resp:
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

hook_wrapped = escape_text(wrap_text(hook_text_display, 22))
cta_escaped = escape_text(cta_text_display)
channel_escaped = escape_text("@midnightcabins")

hook_show_until = min(vo_duration + 2, 9)

# For contrast style — show silence label first 5s, then sound label
# ─────────────────────────────────────────────
# FONT SELECTION
# Uses best available font on current platform
# Falls back gracefully if font not found
# ─────────────────────────────────────────────

def find_font():
    """Find best available TTF font for the current platform."""
    system = platform.system()

    if system == "Darwin":  # macOS — use TTF only, avoid TTC
        mac_fonts = [
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Verdana.ttf",
            "/System/Library/Fonts/Supplemental/Trebuchet MS.ttf",
        ]
        for path in mac_fonts:
            if os.path.exists(path):
                return path
        # Search user fonts
        user_fonts = os.path.expanduser("~/Library/Fonts")
        for f in ["Arial.ttf", "Helvetica.ttf", "Georgia.ttf"]:
            p = os.path.join(user_fonts, f)
            if os.path.exists(p):
                return p

    else:  # Linux / Railway
        linux_fonts = [
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]
        for path in linux_fonts:
            if os.path.exists(path):
                return path

    return ""  # ffmpeg default font

FONT_FILE = find_font()
# Escape font path for ffmpeg filter string
font_path_escaped = FONT_FILE.replace("\\", "/").replace(":", "\\:").replace("'", "\\'") if FONT_FILE else ""
font_attr = f":fontfile='{font_path_escaped}'" if font_path_escaped else ""
print(f"Using font: {FONT_FILE or 'ffmpeg default'}")

# Build vf — no enable expressions to avoid ffmpeg comma parsing issues
# Hook shows full duration, CTA always visible at bottom
vf = (
    f"scale=1080:1920:force_original_aspect_ratio=increase,"
    f"crop=1080:1920,"
    f"drawtext=text='{hook_wrapped}'{font_attr}"
    f":fontsize=52:fontcolor=white"
    f":x=(w-text_w)/2:y=h/4"
    f":box=1:boxcolor=black@0.35:boxborderw=24"
    f","
    f"drawtext=text='{cta_escaped}'{font_attr}"
    f":fontsize=34:fontcolor=white"
    f":x=(w-text_w)/2:y=3*h/4"
    f":box=1:boxcolor=black@0.4:boxborderw=16"
    f","
    f"drawtext=text='{channel_escaped}'{font_attr}"
    f":fontsize=26:fontcolor=white@0.55"
    f":x=(w-text_w)/2:y=h-65,"
    f"format=yuv420p"
)

# ─────────────────────────────────────────────
# AUDIO — reveal effect + voiceover mix
# Audio fades from 20% to 100% over first 3 seconds
# giving a satisfying "sound reveal" feel
# For contrast style: near-silence for first 5s then full volume
# ─────────────────────────────────────────────
if not os.path.exists(SOURCE_VIDEO):
    raise FileNotFoundError(f"Main video not found: {SOURCE_VIDEO}")

# Audio reveal: simple fade-in using afade filter — universally compatible
# Fade from silence to full volume over 3 seconds
ambient_fade = "afade=t=in:st=0:d=3"

if has_voiceover and os.path.exists(VOICEOVER_PATH):
    filter_complex = (
        f"[0:a]{ambient_fade},volume=0.5[ambient];"
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
        "-af", f"{ambient_fade},volume=0.5",
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