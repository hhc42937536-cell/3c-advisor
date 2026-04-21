"""Local JSON cache loaders for weather-adjacent features."""

from __future__ import annotations

import json
import os


_SURPRISE_CACHE: dict | None = None
_ACCUPASS_CACHE: dict | None = None


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_surprise_cache() -> dict:
    """Load crawler surprise cache from surprise_cache.json."""
    try:
        path = os.path.join(_project_root(), "surprise_cache.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_surprise_cache() -> dict:
    global _SURPRISE_CACHE
    if _SURPRISE_CACHE is None:
        _SURPRISE_CACHE = load_surprise_cache()
    return _SURPRISE_CACHE


def load_accupass_cache() -> dict:
    """Load cached Accupass crawler events from accupass_cache.json."""
    try:
        cache_path = os.path.join(_project_root(), "accupass_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", {})
    except Exception:
        return {}


def get_accupass_cache() -> dict:
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        _ACCUPASS_CACHE = load_accupass_cache()
    return _ACCUPASS_CACHE
