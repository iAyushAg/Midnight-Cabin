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

# ─────────────────────────────────────────────
# LLM GENERATION — Claude generates fresh hook
# and voiceover text every time
# ─────────────────────────────────────────────
from anthropic import Anthropic

_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

def generate_short_content(primary, hook_style, duration_label, theme, mood):
    """Use Claude to generate hook text and voiceover script."""

    style_descriptions = {
        "pov": "POV (point of view) — second person, immersive, emotional. Starts with 'POV:'. Makes the viewer feel they are IN the scene.",
        "educational": "Educational — one surprising scientific fact about how this sound affects the brain or sleep. Conversational, warm, not clinical.",
    }

    prompt = f"""You are writing content for a YouTube Shorts video for the channel Midnight Cabins.

The channel posts long ambient sleep/focus soundscape videos. This Short is a 60-second preview.

Theme: {theme}
Primary sound: {primary.replace('_', ' ')}
Mood: {mood}
Duration of full video: {duration_label}
Hook style: {style_descriptions.get(hook_style, hook_style)}
Generate a fresh, unique version each time — vary the angle, the specific scientific fact used, and the phrasing.

Generate:

1. HOOK_TEXT: Short punchy text shown on screen (max 8 words, no emojis — they break video rendering). This is the first thing viewers read. Must stop the scroll.

2. VOICEOVER: A warm, narrative voiceover script (spoken aloud by a calm female voice). Max 12 seconds when spoken at normal pace (~35 words max). 
   - Warm, intelligent, slightly poetic tone
   - Include one specific scientific or psychological insight about why this sound helps sleep/focus
   - End with: "Subscribe to Midnight Cabins for more."
   - No emojis, no symbols

Return ONLY this JSON, no markdown:
{{
  "hook_text": "...",
  "voiceover": "..."
}}"""

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — skipping LLM generation")
        return None, None

    try:
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Parse JSON
        import re
        text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(text)
        print(f"LLM generated hook: {data.get('hook_text', '')[:60]}")
        print(f"LLM generated VO: {data.get('voiceover', '')[:80]}...")
        return data.get("hook_text", ""), data.get("voiceover", "")
    except Exception as e:
        print(f"LLM generation failed: {e} — using fallback")
        return None, None

# Generate content via LLM
hook_text, voiceover_text = generate_short_content(
    primary, hook_style, duration_label, theme, mood
)

# Fallback if LLM fails
if not hook_text:
    hook_maps = {
        "pov": POV_HOOKS,
        "educational": EDUCATIONAL_HOOKS,
    }
    hook_text = hook_maps.get(hook_style, POV_HOOKS).get(
        primary,
        f"The perfect sound for tonight"
    )

if not voiceover_text:
    # Simple fallback if Claude fails
    voiceover_text = f"{theme}. {duration_label} of uninterrupted ambient sound. No ads. Subscribe to Midnight Cabins for more."


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
        .replace("%", "\\%"))

def wrap_text(text, width=20):
    """Wrap text at word boundaries — returns lines joined by ffmpeg \\n escape."""
    words = text.split(" ")
    lines = []
    current_words = []
    current_len = 0

    for word in words:
        space = 1 if current_words else 0
        if current_len + space + len(word) > width and current_words:
            lines.append(" ".join(current_words))
            current_words = [word]
            current_len = len(word)
        else:
            current_words.append(word)
            current_len += space + len(word)

    if current_words:
        lines.append(" ".join(current_words))

    return "\\n".join(lines)

hook_wrapped = escape_text(wrap_text(hook_text_display, 20))
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

# ─────────────────────────────────────────────
# BUILD VERTICAL 1080x1920 BACKGROUND
# Use bg.jpg directly — scale to fill vertical frame
# Centre crop to avoid stretching
# This gives clean 1080x1920 from the start so text
# coordinates are always accurate
# ─────────────────────────────────────────────
BG_IMAGE = os.path.join(BASE_DIR, "video", "bg.jpg")
VERTICAL_BG = os.path.join(BASE_DIR, "output", "short_bg.jpg")

if os.path.exists(BG_IMAGE):
    # Resize bg.jpg to 1080x1920 — scale height to 1920,
    # then centre-crop width to 1080
    result_bg = subprocess.run([
        "ffmpeg", "-y",
        "-i", BG_IMAGE,
        "-vf", "scale=-2:1920,crop=1080:1920",
        "-q:v", "2",
        VERTICAL_BG
    ], capture_output=True, text=True)
    if result_bg.returncode != 0:
        VERTICAL_BG = BG_IMAGE  # fallback to original
    else:
        print(f"Vertical background prepared: 1080x1920")
else:
    VERTICAL_BG = None

# ─────────────────────────────────────────────
# VIDEO FILTER — text overlays on true 1080x1920
# Text coordinates now accurate since canvas is exactly 1080x1920
# ─────────────────────────────────────────────
text_vf = (
    f"drawtext=text='{hook_wrapped}'{font_attr}"
    f":fontsize=52:fontcolor=white"
    f":x=(w-text_w)/2:y=(h/4)-(text_h/2)"
    f":box=1:boxcolor=black@0.4:boxborderw=20"
    f","
    f"drawtext=text='{cta_escaped}'{font_attr}"
    f":fontsize=36:fontcolor=white"
    f":x=(w-text_w)/2:y=(3*h/4)-(text_h/2)"
    f":box=1:boxcolor=black@0.45:boxborderw=16"
    f","
    f"drawtext=text='{channel_escaped}'{font_attr}"
    f":fontsize=28:fontcolor=white@0.6"
    f":x=(w-text_w)/2:y=h-80,"
    f"format=yuv420p"
)

# ─────────────────────────────────────────────
# AUDIO — reveal effect + voiceover mix
# ─────────────────────────────────────────────
if not os.path.exists(SOURCE_VIDEO):
    raise FileNotFoundError(f"Main video not found: {SOURCE_VIDEO}")

ambient_fade = "afade=t=in:st=0:d=3"

if VERTICAL_BG and os.path.exists(VERTICAL_BG):
    # Use vertical bg image as video source — clean 1080x1920 from start
    if has_voiceover and os.path.exists(VOICEOVER_PATH):
        filter_complex = (
            f"[1:a]{ambient_fade},volume=0.5[ambient];"
            f"[2:a]volume=1.1,adelay=300|300[vo];"
            f"[ambient][vo]amix=inputs=2:duration=first:weights=1 1[audio]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", VERTICAL_BG,
            "-ss", str(START_OFFSET), "-t", str(SHORT_DURATION),
            "-i", SOURCE_VIDEO,
            "-i", VOICEOVER_PATH,
            "-filter_complex", filter_complex,
            "-vf", f"scale=1080:1920,{text_vf}",
            "-map", "0:v",
            "-map", "[audio]",
            "-t", str(SHORT_DURATION),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-r", "30", "-movflags", "+faststart",
            SHORT_OUTPUT
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", VERTICAL_BG,
            "-ss", str(START_OFFSET), "-t", str(SHORT_DURATION),
            "-i", SOURCE_VIDEO,
            "-vf", f"scale=1080:1920,{text_vf}",
            "-map", "0:v",
            "-map", "1:a",
            "-af", f"{ambient_fade},volume=0.5",
            "-t", str(SHORT_DURATION),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-r", "30", "-movflags", "+faststart",
            SHORT_OUTPUT
        ]
else:
    # Fallback — crop from landscape source video
    vf_fallback = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,{text_vf}"
    )
    if has_voiceover and os.path.exists(VOICEOVER_PATH):
        filter_complex = (
            f"[0:a]{ambient_fade},volume=0.5[ambient];"
            f"[1:a]volume=1.1,adelay=300|300[vo];"
            f"[ambient][vo]amix=inputs=2:duration=first:weights=1 1[audio]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(START_OFFSET), "-t", str(SHORT_DURATION),
            "-i", SOURCE_VIDEO,
            "-i", VOICEOVER_PATH,
            "-filter_complex", filter_complex,
            "-vf", vf_fallback,
            "-map", "0:v", "-map", "[audio]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-r", "30", "-movflags", "+faststart",
            SHORT_OUTPUT
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(START_OFFSET), "-t", str(SHORT_DURATION),
            "-i", SOURCE_VIDEO,
            "-vf", vf_fallback,
            "-af", f"{ambient_fade},volume=0.5",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-r", "30", "-movflags", "+faststart",
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