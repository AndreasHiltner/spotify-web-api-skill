#!/usr/bin/env python3
"""
Spotify Web API Controller
Cross-platform Spotify control via Web API
"""

import os
import sys
import json
import time
import base64
import hashlib
import secrets
import webbrowser
import http.server
import socketserver
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Version (single source of truth)
# ---------------------------------------------------------------------------
__version__ = "1.2.0"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
CACHE_FILE = Path.home() / ".spotify_cache.json"
API_TIMEOUT = 30  # seconds — prevents hanging on unresponsive Spotify servers
PORT = 8888

# Global debug flag
DEBUG_MODE = False

# Check for help/version FIRST (before credential check)
if len(sys.argv) < 2 or sys.argv[1] in ["--help", "-h", "help", "--version", "-v", "version"]:
    pass
elif not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
    sys.exit(1)


# ---------------------------------------------------------------------------
# OAuth Authentication
# ---------------------------------------------------------------------------
class SpotifyAuth:
    """Handle Spotify OAuth authentication"""

    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.redirect_uri = REDIRECT_URI
        # Only officially documented scopes — no extended-approval ones
        self.scope = " ".join([
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "streaming",
            "playlist-read-private",
            "playlist-modify-private",
            "user-library-read",
            "user-library-modify",
            "user-read-recently-played",
            "user-top-read",
        ])

    def get_auth_url(self):
        """Generate Spotify authorization URL with PKCE"""
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": self.scope,
            "redirect_uri": self.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }

        cache = self._load_cache()
        cache["code_verifier"] = code_verifier
        self._save_cache(cache)

        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code):
        """Exchange authorization code for tokens"""
        cache = self._load_cache()
        code_verifier = cache.get("code_verifier")
        if not code_verifier:
            raise RuntimeError("No code_verifier found. Please restart auth flow.")

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }).encode()

        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            tokens = json.loads(response.read().decode())

        cache["access_token"] = tokens["access_token"]
        cache["refresh_token"] = tokens.get("refresh_token", cache.get("refresh_token"))
        cache["token_expires"] = (
            datetime.now() + timedelta(seconds=tokens["expires_in"])
        ).isoformat()
        self._save_cache(cache)
        return tokens

    def refresh_token(self):
        """Refresh access token using refresh token"""
        cache = self._load_cache()
        refresh_tok = cache.get("refresh_token")
        if not refresh_tok:
            raise RuntimeError(
                "No refresh token available. Please re-authenticate: spotify auth"
            )

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        }).encode()

        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
                tokens = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Token refresh failed (HTTP {exc.code}). "
                "Please re-authenticate: spotify auth"
            ) from exc

        cache["access_token"] = tokens["access_token"]
        cache["token_expires"] = (
            datetime.now() + timedelta(seconds=tokens["expires_in"])
        ).isoformat()
        self._save_cache(cache)
        return tokens["access_token"]

    def get_access_token(self):
        """Get valid access token, refreshing if needed"""
        cache = self._load_cache()
        if not cache.get("access_token"):
            raise RuntimeError("Not authenticated. Run 'spotify auth' first.")

        expires_str = cache.get("token_expires")
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if datetime.now() >= expires - timedelta(minutes=5):
                if DEBUG_MODE:
                    print("[debug] Token near expiry, refreshing…")
                return self.refresh_token()

        return cache["access_token"]

    def authenticate(self):
        """Run full authentication flow"""
        print("🎵 Starting Spotify authentication...")
        print(f"📋 Scope: {self.scope}")
        print()

        auth_url = self.get_auth_url()
        print(f"🔗 Opening browser for authentication...")
        print(f"   URL: {auth_url[:80]}...")
        print()

        webbrowser.open(auth_url)

        auth_instance = self

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/callback"):
                    query = urllib.parse.parse_qs(
                        urllib.parse.urlparse(self.path).query
                    )
                    code = query.get("code", [None])[0]
                    error = query.get("error", [None])[0]

                    if error:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(f"Error: {error}".encode())
                        return

                    if code:
                        try:
                            auth_instance.exchange_code(code)
                            self.send_response(200)
                            self.send_header("Content-type", "text/html")
                            self.end_headers()
                            self.wfile.write(
                                b"<html><head><title>Spotify Auth Success</title></head>"
                                b"<body><h1>Authentication successful!</h1>"
                                b"<p>You can close this window and return to the terminal.</p>"
                                b"</body></html>"
                            )
                            server.auth_success = True
                        except Exception as exc:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(f"Error: {exc}".encode())
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b"No code received")
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                pass

        server = socketserver.TCPServer(("127.0.0.1", PORT), CallbackHandler)
        server.auth_success = False
        server.timeout = 120

        print(f"⏳ Waiting for callback on http://127.0.0.1:{PORT}/callback")
        print("   (Timeout: 2 minutes)")
        print()

        try:
            while not server.auth_success:
                server.handle_request()
            print("\n✅ Authentication complete! Token cached.")
        except KeyboardInterrupt:
            print("\n❌ Authentication cancelled.")
        finally:
            server.server_close()

    def _load_cache(self):
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE) as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache(self, cache):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as fh:
            json.dump(cache, fh, indent=2)
        os.chmod(CACHE_FILE, 0o600)


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------
class SpotifyAPI:
    """Spotify Web API client"""

    def __init__(self):
        self.auth = SpotifyAuth()
        self.base_url = "https://api.spotify.com/v1"

    def _request(self, method, endpoint, data=None, allow_empty=False):
        """Make an authenticated API request.

        Handles:
        - 429 rate-limit (Retry-After, up to 3 retries)
        - 401 token refresh (once)
        - Debug logging
        """
        token = self.auth.get_access_token()
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        refreshed_once = False

        for attempt in range(max_retries + 1):
            req = urllib.request.Request(url, method=method)
            req.add_header("Authorization", f"Bearer {token}")
            if data:
                req.add_header("Content-Type", "application/json")
                req.data = json.dumps(data).encode()

            if DEBUG_MODE:
                _start = time.monotonic()
                print(f"[debug] {method} {url}")

            try:
                with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                    body = resp.read().decode()
                    if DEBUG_MODE:
                        elapsed = (time.monotonic() - _start) * 1000
                        print(
                            f"[debug] ← {resp.status} ({len(body)} bytes, {elapsed:.0f}ms)"
                        )

                    if not body:
                        return None
                    try:
                        return json.loads(body)
                    except json.JSONDecodeError:
                        if method in ("PUT", "POST", "DELETE"):
                            return None
                        raise

            except urllib.error.HTTPError as exc:
                if DEBUG_MODE:
                    print(f"[debug] ← HTTP {exc.code}")

                if exc.code == 429:
                    retry_after = int(exc.headers.get("Retry-After", 1))
                    if attempt < max_retries:
                        if DEBUG_MODE:
                            print(
                                f"[debug] Rate-limited, waiting {retry_after}s "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                        else:
                            print(f"⏳ Rate-limited, waiting {retry_after}s…")
                        time.sleep(retry_after)
                        continue
                    raise RuntimeError(
                        f"Rate limited after {max_retries} retries. Try again later."
                    ) from exc

                # Transient server errors (502/503/504) — retry with backoff
                if exc.code in (502, 503, 504) and attempt < max_retries:
                    wait = min(2 ** attempt, 8)
                    if DEBUG_MODE:
                        print(
                            f"[debug] Server error {exc.code}, retrying in {wait}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                    else:
                        print(f"⏳ Server error {exc.code}, retrying in {wait}s…")
                    time.sleep(wait)
                    continue

                if exc.code in (401, 403) and not refreshed_once:
                    try:
                        token = self.auth.refresh_token()
                        refreshed_once = True
                        if DEBUG_MODE:
                            print("[debug] Token refreshed, retrying…")
                        continue
                    except RuntimeError:
                        raise

                if exc.code in (204, 404) and method in ("PUT", "POST", "DELETE"):
                    return None

                raise

        raise RuntimeError("Request exhausted retry loop unexpectedly.")

    # -- now playing -----------------------------------------------------------
    def now_playing(self):
        result = self._request("GET", "/me/player/currently-playing", allow_empty=True)
        if not result or not result.get("item"):
            return "⏸️  Nothing is currently playing"
        item = result["item"]
        artists = ", ".join(a["name"] for a in item["artists"])
        return f"🎵 {artists} - {item['name']}\n💿 {item['album']['name']}"

    def now_playing_detailed(self):
        result = self._request("GET", "/me/player/currently-playing", allow_empty=True)
        if not result or not result.get("item"):
            return "⏸️  Nothing is currently playing"

        item = result["item"]
        artists = ", ".join(a["name"] for a in item["artists"])
        album = item.get("album", {})
        album_name = album.get("name", "Unknown Album")

        images = album.get("images", [])
        album_art = ""
        if images:
            largest = max(images, key=lambda x: x.get("width", 0))
            album_art = f"\n🖼️  Album Art: {largest['url']}"

        progress_ms = result.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 0)
        progress_sec = progress_ms // 1000
        duration_sec = duration_ms // 1000

        progress_bar = self._format_progress(progress_sec, duration_sec)

        return (
            f"🎵 {artists} - {item['name']}\n"
            f"💿 {album_name}{album_art}\n"
            f"⏱️  {progress_bar} {self._format_time(progress_sec)} / {self._format_time(duration_sec)}"
        )

    # -- recent / top ----------------------------------------------------------
    def recent_tracks(self, limit=10):
        result = self._request("GET", f"/me/player/recently-played?limit={limit}")
        items = result.get("items", [])
        if not items:
            return "📭 No recent tracks found"
        lines = ["🕐 Recently played:"]
        for i, item in enumerate(items, 1):
            track = item["track"]
            artists = ", ".join(a["name"] for a in track["artists"])
            lines.append(f"   {i}. {artists} - {track['name']}")
        return "\n".join(lines)

    def top_tracks(self, period="medium_term", limit=10):
        result = self._request(
            "GET", f"/me/top/tracks?time_range={period}&limit={limit}"
        )
        items = result.get("items", [])
        period_names = {
            "short_term": "Last 4 weeks",
            "medium_term": "Last 6 months",
            "long_term": "All time",
        }
        if not items:
            return "📭 No top tracks found"
        lines = [f"🏆 Top tracks ({period_names.get(period, period)}):"]
        for i, track in enumerate(items, 1):
            artists = ", ".join(a["name"] for a in track["artists"])
            lines.append(f"   {i}. {artists} - {track['name']}")
        return "\n".join(lines)

    def top_artists(self, period="medium_term", limit=10):
        result = self._request(
            "GET", f"/me/top/artists?time_range={period}&limit={limit}"
        )
        items = result.get("items", [])
        period_names = {
            "short_term": "Last 4 weeks",
            "medium_term": "Last 6 months",
            "long_term": "All time",
        }
        if not items:
            return "📭 No top artists found"
        lines = [f"🎤 Top artists ({period_names.get(period, period)}):"]
        for i, artist in enumerate(items, 1):
            lines.append(f"   {i}. {artist['name']}")
        return "\n".join(lines)

    # -- playback control ------------------------------------------------------
    def _resolve_device(self, device_name):
        """Resolve device name to device_id from the device list."""
        devices = self.devices(raw=True)
        if not devices:
            return None, None
        name_lower = device_name.lower()
        for d in devices:
            if d["name"].lower() == name_lower:
                return d["id"], d["name"]
        return None, device_name

    def play(self, query=None, device_name=None, context_uri=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"

        # Resolve device name → device_id
        device_id = None
        resolved_name = None
        if device_name:
            device_id, resolved_name = self._resolve_device(device_name)
            if not device_id:
                return f"❌ Device '{device_name}' not found. Use 'spotify devices' to list available devices."
        else:
            # Default: use first active device so playback targets a single device
            active = [d for d in devices if d.get("is_active")]
            if active:
                device_id = active[0]["id"]
                resolved_name = active[0]["name"]
            else:
                device_id = devices[0]["id"]
                resolved_name = devices[0]["name"]

        if context_uri:
            self._request(
                "PUT",
                f"/me/player/play?device_id={device_id}",
                {"context_uri": context_uri},
                allow_empty=True,
            )
            uri_type = context_uri.split(":")[1] if ":" in context_uri else "content"
            return f"▶️ Playing {uri_type} on {resolved_name}"

        if query:
            if query.startswith("spotify:"):
                self._request(
                    "PUT",
                    f"/me/player/play?device_id={device_id}",
                    {"context_uri": query},
                    allow_empty=True,
                )
                uri_type = query.split(":")[1] if ":" in query else "content"
                return f"▶️ Playing {uri_type} on {resolved_name}"

            search = self._request(
                "GET",
                f"/search?q={urllib.parse.quote(query)}&type=track&limit=1",
            )
            tracks = search.get("tracks", {}).get("items", [])
            if not tracks:
                return f"❌ No tracks found for '{query}'"

            track_uri = tracks[0]["uri"]
            self._request(
                "PUT",
                f"/me/player/play?device_id={device_id}",
                {"uris": [track_uri]},
                allow_empty=True,
            )
            return (
                f"▶️ Playing: {tracks[0]['name']} - "
                f"{', '.join(a['name'] for a in tracks[0]['artists'])} "
                f"on {resolved_name}"
            )

        self._request(
            "PUT", f"/me/player/play?device_id={device_id}", allow_empty=True
        )
        return f"▶️ Playback resumed on {resolved_name}"

    def pause(self, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]

        try:
            self._request(
                "PUT", f"/me/player/pause?device_id={device_id}", allow_empty=True
            )
            return "⏸️ Playback paused"
        except Exception as exc:
            try:
                self._request("PUT", "/me/player/pause", allow_empty=True)
                return "⏸️ Playback paused"
            except Exception:
                return f"⚠️ Pause failed: {exc}"

    def next_track(self, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]
        self._request("POST", f"/me/player/next?device_id={device_id}", allow_empty=True)
        return "⏭️ Skipped to next track"

    def previous_track(self, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]
        self._request(
            "POST", f"/me/player/previous?device_id={device_id}", allow_empty=True
        )
        return "⏮️ Went to previous track"

    # -- shuffle / repeat / seek -----------------------------------------------
    def set_shuffle(self, state, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]

        if isinstance(state, str) and state.lower() == "toggle":
            try:
                status = self._request("GET", "/me/player")
                current = status.get("shuffle_state", False)
                state = "off" if current else "on"
            except Exception:
                state = "on"

        state_bool = state.lower() == "on"
        self._request(
            "PUT",
            f"/me/player/shuffle?state={str(state_bool).lower()}&device_id={device_id}",
            allow_empty=True,
        )
        return f"🔀 Shuffle {'on' if state_bool else 'off'}"

    def set_repeat(self, state, device_id=None):
        valid = ("track", "context", "off")
        state = state.lower()
        if state not in valid:
            return f"❌ Invalid repeat state. Use: {', '.join(valid)}"

        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]

        icons = {"track": "🔂", "context": "🔁", "off": "➡️"}
        self._request(
            "PUT",
            f"/me/player/repeat?state={state}&device_id={device_id}",
            allow_empty=True,
        )
        return f"{icons[state]} Repeat {state}"

    def seek_to(self, position, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]

        pos_str = str(position)
        if pos_str.startswith("+") or pos_str.startswith("-"):
            status = self._request("GET", "/me/player")
            if not status or status.get("progress_ms") is None:
                return "⚠️ Could not determine current position for relative seek"
            current_ms = status["progress_ms"]
            delta_ms = int(pos_str) * 1000
            target_ms = max(0, current_ms + delta_ms)
            pos_ms = target_ms
        else:
            pos_ms = int(pos_str) * 1000

        self._request(
            "PUT",
            f"/me/player/seek?position_ms={pos_ms}&device_id={device_id}",
            allow_empty=True,
        )
        return f"⏩ Seeked to {self._format_time(pos_ms // 1000)}"

    # -- volume ----------------------------------------------------------------
    def set_volume(self, volume_percent, device_id=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        if not device_id:
            active = [d for d in devices if d.get("is_active")]
            device_id = (active[0] if active else devices[0])["id"]

        device_name = next(
            (d["name"] for d in devices if d["id"] == device_id), "Unknown"
        )
        self._request(
            "PUT",
            f"/me/player/volume?volume_percent={volume_percent}&device_id={device_id}",
            allow_empty=True,
        )
        return f"🔊 Volume set to {volume_percent}% on {device_name}"

    # -- playlist --------------------------------------------------------------
    def play_playlist(self, playlist_query, device_name=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"

        # Resolve device name → device_id
        device_id = None
        resolved_name = None
        if device_name:
            device_id, resolved_name = self._resolve_device(device_name)
            if not device_id:
                return f"❌ Device '{device_name}' not found. Use 'spotify devices' to list available devices."
        else:
            active = [d for d in devices if d.get("is_active")]
            if active:
                device_id = active[0]["id"]
                resolved_name = active[0]["name"]
            else:
                device_id = devices[0]["id"]
                resolved_name = devices[0]["name"]

        search = self._request(
            "GET",
            f"/search?q={urllib.parse.quote(playlist_query)}&type=playlist&limit=5",
        )
        playlists = [pl for pl in search.get("playlists", {}).get("items", []) if pl]
        if not playlists:
            return f"📭 No playlists found for '{playlist_query}'"

        best = None
        query_lower = playlist_query.lower()
        for pl in playlists:
            if pl["name"].lower() == query_lower:
                best = pl
                break
        if not best:
            best = playlists[0]

        self._request(
            "PUT",
            f"/me/player/play?device_id={device_id}",
            {"context_uri": best["uri"]},
            allow_empty=True,
        )
        return f"▶️ Playing playlist '{best['name']}' on {device_name}"

    # -- devices / queue -------------------------------------------------------
    def devices(self, raw=False):
        result = self._request("GET", "/me/player/devices")
        devs = result.get("devices", [])
        if raw:
            return devs
        if not devs:
            return "📭 No active Spotify devices found"

        lines = ["📱 Available devices:"]
        for d in devs:
            status = "🔊" if d["is_active"] else "⏸️"
            vol = f" ({d['volume_percent']}%)" if d.get("volume_percent") is not None else ""
            lines.append(f"   {status} {d['name']}{vol}")
        return "\n".join(lines)

    def queue(self, action=None, uri=None):
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"

        active = [d for d in devices if d.get("is_active")]
        device_id = active[0]["id"] if active else None

        if action == "add" and uri:
            qs = f"uri={urllib.parse.quote(uri)}"
            if device_id:
                qs += f"&device_id={device_id}"
            self._request("POST", f"/me/player/queue?{qs}", allow_empty=True)
            return "➕ Added to queue"

        if action == "view":
            result = self._request("GET", "/me/player/queue")
            if not result:
                return "📭 Queue is empty"

            now = result.get("currently_playing")
            queued = result.get("queue", [])

            lines = ["🎵 Queue:"]
            if now:
                artists = ", ".join(a["name"] for a in now.get("artists", []))
                lines.append(f"   ▶️ NOW: {artists} - {now['name']}")

            if queued:
                lines.append(f"   Up next ({len(queued)} tracks):")
                for i, t in enumerate(queued[:5], 1):
                    artists = ", ".join(a["name"] for a in t.get("artists", []))
                    lines.append(f"      {i}. {artists} - {t['name']}")
                if len(queued) > 5:
                    lines.append(f"      ... and {len(queued) - 5} more")
            else:
                lines.append("   (No tracks queued)")
            return "\n".join(lines)

        return "Usage: spotify queue [view|add <uri>]"

    # -- search ----------------------------------------------------------------
    def search(self, query, type="track", limit=10):
        result = self._request(
            "GET",
            f"/search?q={urllib.parse.quote(query)}&type={type}&limit={limit}",
        )
        if not result:
            return f"📭 No results found for '{query}'"

        if type == "track":
            items = result.get("tracks", {}).get("items", [])
            if not items:
                return f"📭 No tracks found for '{query}'"
            lines = [f"🔍 Search results for '{query}':"]
            for i, t in enumerate(items, 1):
                artists = ", ".join(a["name"] for a in t["artists"])
                lines.append(f"   {i}. {artists} - {t['name']}")
            return "\n".join(lines)

        if type == "playlist":
            items = result.get("playlists", {}).get("items", [])
            if not items:
                return f"📭 No playlists found for '{query}'"
            lines = [f"📋 Playlists for '{query}':"]
            for i, pl in enumerate(items, 1):
                if pl:
                    owner = pl.get("owner", {}).get("display_name", "Unknown")
                    lines.append(f"   {i}. {pl['name']} by {owner}")
            return "\n".join(lines)

        if type == "artist":
            items = result.get("artists", {}).get("items", [])
            if not items:
                return f"📭 No artists found for '{query}'"
            lines = [f"🎤 Artists for '{query}':"]
            for i, a in enumerate(items, 1):
                lines.append(f"   {i}. {a['name']} (URI: {a['uri']})")
            return "\n".join(lines)

        if type == "album":
            items = result.get("albums", {}).get("items", [])
            if not items:
                return f"📭 No albums found for '{query}'"
            lines = [f"💿 Albums for '{query}':"]
            for i, alb in enumerate(items, 1):
                artists = ", ".join(a["name"] for a in alb.get("artists", []))
                lines.append(f"   {i}. {alb['name']} by {artists}")
            return "\n".join(lines)

        return json.dumps(result, indent=2)

    # -- cover -----------------------------------------------------------------
    def save_cover(self, path=None):
        result = self._request("GET", "/me/player/currently-playing", allow_empty=True)
        if not result or not result.get("item"):
            return "⏸️  Nothing is currently playing"

        images = result["item"].get("album", {}).get("images", [])
        if not images:
            return "⚠️  No cover art available"

        largest = max(images, key=lambda x: x.get("width", 0))
        url = largest["url"]

        if not path:
            return f"🖼️  Album Art: {url}"

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            data = resp.read()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return f"💾 Cover saved to {out} ({len(data)} bytes)"

    # -- lyrics ----------------------------------------------------------------
    def get_lyrics(self):
        result = self._request("GET", "/me/player/currently-playing", allow_empty=True)
        if not result or not result.get("item"):
            return "⏸️  Nothing is currently playing"

        item = result["item"]
        track_id = item.get("id")
        track_name = item.get("name", "Unknown")
        artists = ", ".join(a["name"] for a in item.get("artists", []))

        if not track_id:
            return f"📝 Lyrics for '{track_name}' by {artists}\n⚠️  Track ID not available"

        token = self.auth.get_access_token()
        req_url = f"https://api.spotify.com/v1/tracks/{track_id}/lyrics"

        req = urllib.request.Request(req_url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                lyrics_data = json.loads(resp.read().decode())

            lines_data = lyrics_data.get("lyrics", {}).get("lines", [])
            if not lines_data:
                return f"📝 {artists} - {track_name}\n⚠️  No lyrics available"

            output = [f"📝 {artists} - {track_name}\n"]
            for line in lines_data[:20]:
                text = line.get("words", {}).get("text", "")
                if text:
                    output.append(f"   {text}")
            if len(lines_data) > 20:
                output.append(f"\n   ... ({len(lines_data) - 20} more lines)")
            return "\n".join(output)

        except urllib.error.HTTPError as exc:
            msgs = {
                404: "Lyrics not available for this track",
                403: "Lyrics feature not available in your region",
            }
            msg = msgs.get(exc.code, f"Could not fetch lyrics (Error {exc.code})")
            return f"📝 {artists} - {track_name}\n⚠️  {msg}"
        except Exception as exc:
            return f"📝 {artists} - {track_name}\n⚠️  Error: {exc}"

    # -- playlists -------------------------------------------------------------
    def my_playlists(self, limit=20):
        result = self._request("GET", f"/me/playlists?limit={limit}")
        playlists = result.get("items", [])
        if not playlists:
            return "📭 No playlists found in your library"

        lines = [f"📚 Your Playlists ({len(playlists)} found):"]
        for i, pl in enumerate(playlists, 1):
            if not pl:
                continue
            name = pl.get("name", "Unknown")
            owner = pl.get("owner", {}).get("display_name", "Unknown")
            tracks = pl.get("tracks", {}).get("total", 0)
            public = "🌍" if pl.get("public") else "🔒"
            collab = "👥" if pl.get("collaborative") else ""
            lines.append(f"   {i}. {public}{collab} {name}")
            lines.append(f"      Owner: {owner} | Tracks: {tracks}")
        return "\n".join(lines)

    # -- formatting helpers ----------------------------------------------------
    def _format_progress(self, current, total):
        if total == 0:
            return "[--:--/--:--]"
        filled = int(20 * current / total)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}]"

    def _format_time(self, seconds):
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
def print_help():
    help_text = f"""
🎵 Spotify Web API Controller v{__version__}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USAGE:
    spotify                       Show currently playing track
    spotify <command> [options]

COMMANDS:

  🔐 Authentication
    auth                         Authenticate with Spotify (one-time setup)

  ▶️  Playback Control
    play [query]                 Play/resume or search & play track
    play --device <name> [query] Play on specific device
    play --all [query]           Play on all devices (group playback)
    play --playlist <name>       Play a playlist by name
    pause                        Pause current playback
    next                         Skip to next track
    prev                         Go to previous track
    volume <0-100>               Set volume percentage
    shuffle [on|off|toggle]      Toggle shuffle mode
    repeat [track|context|off]   Set repeat mode
    seek <sec|+sec|-sec>         Seek to position (e.g. 120, +30, -15)

  🎵 Queue Management
    queue view                   Show current playback queue
    queue add <uri>              Add track to queue (Spotify URI)

  📊 Information & Media
    now                          Show currently playing track (with progress)
    cover [--save <path>]        Show/download album cover art
    lyrics                       Get lyrics for current track
    devices                      List available Spotify Connect devices
    playlists [limit]            Show your library playlists (default: 20)
    recent [n]                   Recently played tracks (default: 10)

  🔍 Search
    search <query> [type]        Search Spotify
                                 Types: track (default), playlist, artist, album

  📈 Statistics
    top tracks [period]          Your top tracks
    top artists [period]         Your top artists
                                 Periods: short_term (4w), medium_term (6m), long_term (all time)

OPTIONS:
    --debug                      Enable debug output (URLs, timing, status)
    --help, -h, help             Show this help message
    --version, -v                Show version information

EXAMPLES:
    spotify                                    # Show currently playing
    spotify play "daft punk"                   # Search & play on current device
    spotify play --device "Büro"               # Play on device "Büro"
    spotify play --device "Überall" "daft punk" # Play on all devices
    spotify play --all                         # Resume on all devices (group)
    spotify play --playlist "Happy Rock"       # Play playlist
    spotify shuffle toggle                     # Toggle shuffle
    spotify repeat track                       # Repeat current track
    spotify seek +30                           # Skip ahead 30s
    spotify cover --save /tmp/cover.jpg        # Save cover art
    spotify --debug now                        # Debug mode

ENVIRONMENT:
    SPOTIFY_CLIENT_ID                     Your Spotify Client ID
    SPOTIFY_CLIENT_SECRET                 Your Spotify Client Secret
    Or store in: ~/.config/spotify.cred

REQUIREMENTS:
    - Spotify Premium account (for playback control)
    - Spotify Developer Account (free, for API access)
    - Python 3.8+

GITHUB:
    https://github.com/AndreasHiltner/spotify-web-api-skill

VERSION:
    {__version__}
"""
    print(help_text)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    global DEBUG_MODE

    args = sys.argv[1:]
    if "--debug" in args:
        DEBUG_MODE = True
        args = [a for a in args if a != "--debug"]

    auth = SpotifyAuth()
    api = SpotifyAPI()

    if not args:
        try:
            print(api.now_playing_detailed())
        except Exception as exc:
            print(f"❌ Error: {exc}")
            sys.exit(1)
        sys.exit(0)

    if args[0] in ("--help", "-h", "help"):
        print_help()
        sys.exit(0)

    if args[0] in ("--version", "-v", "version"):
        print(f"Spotify Web API Controller v{__version__}")
        print("GitHub: https://github.com/AndreasHiltner/spotify-web-api-skill")
        sys.exit(0)

    cmd = args[0]

    try:
        if cmd == "auth":
            auth.authenticate()

        elif cmd == "now":
            print(api.now_playing_detailed())

        elif cmd == "cover":
            save_path = None
            if len(args) > 2 and args[1] == "--save":
                save_path = args[2]
            print(api.save_cover(save_path))

        elif cmd == "lyrics":
            print(api.get_lyrics())

        elif cmd == "queue":
            if len(args) > 2:
                if args[1] == "add" and len(args) > 3:
                    print(api.queue("add", args[2]))
                elif args[1] == "view":
                    print(api.queue("view"))
                else:
                    print("Usage: spotify queue [view|add <spotify:uri>]")
            else:
                print(api.queue("view"))

        elif cmd == "recent":
            limit = int(args[1]) if len(args) > 1 else 10
            print(api.recent_tracks(limit))

        elif cmd == "top":
            if len(args) < 2:
                print("Usage: spotify top [tracks|artists] [period]")
                return
            subtype = args[1]
            period = args[2] if len(args) > 2 else "medium_term"
            if subtype == "tracks":
                print(api.top_tracks(period))
            elif subtype == "artists":
                print(api.top_artists(period))
            else:
                print("Unknown subtype. Use 'tracks' or 'artists'")

        elif cmd == "play":
            # Parse --device and --all flags
            device_name = None
            if "--device" in args:
                idx = args.index("--device")
                if idx + 1 < len(args):
                    device_name = args[idx + 1]
                else:
                    print("Usage: spotify play --device <device name>")
                    return
                # Remove --device and its value from args
                args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]
            elif "--all" in args:
                device_name = "Überall"
                args = [a for a in args if a != "--all"]

            if "--playlist" in args:
                idx = args.index("--playlist")
                playlist_args = [a for a in args if a not in ("--playlist", "--device")]
                playlist_query = " ".join(args[idx + 1:]) if idx + 1 < len(args) else None
                if not playlist_query:
                    print("Usage: spotify play --playlist <playlist name> [--device <name>]")
                    return
                print(api.play_playlist(playlist_query, device_name=device_name))
            else:
                query_args = [a for a in args if a not in ("--device", "--all")]
                # Remove --device value if present
                if "--device" in query_args:
                    idx = query_args.index("--device")
                    if idx + 1 < len(query_args):
                        query_args.pop(idx + 1)
                    query_args.pop(idx)
                query = " ".join(query_args) if query_args else None
                print(api.play(query, device_name=device_name))

        elif cmd == "pause":
            print(api.pause())

        elif cmd == "next":
            print(api.next_track())

        elif cmd == "prev":
            print(api.previous_track())

        elif cmd == "search":
            if len(args) < 2:
                print("Usage: spotify search <query> [type]")
                print("Types: track (default), playlist, artist, album")
                return
            query = args[1]
            search_type = args[2] if len(args) > 2 else "track"
            print(api.search(query, search_type))

        elif cmd == "devices":
            print(api.devices())

        elif cmd == "playlists":
            limit = int(args[1]) if len(args) > 1 else 20
            print(api.my_playlists(limit))

        elif cmd == "volume":
            if len(args) < 2:
                print("Usage: spotify volume <percent> [device]")
                return
            volume = int(args[1])
            device = args[2] if len(args) > 2 else None
            print(api.set_volume(volume, device))

        elif cmd == "shuffle":
            state = args[1] if len(args) > 1 else "toggle"
            print(api.set_shuffle(state))

        elif cmd == "repeat":
            if len(args) < 2:
                print("Usage: spotify repeat [track|context|off]")
                return
            print(api.set_repeat(args[1]))

        elif cmd == "seek":
            if len(args) < 2:
                print("Usage: spotify seek <seconds|+seconds|-seconds>")
                return
            print(api.seek_to(args[1]))

        else:
            print(f"Unknown command: {cmd}")

    except Exception as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
