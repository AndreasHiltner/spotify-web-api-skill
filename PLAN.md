# Spotify Web API Skill - Improvement Plan

**Date:** 2026-05-17
**Requested by:** Andreas
**Scope:** `scripts/spotify.py`, `spotify` wrapper, `SKILL.md`

---

## Step 1: 429 Rate-Limiting with Retry-After
**Priority:** CRITICAL
**Files:** `scripts/spotify.py` → `_request()`
**What:** Catch HTTPError 429, read `Retry-After` header, sleep & retry. Max 3 retries.
**Success:** 429 responses trigger automatic retry instead of crashing.

## Step 2: Replace Bare `except:` with Specific Exceptions
**Priority:** CRITICAL
**Files:** `scripts/spotify.py` → all methods
**What:** Replace `except:` with `except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, Exception)`. Add meaningful error messages.
**Success:** No silent bug swallowing, clear error output on failure.

## Step 3: Route `set_volume` and `play_playlist` Through `_request()`
**Priority:** HIGH
**Files:** `scripts/spotify.py` → `set_volume()`, `play_playlist()`
**What:** Remove duplicate urllib.Request code. Use `_request("PUT", ...)` for both methods. Delete custom 405 fallbacks.
**Success:** DRY, single error-handling path for all API calls.

## Step 4: Add Shuffle, Repeat, Seek Commands
**Priority:** HIGH
**Files:** `scripts/spotify.py` → new methods + CLI routing
**What:**
- `spotify shuffle [on|off|toggle]` → PUT `/me/player/shuffle`
- `spotify repeat [track|context|off]` → PUT `/me/player/repeat`
- `spotify seek <seconds>` or `spotify seek +30` / `spotify seek -15` → PUT `/me/player/seek`
**Success:** Commands work, help text updated.

## Step 5: Consolidate Version to Single Source
**Priority:** MEDIUM
**Files:** `scripts/spotify.py`, `SKILL.md`, `spotify` wrapper
**What:** `__version__ = "1.2.0"` in spotify.py. SKILL.md and help text read from it.
**Success:** One version number, everywhere consistent.

## Step 6: Fix Token Refresh Failure Path
**Priority:** HIGH
**Files:** `scripts/spotify.py` → `_request()` 401 handler
**What:** When refresh_token also fails → clear message "Re-Auth nötig: spotify auth" instead of stacktrace.
**Success:** Graceful degradation with actionable error message.

## Step 7: Fix Credential Parsing in Bash Wrapper
**Priority:** MEDIUM
**Files:** `spotify` (bash wrapper)
**What:** Replace fragile `grep -A1` with robust parser. Handle edge cases (missing lines, whitespace variations).
**Success:** Credentials load reliably even with format variations.

## Step 8: Fix Album Search Support
**Priority:** LOW
**Files:** `scripts/spotify.py` → `search()`
**What:** Add `album` formatting in search type handling (currently falls through to raw json.dumps).
**Success:** `spotify search "query" album` returns formatted results.

## Step 9: Improve Cover Command
**Priority:** LOW
**Files:** `scripts/spotify.py` → `cover` handling
**What:** Add `--save <path>` option to download cover art. Default: print URL (current behavior).
**Success:** `spotify cover --save /tmp/cover.jpg` downloads the image.

## Step 10: Update SKILL.md Tables → Lists + Add New Commands
**Priority:** LOW
**Files:** `SKILL.md`
**What:** Replace markdown tables with lists (Discord/Telegram compatible). Document shuffle/repeat/seek. Sync version to 1.2.0.
**Success:** SKILL.md renders correctly everywhere, reflects all new commands.

## Step 11: Add Debug Mode
**Priority:** LOW
**Files:** `scripts/spotify.py` → `_request()`
**What:** `--debug` flag prints request URL, method, status code, response time.
**Success:** `spotify --debug now` shows timing and response details.

---

## Execution Order
Steps 1→11 in order. Steps 1-3 are critical path, 4-6 high value, 7-11 polish.
