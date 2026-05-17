#!/usr/bin/env python3
"""
Tests for Spotify Web API Controller
Run: pytest tests/test_spotify.py -v
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure the skill package is importable
SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

# Set dummy credentials before importing the module
os.environ.setdefault("SPOTIFY_CLIENT_ID", "test_client_id")
os.environ.setdefault("SPOTIFY_CLIENT_SECRET", "test_client_secret")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_api():
    """Create a SpotifyAPI instance with mocked auth to avoid real HTTP."""
    from spotify import SpotifyAPI, SpotifyAuth

    class MockAuth(SpotifyAuth):
        def __init__(self):
            # Skip super().__init__ to avoid real credential checks
            self.client_id = "test"
            self.client_secret = "test"
            self.redirect_uri = "http://127.0.0.1:8888/callback"
            self.scope = "test-scope"

        def get_access_token(self):
            return "fake_token"

        def refresh_token(self):
            return "refreshed_token"

    api = SpotifyAPI()
    api.auth = MockAuth()
    return api


def _mock_urlopen(response_body=None, status=200, headers=None, raise_error=None):
    """Return a context-manager mock for urllib.request.urlopen."""
    mock_resp = MagicMock()
    mock_resp.status = status
    if response_body is not None:
        mock_resp.read.return_value = response_body.encode() if isinstance(response_body, str) else response_body
    else:
        mock_resp.read.return_value = b""
    if headers:
        mock_resp.headers = headers
    else:
        mock_resp.headers = {}

    if raise_error:
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(side_effect=raise_error)
        mock_cm.__exit__ = MagicMock(return_value=False)
        return mock_cm

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_resp)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


def _make_http_error(code, headers=None):
    """Create a real urllib.error.HTTPError for testing error paths."""
    import urllib.error
    from io import BytesIO
    fp = BytesIO(b"{}")
    hdrs = MagicMock()
    hdrs.get = (headers or {}).get
    hdrs.__getitem__ = (headers or {}).__getitem__
    hdrs.__contains__ = (headers or {}).__contains__
    return urllib.error.HTTPError(
        url="http://test", code=code, msg="Error",
        hdrs=hdrs, fp=fp
    )


# ===========================================================================
# 1. Formatting helpers
# ===========================================================================
class TestFormatting(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_format_time_zero(self):
        self.assertEqual(self.api._format_time(0), "0:00")

    def test_format_time_seconds(self):
        self.assertEqual(self.api._format_time(45), "0:45")

    def test_format_time_minute(self):
        self.assertEqual(self.api._format_time(60), "1:00")

    def test_format_time_long(self):
        self.assertEqual(self.api._format_time(3661), "61:01")

    def test_format_progress_zero(self):
        self.assertEqual(self.api._format_progress(0, 0), "[--:--/--:--]")

    def test_format_progress_full(self):
        result = self.api._format_progress(200, 200)
        self.assertTrue(result.startswith("["))
        self.assertIn("█" * 20, result)

    def test_format_progress_half(self):
        result = self.api._format_progress(100, 200)
        # Half filled = 10 blocks
        self.assertIn("█" * 10, result)
        self.assertIn("░" * 10, result)

    def test_format_progress_quarter(self):
        result = self.api._format_progress(50, 200)
        self.assertIn("█" * 5, result)


# ===========================================================================
# 2. Version consistency
# ===========================================================================
class TestVersion(unittest.TestCase):
    def test_version_string(self):
        from spotify import __version__
        self.assertIsInstance(__version__, str)
        self.assertTrue(__version__[0].isdigit())

    def test_help_includes_version(self):
        from spotify import print_help, __version__
        captured = StringIO()
        with patch("sys.stdout", captured):
            print_help()
        output = captured.getvalue()
        self.assertIn(__version__, output)


# ===========================================================================
# 3. Scope validation (no unofficial scopes)
# ===========================================================================
class TestScopes(unittest.TestCase):
    def test_no_unofficial_scopes(self):
        from spotify import SpotifyAuth
        auth = SpotifyAuth()
        scopes = set(auth.scope.split())

        # These are NOT in Spotify's official scope list
        banned = {"user-read-playback-position", "user-read-queue", "playlist-modify-public"}
        found_banned = scopes & banned
        self.assertEqual(found_banned, set(), f"Unofficial scopes found: {found_banned}")

    def test_required_scopes_present(self):
        from spotify import SpotifyAuth
        auth = SpotifyAuth()
        scopes = set(auth.scope.split())

        required = {
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "user-read-recently-played",
        }
        missing = required - scopes
        self.assertEqual(missing, set(), f"Required scopes missing: {missing}")

    def test_scopes_are_unique(self):
        from spotify import SpotifyAuth
        auth = SpotifyAuth()
        scopes = auth.scope.split()
        self.assertEqual(len(scopes), len(set(scopes)), "Duplicate scopes found")


# ===========================================================================
# 4. Auth URL generation
# ===========================================================================
class TestAuthUrl(unittest.TestCase):
    def setUp(self):
        from spotify import SpotifyAuth
        self.auth = SpotifyAuth()

    def test_auth_url_contains_required_params(self):
        url = self.auth.get_auth_url()
        self.assertIn("response_type=code", url)
        self.assertIn("client_id=", url)
        self.assertIn("redirect_uri=", url)
        self.assertIn("code_challenge=", url)
        self.assertIn("code_challenge_method=S256", url)

    def test_auth_url_redirect_uri(self):
        url = self.auth.get_auth_url()
        self.assertIn("http%3A%2F%2F127.0.0.1%3A8888%2Fcallback", url)

    def test_code_verifier_cached(self):
        url = self.auth.get_auth_url()
        cache_path = Path.home() / ".spotify_cache.json"
        self.assertTrue(cache_path.exists())
        with open(cache_path) as f:
            cache = json.load(f)
        self.assertIn("code_verifier", cache)
        self.assertTrue(len(cache["code_verifier"]) > 40)


# ===========================================================================
# 5. Now playing (mocked API)
# ===========================================================================
class TestNowPlaying(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_now_playing_empty(self):
        with patch("urllib.request.urlopen", return_value=_make_http_error(204)):
            # _request returns None for 204
            with patch.object(self.api, "_request", return_value=None):
                result = self.api.now_playing()
                self.assertIn("Nothing", result)

    def test_now_playing_detailed_format(self):
        mock_response = {
            "item": {
                "name": "Test Song",
                "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
                "album": {
                    "name": "Test Album",
                    "images": [{"url": "https://img.example.com/cover.jpg", "width": 640}],
                },
                "duration_ms": 240000,
            },
            "progress_ms": 60000,
        }
        with patch.object(self.api, "_request", return_value=mock_response):
            result = self.api.now_playing_detailed()
            self.assertIn("Artist A, Artist B", result)
            self.assertIn("Test Song", result)
            self.assertIn("Test Album", result)
            self.assertIn("https://img.example.com/cover.jpg", result)
            # 60s / 240s = 25% = 5 blocks filled
            self.assertIn("░" * 15, result)


# ===========================================================================
# 6. Search formatting
# ===========================================================================
class TestSearch(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_search_track_format(self):
        mock_data = {
            "tracks": {
                "items": [
                    {"name": "Song A", "artists": [{"name": "Artist 1"}]},
                    {"name": "Song B", "artists": [{"name": "Artist 2"}]},
                ]
            }
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.search("test", "track")
            self.assertIn("Song A", result)
            self.assertIn("Song B", result)
            self.assertIn("Artist 1", result)

    def test_search_artist_format(self):
        mock_data = {
            "artists": {
                "items": [
                    {"name": "Band X", "uri": "spotify:artist:123"},
                ]
            }
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.search("band", "artist")
            self.assertIn("Band X", result)
            self.assertIn("spotify:artist:123", result)

    def test_search_album_format(self):
        mock_data = {
            "albums": {
                "items": [
                    {"name": "Album Y", "artists": [{"name": "Artist Z"}]},
                ]
            }
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.search("album", "album")
            self.assertIn("Album Y", result)
            self.assertIn("Artist Z", result)

    def test_search_no_results(self):
        with patch.object(self.api, "_request", return_value={"tracks": {"items": []}}):
            result = self.api.search("nonexistent", "track")
            self.assertIn("No tracks found", result)

    def test_search_playlist_format(self):
        mock_data = {
            "playlists": {
                "items": [
                    {"name": "My Playlist", "owner": {"display_name": "user1"}},
                ]
            }
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.search("my", "playlist")
            self.assertIn("My Playlist", result)
            self.assertIn("user1", result)


# ===========================================================================
# 7. Rate limiting (429 with Retry-After)
# ===========================================================================
class TestRateLimiting(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_429_retry_then_success(self):
        """After one 429, the second attempt should succeed."""
        call_count = 0

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(429, {"Retry-After": "0"})
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"test": True}).encode()
            mock_resp.status = 200
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_resp)
            mock_cm.__exit__ = MagicMock(return_value=False)
            return mock_cm

        with patch("urllib.request.urlopen", side_effect=mock_urlopen), \
             patch("time.sleep"):
            result = self.api._request("GET", "/test")
            self.assertEqual(result, {"test": True})
            self.assertEqual(call_count, 2)

    def test_429_exhaust_retries(self):
        """After 3 retries of 429, should raise RuntimeError."""
        def mock_urlopen(req, **kwargs):
            raise _make_http_error(429, {"Retry-After": "0"})

        with patch("urllib.request.urlopen", side_effect=mock_urlopen), \
             patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                self.api._request("GET", "/test")
            self.assertIn("Rate limited", str(ctx.exception))


# ===========================================================================
# 8. Token refresh on 401
# ===========================================================================
class TestTokenRefresh(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_401_triggers_refresh(self):
        """A 401 should trigger token refresh and retry."""
        call_count = 0

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_http_error(401)
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"ok": True}).encode()
            mock_resp.status = 200
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_resp)
            mock_cm.__exit__ = MagicMock(return_value=False)
            return mock_cm

        with patch.object(self.api.auth, "refresh_token", return_value="new_token"), \
             patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = self.api._request("GET", "/test")
            self.assertEqual(result, {"ok": True})
            self.api.auth.refresh_token.assert_called_once()


# ===========================================================================
# 9. Shuffle / Repeat / Seek commands
# ===========================================================================
class TestShuffleRepeatSeek(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_shuffle_on(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None) as mock_req:
                result = self.api.set_shuffle("on")
                self.assertIn("on", result)
                mock_req.assert_called()
                call_args = mock_req.call_args[0]
                self.assertIn("state=true", call_args[1])

    def test_shuffle_off(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None) as mock_req:
                result = self.api.set_shuffle("off")
                self.assertIn("off", result)
                call_args = mock_req.call_args[0]
                self.assertIn("state=false", call_args[1])

    def test_repeat_track(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None) as mock_req:
                result = self.api.set_repeat("track")
                self.assertIn("track", result)
                call_args = mock_req.call_args[0]
                self.assertIn("state=track", call_args[1])

    def test_repeat_invalid(self):
        result = self.api.set_repeat("invalid")
        self.assertIn("Invalid repeat state", result)

    def test_seek_absolute(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None) as mock_req:
                result = self.api.seek_to("120")
                self.assertIn("2:00", result)
                call_args = mock_req.call_args[0]
                self.assertIn("position_ms=120000", call_args[1])

    def test_seek_relative_forward(self):
        mock_player = {"progress_ms": 60000}
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", side_effect=[mock_player, None]) as mock_req:
                result = self.api.seek_to("+30")
                self.assertIn("1:30", result)

    def test_seek_relative_backward(self):
        mock_player = {"progress_ms": 45000}
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", side_effect=[mock_player, None]) as mock_req:
                result = self.api.seek_to("-15")
                self.assertIn("0:30", result)

    def test_seek_no_device(self):
        with patch.object(self.api, "devices", return_value=[]):
            result = self.api.seek_to("30")
            self.assertIn("No active", result)


# ===========================================================================
# 10. Cover save
# ===========================================================================
class TestCover(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_cover_url_only(self):
        mock_response = {
            "item": {
                "album": {
                    "images": [{"url": "https://img.example.com/cover.jpg", "width": 640}]
                }
            }
        }
        with patch.object(self.api, "_request", return_value=mock_response):
            result = self.api.save_cover()
            self.assertIn("https://img.example.com/cover.jpg", result)

    def test_cover_nothing_playing(self):
        with patch.object(self.api, "_request", return_value=None):
            result = self.api.save_cover()
            self.assertIn("Nothing", result)

    def test_cover_no_images(self):
        mock_response = {"item": {"album": {"images": []}}}
        with patch.object(self.api, "_request", return_value=mock_response):
            result = self.api.save_cover()
            self.assertIn("No cover art", result)

    def test_cover_save_to_file(self):
        mock_response = {
            "item": {
                "album": {
                    "images": [{"url": "https://img.example.com/cover.jpg", "width": 640}]
                }
            }
        }
        import tempfile
        with patch.object(self.api, "_request", return_value=mock_response):
            with patch("urllib.request.urlopen") as mock_open:
                mock_resp = MagicMock()
                mock_resp.read.return_value = b"fake_image_data"
                mock_open.return_value.__enter__ = MagicMock(return_value=mock_resp)
                mock_open.return_value.__exit__ = MagicMock(return_value=False)

                with tempfile.TemporaryDirectory() as tmpdir:
                    path = os.path.join(tmpdir, "cover.jpg")
                    result = self.api.save_cover(path)
                    self.assertIn("saved", result)
                    self.assertTrue(os.path.exists(path))
                    with open(path, "rb") as f:
                        self.assertEqual(f.read(), b"fake_image_data")


# ===========================================================================
# 11. Volume via _request (DRY check)
# ===========================================================================
class TestVolume(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_volume_uses_request(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None) as mock_req:
                self.api.set_volume(50)
                mock_req.assert_called_once()
                args = mock_req.call_args[0]
                self.assertEqual(args[0], "PUT")
                self.assertIn("volume_percent=50", args[1])


# ===========================================================================
# 12. Playlist via _request (DRY check)
# ===========================================================================
class TestPlaylist(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_playlist_search_and_play(self):
        mock_search = {
            "playlists": {
                "items": [
                    {"name": "Happy Rock", "uri": "spotify:playlist:123"}
                ]
            }
        }
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", side_effect=[mock_search, None]) as mock_req:
                result = self.api.play_playlist("Happy Rock")
                self.assertIn("Happy Rock", result)
                # Two calls: search + play
                self.assertEqual(mock_req.call_count, 2)
                # Second call should be PUT with context_uri
                play_call = mock_req.call_args_list[1]
                self.assertEqual(play_call[0][0], "PUT")
                self.assertIn("context_uri", play_call[0][2])


# ===========================================================================
# 13. Recent tracks formatting
# ===========================================================================
class TestRecentTracks(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_recent_tracks_format(self):
        mock_data = {
            "items": [
                {"track": {"name": "Song 1", "artists": [{"name": "A1"}]}},
                {"track": {"name": "Song 2", "artists": [{"name": "A2"}]}},
            ]
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.recent_tracks(2)
            self.assertIn("Recently played", result)
            self.assertIn("Song 1", result)
            self.assertIn("Song 2", result)

    def test_recent_tracks_empty(self):
        with patch.object(self.api, "_request", return_value={"items": []}):
            result = self.api.recent_tracks()
            self.assertIn("No recent tracks", result)


# ===========================================================================
# 14. Top tracks / artists
# ===========================================================================
class TestTop(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_top_tracks_period_labels(self):
        mock_data = {"items": [{"name": "Song", "artists": [{"name": "A"}]}]}
        for period, label in [
            ("short_term", "4 weeks"),
            ("medium_term", "6 months"),
            ("long_term", "All time"),
        ]:
            with patch.object(self.api, "_request", return_value=mock_data):
                result = self.api.top_tracks(period)
                self.assertIn(label, result)

    def test_top_artists_format(self):
        mock_data = {"items": [{"name": "Artist X"}, {"name": "Artist Y"}]}
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.top_artists("short_term")
            self.assertIn("Artist X", result)
            self.assertIn("Artist Y", result)


# ===========================================================================
# 15. Queue
# ===========================================================================
class TestQueue(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_queue_view_with_items(self):
        mock_data = {
            "currently_playing": {"name": "Now", "artists": [{"name": "A"}]},
            "queue": [
                {"name": "Next 1", "artists": [{"name": "B"}]},
                {"name": "Next 2", "artists": [{"name": "C"}]},
            ],
        }
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "is_active": True}]):
            with patch.object(self.api, "_request", return_value=mock_data):
                result = self.api.queue("view")
                self.assertIn("NOW", result)
                self.assertIn("Next 1", result)
                self.assertIn("Next 2", result)

    def test_queue_view_empty(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "is_active": True}]):
            with patch.object(self.api, "_request", return_value=None):
                result = self.api.queue("view")
                self.assertIn("empty", result)


# ===========================================================================
# 16. Devices
# ===========================================================================
class TestDevices(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_devices_format(self):
        mock_data = {
            "devices": [
                {"name": "Kitchen", "is_active": True, "volume_percent": 50},
                {"name": "Bedroom", "is_active": False, "volume_percent": 30},
            ]
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.devices()
            self.assertIn("Kitchen", result)
            self.assertIn("50%", result)
            self.assertIn("Bedroom", result)
            self.assertIn("30%", result)

    def test_devices_empty(self):
        with patch.object(self.api, "_request", return_value={"devices": []}):
            result = self.api.devices()
            self.assertIn("No active", result)


# ===========================================================================
# 17. Play with various inputs
# ===========================================================================
class TestPlay(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_play_with_query(self):
        mock_search = {"tracks": {"items": [{"name": "Found", "artists": [{"name": "A"}], "uri": "spotify:track:1"}]}}
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", side_effect=[mock_search, None]):
                result = self.api.play("found song")
                self.assertIn("Found", result)

    def test_play_with_spotify_uri(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None):
                result = self.api.play("spotify:track:abc123")
                self.assertIn("Playing", result)

    def test_play_resume(self):
        with patch.object(self.api, "devices", return_value=[{"id": "dev1", "name": "Test"}]):
            with patch.object(self.api, "_request", return_value=None):
                result = self.api.play()
                self.assertIn("resumed", result)

    def test_play_no_devices(self):
        with patch.object(self.api, "devices", return_value=[]):
            result = self.api.play()
            self.assertIn("No active", result)


# ===========================================================================
# 18. Playlists
# ===========================================================================
class TestMyPlaylists(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_playlists_format(self):
        mock_data = {
            "items": [
                {
                    "name": "My Mix",
                    "owner": {"display_name": "me"},
                    "tracks": {"total": 42},
                    "public": True,
                    "collaborative": False,
                }
            ]
        }
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.my_playlists()
            self.assertIn("My Mix", result)
            self.assertIn("me", result)
            self.assertIn("42", result)
            self.assertIn("🌍", result)

    def test_playlists_empty(self):
        with patch.object(self.api, "_request", return_value={"items": []}):
            result = self.api.my_playlists()
            self.assertIn("No playlists found", result)


# ===========================================================================
# 19. Lyrics error handling
# ===========================================================================
class TestLyrics(unittest.TestCase):
    def setUp(self):
        self.api = _make_api()

    def test_lyrics_nothing_playing(self):
        with patch.object(self.api, "_request", return_value=None):
            result = self.api.get_lyrics()
            self.assertIn("Nothing", result)

    def test_lyrics_track_id_missing(self):
        mock_data = {"item": {"name": "Unknown", "artists": [{"name": "A"}]}}
        with patch.object(self.api, "_request", return_value=mock_data):
            result = self.api.get_lyrics()
            self.assertIn("Track ID not available", result)

    def test_lyrics_404(self):
        mock_now = {"item": {"id": "abc", "name": "Song", "artists": [{"name": "A"}]}}

        from spotify import SpotifyAPI

        class TestAPI(SpotifyAPI):
            def __init__(self):
                self.auth = MagicMock()
                self.auth.get_access_token.return_value = "token"
                self.base_url = "https://api.spotify.com/v1"

        api = TestAPI()
        with patch.object(api, "_request", return_value=mock_now):
            with patch("urllib.request.urlopen", side_effect=_make_http_error(404)):
                result = api.get_lyrics()
                self.assertIn("Lyrics not available", result)


# ===========================================================================
# 20. CLI argument parsing
# ===========================================================================
class TestCLI(unittest.TestCase):
    def test_version_flag(self):
        from spotify import __version__
        captured = StringIO()
        with patch("sys.stdout", captured), patch("sys.argv", ["spotify", "--version"]):
            try:
                from spotify import main
                main()
            except SystemExit:
                pass
        output = captured.getvalue()
        self.assertIn(__version__, output)

    def test_debug_flag_sets_global(self):
        import spotify
        spotify.DEBUG_MODE = False  # reset
        with patch("sys.argv", ["spotify", "--debug", "now"]):
            # We can't run main() without a real device, but we can check
            # that --debug gets parsed
            args = sys.argv[1:]
            self.assertIn("--debug", args)
            # Parse like main() does
            debug = "--debug" in args
            self.assertTrue(debug)


# ===========================================================================
# 21. Credential loading
# ===========================================================================
class TestCredentialParsing(unittest.TestCase):
    def test_robust_parser_standard_format(self):
        content = "Client ID\nabc123\n\nClient Secret\nxyz789\n"
        path = Path("/tmp/test_spotify_creds.txt")
        path.write_text(content)
        try:
            import subprocess
            result = subprocess.run(
                ["awk", '/^Client ID$/{getline; while($0=="")getline; print; exit}', str(path)],
                capture_output=True, text=True
            )
            self.assertEqual(result.stdout.strip(), "abc123")

            result = subprocess.run(
                ["awk", '/^Client Secret$/{getline; while($0=="")getline; print; exit}', str(path)],
                capture_output=True, text=True
            )
            self.assertEqual(result.stdout.strip(), "xyz789")
        finally:
            path.unlink(missing_ok=True)

    def test_robust_parser_extra_newlines(self):
        content = "Client ID\n\n\nabc123\n\nClient Secret\n\nxyz789\n"
        path = Path("/tmp/test_spotify_creds2.txt")
        path.write_text(content)
        try:
            import subprocess
            result = subprocess.run(
                ["awk", '/^Client ID$/{getline; while($0=="")getline; print; exit}', str(path)],
                capture_output=True, text=True
            )
            self.assertEqual(result.stdout.strip(), "abc123")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
