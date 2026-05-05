import json
import os
import random
import numpy as np
from scipy.io.wavfile import write, read

SAMPLE_RATE = 44100
DURATION = 10 * 60  # source audio length; FFmpeg loops this into longer video
MIN_SAMPLE_SECONDS = 45

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSISTENT_DIR = os.environ.get("PERSISTENT_DIR", "/data")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SAMPLES_DIR = os.path.join(BASE_DIR, "audio_samples")

# Read idea from persistent dir — falls back to BASE_DIR if not found
IDEA_PATH = os.path.join(PERSISTENT_DIR, "current_idea.json")
if not os.path.exists(IDEA_PATH):
    IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

os.makedirs(AUDIO_DIR, exist_ok=True)

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

layers = idea.get("sound_layers", [])
n = SAMPLE_RATE * DURATION
t = np.linspace(0, DURATION, n, endpoint=False)


def normalize(x, peak=0.95):
    max_amp = np.max(np.abs(x))
    if max_amp > 0:
        return (x / max_amp) * peak
    return x


def soft_limiter(x, drive=1.2):
    return np.tanh(x * drive) / np.tanh(drive)


def fade(audio, seconds=5):
    fade_len = min(SAMPLE_RATE * seconds, len(audio) // 2)
    curve = np.linspace(0, 1, fade_len)

    if audio.ndim == 2:
        curve = curve[:, None]

    audio[:fade_len] *= curve
    audio[-fade_len:] *= curve[::-1]
    return audio


def crossfade_join(clips, target_len, crossfade_seconds=6):
    if not clips:
        return np.zeros(target_len)

    crossfade_len = SAMPLE_RATE * crossfade_seconds
    output = clips[0].copy()

    for clip in clips[1:]:
        if len(output) >= target_len:
            break

        fade_len = min(crossfade_len, len(output), len(clip))

        fade_out = np.linspace(1, 0, fade_len)
        fade_in = np.linspace(0, 1, fade_len)

        blended = output[-fade_len:] * fade_out + clip[:fade_len] * fade_in
        output = np.concatenate([output[:-fade_len], blended, clip[fade_len:]])

    if len(output) < target_len:
        repeat = int(np.ceil(target_len / len(output)))
        output = np.tile(output, repeat)

    return output[:target_len]


def seamless_loop(audio, seconds=8):
    fade_len = min(SAMPLE_RATE * seconds, len(audio) // 3)

    if fade_len <= 0:
        return audio

    fade_in = np.linspace(0, 1, fade_len)
    fade_out = 1 - fade_in

    if audio.ndim == 2:
        fade_in = fade_in[:, None]
        fade_out = fade_out[:, None]

    start = audio[:fade_len].copy()
    end = audio[-fade_len:].copy()
    blended = end * fade_out + start * fade_in

    audio[:fade_len] = blended
    audio[-fade_len:] = blended

    return audio


def stereo(layer, delay_samples=350, width=0.9):
    left = layer
    right = np.roll(layer, delay_samples)
    return np.column_stack((left, right * width))


def add_layer(mix, layer, volume=0.5, delay=350, width=0.9):
    return mix + volume * stereo(layer, delay, width)


def smooth_noise(smoothness=800):
    white = np.random.normal(0, 1, n)
    kernel = np.ones(smoothness) / smoothness
    return normalize(np.convolve(white, kernel, mode="same"))


def brown_noise():
    white = np.random.normal(0, 1, n)
    brown = np.cumsum(white)
    brown = brown - np.mean(brown)
    return normalize(brown)


def pink_noise():
    low = smooth_noise(900)
    high = smooth_noise(120)
    return normalize(0.75 * low + 0.25 * high)


def read_wav_mono(path):
    sr, data = read(path)

    if data.ndim > 1:
        data = data.mean(axis=1)

    data = data.astype(np.float32)

    max_amp = np.max(np.abs(data))
    if max_amp > 0:
        data = data / max_amp

    if sr != SAMPLE_RATE:
        old_indices = np.arange(len(data))
        new_length = int(len(data) * SAMPLE_RATE / sr)
        new_indices = np.linspace(0, len(data) - 1, new_length)
        data = np.interp(new_indices, old_indices, data)

    return normalize(data)


def load_sample(path):
    data = read_wav_mono(path)

    if len(data) < SAMPLE_RATE * MIN_SAMPLE_SECONDS:
        raise ValueError(f"Sample too short: {path}")

    if len(data) > n:
        start = random.randint(0, len(data) - n)
        data = data[start:start + n]

    return normalize(data)


def pick_samples(category, max_files=4):
    folder = os.path.join(SAMPLES_DIR, category)

    if not os.path.exists(folder):
        return []

    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".wav")
    ]

    random.shuffle(files)

    valid = []
    for path in files:
        try:
            sr, data = read(path)
            seconds = len(data) / sr
            if seconds >= MIN_SAMPLE_SECONDS:
                valid.append(path)
        except Exception:
            continue

    return valid[:max_files]


def build_sample_layer(category):
    sample_paths = pick_samples(category, max_files=4)

    if not sample_paths:
        return None

    clips = []

    for path in sample_paths:
        try:
            clip = load_sample(path)
            clip = fade(clip, seconds=3)
            clips.append(clip)
        except Exception as e:
            print(f"Skipping sample {path}: {e}")

    if not clips:
        return None

    layer = crossfade_join(clips, n, crossfade_seconds=6)
    return normalize(layer)


def procedural_rain():
    low_body = smooth_noise(300)
    mid_texture = smooth_noise(80)
    droplets = np.random.normal(0, 1, n)
    droplets = np.convolve(droplets, np.ones(10) / 10, mode="same")
    movement = 0.85 + 0.15 * np.sin(2 * np.pi * 0.025 * t)
    return normalize((0.45 * low_body + 0.35 * mid_texture + 0.2 * droplets) * movement)


def procedural_ocean():
    base = brown_noise()
    swell_1 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.055 * t)
    swell_2 = 0.7 + 0.3 * np.sin(2 * np.pi * 0.087 * t + 1.7)
    foam = smooth_noise(180)
    return normalize(0.7 * base * swell_1 * swell_2 + 0.3 * foam * swell_1)


def procedural_wind():
    base = smooth_noise(1800)
    gust = 0.45 + 0.55 * np.sin(2 * np.pi * 0.035 * t + 0.6)
    return normalize(base * gust)


def thunder_layer():
    thunder = build_sample_layer("thunder")

    if thunder is not None:
        return thunder

    thunder = np.zeros(n)

    for _ in range(max(1, DURATION // 60)):
        start = random.randint(0, max(1, n - SAMPLE_RATE * 8))
        length = random.randint(SAMPLE_RATE * 3, SAMPLE_RATE * 8)
        rumble = brown_noise()[:length]
        env = np.exp(-np.linspace(0, 7, length))
        thunder[start:start + length] += rumble * env

    return normalize(thunder)


def fireplace_layer():
    fireplace = build_sample_layer("fireplace")

    if fireplace is not None:
        return fireplace

    warm = smooth_noise(1300) * 0.35
    crackles = np.zeros(n)

    positions = np.where(np.random.random(n) < 0.0012)[0]
    for pos in positions:
        length = random.randint(120, 1200)
        end = min(n, pos + length)
        env = np.exp(-np.linspace(0, 8, end - pos))
        crackles[pos:end] += np.random.normal(0, 1, end - pos) * env

    return normalize(warm + 0.55 * crackles)

mix = np.zeros((n, 2))

mix = add_layer(mix, brown_noise(), 0.08, delay=500, width=0.85)

if "brown_noise" in layers:
    mix = add_layer(mix, brown_noise(), 0.30, delay=450, width=0.85)

if "pink_noise" in layers:
    mix = add_layer(mix, pink_noise(), 0.28, delay=380, width=0.88)

if "rain" in layers:
    rain = build_sample_layer("rain")
    if rain is None:
        rain = procedural_rain()
    mix = add_layer(mix, rain, 0.62, delay=220, width=0.95)

if "river" in layers:
    river = build_sample_layer("river")
    if river is None:
        river = procedural_rain()
    mix = add_layer(mix, river, 0.52, delay=500, width=0.9)

if "ocean_waves" in layers:
    ocean = build_sample_layer("ocean")
    if ocean is None:
        ocean = procedural_ocean()
    mix = add_layer(mix, ocean, 0.62, delay=700, width=0.9)

if "soft_wind" in layers or "wind" in layers:
    wind = build_sample_layer("wind")
    if wind is None:
        wind = procedural_wind()
    mix = add_layer(mix, wind, 0.25, delay=900, width=0.82)

if "soft_thunder" in layers or "thunder" in layers:
    thunder = thunder_layer()
    mix = add_layer(mix, thunder, 0.14, delay=1100, width=0.75)

if "fireplace" in layers:
    fireplace = fireplace_layer()
    mix = add_layer(mix, fireplace, 0.42, delay=150, width=0.96)

mix = normalize(mix, peak=0.85)
mix = soft_limiter(mix, drive=1.2)
mix = seamless_loop(mix, seconds=8)
mix = fade(mix, seconds=4)

file_path = os.path.join(AUDIO_DIR, "brown_noise.wav")
write(file_path, SAMPLE_RATE, mix.astype(np.float32))

print("Generated audio for:", idea.get("theme", "Unknown theme"))
print("Layers:", layers)
print("Saved audio at:", file_path)