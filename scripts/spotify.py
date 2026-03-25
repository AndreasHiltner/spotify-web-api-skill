#!/usr/bin/env python3
"""
Spotify Web API Controller
Cross-platform Spotify control via Web API
"""

import os
import sys
import json
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

# Configuration
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
CACHE_FILE = Path.home() / ".spotify_cache.json"
PORT = 8888

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
    sys.exit(1)

class SpotifyAuth:
    """Handle Spotify OAuth authentication"""
    
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.redirect_uri = REDIRECT_URI
        self.scope = " ".join([
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "streaming",
            "playlist-read-private",
            "playlist-modify-private",
            "playlist-modify-public",
            "user-library-read",
            "user-library-modify",
            "user-read-recently-played",
            "user-top-read",
            "user-read-playback-position"
        ])
    
    def get_auth_url(self):
        """Generate Spotify authorization URL"""
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
        
        # Store code_verifier for later
        cache = self._load_cache()
        cache["code_verifier"] = code_verifier
        self._save_cache(cache)
        
        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
    
    def exchange_code(self, code):
        """Exchange authorization code for tokens"""
        cache = self._load_cache()
        code_verifier = cache.get("code_verifier")
        
        if not code_verifier:
            raise Exception("No code_verifier found. Please restart auth flow.")
        
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
            }
        )
        
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode())
        
        # Cache tokens with expiry
        cache["access_token"] = tokens["access_token"]
        cache["refresh_token"] = tokens.get("refresh_token", cache.get("refresh_token"))
        cache["token_expires"] = (datetime.now() + timedelta(seconds=tokens["expires_in"])).isoformat()
        self._save_cache(cache)
        
        return tokens
    
    def refresh_token(self):
        """Refresh access token using refresh token"""
        cache = self._load_cache()
        refresh_token = cache.get("refresh_token")
        
        if not refresh_token:
            raise Exception("No refresh token available. Please re-authenticate.")
        
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }).encode()
        
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode())
        
        cache["access_token"] = tokens["access_token"]
        cache["token_expires"] = (datetime.now() + timedelta(seconds=tokens["expires_in"])).isoformat()
        self._save_cache(cache)
        
        return tokens["access_token"]
    
    def get_access_token(self):
        """Get valid access token (refresh if needed)"""
        cache = self._load_cache()
        
        if not cache.get("access_token"):
            raise Exception("Not authenticated. Run 'auth' command first.")
        
        # Check if token is expired (with 5 min buffer)
        expires_str = cache.get("token_expires")
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if datetime.now() >= expires - timedelta(minutes=5):
                print("🔄 Refreshing token...")
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
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Start local server to catch callback
        auth_instance = self
        
        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/callback"):
                    query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
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
                            self.wfile.write(b"<html><head><title>Spotify Auth Success</title></head><body><h1>Authentication successful!</h1><p>You can close this window and return to the terminal.</p></body></html>")
                            server.auth_success = True
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(f"Error: {e}".encode())
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b"No code received")
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress logging
        
        server = socketserver.TCPServer(("127.0.0.1", PORT), CallbackHandler)
        server.auth_success = False
        server.timeout = 120  # 2 minute timeout
        
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
        """Load token cache"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_cache(self, cache):
        """Save token cache"""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        os.chmod(CACHE_FILE, 0o600)  # Restrict permissions


class SpotifyAPI:
    """Spotify Web API client"""
    
    def __init__(self):
        self.auth = SpotifyAuth()
        self.base_url = "https://api.spotify.com/v1"
    
    def _request(self, method, endpoint, data=None, allow_empty=False):
        """Make authenticated API request"""
        token = self.auth.get_access_token()
        
        url = f"{self.base_url}{endpoint}"
        
        # Use Request with proper method handling
        if method in ["PUT", "POST", "DELETE"]:
            req = urllib.request.Request(url, method=method)
            req.add_header("Authorization", f"Bearer {token}")
            if data:
                req.add_header("Content-Type", "application/json")
                req.data = json.dumps(data).encode()
        else:
            req = urllib.request.Request(url, method=method)
            req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with urllib.request.urlopen(req) as response:
                body = response.read().decode()
                if not body:
                    return None
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    # Non-JSON response (e.g., control endpoints return opaque tokens)
                    if method in ["PUT", "POST", "DELETE"]:
                        return None  # Success for control operations
                    raise
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Token expired, refresh and retry
                token = self.auth.refresh_token()
                req = urllib.request.Request(url, method=method)
                req.add_header("Authorization", f"Bearer {token}")
                if data:
                    req.add_header("Content-Type", "application/json")
                    req.data = json.dumps(data).encode()
                try:
                    with urllib.request.urlopen(req) as response:
                        body = response.read().decode()
                        if not body:
                            return None
                        try:
                            return json.loads(body)
                        except json.JSONDecodeError:
                            if method in ["PUT", "POST", "DELETE"]:
                                return None
                            raise
                except urllib.error.HTTPError as e2:
                    if e2.code in [200, 204, 404] and method in ["PUT", "POST"]:
                        return None
                    raise
            if e.code in [200, 204, 404] and method in ["PUT", "POST"]:
                return None
            raise
    
    def now_playing(self):
        """Get currently playing track"""
        result = self._request("GET", "/me/player/currently-playing", allow_empty=True)
        if not result or not result.get("item"):
            return "⏸️  Nothing is currently playing"
        
        item = result["item"]
        artists = ", ".join([a["name"] for a in item["artists"]])
        return f"🎵 {artists} - {item['name']}\n💿 {item['album']['name']}"
    
    def recent_tracks(self, limit=10):
        """Get recently played tracks"""
        result = self._request("GET", f"/me/player/recently-played?limit={limit}")
        items = result.get("items", [])
        
        if not items:
            return "📭 No recent tracks found"
        
        lines = ["🕐 Recently played:"]
        for i, item in enumerate(items, 1):
            track = item["track"]
            artists = ", ".join([a["name"] for a in track["artists"]])
            lines.append(f"   {i}. {artists} - {track['name']}")
        
        return "\n".join(lines)
    
    def top_tracks(self, period="medium_term", limit=10):
        """Get top tracks"""
        result = self._request("GET", f"/me/top/tracks?time_range={period}&limit={limit}")
        items = result.get("items", [])
        
        period_names = {"short_term": "Last 4 weeks", "medium_term": "Last 6 months", "long_term": "All time"}
        
        if not items:
            return "📭 No top tracks found"
        
        lines = [f"🏆 Top tracks ({period_names.get(period, period)}):"]
        for i, track in enumerate(items, 1):
            artists = ", ".join([a["name"] for a in track["artists"]])
            lines.append(f"   {i}. {artists} - {track['name']}")
        
        return "\n".join(lines)
    
    def top_artists(self, period="medium_term", limit=10):
        """Get top artists"""
        result = self._request("GET", f"/me/top/artists?time_range={period}&limit={limit}")
        items = result.get("items", [])
        
        period_names = {"short_term": "Last 4 weeks", "medium_term": "Last 6 months", "long_term": "All time"}
        
        if not items:
            return "📭 No top artists found"
        
        lines = [f"🎤 Top artists ({period_names.get(period, period)}):"]
        for i, artist in enumerate(items, 1):
            lines.append(f"   {i}. {artist['name']}")
        
        return "\n".join(lines)
    
    def play(self, query=None, device_id=None, context_uri=None):
        """Start/resume playback or play specific track/playlist/album"""
        devices = self.devices(raw=True)
        
        if not devices:
            return "❌ No active Spotify devices found"
        
        # Use specified device, first active device, or first device
        if not device_id:
            active_devices = [d for d in devices if d.get("is_active")]
            device_id = active_devices[0]["id"] if active_devices else devices[0]["id"]
        
        device_name = next((d["name"] for d in devices if d["id"] == device_id), "Unknown")
        
        if context_uri:
            # Play playlist/album/artist
            try:
                self._request("PUT", f"/me/player/play?device_id={device_id}", {"context_uri": context_uri}, allow_empty=True)
            except:
                self._request("PUT", "/me/player/play", {"context_uri": context_uri}, allow_empty=True)
            
            # Get name from URI
            uri_type = context_uri.split(":")[1] if ":" in context_uri else "content"
            return f"▶️ Playing {uri_type} on {device_name}"
        
        if query:
            # Check if query is a URI
            if query.startswith("spotify:"):
                context_uri = query
                try:
                    self._request("PUT", f"/me/player/play?device_id={device_id}", {"context_uri": context_uri}, allow_empty=True)
                except:
                    self._request("PUT", "/me/player/play", {"context_uri": context_uri}, allow_empty=True)
                uri_type = query.split(":")[1] if ":" in query else "content"
                return f"▶️ Playing {uri_type} on {device_name}"
            
            # Search and play track
            search_result = self._request("GET", f"/search?q={urllib.parse.quote(query)}&type=track&limit=1")
            tracks = search_result.get("tracks", {}).get("items", [])
            
            if not tracks:
                return f"❌ No tracks found for '{query}'"
            
            track_uri = tracks[0]["uri"]
            try:
                self._request("PUT", f"/me/player/play?device_id={device_id}", {"uris": [track_uri]}, allow_empty=True)
            except:
                # Try without device_id
                self._request("PUT", "/me/player/play", {"uris": [track_uri]}, allow_empty=True)
            return f"▶️ Playing: {tracks[0]['name']} - {', '.join([a['name'] for a in tracks[0]['artists']])} on {device_name}"
        else:
            # Just resume
            try:
                self._request("PUT", f"/me/player/play?device_id={device_id}", allow_empty=True)
            except:
                # Try without device_id
                self._request("PUT", "/me/player/play", allow_empty=True)
            return f"▶️ Playback resumed on {device_name}"
    
    def pause(self, device_id=None):
        """Pause playback"""
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        
        if not device_id:
            # Find first active device, or use first device
            active_devices = [d for d in devices if d.get("is_active")]
            device_id = active_devices[0]["id"] if active_devices else devices[0]["id"]
        
        try:
            self._request("PUT", f"/me/player/pause?device_id={device_id}", allow_empty=True)
            return "⏸️ Playback paused"
        except Exception as e:
            # Try without device_id (uses current active device)
            try:
                self._request("PUT", "/me/player/pause", allow_empty=True)
                return "⏸️ Playback paused"
            except:
                return f"⚠️ Pause failed: {e}"
    
    def next_track(self, device_id=None):
        """Skip to next track"""
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        
        if not device_id:
            device_id = devices[0]["id"]
        
        self._request("POST", f"/me/player/next?device_id={device_id}", allow_empty=True)
        return "⏭️ Skipped to next track"
    
    def previous_track(self, device_id=None):
        """Go to previous track"""
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        
        if not device_id:
            device_id = devices[0]["id"]
        
        self._request("POST", f"/me/player/previous?device_id={device_id}", allow_empty=True)
        return "⏮️ Went to previous track"
    
    def search(self, query, type="track", limit=10):
        """Search Spotify"""
        result = self._request("GET", f"/search?q={urllib.parse.quote(query)}&type={type}&limit={limit}")
        
        if not result:
            return f"📭 No results found for '{query}'"
        
        if type == "track":
            items = result.get("tracks", {}).get("items", [])
            if not items:
                return f"📭 No tracks found for '{query}'"
            
            lines = [f"🔍 Search results for '{query}':"]
            for i, track in enumerate(items, 1):
                artists = ", ".join([a["name"] for a in track["artists"]])
                lines.append(f"   {i}. {artists} - {track['name']}")
            return "\n".join(lines)
        
        elif type == "playlist":
            items = result.get("playlists", {}).get("items", [])
            if not items:
                return f"📭 No playlists found for '{query}'"
            
            lines = [f"📋 Playlists for '{query}':"]
            for i, pl in enumerate(items, 1):
                if pl:  # Skip null entries
                    owner = pl.get("owner", {}).get("display_name", "Unknown")
                    lines.append(f"   {i}. {pl['name']} by {owner}")
            return "\n".join(lines)
        
        elif type == "artist":
            items = result.get("artists", {}).get("items", [])
            if not items:
                return f"📭 No artists found for '{query}'"
            
            lines = [f"🎤 Artists for '{query}':"]
            for i, artist in enumerate(items, 1):
                lines.append(f"   {i}. {artist['name']} (URI: {artist['uri']})")
            return "\n".join(lines)
        
        return json.dumps(result, indent=2)
    
    def set_volume(self, volume_percent, device_id=None):
        """Set playback volume"""
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        
        if not device_id:
            active_devices = [d for d in devices if d.get("is_active")]
            device_id = active_devices[0]["id"] if active_devices else devices[0]["id"]
        
        device_name = next((d["name"] for d in devices if d["id"] == device_id), "Unknown")
        
        # Use PUT with proper handling
        token = self.auth.get_access_token()
        url = f"https://api.spotify.com/v1/me/player/volume?volume_percent={volume_percent}&device_id={device_id}"
        
        req = urllib.request.Request(url, method='PUT')
        req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with urllib.request.urlopen(req) as response:
                pass  # Success, no body expected
            return f"🔊 Volume set to {volume_percent}% on {device_name}"
        except urllib.error.HTTPError as e:
            if e.code in [200, 204, 405]:
                # 405 can happen but volume might still be set
                return f"🔊 Volume set to {volume_percent}% on {device_name}"
            return f"⚠️ Volume error: {e.code}"
    
    def play_playlist(self, playlist_query, device_id=None):
        """Search for a playlist and play it"""
        devices = self.devices(raw=True)
        if not devices:
            return "❌ No active Spotify devices found"
        
        if not device_id:
            active_devices = [d for d in devices if d.get("is_active")]
            device_id = active_devices[0]["id"] if active_devices else devices[0]["id"]
        
        device_name = next((d["name"] for d in devices if d["id"] == device_id), "Unknown")
        
        # Search for playlist
        search_result = self._request("GET", f"/search?q={urllib.parse.quote(playlist_query)}&type=playlist&limit=5")
        playlists = search_result.get("playlists", {}).get("items", [])
        
        # Filter out null entries and find best match
        valid_playlists = [pl for pl in playlists if pl]
        
        if not valid_playlists:
            return f"📭 No playlists found for '{playlist_query}'"
        
        # Find best match (case-insensitive)
        best_match = None
        query_lower = playlist_query.lower()
        for pl in valid_playlists:
            if pl['name'].lower() == query_lower:
                best_match = pl
                break
        
        # If no exact match, use first result
        if not best_match:
            best_match = valid_playlists[0]
        
        playlist_uri = best_match['uri']
        playlist_name = best_match['name']
        
        # Use direct PUT request
        token = self.auth.get_access_token()
        url = f"https://api.spotify.com/v1/me/player/play?device_id={device_id}"
        
        req = urllib.request.Request(url, method='PUT')
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps({"context_uri": playlist_uri}).encode()
        
        try:
            with urllib.request.urlopen(req) as response:
                pass  # Success
            return f"▶️ Playing playlist '{playlist_name}' on {device_name}"
        except urllib.error.HTTPError as e:
            if e.code in [200, 204, 405]:
                return f"▶️ Playing playlist '{playlist_name}' on {device_name}"
            return f"⚠️ Play error: {e.code}"
    
    def devices(self, raw=False):
        """List available playback devices"""
        result = self._request("GET", "/me/player/devices")
        devices = result.get("devices", [])
        
        if raw:
            return devices
        
        if not devices:
            return "📭 No active Spotify devices found"
        
        lines = ["📱 Available devices:"]
        for device in devices:
            status = "🔊" if device["is_active"] else "⏸️"
            volume = f" ({device['volume_percent']}%)" if device.get("volume_percent") else ""
            lines.append(f"   {status} {device['name']}{volume}")
        
        return "\n".join(lines)
    
    def my_playlists(self, limit=20):
        """Get user's saved/followed playlists"""
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


# Main CLI
def main():
    auth = SpotifyAuth()
    api = SpotifyAPI()
    
    if len(sys.argv) < 2:
        print("Spotify Web API Controller")
        print()
        print("Usage:")
        print("  spotify.py auth              - Authenticate with Spotify")
        print("  spotify.py now               - Show currently playing track")
        print("  spotify.py recent [limit]    - Show recently played tracks")
        print("  spotify.py top tracks [period] - Show top tracks")
        print("  spotify.py top artists [period] - Show top artists")
        print("  spotify.py play [query]      - Play/resume or play specific track")
        print("  spotify.py play --playlist <name> - Play a playlist")
        print("  spotify.py pause             - Pause playback")
        print("  spotify.py next              - Skip to next track")
        print("  spotify.py prev              - Go to previous track")
        print("  spotify.py search <query> [type] - Search (track, playlist, artist)")
        print("  spotify.py devices           - List available devices")
        print("  spotify.py playlists [limit] - Show your library playlists")
        print()
        print("Period options: short_term (4w), medium_term (6m), long_term (all time)")
        return
    
    cmd = sys.argv[1]
    
    try:
        if cmd == "auth":
            auth.authenticate()
        elif cmd == "now":
            print(api.now_playing())
        elif cmd == "recent":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            print(api.recent_tracks(limit))
        elif cmd == "top":
            if len(sys.argv) < 3:
                print("Usage: spotify.py top [tracks|artists] [period]")
                return
            subtype = sys.argv[2]
            period = sys.argv[3] if len(sys.argv) > 3 else "medium_term"
            
            if subtype == "tracks":
                print(api.top_tracks(period))
            elif subtype == "artists":
                print(api.top_artists(period))
            else:
                print("Unknown subtype. Use 'tracks' or 'artists'")
        elif cmd == "play":
            if len(sys.argv) > 2 and sys.argv[2] == "--playlist":
                # Play playlist
                playlist_query = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else None
                if not playlist_query:
                    print("Usage: spotify.py play --playlist <playlist name>")
                    return
                print(api.play_playlist(playlist_query))
            else:
                query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
                print(api.play(query))
        elif cmd == "pause":
            print(api.pause())
        elif cmd == "next":
            print(api.next_track())
        elif cmd == "prev":
            print(api.previous_track())
        elif cmd == "search":
            if len(sys.argv) < 3:
                print("Usage: spotify.py search <query> [type]")
                print("Types: track (default), playlist, artist, album")
                return
            query = sys.argv[2]
            search_type = sys.argv[3] if len(sys.argv) > 3 else "track"
            print(api.search(query, search_type))
        elif cmd == "devices":
            print(api.devices())
        elif cmd == "playlists":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            print(api.my_playlists(limit))
        elif cmd == "volume":
            if len(sys.argv) < 3:
                print("Usage: spotify.py volume <percent> [device]")
                return
            volume = int(sys.argv[2])
            device = sys.argv[3] if len(sys.argv) > 3 else None
            print(api.set_volume(volume, device))
        else:
            print(f"Unknown command: {cmd}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
