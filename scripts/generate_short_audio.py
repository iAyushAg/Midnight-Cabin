#!/usr/bin/env python3
"""
generate_short_audio.py — Dedicated audio generator for Shorts

Reads: $PERSISTENT_DIR/short_idea.json  (Short's own idea)
Writes: audio/short_audio.wav           (3-minute mix for the Short)

Completely independent from generate_audio.py.
Produces a 3-minute atmospheric mix using:
  1. Real Freesound samples if available in audio_samples/
  2. Procedural generation as fallback (numpy)
  3. Niche-specific EQ and mixing

The 3-minute mix is clipped to 28s in generate_short.py.
"""

import json
import os
import random
import numpy as np
from pathlib import Path
from scipy.io.wavfile import write as wav_write

SAMPLE_RATE     = 44100
DURATION        = 3 * 60  # 3 minutes — enough for any Short format
TARGET_SAMPLES  = SAMPLE_RATE * DURATION

BASE_DIR        = Path(__file__).resolve().parent.parent
PERSISTENT_DIR  = Path(os.environ.get("PERSISTENT_DIR", "/data"))
AUDIO_DIR       = BASE_DIR / "audio"
SAMPLES_DIR     = BASE_DIR / "audio_samples"

SHORT_IDEA_PATH = Path(os.environ.get("SHORT_IDEA_PATH",
                       str(PERSISTENT_DIR / "short_idea.json")))
SHORT_AUDIO_OUT = AUDIO_DIR / "short_audio.wav"

AUDIO_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# LOAD SHORT IDEA
# ─────────────────────────────────────────────
with open(SHORT_IDEA_PATH) as f:
    idea = json.load(f)

primary   = idea.get("audio_strategy", {}).get("primary_category", "rain")
secondary = idea.get("audio_strategy", {}).get("secondary_category", "soft_wind")
layers    = idea.get("sound_layers", [primary])
print(f"Short audio: primary={primary}, layers={layers}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def normalize(x, peak=0.90):
    m = np.max(np.abs(x))
    return (x / m * peak) if m > 0 else x

def soft_limit(x, drive=1.15):
    return np.tanh(x * drive) / np.tanh(drive)

def fade_in_out(audio, fade_sec=3):
    fade_len = min(SAMPLE_RATE * fade_sec, len(audio) // 4)
    ramp = np.linspace(0, 1, fade_len)
    if audio.ndim == 2:
        ramp = ramp[:, None]
    audio[:fade_len]  *= ramp
    audio[-fade_len:] *= ramp[::-1]
    return audio

def to_stereo(mono, width=0.3):
    """Convert mono to stereo with subtle width."""
    left  = mono * (1 + width * 0.5)
    right = mono * (1 - width * 0.5)
    # Slight delay on right for width
    delay = int(0.008 * SAMPLE_RATE)
    right = np.roll(right, delay)
    return np.column_stack([left, right])

def load_sample(niche, min_len=SAMPLE_RATE * 45):
    """Load a real audio sample from audio_samples/{niche}/"""
    folder = SAMPLES_DIR / niche
    if not folder.exists():
        return None
    files = list(folder.glob("*.wav")) + list(folder.glob("*.WAV"))
    if not files:
        return None
    path = random.choice(files)
    try:
        from scipy.io.wavfile import read as wav_read
        sr, data = wav_read(str(path))
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32)
        m = np.max(np.abs(data))
        if m > 0: data /= m
        # Resample if needed
        if sr != SAMPLE_RATE:
            ratio = SAMPLE_RATE / sr
            new_len = int(len(data) * ratio)
            indices = np.linspace(0, len(data) - 1, new_len)
            data = np.interp(indices, np.arange(len(data)), data)
        if len(data) < min_len:
            return None
        print(f"Loaded sample: {path.name} ({len(data)//SAMPLE_RATE}s)")
        return data
    except Exception as e:
        print(f"Sample load failed {path.name}: {e}")
        return None

def loop_to_length(audio, target_len, crossfade_sec=4):
    """Loop audio with crossfade joins to reach target length."""
    if len(audio) >= target_len:
        return audio[:target_len]
    cf = int(SAMPLE_RATE * crossfade_sec)
    result = audio.copy()
    while len(result) < target_len:
        fade_out = np.linspace(1, 0, cf)
        fade_in  = np.linspace(0, 1, cf)
        if len(result) >= cf and len(audio) >= cf:
            result[-cf:] *= fade_out
            blend = audio[:cf] * fade_in
            result[-cf:] += blend
            result = np.concatenate([result, audio[cf:]])
        else:
            result = np.concatenate([result, audio])
    return result[:target_len]

# ─────────────────────────────────────────────
# PROCEDURAL GENERATORS — fallback when no samples
# ─────────────────────────────────────────────
def gen_brown_noise(n):
    white = np.random.normal(0, 1, n).astype(np.float64)
    b = np.zeros(n)
    b[0] = white[0]
    for i in range(1, n):
        b[i] = 0.99 * b[i-1] + white[i] * 0.1
    return b.astype(np.float32)

def gen_rain(n, intensity=0.7):
    # Brown noise base + filtered white noise bursts
    base = gen_brown_noise(n) * 0.4
    noise = np.random.normal(0, 1, n).astype(np.float32)
    # Simple lowpass via cumsum
    lp = np.cumsum(noise) / SAMPLE_RATE * 0.3
    lp = lp - np.mean(lp)
    m = np.max(np.abs(lp))
    if m > 0: lp /= m
    return (base + lp * intensity * 0.6).astype(np.float32)

def gen_fireplace(n):
    # Pink noise (approx) + low rumble
    brown = gen_brown_noise(n)
    white = np.random.normal(0, 0.3, n).astype(np.float32)
    # Low rumble
    t = np.linspace(0, DURATION, n)
    rumble = (np.sin(2 * np.pi * 45 * t) * 0.1 +
              np.sin(2 * np.pi * 63 * t) * 0.07).astype(np.float32)
    crackle = (white * (np.random.uniform(0.3, 0.8, n)).astype(np.float32))
    return (brown * 0.4 + crackle * 0.3 + rumble).astype(np.float32)

def gen_river(n):
    brown = gen_brown_noise(n)
    t = np.linspace(0, DURATION, n)
    # Babbling variation via low-freq AM
    am = (0.85 + 0.15 * np.sin(2 * np.pi * 0.3 * t)).astype(np.float32)
    return (brown * am * 0.7).astype(np.float32)

def gen_ocean(n):
    brown = gen_brown_noise(n)
    t = np.linspace(0, DURATION, n)
    # Wave rhythm ~0.2Hz (5s cycle)
    wave = (0.6 + 0.4 * np.sin(2 * np.pi * 0.2 * t)).astype(np.float32)
    return (brown * wave).astype(np.float32)

def gen_wind(n):
    brown = gen_brown_noise(n)
    t = np.linspace(0, DURATION, n)
    gust = (0.7 + 0.3 * np.sin(2 * np.pi * 0.08 * t +
             np.random.uniform(0, np.pi))).astype(np.float32)
    return (brown * gust * 0.6).astype(np.float32)

def gen_forest_night(n):
    # Wind base + subtle high-freq cricket-like texture
    wind = gen_wind(n) * 0.6
    t = np.linspace(0, DURATION, n)
    cricket = (np.sin(2 * np.pi * 4200 * t) *
               np.random.uniform(0, 0.08, n)).astype(np.float32)
    return (wind + cricket).astype(np.float32)

def gen_thunder(n):
    rain = gen_rain(n, intensity=0.9)
    t = np.linspace(0, DURATION, n)
    # Thunder rumble at ~30s, ~90s, ~150s
    rumble = np.zeros(n, dtype=np.float32)
    for strike_t in [30, 90, 150]:
        strike_s = int(strike_t * SAMPLE_RATE)
        strike_len = int(8 * SAMPLE_RATE)
        if strike_s + strike_len < n:
            env = np.exp(-np.linspace(0, 5, strike_len)).astype(np.float32)
            rumble_seg = (np.random.normal(0, 1, strike_len) * env * 0.5).astype(np.float32)
            rumble[strike_s:strike_s + strike_len] += rumble_seg
    return (rain * 0.7 + rumble * 0.5).astype(np.float32)

PROCEDURAL = {
    "rain":         gen_rain,
    "river":        gen_river,
    "fireplace":    gen_fireplace,
    "ocean_waves":  gen_ocean,
    "soft_wind":    gen_wind,
    "night_forest": gen_forest_night,
    "brown_noise":  gen_brown_noise,
    "thunder":      gen_thunder,
}

# ─────────────────────────────────────────────
# NICHE-SPECIFIC MIX VOLUMES
# Primary layer is dominant; secondary is subtle texture
# ─────────────────────────────────────────────
MIX_VOLUMES = {
    "rain":         {"primary": 0.80, "secondary": 0.25},
    "river":        {"primary": 0.75, "secondary": 0.30},
    "fireplace":    {"primary": 0.85, "secondary": 0.20},
    "ocean_waves":  {"primary": 0.80, "secondary": 0.25},
    "soft_wind":    {"primary": 0.70, "secondary": 0.35},
    "night_forest": {"primary": 0.70, "secondary": 0.35},
    "brown_noise":  {"primary": 0.90, "secondary": 0.20},
    "thunder":      {"primary": 0.85, "secondary": 0.20},
}

# ─────────────────────────────────────────────
# BUILD THE MIX
# ─────────────────────────────────────────────
def build_layer(niche, target_len):
    """Build a single audio layer — real sample or procedural."""
    sample = load_sample(niche)
    if sample is not None:
        audio = loop_to_length(sample, target_len)
    else:
        print(f"No sample for '{niche}' — using procedural generator")
        gen = PROCEDURAL.get(niche, gen_brown_noise)
        audio = gen(target_len)
    return audio[:target_len].astype(np.float32)

vols = MIX_VOLUMES.get(primary, {"primary": 0.80, "secondary": 0.25})

print(f"Building primary layer: {primary}")
primary_audio = build_layer(primary, TARGET_SAMPLES)

mix = primary_audio * vols["primary"]

if secondary and secondary != primary:
    print(f"Building secondary layer: {secondary}")
    secondary_audio = build_layer(secondary, TARGET_SAMPLES)
    mix = mix + secondary_audio * vols["secondary"]

# Normalise and soft limit
mix = normalize(mix)
mix = soft_limit(mix)
mix = normalize(mix, peak=0.88)

# Fade in/out
mix = fade_in_out(mix, fade_sec=5)

# Convert to stereo
stereo = to_stereo(mix)

# To int16
stereo_int = np.clip(stereo * 32767, -32768, 32767).astype(np.int16)

wav_write(str(SHORT_AUDIO_OUT), SAMPLE_RATE, stereo_int)
size_kb = SHORT_AUDIO_OUT.stat().st_size // 1024
print(f"Short audio saved: {SHORT_AUDIO_OUT} ({size_kb}KB, {DURATION}s)")