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
- If force_refresh=True and cache is expired, fetch fresh data from API
"""

# Standard library imports for file I/O, networking, and time
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
# Cache time-to-live in seconds (86400 = 24 hours)
CACHE_MAX_AGE = 86400


def fetch_drop_data(force_refresh: bool = False) -> tuple[dict[str, Any], bool]:
    """Fetch drop data from cache or API.

    This is the main entry point for getting drop table data.
    It checks if valid cached data exists and returns it,
    otherwise fetches fresh data from the API.

    Args:
        force_refresh: If False (default), use cached data if available and not expired.
            If True, fetch fresh data from the API even if cache is valid.

    Returns:
        A tuple of (drop data dictionary, boolean indicating if data was refreshed).
        The boolean is True if new data was fetched from the API, False if from cache.

    Raises:
        SystemExit(1): If force_refresh=True and no cached data exists to fall back on
            (cannot fetch from API in that case).
    """
    # Check if cache file exists and whether we should use it
    cache_exists = os.path.exists(CACHE_FILE)
    cache_expired = cache_exists and (time.time() - os.path.getmtime(CACHE_FILE) > CACHE_MAX_AGE)

    # Missing cache, expired cache, or forced refresh -> fetch fresh data
    if not cache_exists or (force_refresh and cache_expired):
        return refresh_drop_data(), True

    # Cache exists and is valid -> try to load it
    try:
        with open(CACHE_FILE) as f:
            return json.load(f), False
    except (json.JSONDecodeError, IOError) as e:
        # Cache is corrupted -> refresh
        print(f"Cache error: {e}. Refreshing data.")
        return refresh_drop_data(), True


def refresh_drop_data() -> dict[str, Any]:
    """Fetch fresh data from the API and update cache.

    Makes an HTTP request to the WarframeStat.us API to get the latest
    drop table data. If the request fails, falls back to existing cache
    if available. If both fail, exits with error.

    Returns:
        Dictionary containing all drop table data from the API.

    Raises:
        SystemExit(1): If API request fails and no cached data exists to fall back on.
    """
    try:
        # Create HTTP request with User-Agent header (some APIs require it)
        request = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        # Open URL with 60-second timeout
        with urllib.request.urlopen(request, timeout=60) as response:
            # Read response body and parse JSON
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        # API request failed -> try to use existing cache
        print(f"Failed to fetch data: {e}")
        if os.path.exists(CACHE_FILE):
            print("Using cached data.")
            with open(CACHE_FILE) as f:
                return json.load(f)
        # No cache available -> fatal error
        raise SystemExit(1)

    # Write fresh data to cache file for future use
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

    return data
