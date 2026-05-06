#!/usr/bin/env python3
"""Retention/audio/visual quality gate for Midnight Cabin renders.

This script catches content problems that hurt trust and retention before upload:
- missing video/audio streams
- wrong duration
- obvious loud peaks or too-quiet audio
- missing or low-quality visual assets
- Pollinations image too small
- black-screen visual prompts leaking into normal videos
- generated metadata promises that are too generic

It is intentionally conservative: hard failures stop broken uploads; softer issues are
warnings unless STRICT_QUALITY_GATE=1 is set.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PERSISTENT_DIR = Path(os.environ.get("PERSISTENT_DIR", "/data"))
REPORT_PATH = PERSISTENT_DIR / "quality_gate_report.json"
STRICT = os.environ.get("STRICT_QUALITY_GATE", "").lower() in {"1", "true", "yes"}


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def ffprobe_json(video_path):
    proc = run([
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        str(video_path),
    ])

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")

    return json.loads(proc.stdout)


def volumedetect(video_path, seconds):
    cmd = [
        "ffmpeg",
        "-v",
        "info",
        "-t",
        str(seconds),
        "-i",
        str(video_path),
        "-vn",
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]

    proc = run(cmd)
    text = proc.stderr + "\n" + proc.stdout

    mean = None
    maxv = None

    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
    if m:
        mean = float(m.group(1))

    m = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
    if m:
        maxv = float(m.group(1))

    return {
        "mean_volume_db": mean,
        "max_volume_db": maxv,
        "returncode": proc.returncode,
    }


def load_idea():
    for path in [PERSISTENT_DIR / "current_idea.json", BASE_DIR / "current_idea.json"]:
        if path.exists():
            with open(path) as f:
                return json.load(f)

    return {}


def load_visual_meta():
    path = PERSISTENT_DIR / "current_visual.json"

    if not path.exists():
        return {}

    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def contains_generic_title(title):
    title = (title or "").lower()

    generic = [
        "relaxing sleep sounds",
        "gentle rain and river",
        "deep sleep & relaxation",
        "ambient sounds for sleep",
        "sleep sounds for relaxation",
    ]

    return any(g in title for g in generic)


def inspect_bg_image(bg_path, errors, warnings, checks, video_type):
    if not bg_path.exists():
        return

    bg_size = bg_path.stat().st_size
    checks["bg_image_size_bytes"] = bg_size

    min_bg_size = int(os.environ.get("MIN_BG_IMAGE_BYTES", "500000"))
    checks["min_bg_image_bytes"] = min_bg_size

    if bg_size < min_bg_size:
        errors.append(
            f"Background image is too small / low quality: "
            f"{bg_size // 1024}KB. Minimum is {min_bg_size // 1024}KB."
        )

    try:
        from PIL import Image

        with Image.open(bg_path) as img:
            checks["bg_image_width"] = img.width
            checks["bg_image_height"] = img.height

            if img.width < 1280 or img.height < 720:
                errors.append(
                    f"Background image dimensions too small: {img.width}x{img.height}"
                )

            if video_type != "dark_screen" and (img.width < 1920 or img.height < 1080):
                warnings.append(
                    f"Background image is below preferred 1920x1080 source size: "
                    f"{img.width}x{img.height}"
                )

    except Exception as exc:
        warnings.append(f"Could not inspect background image dimensions: {exc}")


def inspect_visual_meta(visual_meta, errors, warnings, checks, video_type):
    if not visual_meta:
        warnings.append("No current_visual.json found; visual generation metadata unavailable.")
        return

    checks["visual_source"] = visual_meta.get("source")
    checks["visual_motion_style"] = visual_meta.get("motion_style")
    checks["visual_is_dark_screen"] = visual_meta.get("is_dark_screen")
    checks["visual_image_size_bytes"] = visual_meta.get("image_size_bytes")
    checks["visual_image_width"] = visual_meta.get("image_width")
    checks["visual_image_height"] = visual_meta.get("image_height")
    checks["visual_model"] = visual_meta.get("model")
    checks["pollinations_seed"] = visual_meta.get("pollinations_seed")
    checks["pollinations_attempt"] = visual_meta.get("pollinations_attempt")

    if visual_meta.get("source") == "pollinations":
        image_size = int(visual_meta.get("image_size_bytes") or 0)
        min_size = int(
            visual_meta.get("min_image_bytes")
            or os.environ.get("MIN_BG_IMAGE_BYTES", "500000")
        )

        if image_size and image_size < min_size:
            errors.append(
                f"Pollinations image failed size requirement: "
                f"{image_size // 1024}KB < {min_size // 1024}KB."
            )

        width = int(visual_meta.get("image_width") or 0)
        height = int(visual_meta.get("image_height") or 0)

        if width and height and (width < 1280 or height < 720):
            errors.append(f"Pollinations image dimensions too small: {width}x{height}")

    if video_type != "dark_screen":
        prompt = (visual_meta.get("prompt") or "").lower()

        blackscreen_phrases = [
            "true black screen after 10 seconds",
            "black screen after 10 seconds",
            "screen stays black",
        ]

        if any(p in prompt for p in blackscreen_phrases):
            errors.append("Non-dark-screen video contains black-screen visual prompt.")

        motion_style = visual_meta.get("motion_style", "")
        has_animation = bool(visual_meta.get("has_animation"))

        if not has_animation and motion_style != "ffmpeg_procedural_motion":
            warnings.append(
                "No AI animation found. This is acceptable only if FFmpeg procedural motion is enabled."
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=str(BASE_DIR / "output" / "video.mp4"))
    parser.add_argument(
        "--type",
        default="main",
        choices=["main", "dark_screen", "adhd", "study_with_me", "short"],
    )
    parser.add_argument("--expected-minutes", type=int, default=0)
    parser.add_argument(
        "--sample-seconds",
        type=int,
        default=int(os.environ.get("QUALITY_SAMPLE_SECONDS", "300")),
    )

    args = parser.parse_args()

    video_path = Path(args.video)
    idea = load_idea()
    visual_meta = load_visual_meta()

    errors = []
    warnings = []

    checks = {
        "video": str(video_path),
        "type": args.type,
        "strict": STRICT,
    }

    # ─────────────────────────────────────────
    # Media container checks
    # ─────────────────────────────────────────
    if not video_path.exists():
        errors.append(f"Rendered file missing: {video_path}")
    else:
        try:
            data = ffprobe_json(video_path)
            streams = data.get("streams", [])
            fmt = data.get("format", {})

            duration = float(fmt.get("duration", 0) or 0)
            checks["duration_seconds"] = round(duration, 2)
            checks["size_bytes"] = int(fmt.get("size", 0) or 0)

            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            has_video = any(s.get("codec_type") == "video" for s in streams)

            checks["has_audio"] = has_audio
            checks["has_video"] = has_video

            if not has_audio:
                errors.append("No audio stream found.")

            if not has_video:
                errors.append("No video stream found.")

            if args.expected_minutes:
                expected = args.expected_minutes * 60
                checks["expected_seconds"] = expected

                if duration < expected * 0.97:
                    errors.append(
                        f"Video is too short: {duration:.0f}s vs expected {expected}s."
                    )

            if checks["size_bytes"] < 500_000:
                errors.append("Rendered file is suspiciously small.")

        except Exception as exc:
            errors.append(f"Could not inspect media: {exc}")

    # ─────────────────────────────────────────
    # Audio loudness checks
    # ─────────────────────────────────────────
    if video_path.exists() and not errors:
        vd = volumedetect(video_path, max(30, args.sample_seconds))
        checks.update(vd)

        mean = vd.get("mean_volume_db")
        maxv = vd.get("max_volume_db")

        if maxv is None:
            warnings.append("Could not read max volume; manually listen before upload.")
        else:
            if maxv > -0.2:
                errors.append(f"Audio peak is too close to clipping ({maxv} dB).")
            elif maxv > -1.0:
                warnings.append(f"Audio peak is high for sleep ambience ({maxv} dB).")

        if mean is not None:
            if mean > -10:
                warnings.append(
                    f"Average volume may be too loud for sleep ambience ({mean} dB)."
                )
            elif mean < -38:
                warnings.append(f"Average volume may be too quiet ({mean} dB).")

    # ─────────────────────────────────────────
    # Title / idea quality checks
    # ─────────────────────────────────────────
    title = idea.get("title", "")
    checks["title"] = title

    if args.type == "main":
        if contains_generic_title(title):
            warnings.append(
                "Title still looks generic; consider a more specific scene-first title."
            )

        if "|" not in title:
            warnings.append(
                "Title does not use the scene-first packaging pattern with separators."
            )

        if not idea.get("unique_angle"):
            warnings.append("Idea is missing unique_angle; description may feel generic.")

        if not idea.get("first_30_seconds"):
            warnings.append(
                "Idea is missing first_30_seconds; opening experience is undefined."
            )

        if not idea.get("retention_hook"):
            warnings.append(
                "Idea is missing retention_hook; long-play promise is undefined."
            )

    # ─────────────────────────────────────────
    # Visual quality checks
    # ─────────────────────────────────────────
    bg = BASE_DIR / "video" / "bg.jpg"
    bg_anim = BASE_DIR / "video" / "bg_animated.mp4"

    if not bg.exists() and not bg_anim.exists():
        errors.append("No background image or animated visual found.")

    inspect_bg_image(bg, errors, warnings, checks, args.type)
    inspect_visual_meta(visual_meta, errors, warnings, checks, args.type)

    # ─────────────────────────────────────────
    # Write report
    # ─────────────────────────────────────────
    report = {
        "passed": not errors and not (STRICT and warnings),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }

    PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print("Quality gate report:")
    print(json.dumps(report, indent=2))

    if errors or (STRICT and warnings):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())