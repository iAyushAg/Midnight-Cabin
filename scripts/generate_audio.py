import os
import json
import numpy as np
from scipy.io.wavfile import write

sample_rate = 44100
duration = 30  # test first; later use 60 * 60 or 60 * 180

os.makedirs("audio", exist_ok=True)

with open("current_idea.json", "r") as f:
    idea = json.load(f)

layers = idea["sound_layers"]

audio = np.zeros(sample_rate * duration)

def brown_noise():
    white = np.random.normal(0, 1, sample_rate * duration)
    brown = np.cumsum(white)
    return brown / np.max(np.abs(brown))

def pinkish_noise():
    white = np.random.normal(0, 1, sample_rate * duration)
    smooth = np.convolve(white, np.ones(1000)/1000, mode="same")
    return smooth / np.max(np.abs(smooth))

def soft_pulses(speed=3):
    t = np.linspace(0, duration, sample_rate * duration)
    return 0.2 * np.sin(2 * np.pi * speed * t)

if "brown_noise" in layers:
    audio += 0.7 * brown_noise()

if "pink_noise" in layers:
    audio += 0.5 * pinkish_noise()

if "rain" in layers:
    audio += 0.25 * np.random.normal(0, 1, sample_rate * duration)

if "soft_thunder" in layers:
    audio += 0.8 * soft_pulses(0.5)

if "ocean_waves" in layers:
    audio += 0.25 * soft_pulses(0.08) + 0.2 * brown_noise()

if "soft_wind" in layers:
    audio += 0.25 * pinkish_noise()

if "fireplace" in layers:
    crackle = np.random.choice([0, 1], size=sample_rate * duration, p=[0.995, 0.005])
    audio += 0.4 * crackle * np.random.normal(0, 1, sample_rate * duration)

if "night_forest" in layers:
    audio += 0.05 * soft_pulses(8)

audio = audio / np.max(np.abs(audio))
write("audio/brown_noise.wav", sample_rate, audio.astype(np.float32))

print("Generated audio for:", idea["theme"])