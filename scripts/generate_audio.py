import json
import os
import random
import numpy as np
from scipy.io.wavfile import write, read

SAMPLE_RATE = 44100
DURATION = 10 * 60  # 10 min source audio; FFmpeg can loop this into longer video

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
SAMPLES_DIR = os.path.join(BASE_DIR, "audio_samples")
IDEA_PATH = os.path.join(BASE_DIR, "current_idea.json")

os.makedirs(AUDIO_DIR, exist_ok=True)

with open(IDEA_PATH, "r") as f:
    idea = json.load(f)

layers = idea.get("sound_layers", [])
theme = idea.get("theme", "").lower()

n = SAMPLE_RATE * DURATION
t = np.linspace(0, DURATION, n, endpoint=False)


def normalize(x, peak=0.95):
    max_amp = np.max(np.abs(x))
    if max_amp > 0:
        return (x / max_amp) * peak
    return x


def soft_limiter(x, drive=1.25):
    return np.tanh(x * drive) / np.tanh(drive)


def fade(audio, seconds=5):
    fade_len = min(SAMPLE_RATE * seconds, len(audio) // 2)
    curve = np.linspace(0, 1, fade_len)

    if audio.ndim == 2:
        curve = curve[:, None]

    audio[:fade_len] *= curve
    audio[-fade_len:] *= curve[::-1]
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


def load_sample(path):
    sr, data = read(path)

    if data.ndim > 1:
        data = data.mean(axis=1)

    data = data.astype(np.float32)

    if np.max(np.abs(data)) > 0:
        data = data / np.max(np.abs(data))

    if sr != SAMPLE_RATE:
        old_indices = np.arange(len(data))
        new_length = int(len(data) * SAMPLE_RATE / sr)
        new_indices = np.linspace(0, len(data) - 1, new_length)
        data = np.interp(new_indices, old_indices, data)

    if len(data) < n:
        repeat = int(np.ceil(n / len(data)))
        data = np.tile(data, repeat)

    start = random.randint(0, max(0, len(data) - n))
    return normalize(data[start:start + n])


def pick_sample(category):
    folder = os.path.join(SAMPLES_DIR, category)

    if not os.path.exists(folder):
        return None

    files = [
        f for f in os.listdir(folder)
        if f.lower().endswith((".wav"))
    ]

    if not files:
        return None

    return os.path.join(folder, random.choice(files))


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
    thunder = np.zeros(n)

    for _ in range(max(1, DURATION // 60)):
        start = random.randint(0, max(1, n - SAMPLE_RATE * 8))
        length = random.randint(SAMPLE_RATE * 3, SAMPLE_RATE * 8)
        rumble = brown_noise()[:length]
        env = np.exp(-np.linspace(0, 7, length))
        thunder[start:start + length] += rumble * env

    return normalize(thunder)


def fireplace_layer():
    sample_path = pick_sample("fireplace")
    if sample_path:
        return load_sample(sample_path)

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

# quiet base bed
mix = add_layer(mix, brown_noise(), 0.08, delay=500, width=0.85)

if "brown_noise" in layers:
    mix = add_layer(mix, brown_noise(), 0.35, delay=450, width=0.85)

if "pink_noise" in layers:
    mix = add_layer(mix, pink_noise(), 0.30, delay=380, width=0.88)

if "rain" in layers:
    sample_path = pick_sample("rain")
    rain = load_sample(sample_path) if sample_path else procedural_rain()
    mix = add_layer(mix, rain, 0.65, delay=220, width=0.95)

if "ocean_waves" in layers:
    sample_path = pick_sample("ocean")
    ocean = load_sample(sample_path) if sample_path else procedural_ocean()
    mix = add_layer(mix, ocean, 0.65, delay=700, width=0.9)

if "soft_wind" in layers or "wind" in layers:
    sample_path = pick_sample("wind")
    wind = load_sample(sample_path) if sample_path else procedural_wind()
    mix = add_layer(mix, wind, 0.28, delay=900, width=0.82)

if "soft_thunder" in layers or "thunder" in layers:
    sample_path = pick_sample("thunder")
    thunder = load_sample(sample_path) if sample_path else thunder_layer()
    mix = add_layer(mix, thunder, 0.16, delay=1100, width=0.75)

if "fireplace" in layers:
    mix = add_layer(mix, fireplace_layer(), 0.45, delay=150, width=0.96)

if "river" in layers:
    sample_path = pick_sample("river")
    river = load_sample(sample_path) if sample_path else procedural_rain()
    mix = add_layer(mix, river, 0.55, delay=500, width=0.9)

# mastering
mix = normalize(mix, peak=0.85)
mix = soft_limiter(mix, drive=1.2)
mix = fade(mix, seconds=5)

file_path = os.path.join(AUDIO_DIR, "brown_noise.wav")
write(file_path, SAMPLE_RATE, mix.astype(np.float32))

print("Generated audio for:", idea.get("theme", "Unknown theme"))
print("Layers:", layers)
print("Saved audio at:", file_path)