"""Data fetching and caching for Warframe drop tables.

Source: https://drops.warframestat.us/data/all.json
Cache: .drop_cache.json (24 hour TTL by default)
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://drops.warframestat.us/data/all.json"
CACHE_FILE = ".drop_cache.json"
CACHE_MAX_AGE = 86400


def fetch_drop_data(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch drop data from cache or API.

    Args:
        force_refresh: If False (default), only refetch if cache is missing or corrupted.
            If True, also fetch fresh data from API if the cache if it is expired (>24h old).

    Returns:
        Dictionary containing all drop table data from the API.

    Raises:
        SystemExit(1): If force_refresh=True and no cached data exists to fall back on.
    """
    if not os.path.exists(CACHE_FILE) or (force_refresh and (time.time() - os.path.getmtime(CACHE_FILE) > CACHE_MAX_AGE)):
        return refresh_drop_data()

    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Cache error: {e}. Refreshing data.")
        return refresh_drop_data()


def refresh_drop_data() -> dict[str, Any]:
    """Fetch fresh data from the API and update cache.

    If the API request fails, falls back to existing cache if available.

    Returns:
        Dictionary containing all drop table data from the API.

    Raises:
        SystemExit(1): If API request fails and no cached data exists to fall back on.
    """
    try:
        request = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Failed to fetch data: {e}")
        if os.path.exists(CACHE_FILE):
            print("Using cached data.")
            with open(CACHE_FILE) as f:
                return json.load(f)
        raise SystemExit(1)

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

    return data
