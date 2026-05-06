"""
generate_short.py — YouTube Shorts generator for Midnight Cabin

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
# HOOK TEXT + VOICEOVER
# ─────────────────────────────────────────────
# Shorts should feel like useful micro-experiences, not ads. Hooks are
# emotional/scene-based first, with softer science phrasing for trust.
POV_HOOKS = {
    "rain":         "POV: You found the 3AM rain",
    "fireplace":    "POV: The cabin is finally warm",
    "river":        "POV: You hear water outside",
    "ocean_waves":  "POV: The ocean keeps breathing",
    "soft_wind":    "POV: Midnight wind through the window",
    "night_forest": "POV: The forest is completely still",
    "brown_noise":  "POV: Your thoughts get quieter",
}

EDUCATIONAL_HOOKS = {
    "rain":         "Your brain likes steady sound",
    "fireplace":    "Why fire feels so calming",
    "river":        "A softer background for sleep",
    "ocean_waves":  "A rhythm your body understands",
    "soft_wind":    "Soft wind, fewer sharp edges",
    "night_forest": "Nature sound without sudden noise",
    "brown_noise":  "Brown noise makes distractions softer",
}

hook_maps = {
    "pov": POV_HOOKS,
    "educational": EDUCATIONAL_HOOKS,
}

hook_text = hook_maps[hook_style].get(
    primary,
    f"Save this sound for tonight"
)

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

SOFT_CTA = [
    "Full version on Midnight Cabin.",
    "Save this for tonight.",
    "Let the full version play later.",
]

POV_VOICEOVERS = {
    "rain": [
        f"You are inside, dry and still, while the rain gives your mind one steady thing to follow. Nothing sharp. Nothing sudden. {random.choice(SOFT_CTA)}",
        f"Rain fills the silence without asking for your attention. Let it become the background your thoughts can finally fade into. {random.choice(SOFT_CTA)}",
        f"This is the sound of the world slowing down outside your window. Keep it low, let it run, and stop chasing sleep. {random.choice(SOFT_CTA)}",
    ],
    "fireplace": [
        f"A quiet room, a small fire, and nowhere else to be. The crackle stays gentle enough to keep the night feeling safe. {random.choice(SOFT_CTA)}",
        f"Fireplace sounds can make a room feel warmer before anything else changes. Let the crackle sit in the background. {random.choice(SOFT_CTA)}",
        f"This is not music. Just a warm, steady cabin soundscape for reading, resting, or falling asleep. {random.choice(SOFT_CTA)}",
    ],
    "river": [
        f"A river never rushes you. It just keeps moving, giving your mind a soft pattern to rest against. {random.choice(SOFT_CTA)}",
        f"Flowing water can make background noise feel smoother and less distracting. Let it carry the room for a minute. {random.choice(SOFT_CTA)}",
        f"You found a quiet place near the river, where every sound moves at the same calm pace. {random.choice(SOFT_CTA)}",
    ],
    "ocean_waves": [
        f"The ocean gives you a slow pattern that arrives, fades, and returns. No hurry. No sharp edges. {random.choice(SOFT_CTA)}",
        f"Wave sounds can help a room feel more predictable, which is exactly what a tired mind wants. {random.choice(SOFT_CTA)}",
        f"Let one wave replace one thought at a time. Keep the volume low and let the full version play when you rest. {random.choice(SOFT_CTA)}",
    ],
    "soft_wind": [
        f"Soft wind is the sound of nothing needing you right now. Just a quiet room, a dark window, and steady air outside. {random.choice(SOFT_CTA)}",
        f"When the background is gentle and consistent, distractions feel less important. Let the wind hold the space. {random.choice(SOFT_CTA)}",
        f"A midnight breeze through the trees, low enough for sleep and steady enough for focus. {random.choice(SOFT_CTA)}",
    ],
    "night_forest": [
        f"The forest is not silent, but nothing is demanding your attention. That is what makes it feel restful. {random.choice(SOFT_CTA)}",
        f"Natural ambience can make a room feel less empty and more settled. Let this become the background. {random.choice(SOFT_CTA)}",
        f"You are far from traffic, screens, and voices. Just a dark forest and a steady night around you. {random.choice(SOFT_CTA)}",
    ],
    "brown_noise": [
        f"Brown noise gives your brain a steady low background, so small distractions feel less sharp. Try it quietly. {random.choice(SOFT_CTA)}",
        f"Many people use brown noise for focus because it fills the empty space without turning into music. {random.choice(SOFT_CTA)}",
        f"If silence makes every little sound stand out, brown noise can make the room feel smoother. {random.choice(SOFT_CTA)}",
    ],
}

EDUCATIONAL_VOICEOVERS = POV_VOICEOVERS
voiceover_maps = {
    "pov": POV_VOICEOVERS,
    "educational": EDUCATIONAL_VOICEOVERS,
}

variants = voiceover_maps[hook_style].get(
    primary,
    [f"{theme}. {duration_label} of uninterrupted ambient sound. Full version on Midnight Cabin."]
)
voiceover_text = variants[vo_index % len(variants)]

cta_text = random.choice([
    "Save this for tonight",
    f"Full {duration_label} on Midnight Cabin",
    "Let this play later",
])

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

    else:  # Linux / Railway (Debian trixie)
        linux_fonts = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
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