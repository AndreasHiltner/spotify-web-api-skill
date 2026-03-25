---
name: spotify-web-api
version: 1.0.0
description: Control Spotify playback via Web API - play, pause, skip, search, playlists, devices. Cross-platform (Linux/macOS/Windows).
homepage: https://spotify.com
author: Andreas
license: MIT
metadata:
  clawdbot:
    emoji: 🎵
    requires:
      env:
        - SPOTIFY_CLIENT_ID
        - SPOTIFY_CLIENT_SECRET
  commands:
    - spotify auth
    - spotify now
    - spotify play [query]
    - spotify play --playlist <name>
    - spotify pause
    - spotify next
    - spotify prev
    - spotify volume <percent>
    - spotify devices
    - spotify playlists
    - spotify search <query> [type]
    - spotify recent [limit]
    - spotify top tracks [period]
    - spotify top artists [period]
---

# Spotify Web API Skill

**Cross-platform Spotify control via Web API.** Works from any platform — no Mac-only dependencies.

## Quick Start

### 1. Setup Credentials

Create `/srv/clawd-share/Andreas/Spotify.txt`:
```
Client ID
your_client_id_here

Client Secret
your_client_secret_here
```

### 2. Authenticate (One-Time)

```bash
cd /home/andreas/clawd/.openclaw/workspace/skills/spotify-web-api
./spotify auth
```

Opens browser for OAuth. Token cached in `~/.spotify_cache.json`.

### 3. Use

```bash
spotify now              # What's playing
spotify play "daft punk" # Search & play
spotify pause            # Pause
spotify devices          # List devices
```

## Commands

### Playback Control

| Command | Description |
|---------|-------------|
| `spotify play` | Resume playback |
| `spotify play "song name"` | Search & play specific track |
| `spotify play --playlist "name"` | Play a playlist |
| `spotify pause` | Pause playback |
| `spotify next` | Skip to next track |
| `spotify prev` | Go to previous track |
| `spotify volume <0-100>` | Set volume percentage |

### Information

| Command | Description |
|---------|-------------|
| `spotify now` | Show currently playing track |
| `spotify devices` | List available Spotify Connect devices |
| `spotify playlists [limit]` | Show your library playlists |
| `spotify recent [n]` | Recently played tracks (default: 10) |
| `spotify top tracks [period]` | Top tracks (short_term/medium_term/long_term) |
| `spotify top artists [period]` | Top artists |

### Search

| Command | Description |
|---------|-------------|
| `spotify search "query"` | Search tracks (default) |
| `spotify search "query" playlist` | Search playlists |
| `spotify search "query" artist` | Search artists |

## Discord/Telegram Integration

Natural language commands via Kira:

```
"Was läuft gerade?"
"Spiel Daft Punk auf der Küche"
"Pause die Musik"
"Nächster Track"
"Spiele Playlist 'Happy Rock'"
"Stell Lautstärke auf 30%"
```

## Requirements

- **Spotify Premium** (for playback control)
- **Spotify Developer Account** (free)
- **Python 3.8+**

## Setup Details

### Create Spotify App

1. Go to https://developer.spotify.com/dashboard
2. Create app with redirect URI: `http://127.0.0.1:8888/callback`
3. Copy Client ID and Client Secret

### Environment Variables (Alternative)

```bash
export SPOTIFY_CLIENT_ID="your_id"
export SPOTIFY_CLIENT_SECRET="your_secret"
```

## Example Chat Usage

- "What am I listening to?" → `spotify now`
- "What have I listened to lately?" → `spotify recent`
- "What are my top tracks this month?" → `spotify top tracks short_term`
- "Play Bohemian Rhapsody" → `spotify play "bohemian rhapsody"`
- "Skip this song" → `spotify next`
- "Pause the music" → `spotify pause`
- "Show my devices" → `spotify devices`

## Files

- `spotify` - Bash wrapper (auto-loads credentials)
- `scripts/spotify.py` - Main Python script
- `~/.spotify_cache.json` - OAuth token cache (auto-created)

## API Reference

Uses the Spotify Web API: https://developer.spotify.com/documentation/web-api

## Troubleshooting

**No devices found?** Open Spotify on at least one device (phone, desktop, Alexa).

**Token expired?** Run `spotify auth` again.

**Redirect URI error?** Use `http://127.0.0.1:8888/callback` (not `localhost`).

## License

MIT
