import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests as http_requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
HISTORY_FILE = os.path.join(BASE_DIR, "video_history.json")
AB_LOG_PATH = os.path.join(BASE_DIR, "thumbnail_ab_log.json")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
REPORT_EMAIL = os.environ.get("REPORT_EMAIL")

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

youtube = build("youtube", "v3", credentials=creds)

with open(HISTORY_FILE, "r") as f:
    history = json.load(f)

# ─────────────────────────────────────────────
# UPDATE STATS FOR ALL VIDEOS
# ─────────────────────────────────────────────
for item in history:
    video_id = item.get("video_id")
    if not video_id:
        continue

    try:
        response = youtube.videos().list(
            part="statistics,status",
            id=video_id
        ).execute()

        videos = response.get("items", [])
        if not videos:
            continue

        stats = videos[0].get("statistics", {})
        status = videos[0].get("status", {})

        views = int(stats.get("viewCount", 0))
        impressions = int(stats.get("favoriteCount", 0)) or 1  # fallback; real impressions need Analytics API

        item["performance"] = {
            "views": views,
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "privacy_status": status.get("privacyStatus")
        }

    except Exception as e:
        print(f"Could not fetch stats for {video_id}: {e}")

# ─────────────────────────────────────────────
# UPDATE A/B CTR LOG
# Uses views as proxy for CTR (real CTR needs YouTube Analytics API OAuth scope)
# ─────────────────────────────────────────────
ab_log = []
if os.path.exists(AB_LOG_PATH):
    with open(AB_LOG_PATH) as f:
        ab_log = json.load(f)

existing_video_ids = {entry["video_id"] for entry in ab_log if "video_id" in entry}

for item in history:
    video_id = item.get("video_id")
    variant = item.get("thumbnail_variant")
    views = item.get("performance", {}).get("views", 0)

    if not video_id or not variant or video_id in existing_video_ids:
        continue

    # Use views-per-day as CTR proxy until Analytics API scope is added
    uploaded_at = item.get("uploaded_at", "")
    try:
        age_days = max((datetime.now() - datetime.fromisoformat(uploaded_at)).days, 1)
    except Exception:
        age_days = 1

    ctr_proxy = views / age_days

    ab_log.append({
        "video_id": video_id,
        "variant": variant,
        "ctr": round(ctr_proxy, 2),
        "views": views,
        "logged_at": datetime.now().isoformat()
    })

with open(AB_LOG_PATH, "w") as f:
    json.dump(ab_log, f, indent=2)

with open(HISTORY_FILE, "w") as f:
    json.dump(history, f, indent=2)

print("Updated video stats")

# ─────────────────────────────────────────────
# DAILY PERFORMANCE SUMMARY
# Only send once per day — check if already sent today
# ─────────────────────────────────────────────
SUMMARY_SENT_PATH = os.path.join(BASE_DIR, ".last_summary_date")

today_str = datetime.now().strftime("%Y-%m-%d")
last_sent = ""
if os.path.exists(SUMMARY_SENT_PATH):
    with open(SUMMARY_SENT_PATH) as f:
        last_sent = f.read().strip()

if last_sent == today_str:
    print("Summary already sent today, skipping")
    exit()

# Build summary
total_views = sum(v.get("performance", {}).get("views", 0) for v in history)
total_videos = len(history)

recent_7_days = [
    v for v in history
    if v.get("uploaded_at", "") >= (datetime.now() - timedelta(days=7)).isoformat()
]
recent_views = sum(v.get("performance", {}).get("views", 0) for v in recent_7_days)

top_video = max(history, key=lambda v: v.get("performance", {}).get("views", 0), default=None)
top_title = top_video.get("title", "N/A") if top_video else "N/A"
top_views = top_video.get("performance", {}).get("views", 0) if top_video else 0

ab_a = [e["ctr"] for e in ab_log if e.get("variant") == "A"]
ab_b = [e["ctr"] for e in ab_log if e.get("variant") == "B"]
avg_a = round(sum(ab_a) / len(ab_a), 1) if ab_a else 0
avg_b = round(sum(ab_b) / len(ab_b), 1) if ab_b else 0

summary_lines = [
    f"🌙 Midnight Cabin Daily Report — {today_str}",
    f"",
    f"📊 Channel Overview",
    f"  Total videos: {total_videos}",
    f"  Total views: {total_views:,}",
    f"  Views (last 7 days): {recent_views:,}",
    f"",
    f"🏆 Top Video",
    f"  {top_title}",
    f"  Views: {top_views:,}",
    f"",
    f"🎨 Thumbnail A/B Results",
    f"  Variant A avg views/day: {avg_a}  (n={len(ab_a)})",
    f"  Variant B avg views/day: {avg_b}  (n={len(ab_b)})",
    f"  Winner so far: {'A' if avg_a >= avg_b else 'B'}",
]

summary_text = "\n".join(summary_lines)
print(summary_text)

# Send to Discord
if DISCORD_WEBHOOK_URL:
    try:
        http_requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": f"```\n{summary_text}\n```"},
            timeout=10
        )
        print("Discord summary sent")
    except Exception as e:
        print("Discord send failed:", e)

# Send via email
if SMTP_USER and SMTP_PASS and REPORT_EMAIL:
    try:
        msg = MIMEText(summary_text)
        msg["Subject"] = f"Midnight Cabin Daily Report — {today_str}"
        msg["From"] = SMTP_USER
        msg["To"] = REPORT_EMAIL

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print("Email summary sent to", REPORT_EMAIL)
    except Exception as e:
        print("Email send failed:", e)

with open(SUMMARY_SENT_PATH, "w") as f:
    f.write(today_str)
