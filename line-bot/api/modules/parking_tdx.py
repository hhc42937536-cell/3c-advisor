"""TDX API and parking result cache helpers."""

from __future__ import annotations

import gzip
import json
import time
import urllib.parse
import urllib.request


def get_tdx_token(
    *,
    client_id: str,
    client_secret: str,
    token_cache: dict,
    redis_get,
    redis_set,
) -> str:
    """Get a TDX API token with memory and Redis caching."""
    now = time.time()
    if token_cache["token"] and now < token_cache["expires"]:
        return token_cache["token"]
    if not client_id or not client_secret:
        return ""

    cached = redis_get("tdx_token")
    if cached and isinstance(cached, str) and len(cached) > 20:
        print("[TDX] token Redis命中")
        token_cache["token"] = cached
        token_cache["expires"] = now + 3000
        return cached

    try:
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode()
        req = urllib.request.Request(
            "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read())
        token = result.get("access_token", "")
        expires_in = int(result.get("expires_in", 3600))
        safe_ttl = max(expires_in - 60, 300)
        token_cache["token"] = token
        token_cache["expires"] = now + safe_ttl
        redis_set("tdx_token", token, ttl=safe_ttl)
        print("[TDX] token 重新取得並存 Redis")
        return token
    except Exception as exc:
        print(f"[TDX] token 失敗: {exc}")
        return ""


def tdx_get(path: str, token: str, timeout: int = 20) -> list:
    """Call a TDX API endpoint and normalize common nested list responses."""
    url = "https://tdx.transportdata.tw/api/basic/v1/" + path
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            for key in ("CarParks", "ParkingAvailabilities", "ParkingLots", "RoadSections"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            for value in data.values():
                if isinstance(value, list):
                    return value
            return []
    except Exception as exc:
        print(f"[TDX] GET {path[:80]} 失敗: {exc}")
        return []


def parking_cache_key(lat: float, lon: float) -> str:
    """Round coordinates to roughly 2km buckets for parking result cache."""
    return f"{round(lat / 0.02) * 0.02:.3f}_{round(lon / 0.02) * 0.02:.3f}"


def peek_parking_cache(lat: float, lon: float, *, redis_get, result_cache: dict, ttl: int):
    """Read cached parking messages without triggering any API calls."""
    cache_key = parking_cache_key(lat, lon)
    now = time.time()
    cached = redis_get(f"parking_{cache_key}")
    if cached is not None:
        return cached
    if cache_key in result_cache:
        ts, messages = result_cache[cache_key]
        if now - ts < ttl:
            return messages
    return None
