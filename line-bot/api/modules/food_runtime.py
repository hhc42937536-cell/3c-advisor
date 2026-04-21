"""Food runtime configuration, caches, weather, and user-state helpers."""

from __future__ import annotations

import datetime
import json
import os
import urllib.parse
import urllib.request

from modules.food_data import _CWA_CITY_MAP
from utils.redis import redis_get as _redis_get
from utils.redis import redis_set as _redis_set


ADMIN_USER_ID        = os.environ.get("ADMIN_USER_ID", "")


GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")


CWA_API_KEY          = os.environ.get("CWA_API_KEY", "")


_RESTAURANT_CACHE: dict = {}


try:
    _rest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "restaurant_cache.json"
    )
    if os.path.isfile(_rest_path):
        with open(_rest_path, encoding="utf-8") as _rf:
            _rest_data = json.load(_rf)
            _RESTAURANT_CACHE = _rest_data.get("restaurants", {})
except Exception:
    _RESTAURANT_CACHE = {}


_food_recent: dict = {}


def _tw_season(city: str = "") -> str:
    """依實際氣溫判斷季節（優先查天氣 API，fallback 月份）
    max_t >= 27°C → hot；<= 22°C → cold；23-26 → 依月份（4-10 hot）
    """
    if city:
        try:
            w = _fetch_cwa_weather(city)
            max_t = w.get("max_t")
            if max_t is not None:
                if max_t >= 27:
                    return "hot"
                if max_t <= 22:
                    return "cold"
        except Exception:
            pass
    m = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).month
    return "hot" if 4 <= m <= 10 else "cold"


def _fetch_cwa_weather(city: str) -> dict:
    """呼叫中央氣象署 F-C0032-001 取得36小時天氣預報（Redis cache 15 分鐘）"""
    if not CWA_API_KEY:
        return {"ok": False, "error": "no_key"}
    try:
        cached = _redis_get(f"cwa_wx:{city}")
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        pass
    cwb_name = _CWA_CITY_MAP.get(city, city + "市")
    url = (
        "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        f"?Authorization={CWA_API_KEY}"
        f"&locationName={urllib.parse.quote(cwb_name)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        locs = data.get("records", {}).get("location", [])
        if not locs:
            return {"ok": False, "error": "no_data"}
        elems = {e["elementName"]: e["time"] for e in locs[0]["weatherElement"]}

        def _get(key, idx, default="—"):
            try:
                return elems[key][idx]["parameter"]["parameterName"]
            except Exception:
                return default

        result = {
            "ok": True, "city": city,
            "wx": _get("Wx", 0), "pop": int(_get("PoP", 0, "0")),
            "min_t": int(_get("MinT", 0, "20")), "max_t": int(_get("MaxT", 0, "25")),
            "wx_night": _get("Wx", 1), "pop_night": int(_get("PoP", 1, "0")),
            "wx_tom": _get("Wx", 2), "pop_tom": int(_get("PoP", 2, "0")),
            "min_tom": int(_get("MinT", 2, "20")), "max_tom": int(_get("MaxT", 2, "25")),
        }
        try:
            _redis_set(f"cwa_wx:{city}", json.dumps(result), ttl=900)
        except Exception:
            pass
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_user_city(user_id: str) -> str:
    """從 Redis 取得用戶上次使用的城市"""
    if not user_id:
        return ""
    cached = _redis_get(f"user_city:{user_id}")
    if cached and isinstance(cached, str):
        return cached
    return ""


def _set_user_city(user_id: str, city: str) -> None:
    """將用戶城市偏好存入 Redis（90 天）"""
    if user_id and city:
        _redis_set(f"user_city:{user_id}", city, ttl=86400 * 90)
