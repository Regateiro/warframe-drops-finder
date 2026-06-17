"""
Data fetching and caching for Warframe drop tables.

This module handles fetching drop table data from the WarframeStat.us API
and caching it locally to avoid repeated network requests.

Source: https://drops.warframestat.us/data/all.json
Cache: .drop_cache.json (24 hour TTL by default)

The caching strategy:
- On first run, fetch data from the API and save to cache file
- On subsequent runs, load from cache
- If cache is missing or corrupted, fetch fresh data from API
- Expired cache (> 24 hours old) auto-refreshes regardless of force_refresh
- force_refresh=True forces a refresh after at least 5 minutes have passed
"""

# Standard library imports for file I/O, networking, and time
import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# API endpoint for Warframe drop tables (WarframeStat.us)
API_URL = "https://drops.warframestat.us/data/all.json"
# Local cache file to store fetched data
CACHE_FILE = ".drop_cache.json"
# Lock file to coordinate cache access across gunicorn workers
LOCK_FILE = CACHE_FILE + ".lock"
# Cache time-to-live in seconds (86400 = 24 hours)
CACHE_MAX_AGE = 86400
# Minimum age before force_refresh takes effect (300 = 5 minutes)
FORCE_REFRESH_MIN_AGE = 300


def fetch_drop_data(force_refresh: bool = False, force_load: bool = False) -> tuple[dict[str, Any], float | None, bool]:
    """Fetch drop data from cache or API.

    This is the main entry point for getting drop table data.
    It checks if valid cached data exists and returns it,
    otherwise fetches fresh data from the API.

    Args:
        force_refresh: If False (default), use cached data if available.
            Expired cache (> 24h) auto-refreshes regardless of this flag.
            If True, forces a refresh only when the cache is at least
            5 minutes old to prevent misuse.
        force_load: If True, forces loading data from disk.

    Returns:
        A tuple of (drop data dictionary, cache timestamp, boolean indicating if refreshed).
        The boolean is True if new data was fetched from the API, False if from cache.

    Raises:
        SystemExit(1): If no cached data exists and API request fails.
    """
    # No cache file at all -> fetch fresh data to populate initial cache
    if not os.path.exists(CACHE_FILE):
        return refresh_drop_data()

    # Cache exists — check expiration before deciding whether to force-load or fetch fresh
    disk_cache_mtime = os.path.getmtime(CACHE_FILE)
    disk_cache_age = time.time() - disk_cache_mtime
    disk_cache_expired = disk_cache_age > CACHE_MAX_AGE  # > 24 hours old

    # Expired cache always refreshes via API
    if disk_cache_expired:
        return refresh_drop_data()

    # Force load from disk if needed
    if force_load:
        return load_drop_data()

    # Guard against force_refresh misuse: if cache is less than 5 minutes old,
    # always use it regardless of the force_refresh flag.
    if force_refresh and disk_cache_age > FORCE_REFRESH_MIN_AGE:
        return refresh_drop_data()

    # No refresh needed, caller can load from internal cache
    return None, disk_cache_mtime, False


def load_drop_data() -> tuple[dict[str, Any], float | None, bool]:
    """Load drop data from cache, refreshing if corrupted.

    Returns:
        A tuple of (drop data dictionary, cache timestamp, boolean indicating if refreshed).
        The boolean is True if new data was fetched from the API due to cache issues, False if from cache.
    """
    with open(CACHE_FILE) as f:
        try:
            return json.load(f), os.path.getmtime(CACHE_FILE), False
        except (json.JSONDecodeError, IOError) as e:
            print(f"Cache error: {e}. Refreshing data.")
            return refresh_drop_data()


def _read_cache_safe() -> tuple[dict[str, Any] | None, float | None, bool]:
    """Try to read cache, return data or None if missing/corrupted."""
    if not os.path.exists(CACHE_FILE):
        return None, None, False
    try:
        with open(CACHE_FILE) as f:
            return json.load(f), os.path.getmtime(CACHE_FILE), False
    except (json.JSONDecodeError, IOError) as e:
        print(f"Cache corrupted: {e}")
        return None, None, False


def refresh_drop_data() -> tuple[dict[str, Any] | None, float | None, bool]:
    """Fetch fresh data from the API and update cache atomically.

    Makes an HTTP request to the WarframeStat.us API to get the latest
    drop table data. If the request fails, falls back to existing cache
    if available. If both fail, returns `(None, None, False)` so callers
    can handle gracefully instead of crashing.

    Uses a file lock to coordinate between gunicorn workers (only one
    worker fetches from API at a time; others use existing cache).
    Writes cache atomically (temp file + rename) so concurrent readers
    never see a partial file.
    """
    # Try non-blocking exclusive lock — if another worker is already
    # refreshing, just use whatever cache exists (even if expired).
    lock_fd = None
    try:
        lock_fd = open(LOCK_FILE, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            lock_fd = None
            cached = _read_cache_safe()
            return cached if cached[0] is not None else (None, None, False)
    except OSError:
        lock_fd = None

    try:
        # Double-check: another worker may have refreshed while we waited
        if os.path.exists(CACHE_FILE):
            age = time.time() - os.path.getmtime(CACHE_FILE)
            if age < FORCE_REFRESH_MIN_AGE:
                with open(CACHE_FILE) as f:
                    return json.load(f), os.path.getmtime(CACHE_FILE), False

        try:
            request = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read())
        except urllib.error.URLError as e:
            print(f"Failed to fetch data: {e}")
            cached = _read_cache_safe()
            return cached if cached[0] is not None else (None, None, False)

        # Atomic write: temp file then rename (prevents partial reads)
        tmp_file = CACHE_FILE + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(data, f)
        os.replace(tmp_file, CACHE_FILE)

        return data, os.path.getmtime(CACHE_FILE), True
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
