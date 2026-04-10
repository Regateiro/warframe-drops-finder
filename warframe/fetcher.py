import json
import os
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://drops.warframestat.us/data/all.json"
CACHE_FILE = ".drop_cache.json"


def fetch_drop_data(force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)

    print("Fetching drop data from API...")
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
    print("Data cached successfully.")
    return data
