"""Central configuration & constants for sPot.

Single source of truth for values that were previously scattered as magic numbers
across the codebase. Importing this module has no side effects and no third-party
dependencies, so it is safe to import anywhere (including tests).
"""
from __future__ import annotations

import os
from typing import Optional


# --- UDP input channel (MUST match clickwheel/click.c) ------------------------
UDP_IP = "127.0.0.1"
UDP_PORT = 9090

# --- Click-wheel button bit codes (MUST match the #defines in clickwheel/click.c).
# These are the bit positions decoded from the wheel packet; they are shared with
# the C driver *by convention* (there is no shared header). Keep both sides in sync.
CENTER_BUTTON_BIT = 7   # select / enter
RIGHT_BUTTON_BIT = 8    # skip to next track
LEFT_BUTTON_BIT = 9     # skip to previous track
DOWN_BUTTON_BIT = 10    # play / pause
UP_BUTTON_BIT = 11      # back / menu
WHEEL_TOUCH_BIT = 29    # finger on/off the wheel

# --- GPIO pins (reference only; the authoritative copy lives in click.c) -------
CLOCK_PIN = 23
DATA_PIN = 25
HAPTIC_PIN = 26

# --- UI -----------------------------------------------------------------------
MENU_PAGE_SIZE = 6
SCREEN_TIMEOUT_SECONDS = 60
SPOT_GREEN = "#1DB954"
SPOT_BLACK = "#191414"
SPOT_WHITE = "#FFFFFF"

# --- Spotify / data sync ------------------------------------------------------
PAGE_SIZE = 50              # Spotify Web API page size for library sync
SEARCH_LIMIT = 5           # results per type (track/artist/album) when searching
DEVICE_NAME_FILTER = "Spotifypod"   # only Connect devices whose name contains this
REQUESTS_TIMEOUT = 10      # seconds, per Spotify HTTP request
REQUESTS_RETRIES = 3       # spotipy automatic retries on transient failures

# Now-playing background poll backoff (seconds): starts fast after an action,
# then backs off exponentially while nothing changes.
NOW_PLAYING_MIN_INTERVAL = 0.3
NOW_PLAYING_MAX_INTERVAL = 4.0
ACTION_INTERVAL = 0.4      # poll interval right after a transport action

# --- Redis (overridable via environment) --------------------------------------
REDIS_HOST: str = os.environ.get("SPOT_REDIS_HOST", "127.0.0.1")
REDIS_PORT: int = int(os.environ.get("SPOT_REDIS_PORT", "6379"))
REDIS_DB: int = int(os.environ.get("SPOT_REDIS_DB", "0"))
REDIS_PASSWORD: Optional[str] = os.environ.get("SPOT_REDIS_PASSWORD") or None

# Key prefixes used in Redis. clear() only wipes these, never the whole db.
REDIS_KEY_PREFIXES: list[str] = [
    "playlist-uri:", "playlist-tracks:", "playlist-index:",
    "album-uri:", "album-index:",
    "nr-uri:", "nr-index:",
    "show-uri:", "show-episodes:", "show-index:",
    "artist:", "track:", "device:",
]
