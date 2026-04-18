"""
Warframe Drop Tables Package

This package provides a web application and API for searching Warframe item drop locations.

Main components:
- fetcher: Downloads and caches drop data from WarframeStat.us API
- parser: Parses and searches drop data
- models: Data models (DropResult)
- web: Flask web application and API endpoints
- iterators: Standalone iterator functions (alternative to parser)

Primary entry points:
- warframe.web: Main web application (run with gunicorn or flask)
- warframe.fetcher.fetch_drop_data(): Fetch drop data programmatically

Example usage:
    from warframe import fetch_drop_data
    data, refreshed = fetch_drop_data()
"""

# Re-export the main fetcher function for convenient access
from .fetcher import fetch_drop_data

# Define public API
__all__ = ["fetch_drop_data"]
