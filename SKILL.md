---
name: spotify-web-api
version: 1.2.0
description: Control Spotify playback via Web API - play, pause, skip, search, playlists, devices, shuffle, repeat, seek. Cross-platform (Linux/macOS/Windows).
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
    - spotify cover [--save path]
    - spotify lyrics
    - spotify queue [view|add uri]
    - spotify play [query]
    - spotify play --playlist name
    - spotify pause
    - spotify next
    - spotify prev
    - spotify shuffle [on|off|toggle]
    - spotify repeat [track|context|off]
    - spotify seek [seconds|+seconds|-seconds]
    - spotify volume percent
    - spotify devices
    - spotify playlists
    - spotify search query [type]
    - spotify recent [limit]
    - spotify top tracks [period]
    - spotify top artists [period]
    - spotify --debug now
---

# Spotify Web API Skill

**Cross-platform Spotify control via Web API.** Works from any platform — no Mac-only dependencies.

**Version:** 1.2.0

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
spotify shuffle toggle   # Toggle shuffle
spotify seek +30         # Skip ahead 30s
```

## Commands

### Playback Control

- `spotify play` — Resume playback
- `spotify play "song name"` — Search & play specific track
- `spotify play --playlist "name"` — Play a playlist
- `spotify pause` — Pause playback
- `spotify next` — Skip to next track
- `spotify prev` — Go to previous track
- `spotify volume <0-100>` — Set volume percentage
- `spotify shuffle [on|off|toggle]` — Toggle shuffle mode
- `spotify repeat [track|context|off]` — Set repeat mode
- `spotify seek <seconds>` — Seek to position (supports +30, -15)
- `spotify queue view` — Show current playback queue
- `spotify queue add <uri>` — Add track to queue

### Information & Media

- `spotify now` — Currently playing (with progress bar)
- `spotify cover` — Show album cover art URL
- `spotify cover --save <path>` — Download and save cover art
- `spotify lyrics` — Get lyrics for current track
- `spotify devices` — List available Spotify Connect devices
- `spotify playlists [limit]` — Show your library playlists (default: 20)
- `spotify recent [n]` — Recently played tracks (default: 10)
- `spotify top tracks [period]` — Top tracks (short_term/medium_term/long_term)
- `spotify top artists [period]` — Top artists

### Search

- `spotify search "query"` — Search tracks (default)
- `spotify search "query" playlist` — Search playlists
- `spotify search "query" artist` — Search artists
- `spotify search "query" album` — Search albums

### Options

- `spotify --debug <command>` — Enable debug output (URLs, timing, status codes)

## Discord/Telegram Integration

Natural language commands via Kira:

```
"Was läuft gerade?"
"Spiel Daft Punk auf der Küche"
"Pause die Musik"
"Nächster Track"
"Spiele Playlist 'Happy Rock'"
"Stell Lautstärke auf 30%"
"Shuffle an"
"Repeat auf track"
"Spul 30 Sekunden vor"
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
export SPOTIFY_CLIENT_SECRET="***"
```

## Example Chat Usage

- "What am I listening to?" → `spotify now`
- "What have I listened to lately?" → `spotify recent`
- "What are my top tracks this month?" → `spotify top tracks short_term`
- "Play Bohemian Rhapsody" → `spotify play "bohemian rhapsody"`
- "Skip this song" → `spotify next`
- "Pause the music" → `spotify pause`
- "Show my devices" → `spotify devices`
- "Save the cover art" → `spotify cover --save /tmp/cover.jpg`
- "Toggle shuffle" → `spotify shuffle toggle`
- "Repeat this track" → `spotify repeat track`
- "Skip ahead 30 seconds" → `spotify seek +30`
- "Debug what's playing" → `spotify --debug now`

## Files

- `spotify` — Bash wrapper (auto-loads credentials)
- `scripts/spotify.py` — Main Python script
- `~/.spotify_cache.json` — OAuth token cache (auto-created)

## API Reference

Uses the Spotify Web API: https://developer.spotify.com/documentation/web-api

## Troubleshooting

- **No devices found?** Open Spotify on at least one device (phone, desktop, Alexa).
- **Token expired?** Run `spotify auth` again.
- **Redirect URI error?** Use `http://127.0.0.1:8888/callback` (not `localhost`).
- **Rate limited?** The CLI auto-waits on 429 responses. Just retry.

## Changelog

### v1.2.0 (2026-05-17)
- Added shuffle, repeat, seek commands
- Rate-limit handling (429 with Retry-After)
- Unified error handling via `_request()` (DRY)
- Debug mode (`--debug`)
- Album search support
- Cover art download (`--save`)
- Robust credential parsing in bash wrapper
- Version consolidated to single source of truth

### v1.1.0 (2026-03-25)
- Initial public release

## License

MIT
