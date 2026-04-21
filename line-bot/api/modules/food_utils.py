"""Shared helpers for food recommendation modules."""

import datetime
import json
import math
import os
import urllib.parse


_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_ACCUPASS_CACHE = None


def _load_json(filename: str, default):
    """Load JSON from api/data; return default when the file is unavailable."""
    try:
        with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as _f:
            return json.load(_f)
    except Exception:
        return default


def _get_accupass_cache() -> dict:
    """Lazy-load cached Accupass crawler data."""
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        try:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_path = os.path.join(base, "accupass_cache.json")
            if os.path.exists(cache_path):
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                _ACCUPASS_CACHE = data.get("events", {})
            else:
                _ACCUPASS_CACHE = {}
        except Exception:
            _ACCUPASS_CACHE = {}
    return _ACCUPASS_CACHE


def _maps_url(keyword: str, area: str = "", **_kw) -> str:
    """Build a Google Maps search URL."""
    if area:
        q = urllib.parse.quote(f"{area} {keyword}")
    else:
        q = urllib.parse.quote(f"{keyword} 附近")
    return f"https://www.google.com/maps/search/{q}/"


def _tw_meal_period() -> tuple:
    """Return (period code, label) using Taiwan time (UTC+8)."""
    h = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).hour
    if 5 <= h < 10:
        return "M", "早餐推薦"
    if 10 <= h < 14:
        return "D", "午餐推薦"
    if 14 <= h < 17:
        return "D", "下午點心推薦"
    if 17 <= h < 22:
        return "N", "晚餐推薦"
    return "L", "消夜推薦"


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Distance between two geo points in meters."""
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return int(earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _btn3d(
    label: str,
    text: str,
    main_c: str,
    shadow_c: str,
    txt_c: str = "#FFFFFF",
    flex: int = None,
) -> dict:
    """Build the raised button style reused across food Flex messages."""
    inner = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": main_c,
        "cornerRadius": "8px",
        "paddingTop": "13px",
        "paddingBottom": "13px",
        "paddingStart": "8px",
        "paddingEnd": "8px",
        "contents": [{
            "type": "text",
            "text": label,
            "color": txt_c,
            "align": "center",
            "weight": "bold",
            "size": "sm",
            "wrap": False,
        }],
    }
    outer = {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": shadow_c,
        "cornerRadius": "10px",
        "paddingBottom": "5px",
        "action": {"type": "message", "label": label[:20], "text": text},
        "contents": [inner],
    }
    if flex is not None:
        outer["flex"] = flex
    return outer
