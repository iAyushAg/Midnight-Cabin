#!/usr/bin/env python3
"""
pinterest_auth.py — One-time OAuth flow to get a Pinterest access token

Run once on your local machine:
  python3 scripts/pinterest_auth.py

Then copy the printed access token into Railway:
  PINTEREST_ACCESS_TOKEN=your_token

And find your board ID:
  python3 scripts/pinterest_auth.py --list-boards
"""

import os, sys, json, webbrowser, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import requests

CLIENT_ID     = os.environ.get("PINTEREST_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("PINTEREST_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8089/callback"
SCOPES        = "pins:read,pins:write,boards:read,user_accounts:read"

if "--list-boards" in sys.argv:
    token = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
    if not token:
        print("Set PINTEREST_ACCESS_TOKEN first")
        sys.exit(1)
    r = requests.get(
        "https://api.pinterest.com/v5/boards",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 25},
    )
    r.raise_for_status()
    boards = r.json().get("items", [])
    print(f"\nYour Pinterest boards:")
    for b in boards:
        print(f"  {b['name']:<40} ID: {b['id']}")
    print(f"\nSet PINTEREST_BOARD_ID to the ID of your sleep/ambient board")
    sys.exit(0)

if not CLIENT_ID or not CLIENT_SECRET:
    print("Set PINTEREST_CLIENT_ID and PINTEREST_CLIENT_SECRET first")
    print("Get them from developers.pinterest.com → My Apps → Create App")
    print("Request scopes: pins:read, pins:write, boards:read")
    sys.exit(1)

# Build auth URL
params = {
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT_URI,
    "response_type": "code",
    "scope":         SCOPES,
    "state":         "midnight_cabin",
}
auth_url = "https://www.pinterest.com/oauth/?" + urllib.parse.urlencode(params)
print(f"\nOpening browser for Pinterest OAuth...")
print(f"URL: {auth_url}\n")
webbrowser.open(auth_url)

# Capture callback
auth_code = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>Authorised! Close this tab and return to terminal.</h1>")

    def log_message(self, *args):
        pass

print("Waiting for OAuth callback on http://localhost:8089...")
server = HTTPServer(("localhost", 8089), Handler)
server.handle_request()

if not auth_code:
    print("No auth code received. Try again.")
    sys.exit(1)

# Exchange for token
r = requests.post(
    "https://api.pinterest.com/v5/oauth/token",
    auth=(CLIENT_ID, CLIENT_SECRET),
    data={
        "grant_type":   "authorization_code",
        "code":         auth_code,
        "redirect_uri": REDIRECT_URI,
    },
)
r.raise_for_status()
token_data = r.json()
access_token  = token_data.get("access_token", "")
refresh_token = token_data.get("refresh_token", "")

print(f"\n✅ Pinterest OAuth complete!")
print(f"\nAdd to Railway environment variables:")
print(f"  PINTEREST_ACCESS_TOKEN={access_token}")
if refresh_token:
    print(f"  PINTEREST_REFRESH_TOKEN={refresh_token}")
print(f"\nThen list your boards:")
print(f"  PINTEREST_ACCESS_TOKEN={access_token} python3 scripts/pinterest_auth.py --list-boards")