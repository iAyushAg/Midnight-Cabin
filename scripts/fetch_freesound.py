import json
import os
import random
import subprocess
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
IDEA_PATH = BASE_DIR / "current_idea.json"
CACHE_DIR = BASE_DIR / "audio_samples"
ATTRIBUTION_PATH = BASE_DIR / "audio_attributions.json"

API_KEY = os.environ.get("FREESOUND_API_KEY")

if not API_KEY:
    raise RuntimeError("Missing FREESOUND_API_KEY environment variable")

HEADERS = {
    "Authorization": f"Token {API_KEY}"
}

SEARCH_TERMS = {
    "rain": ["soft rain ambience", "rain on window", "gentle rain loop"],
    "river": ["flowing river ambience", "gentle stream water", "river loop"],
    "thunder": ["distant thunder rumble", "soft thunder", "thunder ambience"],
    "wind": ["soft wind ambience", "night wind", "gentle wind"],
    "soft_wind": ["soft wind ambience", "night wind", "gentle wind"],
    "fireplace": ["fireplace crackling ambience", "fireplace loop", "warm fire crackle"],
    "ocean_waves": ["calm ocean waves", "ocean waves ambience", "gentle waves loop"],
}

ALLOWED_LICENSES = {
    "Creative Commons 0"
}


def load_json(path, fallback):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return fallback


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def search_sound(category):
    query = random.choice(SEARCH_TERMS.get(category, [category]))

    params = {
        "query": query,
        "filter": 'license:"Creative Commons 0" duration:[30 TO 600]',
        "fields": "id,name,username,license,previews,duration,url,avg_rating,num_ratings",
        "sort": "rating_desc",
        "page_size": 10,
    }

    response = requests.get(
        "https://freesound.org/apiv2/search/text/",
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    results = [
        item for item in results
        if item.get("license") in ALLOWED_LICENSES
        and item.get("previews")
    ]

    if not results:
        return None

    return random.choice(results[:5])


def convert_to_wav(input_path, output_path):
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ar",
        "44100",
        "-ac",
        "2",
        str(output_path),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def download_sound(sound, category):
    category_dir = CACHE_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    preview_url = (
        sound["previews"].get("preview-hq-mp3")
        or sound["previews"].get("preview-lq-mp3")
    )

    if not preview_url:
        return None

    mp3_path = category_dir / f"freesound_{sound['id']}.mp3"
    wav_path = category_dir / f"freesound_{sound['id']}.wav"

    if not wav_path.exists():
        if not mp3_path.exists():
            audio_response = requests.get(preview_url, timeout=60)
            audio_response.raise_for_status()

            with open(mp3_path, "wb") as f:
                f.write(audio_response.content)

        convert_to_wav(mp3_path, wav_path)

    return {
        "category": category,
        "local_path": str(wav_path),
        "sound_id": sound["id"],
        "name": sound["name"],
        "username": sound["username"],
        "license": sound["license"],
        "source_url": sound["url"],
        "duration": sound.get("duration"),
        "avg_rating": sound.get("avg_rating"),
        "num_ratings": sound.get("num_ratings"),
    }


def main():
    with open(IDEA_PATH, "r") as f:
        idea = json.load(f)

    layers = idea.get("sound_layers", [])

    needed_categories = [
        layer for layer in layers
        if layer in SEARCH_TERMS
    ]

    needed_categories = needed_categories[:2]

    attributions = load_json(ATTRIBUTION_PATH, [])
    selected = []

    for category in needed_categories:
        sound = search_sound(category)

        if not sound:
            print(f"No CC0 Freesound result found for: {category}")
            continue

        downloaded = download_sound(sound, category)

        if downloaded:
            selected.append(downloaded)

            if not any(
                item.get("sound_id") == downloaded["sound_id"]
                for item in attributions
            ):
                attributions.append(downloaded)

            print(f"Downloaded {category}: {downloaded['name']}")

    save_json(ATTRIBUTION_PATH, attributions)

    print("Freesound selected:")
    print(json.dumps(selected, indent=2))


if __name__ == "__main__":
    main()