"""External data fetchers used by weather features."""

from __future__ import annotations

import csv as _csv
import json
import ssl as _ssl
import urllib.parse
import urllib.request


def _read_cached(redis_get, key: str):
    try:
        cached = redis_get(key)
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        return None
    return None


def _write_cached(redis_set, key: str, value: dict, ttl: int) -> None:
    try:
        redis_set(key, json.dumps(value), ttl=ttl)
    except Exception:
        pass


def fetch_cwa_weather(city: str, *, cwa_key: str, cwa_city_map: dict, redis_get, redis_set) -> dict:
    """Fetch Taiwan CWA 36-hour forecast with a 15-minute Redis cache."""
    if not cwa_key:
        return {"ok": False, "error": "no_key"}
    cached = _read_cached(redis_get, f"cwa_wx:{city}")
    if cached:
        return cached

    cwa_name = cwa_city_map.get(city, city + "市")
    url = (
        "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        f"?Authorization={cwa_key}"
        f"&locationName={urllib.parse.quote(cwa_name)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("success") != "true":
            return {"ok": False, "error": "api_error"}
        locs = data["records"]["location"]
        if not locs:
            return {"ok": False, "error": "no_data"}
        elems = {e["elementName"]: e["time"] for e in locs[0]["weatherElement"]}

        def _get(key: str, idx: int, default: str = "—") -> str:
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
        _write_cached(redis_set, f"cwa_wx:{city}", result, ttl=900)
        return result
    except Exception as exc:
        print(f"[weather] {exc}")
        return {"ok": False, "error": str(exc)}


def fetch_aqi(city: str, *, moe_key: str, aqi_station: dict) -> dict:
    """Fetch live AQI from Taiwan MOENV."""
    if not moe_key:
        return {"ok": False}
    station = aqi_station.get(city, city)
    url = (
        "https://data.moenv.gov.tw/api/v2/aqx_p_432"
        f"?api_key={moe_key}&limit=3&sort=ImportDate+desc"
        f"&filters=SiteName,EQ,{urllib.parse.quote(station)}"
        "&format=JSON&fields=SiteName,AQI,Status,PM2.5,Pollutant"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
        recs = data.get("records", [])
        if not recs:
            return {"ok": False}
        rec = recs[0]
        aqi = int(rec.get("AQI") or 0)
        status = rec.get("Status", "")
        pm25 = rec.get("PM2.5", "")
        pollutant = rec.get("Pollutant", "")
        if aqi <= 50:
            color, emoji = "#2E7D32", "🟢"
        elif aqi <= 100:
            color, emoji = "#F9A825", "🟡"
        elif aqi <= 150:
            color, emoji = "#E65100", "🟠"
        elif aqi <= 200:
            color, emoji = "#C62828", "🔴"
        else:
            color, emoji = "#6A1B9A", "🟣"
        label = f"{emoji} AQI {aqi}　{status}"
        if pm25:
            label += f"　PM2.5: {pm25}"
        if pollutant:
            label += f"　主因: {pollutant}"
        return {"ok": True, "aqi": aqi, "label": label, "color": color}
    except Exception as exc:
        print(f"[AQI] {exc}")
        return {"ok": False}


def fetch_quick_oil(*, redis_get, redis_set) -> dict:
    """Fetch Taiwan CPC oil prices with a 6-hour Redis cache."""
    cached = _read_cached(redis_get, "morning_oil")
    if cached:
        return cached

    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://www.cpc.com.tw/GetOilPriceJson.aspx?type=TodayOilPriceString",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=4, context=ctx) as response:
            data = json.loads(response.read().decode("utf-8"))
        result = {
            "92": data.get("sPrice1", "?"),
            "95": data.get("sPrice2", "?"),
            "98": data.get("sPrice3", "?"),
        }
        _write_cached(redis_set, "morning_oil", result, ttl=21600)
        return result
    except Exception:
        return {}


def fetch_quick_rates(*, redis_get, redis_set) -> dict:
    """Fetch USD and JPY spot sell rates from Bank of Taiwan with a 1-hour cache."""
    cached = _read_cached(redis_get, "morning_rates")
    if cached:
        return cached

    try:
        req = urllib.request.Request(
            "https://rate.bot.com.tw/xrt/flcsv/0/day",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            raw = response.read().decode("utf-8-sig")
        result = {}
        for row in _csv.reader(raw.strip().split("\n")):
            if len(row) < 14 or row[0] == "幣別":
                continue
            code = row[0].strip()
            if code not in ("USD", "JPY"):
                continue
            try:
                result[code] = {
                    "spot_buy": float(row[3]) if row[3].strip() else 0,
                    "spot_sell": float(row[13]) if row[13].strip() else 0,
                }
            except (ValueError, IndexError):
                pass
        _write_cached(redis_set, "morning_rates", result, ttl=3600)
        return result
    except Exception as exc:
        print(f"[quick_rates] {exc}")
        return {}
