# 🎵 Spotify Web API CLI

Control Spotify playback across all your devices from the command line.

**Version:** 1.2.1

## Features

- ✅ **Playback Control**: Play, pause, skip, previous track, seek
- ✅ **Device Targeting**: `--device "Name"` for specific devices, `--all` for group playback
- ✅ **Shuffle & Repeat**: Toggle shuffle, set repeat mode (track/context/off)
- ✅ **Queue Management**: View and add tracks to queue
- ✅ **Album Art**: Display and download cover art for current track
- ✅ **Lyrics**: Fetch lyrics for currently playing song
- ✅ **Device Management**: List all Spotify Connect devices
- ✅ **Playlist Support**: Play playlists, albums, artists by name
- ✅ **Search**: Find tracks, playlists, artists, albums
- ✅ **Volume Control**: Set volume per device
- ✅ **Library Access**: View playlists, recent tracks, top tracks/artists
- ✅ **Progress Bar**: Visual playback progress
- ✅ **Rate Limiting**: Automatic retry on 429 (Retry-After) and 5xx server errors
- ✅ **Debug Mode**: `--debug` flag for request timing and status
- ✅ **Cross-Platform**: Works on Linux, macOS, Windows

## Requirements

- **Spotify Premium** account (required for playback control)
- **Spotify Developer Account** (free, for API access)
- Python 3.8+

## Setup

### 1. Create Spotify Developer App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify Premium account
3. Click **"Create App"**
4. Fill in:
   - **Name**: e.g., "Spotify CLI"
   - **Description**: Personal music control
   - **Redirect URI**: `http://127.0.0.1:8888/callback` (⚠️ Must be loopback, not localhost!)
   - Check the box for **Spotify Web API**
5. Save and note your **Client ID** and **Client Secret**

### 2. Install

```bash
git clone https://github.com/AndreasHiltner/spotify-web-api-skill.git
cd spotify-web-api-skill
```

### 3. Store Credentials

Save your credentials to `~/.config/spotify.cred`:

```
Client ID
your_client_id_here

Client Secret
your_client_secret_here
```

Or use environment variables:

```bash
export SPOTIFY_CLIENT_ID="your_id"
export SPOTIFY_CLIENT_SECRET="your_secret"
```

### 4. Authenticate

Run the authentication flow once:

```bash
./spotify auth
```

This opens a browser window. Log in to Spotify and authorize the app. The token is cached locally.

## Usage

### Playback Control

```bash
spotify play                           # Resume on current active device
spotify play "song name"               # Search & play track
spotify play --device "Name"           # Play on specific device
spotify play --all                     # Play on all devices (group playback)
spotify play --playlist "Playlist Name" # Play playlist
spotify play --playlist "Rock" --device "Kitchen"  # Playlist on specific device
spotify pause                          # Pause
spotify skip                           # Next track + show what's playing
spotify next                           # Next track
spotify prev                           # Previous track
spotify volume 50                      # Set volume to 50%
spotify shuffle toggle                 # Toggle shuffle mode
spotify shuffle on                     # Enable shuffle
spotify shuffle off                    # Disable shuffle
spotify repeat track                   # Repeat current track
spotify repeat context                 # Repeat playlist/album
spotify repeat off                     # Disable repeat
spotify seek 120                       # Seek to 2:00
spotify seek +30                       # Skip ahead 30 seconds
spotify seek -15                       # Go back 15 seconds
```

### Queue Management

```bash
spotify queue view                     # Show current queue
spotify queue add "spotify:track:..."  # Add track to queue
```

### Information & Media

```bash
spotify now                            # Currently playing (with progress bar)
spotify cover                          # Show album cover art URL
spotify cover --save /tmp/cover.jpg    # Download and save cover art
spotify lyrics                         # Get lyrics for current track
spotify devices                        # List available devices
spotify playlists [20]                 # Your library playlists
spotify recent [10]                    # Recently played (default: 10)
```

### Search

```bash
spotify search "query"                 # Search tracks (default)
spotify search "query" playlist        # Search playlists
spotify search "query" artist          # Search artists
spotify search "query" album           # Search albums
```

### Stats

```bash
spotify top tracks [period]            # Top tracks (short_term/medium_term/long_term)
spotify top artists [period]           # Top artists
```

### Options

```bash
spotify --debug now                    # Debug mode (URLs, timing, status codes)
spotify --help                         # Show help message
spotify --version                      # Show version
```

## Bot/Assistant Integration

This CLI integrates with any chatbot or voice assistant. Natural language commands map directly to CLI calls:

```
"What's playing?"              → spotify now
"Play Daft Punk"               → spotify play "daft punk"
"Play Daft Punk in the Kitchen" → spotify play --device "Kitchen" "daft punk"
"Pause the music"              → spotify pause
"Next track"                   → spotify next
"Skip and show"                → spotify skip
"Play playlist 'Happy Rock'"   → spotify play --playlist "Happy Rock"
"Play 'Happy Rock' on Office"  → spotify play --playlist "Happy Rock" --device "Office"
"Set volume to 30%"            → spotify volume 30
"Shuffle on"                   → spotify shuffle on
"Repeat this track"            → spotify repeat track
"Skip ahead 30 seconds"        → spotify seek +30
```

## Project Structure

```
spotify-web-api/
├── SKILL.md              # Skill definition (for agent frameworks)
├── README.md             # This file
├── spotify               # CLI wrapper script (bash)
├── scripts/
│   └── spotify.py        # Main Python script (Spotify Web API client)
└── tests/
    └── test_spotify.py   # Test suite
```

## API Reference

Uses the official [Spotify Web API](https://developer.spotify.com/documentation/web-api).

### Scopes Required

- `user-read-playback-state`
- `user-modify-playback-state`
- `user-read-currently-playing`
- `streaming`
- `playlist-read-private`
- `playlist-modify-private`
- `user-library-read`
- `user-library-modify`
- `user-read-recently-played`
- `user-top-read`

## Error Handling

The client handles errors gracefully:

- **429 Rate Limited**: Automatically waits for `Retry-After` header, retries up to 3 times
- **502/503/504 Server Errors**: Retries with exponential backoff (1s → 2s → 4s)
- **401/403 Unauthorized**: Automatically refreshes token and retries once
- **30s Timeout**: All requests have a 30-second timeout to prevent hanging

## Troubleshooting

### "No devices found"
Make sure you have Spotify Connect devices active (open Spotify on phone/desktop/smart speaker).

### "401/403 Unauthorized"
Token expired or invalid. Run `spotify auth` to re-authenticate. The client tries to auto-refresh tokens on 401 and 403 errors.

### Rate Limited
The CLI automatically waits and retries. If you see "Rate limited after 3 retries", wait a minute and try again.

### "Lyrics not available"
Lyrics availability depends on Spotify's licensing in your region and track-by-track availability. Not all songs have lyrics enabled.

### Redirect URI Error
Make sure you use `http://127.0.0.1:8888/callback` (not `localhost`) in your Spotify Dashboard.

### Token Expired After Server Errors
If Spotify returns 502 errors followed by 403 on subsequent requests, the token may be corrupted. Delete `~/.spotify_cache.json` and run `spotify auth` again.

## Known Limitations

- **Lyrics**: Spotify's lyrics API is region-dependent and not available for all tracks
- **Queue**: Only works when playback is active on a device
- **Group Playback (`--all`)**: Requires a Spotify Connect group to be set up

## Security

- Credentials are stored locally, never uploaded
- OAuth tokens are cached with restricted permissions (`~/.spotify_cache.json`, mode 600)
- No data is sent to third parties

## Testing

```bash
cd spotify-web-api-skill
pytest tests/test_spotify.py -v
```

60+ tests covering formatting, search, rate limiting, token refresh, commands, and error handling.

## Changelog

### v1.2.0 (2026-05-17)
- **Device targeting**: `--device "Name"` for specific devices, `--all` for group playback
- **Shuffle & Repeat**: New `shuffle` and `repeat` commands
- **Seek**: Absolute and relative seek (`seek 120`, `seek +30`, `seek -15`)
- **Rate limiting**: Auto-retry on 429 (Retry-After) and 5xx server errors
- **Request timeout**: 30s timeout on all API calls to prevent hanging
- **DRY refactor**: Volume and playlist now route through unified `_request()` method
- **Debug mode**: `--debug` flag for request URLs, timing, and status codes
- **Album search**: `spotify search "query" album` support
- **Cover download**: `spotify cover --save <path>` to download album art
- **Scope fix**: Removed unofficial scopes (`user-read-playback-position`, `user-read-queue`)
- **Token refresh**: Now handles both 401 and 403 errors
- **Device selection**: All commands target active device instead of first in list
- **Robust credential parsing**: Bash wrapper handles format variations
- **Version consolidation**: Single `__version__` source of truth
- **Test suite**: 60+ tests for all major functionality

### v1.1.0 (2026-03-25)
- Initial public release

## License

MIT License - See LICENSE file for details.

## Credits

Built by Andreas (2026)
Uses Spotify Web API - <https://developer.spotify.com/documentation/web-api>
