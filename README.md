# 🎵 Spotify Web API Skill for OpenClaw

Control Spotify playback across all your devices (Alexa, Desktop, Mobile) directly from OpenClaw.

## Features

- ✅ **Playback Control**: Play, pause, skip, previous track
- ✅ **Queue Management**: View and add tracks to queue
- ✅ **Album Art**: Display cover art for current track
- ✅ **Lyrics**: Fetch lyrics for currently playing song
- ✅ **Device Management**: List and control all Spotify Connect devices
- ✅ **Playlist Support**: Play playlists, albums, artists by name
- ✅ **Search**: Find tracks, playlists, artists
- ✅ **Volume Control**: Set volume per device
- ✅ **Library Access**: View your playlists, recent tracks, top tracks/artists
- ✅ **Progress Bar**: Visual playback progress
- ✅ **Cross-Platform**: Works on Linux, macOS, Windows (no Mac-only dependencies)

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
   - **Name**: e.g., "OpenClaw Music Control"
   - **Description**: Personal music control
   - **Redirect URI**: `http://127.0.0.1:8888/callback` (⚠️ Must be loopback, not localhost!)
   - Check the box for **Spotify Web API**
5. Save and note your **Client ID** and **Client Secret**

### 2. Install the Skill

```bash
# Clone or copy the skill to your OpenClaw skills directory
cd /path/to/openclaw/workspace/skills
git clone https://github.com/YOUR_USERNAME/spotify-web-api-skill.git
```

### 3. Store Credentials

Save your credentials securely:

```bash
# Option A: In a credentials file (recommended)
echo "Client ID: YOUR_CLIENT_ID" > /srv/clawd-share/Andreas/Spotify.txt
echo "Client Secret: YOUR_CLIENT_SECRET" >> /srv/clawd-share/Andreas/Spotify.txt

# Option B: As environment variables
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
```

### 4. Authenticate

Run the authentication flow once:

```bash
cd skills/spotify-web-api
./spotify auth
```

This opens a browser window. Log in to Spotify and authorize the app. The token is cached locally.

## Usage

### CLI Commands

```bash
# Playback control
spotify play                           # Resume playback
spotify play "song name"               # Search & play track
spotify play --playlist "playlist"     # Play playlist
spotify pause                          # Pause
spotify next                           # Next track
spotify prev                           # Previous track
spotify volume 50                      # Set volume to 50%

# Queue management
spotify queue view                     # Show current queue
spotify queue add "spotify:track:..."  # Add track to queue

# Information & Media
spotify now                            # Currently playing (with progress)
spotify cover                          # Show album cover art
spotify lyrics                         # Get lyrics for current track
spotify recent [10]                    # Recently played (default: 10)
spotify devices                        # Available devices
spotify playlists [20]                 # Your library playlists

# Search
spotify search "query" track           # Search tracks (default)
spotify search "query" playlist        # Search playlists
spotify search "query" artist          # Search artists

# Stats
spotify top tracks [period]            # Top tracks (short_term/medium_term/long_term)
spotify top artists [period]           # Top artists
```

### Discord/Telegram Integration

Once installed, Kira can control Spotify naturally:

```
"Was läuft gerade auf Spotify?"
"Spiel Daft Punk auf der Küche"
"Pause die Musik"
"Nächster Track bitte"
"Spiele Playlist 'Happy Rock' auf Büro"
"Stell Lautstärke auf 30%"
```

### Example: Play on Specific Device

```bash
# Find device name
spotify devices

# Play on specific device (by modifying script or using device_id)
spotify play "bohemian rhapsody"
```

## Project Structure

```
spotify-web-api/
├── SKILL.md              # OpenClaw skill definition
├── package.json          # Package metadata
├── README.md             # This file
├── spotify               # CLI wrapper script (bash)
└── scripts/
    └── spotify.py        # Main Python script (Spotify Web API client)
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
- `playlist-modify-public`
- `user-library-read`
- `user-library-modify`
- `user-read-recently-played`
- `user-top-read`
- `user-read-playback-position`

## Troubleshooting

### "No devices found"
Make sure you have Spotify Connect devices active (open Spotify on phone/desktop/Alexa).

### "401 Unauthorized"
Token expired. Run `spotify auth` again to re-authenticate.

### "403 Forbidden"
Your Spotify account might not have Premium, or the app wasn't approved for certain scopes.

### Redirect URI Error
Make sure you use `http://127.0.0.1:8888/callback` (not `localhost`) in your Spotify Dashboard.

## Security

- Credentials are stored locally, never uploaded
- OAuth tokens are cached with restricted permissions (`~/.spotify_cache.json`, mode 600)
- No data is sent to third parties

## License

MIT License - See LICENSE file for details.

## Credits

Built for OpenClaw by Andreas (2026)
Uses Spotify Web API - https://developer.spotify.com/documentation/web-api
