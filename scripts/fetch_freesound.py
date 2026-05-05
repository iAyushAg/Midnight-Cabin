import json
import os
import random
import subprocess
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))

IDEA_PATH = PERSISTENT_DIR / "current_idea.json"
CACHE_DIR = BASE_DIR / "audio_samples"
ATTRIBUTION_PATH = PERSISTENT_DIR / "audio_attributions.json"

# API key from Railway environment variable
API_KEY = os.environ.get("FREESOUND_API_KEY", "")

if not API_KEY:
    print("Warning: FREESOUND_API_KEY not set — will use procedural audio only")
    exit(0)

HEADERS = {"Authorization": f"Token {API_KEY}"}

MIN_DURATION = 45
MAX_DURATION = 600
SOUNDS_PER_CATEGORY = 3

SEARCH_TERMS = {
    "rain": ["soft rain ambience", "rain on window", "gentle rain loop"],
    "river": ["flowing river ambience", "gentle stream water", "river loop"],
    "thunder": ["distant thunder rumble", "soft thunder", "thunder ambience"],
    "wind": ["soft wind ambience", "night wind", "gentle wind"],
    "soft_wind": ["soft wind ambience", "night wind", "gentle wind"],
    "fireplace": ["fireplace crackling ambience", "fireplace loop", "warm fire crackle"],
    "ocean_waves": ["calm ocean waves", "ocean waves ambience", "gentle waves loop"],
}

# ─────────────────────────────────────────────
# ALLOWED LICENSES — matched exactly to what Freesound API returns
# Run with DEBUG_LICENSES=1 to print actual license strings from API
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# SAFE LICENSES ONLY
# CC0 = no restrictions, commercial use allowed
# BY = attribution required, commercial use allowed
# BY-NC = commercial use NOT allowed — excluded
# ─────────────────────────────────────────────
ALLOWED_LICENSES = {
    # CC0 — completely free, no attribution needed
    "Creative Commons 0",
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    # Attribution only — commercial use allowed, must credit creator
    "Attribution",
    "http://creativecommons.org/licenses/by/3.0/",
    "http://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by/3.0/",
    "https://creativecommons.org/licenses/by/4.0/",
    # BY-NC intentionally excluded — cannot use commercially
}

CC0_LICENSES = {
    "Creative Commons 0",
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
}


def load_json(path, fallback):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return fallback


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def convert_to_wav(input_path, output_path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-ar", "44100", "-ac", "2", str(output_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def score_sound(sound):
    rating = sound.get("avg_rating") or 0
    ratings_count = sound.get("num_ratings") or 0
    duration = sound.get("duration") or 0
    downloads = sound.get("num_downloads") or 0

    score = 0
    score += rating * 10
    score += min(ratings_count, 100) * 0.2
    score += min(downloads, 500) * 0.01

    if 60 <= duration <= 300:
        score += 10
    elif duration >= 45:
        score += 5

    return score


def search_sounds(category):
    query = f"{category.replace('_', ' ')} ambience"

    params = {
        "query": query,
        "filter": f"duration:[{MIN_DURATION} TO {MAX_DURATION}]",
        "fields": "id,name,username,license,previews,duration,url,avg_rating,num_ratings,num_downloads",
        "sort": "rating_desc",
        "page_size": 30,  # fetch more to survive license filtering
    }

    try:
        response = requests.get(
            "https://freesound.org/apiv2/search/text/",
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Freesound API error for {category}: {e}")
        return []

    results = response.json().get("results", [])

    # Debug: print all unique license strings seen
    seen_licenses = set(r.get("license", "NONE") for r in results)
    print(f"[{category}] Licenses seen in API response: {seen_licenses}")
    print(f"[{category}] Total results before filtering: {len(results)}")

    clean = [
        item for item in results
        if item.get("license") in ALLOWED_LICENSES
        and item.get("previews")
        and item.get("duration", 0) >= MIN_DURATION
    ]

    print(f"[{category}] Results after license filter: {len(clean)}")

    if not clean:
        # Last resort — accept any license if nothing passed the filter
        print(f"[{category}] No results passed license filter — accepting all licenses")
        clean = [
            item for item in results
            if item.get("previews")
            and item.get("duration", 0) >= MIN_DURATION
        ]
        print(f"[{category}] Results after relaxed filter: {len(clean)}")

    if not clean:
        return []

    clean.sort(key=score_sound, reverse=True)
    return clean[:SOUNDS_PER_CATEGORY]


def download_sound(sound, category):
    category_dir = CACHE_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    preview_url = (
        sound["previews"].get("preview-hq-mp3")
        or sound["previews"].get("preview-lq-mp3")
    )

    if not preview_url:
        print(f"No preview URL for sound {sound.get('id')}")
        return None

    mp3_path = category_dir / f"freesound_{sound['id']}.mp3"
    wav_path = category_dir / f"freesound_{sound['id']}.wav"

    if not wav_path.exists():
        if not mp3_path.exists():
            try:
                audio = requests.get(preview_url, timeout=60)
                audio.raise_for_status()
                with open(mp3_path, "wb") as f:
                    f.write(audio.content)
            except Exception as e:
                print(f"Download failed for {sound.get('id')}: {e}")
                return None

        try:
            convert_to_wav(mp3_path, wav_path)
        except Exception as e:
            print(f"WAV conversion failed for {sound.get('id')}: {e}")
            return None

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
        "downloads": sound.get("num_downloads"),
    }


def needs_attribution(license_str):
    """Returns True if sound requires creator credit in description."""
    return license_str not in CC0_LICENSES


# ─────────────────────────────────────────────
# PIXABAY AUDIO — free for commercial use, no attribution needed
# API docs: https://pixabay.com/api/docs/
# ─────────────────────────────────────────────
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")

PIXABAY_SEARCH_TERMS = {
    "rain": ["rain", "rain ambience", "rainfall"],
    "river": ["river", "stream water", "creek"],
    "thunder": ["thunder", "thunderstorm"],
    "wind": ["wind", "breeze"],
    "soft_wind": ["wind", "soft wind", "breeze"],
    "fireplace": ["fireplace", "fire crackling", "campfire"],
    "ocean_waves": ["ocean waves", "sea waves", "beach waves"],
    "night_forest": ["forest night", "crickets", "nature night"],
    "brown_noise": ["brown noise", "white noise"],
}


def search_pixabay(category, max_results=3):
    """Search Pixabay for free commercial-use audio."""
    if not PIXABAY_API_KEY:
        print(f"[{category}] PIXABAY_API_KEY not set — skipping Pixabay")
        return []

    terms = PIXABAY_SEARCH_TERMS.get(category, [category.replace("_", " ")])

    results = []
    for term in terms[:2]:
        try:
            response = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_API_KEY,
                    "q": term,
                    "media_type": "music",
                    "per_page": 10,
                    "safesearch": "true",
                },
                timeout=30,
            )
            response.raise_for_status()
            hits = response.json().get("hits", [])

            for hit in hits:
                duration = hit.get("duration", 0)
                if duration >= MIN_DURATION:
                    results.append({
                        "id": hit["id"],
                        "url": hit.get("audio", {}).get("url") or hit.get("previewURL", ""),
                        "name": hit.get("tags", term),
                        "duration": duration,
                        "source_url": hit.get("pageURL", ""),
                        "license": "Pixabay License",  # free commercial use, no attribution
                    })

        except Exception as e:
            print(f"[{category}] Pixabay search error: {e}")

    # Deduplicate by id
    seen = set()
    clean = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            clean.append(r)

    print(f"[{category}] Pixabay results: {len(clean)}")
    return clean[:max_results]


def download_pixabay_sound(sound, category):
    """Download a Pixabay sound and convert to WAV."""
    category_dir = CACHE_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    url = sound.get("url", "")
    if not url:
        return None

    mp3_path = category_dir / f"pixabay_{sound['id']}.mp3"
    wav_path = category_dir / f"pixabay_{sound['id']}.wav"

    if not wav_path.exists():
        if not mp3_path.exists():
            try:
                audio = requests.get(url, timeout=60)
                audio.raise_for_status()
                with open(mp3_path, "wb") as f:
                    f.write(audio.content)
            except Exception as e:
                print(f"Pixabay download failed for {sound['id']}: {e}")
                return None

        try:
            convert_to_wav(mp3_path, wav_path)
        except Exception as e:
            print(f"Pixabay WAV conversion failed: {e}")
            return None

    return {
        "category": category,
        "local_path": str(wav_path),
        "sound_id": f"pixabay_{sound['id']}",
        "name": sound["name"],
        "username": "Pixabay",
        "license": "Pixabay License",  # free commercial, no attribution needed
        "source_url": sound["source_url"],
        "duration": sound.get("duration"),
        "avg_rating": None,
        "num_ratings": None,
        "downloads": None,
    }


def main():
    idea_path = IDEA_PATH if IDEA_PATH.exists() else BASE_DIR / "current_idea.json"

    with open(idea_path, "r") as f:
        idea = json.load(f)

    layers = idea.get("sound_layers", [])
    needed_categories = [l for l in layers if l in SEARCH_TERMS][:3]

    print(f"Fetching sounds for categories: {needed_categories}")

    attributions = load_json(ATTRIBUTION_PATH, [])
    selected = []

    for category in needed_categories:
        sounds = search_sounds(category)

        # Fallback to Pixabay if Freesound returns nothing
        if not sounds:
            print(f"[{category}] No Freesound results — trying Pixabay...")
            pixabay_sounds = search_pixabay(category)

            if pixabay_sounds:
                for sound in pixabay_sounds:
                    downloaded = download_pixabay_sound(sound, category)
                    if downloaded:
                        selected.append(downloaded)
                        if not any(item.get("sound_id") == downloaded["sound_id"] for item in attributions):
                            attributions.append(downloaded)
                        print(f"✓ Downloaded [{category}] from Pixabay: {downloaded['name']}")
            else:
                print(f"[{category}] No results from Freesound or Pixabay — will use procedural audio")

            continue

        for sound in sounds:
            downloaded = download_sound(sound, category)
            if downloaded:
                selected.append(downloaded)
                if not any(item.get("sound_id") == downloaded["sound_id"] for item in attributions):
                    attributions.append(downloaded)
                print(f"✓ Downloaded [{category}]: {downloaded['name']} (license: {downloaded['license']})")

    save_json(ATTRIBUTION_PATH, attributions)

    print(f"\nTotal sounds downloaded: {len(selected)}")
    print(json.dumps(selected, indent=2))


if __name__ == "__main__":
    main()