"""
Shared YouTube utilities:
- generate_chapters(): creates timestamps for video description
- get_full_tags(): builds 15 tags hitting all keyword angles
- pin_comment(): pins a comment on a video
- post_community_update(): posts to Community tab
"""
import os
import json


def get_sound_attributions(persistent_dir):
    """Read audio_attributions.json and return credits for BY-licensed sounds."""
    import json, os

    attr_path = os.path.join(persistent_dir, "audio_attributions.json")
    if not os.path.exists(attr_path):
        return ""

    with open(attr_path) as f:
        attributions = json.load(f)

    cc0_licenses = {
        "Creative Commons 0",
        "http://creativecommons.org/publicdomain/zero/1.0/",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    }

    # Only credit sounds that require attribution (BY license)
    # CC0 and Pixabay License need no attribution
    no_attribution_needed = cc0_licenses | {"Pixabay License"}

    credits = []
    seen = set()
    for item in attributions:
        sound_id = item.get("sound_id")
        license_str = item.get("license", "")
        if license_str not in no_attribution_needed and sound_id not in seen:
            seen.add(sound_id)
            name = item.get("name", "Unknown")
            username = item.get("username", "Unknown")
            url = item.get("source_url", "")
            credits.append(f'• "{name}" by {username} — {url} (CC BY)')

    if not credits:
        return ""

    return "\U0001f3b5 Sound Credits (CC Attribution License):\n" + "\n".join(credits)


def get_ai_disclosure():
    """Returns AI content disclosure text required by YouTube policy."""
    return "ℹ️ This soundscape was created with AI-assisted audio generation and composition tools."


def generate_chapters(duration_minutes, sound_layers, primary):
    """Generate chapter timestamps for a sleep/ambient video."""
    chapters = ["0:00 Intro — Sound begins"]

    if duration_minutes >= 60:
        # Add atmosphere chapters
        if "rain" in sound_layers:
            chapters.append("0:05 Gentle rain settles in")
            chapters.append("15:00 Deep rain phase")
        elif "fireplace" in sound_layers:
            chapters.append("0:05 Fireplace crackles begin")
            chapters.append("15:00 Deep warmth phase")
        elif "brown_noise" in sound_layers:
            chapters.append("0:05 Brown noise deepens")
            chapters.append("15:00 Full focus phase")
        else:
            chapters.append("0:05 Ambience settles in")
            chapters.append("15:00 Deep phase begins")

        chapters.append("30:00 Sustained sleep depth")

    if duration_minutes >= 120:
        chapters.append("1:00:00 Midnight ambience")

    if duration_minutes >= 180:
        chapters.append("2:00:00 Deep night")
        chapters.append("3:00:00 Pre-dawn stillness")

    if duration_minutes >= 300:
        chapters.append("5:00:00 Early morning calm")

    if duration_minutes >= 480:
        chapters.append("8:00:00 Dawn approaches")

    if duration_minutes >= 600:
        chapters.append("10:00:00 Final hour")

    return "\n".join(chapters)


def get_full_tags(primary, layers, duration_label, video_type="main"):
    """Build comprehensive tag list up to 500 characters."""

    base = [
        "sleep sounds",
        "ambient sounds",
        "relaxing sounds",
        "deep sleep sounds",
        "deep sleep sounds",
        f"{duration_label.lower()} sleep",
        f"{duration_label.lower()} ambient",
    ]

    theme_tags = {
        "rain": [
            "rain sounds",
            "rain sounds for sleep",
            f"rain sounds {duration_label.lower()}",
            "rain sounds for sleep",
            "rain sleep sounds",
            "rainy night ambience",
            "rain asmr",
        ],
        "river": [
            "river sounds",
            "river sounds for sleep",
            "flowing river ambience",
            "stream sounds sleep",
            "nature water sounds",
        ],
        "fireplace": [
            "fireplace sounds",
            "crackling fire sleep",
            "cozy fireplace ambience",
            "fireplace asmr",
            "fire sounds sleep",
        ],
        "ocean_waves": [
            "ocean sounds",
            "ocean waves sleep",
            "wave sounds relaxing",
            "beach ambience sleep",
            "ocean asmr",
        ],
        "soft_wind": [
            "wind sounds sleep",
            "wind ambience",
            "soft wind sounds",
            "night wind ambience",
        ],
        "night_forest": [
            "forest sounds sleep",
            "forest ambience",
            "nature sounds sleep",
            "night forest sounds",
        ],
        "brown_noise": [
            "brown noise",
            "brown noise sleep",
            "brown noise focus",
            "brown noise ADHD",
            f"brown noise {duration_label.lower()}",
        ],
    }

    type_tags = {
        "adhd": ["ADHD focus", "ADHD brown noise", "focus music ADHD", "concentration music", "deep work music"],
        "dark_screen": ["dark screen", "black screen sleep", "dark screen sounds", "screen off sleep"],
        "study_with_me": ["study with me", "pomodoro timer", "study session", "focus timer", "study music"],
        "main": ["deep sleep", "white noise", "brown noise", "nature sounds"],
    }

    extra = theme_tags.get(primary, [])
    type_extra = type_tags.get(video_type, type_tags["main"])

    all_tags = base + extra + type_extra
    all_tags = list(dict.fromkeys(all_tags))  # deduplicate

    # Trim to stay under 500 chars total
    final = []
    total_chars = 0
    for tag in all_tags:
        if total_chars + len(tag) + 2 <= 490:
            final.append(tag)
            total_chars += len(tag) + 2
        if len(final) >= 15:
            break

    return final



# ─────────────────────────────────────────────
# CONTENT PACKAGING / MONETIZATION HELPERS
# ─────────────────────────────────────────────

# Hardcoded Midnight Cabin playlist IDs.
# These are used immediately after upload to place each video in the relevant playlists.
PLAYLISTS = {
    "deep_sleep": "PL1C0d7IpxX4s5ZUMMTZShPiEdcc7_mY6k",
    "dark_screen": "PL1C0d7IpxX4tlvxdvXDlQmIHhs0VwxEKi",
    "brown_noise_adhd": "PL1C0d7IpxX4urDAwNHXeOWiow5xOTsye3",
    "study_music": "PL1C0d7IpxX4vaGtoLf3zbjOTSIjY_cWVE",
    "focus_study": "PL1C0d7IpxX4voVewbgJZoQjizPugYaM0n",
}


def _add_playlist(ids, seen, playlist_key):
    """Append a known playlist ID once, preserving order."""
    playlist_id = PLAYLISTS.get(playlist_key, "")
    if playlist_id and playlist_id not in seen:
        ids.append(playlist_id)
        seen.add(playlist_id)

def get_production_note(video_type="main", is_flagship=False):
    """Human-curation signal for descriptions and comments."""
    prefix = "Flagship production note" if is_flagship else "Production note"
    if video_type == "dark_screen":
        body = "This dark-screen soundscape is reviewed for steady volume, smooth looping, no vocals, no visual distractions, and no sudden sounds for overnight playback."
    elif video_type == "study_with_me":
        body = "This focus session is reviewed for steady background sound, timer readability, no vocals, and low-distraction pacing for long work blocks."
    elif video_type == "adhd":
        body = "This focus soundscape is reviewed for stable low-frequency texture, no sudden transitions, and a steady background that many listeners prefer for concentration."
    else:
        body = "This soundscape is reviewed for steady volume, smooth loops, no vocals, no sudden sounds, and overnight listening comfort."
    return f"{prefix}:\n{body}"


def get_quality_summary(idea=None):
    """Short visible promise that reinforces the listening experience."""
    idea = idea or {}
    first = idea.get("first_30_seconds", "Gentle fade-in, clear atmosphere, and no sudden sounds.")
    hook = idea.get("retention_hook", "Stable, low-distraction ambience for long listening sessions.")
    unique = idea.get("unique_angle", "A specific scene and sound mix rather than a generic ambient loop.")
    return (
        "Why this one is different:\n"
        f"• Scene: {unique}\n"
        f"• First 30 seconds: {first}\n"
        f"• Long-play reason: {hook}"
    )


def get_playlist_ids_for_idea(idea, video_type="main"):
    """Return the hardcoded Midnight Cabin playlist IDs relevant to this upload.

    Mapping:
    - Normal sleep ambience -> Deep Sleep Sound
    - Dark-screen uploads -> Dark Screen + Deep Sleep Sound
    - Brown-noise / ADHD uploads -> Brownnoise for ADHD + Focus & Study
    - Study uploads -> Study Music + Focus & Study
    - Any long/focus/brown-noise crossover can be added to multiple relevant playlists.
    """
    idea = idea or {}
    layers = set(idea.get("sound_layers", []) or [])
    primary = idea.get("audio_strategy", {}).get("primary_category", "")
    title_blob = " ".join([
        str(idea.get("title", "")),
        str(idea.get("theme", "")),
        str(idea.get("visual", "")),
        " ".join(str(layer) for layer in layers),
    ]).lower()

    ids = []
    seen = set()

    is_brown_noise = primary == "brown_noise" or "brown_noise" in layers or "brown noise" in title_blob
    is_focus = any(term in title_blob for term in [
        "focus", "study", "work", "productivity", "pomodoro", "adhd", "concentration", "deep work"
    ])

    if video_type == "dark_screen" or "dark screen" in title_blob or "black screen" in title_blob:
        _add_playlist(ids, seen, "dark_screen")
        _add_playlist(ids, seen, "deep_sleep")
    elif video_type == "study_with_me":
        _add_playlist(ids, seen, "study_music")
        _add_playlist(ids, seen, "focus_study")
    elif video_type == "adhd":
        _add_playlist(ids, seen, "brown_noise_adhd")
        _add_playlist(ids, seen, "focus_study")
    else:
        # Default long ambience uploads belong in the main sleep playlist.
        _add_playlist(ids, seen, "deep_sleep")

    # Add crossover playlists when the content clearly matches them.
    if is_brown_noise:
        _add_playlist(ids, seen, "brown_noise_adhd")
    if is_focus:
        _add_playlist(ids, seen, "focus_study")

    # Safety fallback: every uploaded video gets at least one playlist.
    if not ids:
        _add_playlist(ids, seen, "deep_sleep")

    return ids

def add_video_to_playlists(youtube, video_id, playlist_ids):
    """Add a video to multiple playlists. Non-fatal per playlist."""
    added = []
    for playlist_id in playlist_ids:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            print(f"Added to playlist: {playlist_id}")
            added.append(playlist_id)
        except Exception as e:
            print(f"Playlist assignment failed for {playlist_id} (non-fatal): {e}")
    return added

def pin_comment(youtube, video_id, primary, duration_label, sound_layers, idea=None, video_type="main"):
    """Post a community-building pinned comment that creates cabin lore and drives engagement."""

    idea = idea or {}

    # Welcome to the cabin — builds identity, drives comments, creates community
    CABIN_COMMENTS = {
        "rain": (
            "Welcome to the cabin. 🌧️\n\n"
            "The rain started about an hour ago and hasn't let up. "
            "Door's locked, fire's optional, phone's face-down.\n\n"
            f"{duration_label} of steady rain. No talking, no music, no sudden sounds.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "fireplace": (
            "Welcome to the cabin. 🔥\n\n"
            "Fire's been going since dusk. "
            "There's nowhere you need to be and nothing that can't wait until morning.\n\n"
            f"{duration_label} of warmth. No talking, no music, no sudden sounds.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "brown_noise": (
            "Welcome to the cabin. 🧠\n\n"
            "Brown noise is playing. "
            "If you're here because your brain won't stop — you're in the right place. "
            "Best at low-to-medium volume, filling the room, not filling your ears.\n\n"
            f"{duration_label} of steady focus sound.\n\n"
            "Drop a 🕯️ if you're studying or it's past midnight."
        ),
        "river": (
            "Welcome to the cabin. 🌊\n\n"
            "There's a river about 40 feet from the door. "
            "You can hear it from the bedroom. It's been sounding like this for a thousand years.\n\n"
            f"{duration_label} of steady water. No talking, no music.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "ocean_waves": (
            "Welcome to the cabin. 🌊\n\n"
            "The cabin is close enough to the water that you can hear it from bed. "
            "Waves arrive, fade, return. They've been doing this since before sleep was a thing people worried about.\n\n"
            f"{duration_label} of steady waves. No talking, no music.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "thunder": (
            "Welcome to the cabin. ⛈️\n\n"
            "Storm rolled in around midnight. "
            "Big one. The kind where you're genuinely relieved to be inside.\n\n"
            f"{duration_label} of storm sounds. No talking, no music, no sudden sounds.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "soft_wind": (
            "Welcome to the cabin. 🍃\n\n"
            "Quiet night. Just wind moving through the trees. "
            "Nothing is waiting, nothing is urgent, nothing needs you until morning.\n\n"
            f"{duration_label} of soft wind. No talking, no music.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
        "night_forest": (
            "Welcome to the cabin. 🌲\n\n"
            "Deep in the forest tonight. "
            "Crickets, wind in the canopy, occasional distant things that are absolutely fine. "
            "Your nervous system knows the difference between forest sounds and danger.\n\n"
            f"{duration_label} of forest ambience. No talking, no music.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        ),
    }

    # Pick the most relevant comment based on primary sound
    comment = CABIN_COMMENTS.get(primary)
    if not comment:
        # Fallback for any unlisted primary
        for layer in sound_layers:
            if layer in CABIN_COMMENTS:
                comment = CABIN_COMMENTS[layer]
                break

    if not comment:
        comment = (
            "Welcome to the cabin. 🌙\n\n"
            "Whatever brought you here tonight — you're in the right place. "
            f"{duration_label} of steady ambient sound. No talking, no music, no sudden sounds.\n\n"
            "Drop a 🕯️ if you're here late tonight."
        )

    try:
        response = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment
                        }
                    }
                }
            }
        ).execute()

        comment_id = response["id"]
        print(f"Cabin welcome comment posted: {comment_id}")
        print(f"⚠️  Pin this comment manually in YouTube Studio:")
        print(f"   https://studio.youtube.com/video/{video_id}/comments")
        print(f"   Click ⋮ on your comment → Pin comment")
        return comment_id

    except Exception as e:
        print(f"Pin comment failed (non-fatal): {e}")
        return None

def post_community_update(youtube, video_id, title, primary, duration_label):
    """
    Community posts via YouTube API require Partner Program access.
    Instead, we send the post content via Telegram so you can copy-paste it manually.
    """
    import os, random, requests as _req

    emoji_map = {
        "rain": "🌧️", "river": "🌊", "fireplace": "🔥",
        "ocean_waves": "🌊", "soft_wind": "🍃",
        "night_forest": "🌲", "brown_noise": "🧠",
    }
    emoji = emoji_map.get(primary, "🌙")

    hooks = [
        f"{emoji} New {duration_label} ambient just dropped — perfect for tonight. No talking, no music, no sudden sounds.\n\n▶️ youtu.be/{video_id}",
        f"New upload: {title}\n\n{emoji} {duration_label} of pure ambient sound. Let it play while you sleep, study, or just decompress.\n\n▶️ youtu.be/{video_id}\n\n💛 Support the cabin: ko-fi.com/midnightcabins",
        f"{emoji} Can't sleep? Can't focus? Try this.\n\n{title}\n\n{duration_label} of pure {primary.replace('_', ' ')} sounds — no talking, no music.\n\n▶️ youtu.be/{video_id}",
    ]
    post_text = random.choice(hooks)

    # Send to Telegram for manual posting to Community tab
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id:
        try:
            msg = f"📢 Community tab post (copy-paste this):\n\n{post_text}"
            _req.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": msg},
                timeout=10
            )
            print("Community post content sent to Telegram")
        except Exception as e:
            print(f"Telegram community post send failed: {e}")


def send_upload_checklist(video_id, title, video_type="main"):
    """Send a 3-action post-upload checklist to Telegram after every video upload.

    End screens and cards cannot be added via the YouTube Data API -- they require
    YouTube Studio. This reminder goes to your phone so you can do the 2-min step.
    """
    import os, requests as _req

    playlist_hint = {
        "main":         "Deep Sleep Sounds",
        "adhd":         "Brown Noise for ADHD and Focus",
        "dark_screen":  "Deep Sleep Sounds",
        "study_with_me":"Study Music - No Distraction",
    }.get(video_type, "Deep Sleep Sounds")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("Telegram not configured -- skipping upload checklist")
        return

    msg = (
        f"New {video_type} video uploaded!\n"
        f"{title[:60]}\n"
        f"https://youtu.be/{video_id}\n\n"
        f"3 ACTIONS (takes 2 min):\n\n"
        f"1) PIN COMMENT:\n"
        f"   studio.youtube.com/video/{video_id}/comments\n"
        f"   Click the cabin welcome comment then Pin\n\n"
        f"2) ADD END SCREEN (drives subs + watch time):\n"
        f"   studio.youtube.com/video/{video_id}/edit\n"
        f"   End screen > Subscribe button + Best video\n\n"
        f"3) ADD CARD at 20-min mark:\n"
        f"   Cards > Link to '{playlist_hint}' playlist"
    )
    try:
        _req.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": msg},
            timeout=10
        )
        print("Upload checklist sent to Telegram")
    except Exception as e:
        print(f"Telegram checklist send failed (non-fatal): {e}")
