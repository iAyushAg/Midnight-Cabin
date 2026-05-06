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
        "uninterrupted sleep",
        "no interruptions",
        f"{duration_label.lower()} sleep",
        f"{duration_label.lower()} ambient",
    ]

    theme_tags = {
        "rain": [
            "rain sounds",
            "rain sounds for sleep",
            f"rain sounds {duration_label.lower()}",
            "rain sounds uninterrupted",
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


def pin_comment(youtube, video_id, primary, duration_label, sound_layers):
    """Post and pin a comment on the video."""

    # Build comment based on theme
    if "rain" in sound_layers:
        comment = f"🌧️ The rain builds gradually over the first 10 minutes — let it wash everything away. {duration_label} of pure sleep sound, no mid-roll interruptions and no sudden sounds. Sleep well 🌙"
    elif "fireplace" in sound_layers:
        comment = f"🔥 The fire crackles gently throughout — imagine you're in a cozy cabin far from everything. {duration_label} of warmth, no sudden sounds. Sleep well 🌙"
    elif "brown_noise" in primary:
        comment = f"🧠 Brown noise works best at low-medium volume — let it fill the room, not overwhelm it. {duration_label} of pure focus/sleep sound. No sudden sounds 🌙"
    elif "river" in sound_layers:
        comment = f"🌊 The river flows steadily throughout — consistent, calming, uninterrupted. {duration_label} of nature sound. No sudden sounds 🌙"
    else:
        comment = f"🌙 Let this play quietly in the background — {duration_label} of uninterrupted ambient sound. No mid-roll interruptions, no sudden sounds. Sleep well ✨"

    try:
        # Post comment
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
        print(f"Comment posted: {comment_id}")
        print(f"⚠️  Pin this comment manually in YouTube Studio — API pinning is not supported")
        print(f"   Go to: https://studio.youtube.com/video/{video_id}/comments")
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
        f"{emoji} New {duration_label} ambient just dropped — perfect for tonight. No mid-roll interruptions, no sudden sounds.\n\n▶️ youtu.be/{video_id}",
        f"New upload: {title}\n\n{emoji} {duration_label} of pure ambient sound. Let it play while you sleep, study, or just decompress.\n\n▶️ youtu.be/{video_id}",
        f"{emoji} Can't sleep? Can't focus? Try this.\n\n{duration_label} of uninterrupted {primary.replace('_', ' ')} sounds — no mid-roll interruptions.\n\n▶️ youtu.be/{video_id}",
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