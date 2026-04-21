"""
modules/parking.py — 找車位（TDX 停車 API）
==============================================
從 webhook.py 提取的獨立模組（原始行 8728–10079）。

對外接口：
  build_parking_flex(lat, lon, city="")         → list[dict]
  _build_post_parking_food(city, lat, lon, user_id="") → list[dict]
"""

import json
import os
import urllib.parse
import urllib.request

from utils.redis import redis_get as _redis_get, redis_set as _redis_set
from utils.google_places import nearby_places as _nearby_places_google
from utils.google_places import photo_url as _places_photo_url
from utils.google_places import GOOGLE_PLACES_API_KEY
from modules.parking_geo import coords_to_tdx_city as _shared_coords_to_tdx_city
from modules.parking_geo import haversine as _shared_haversine
from modules.parking_geo import twd97tm2_to_wgs84 as _shared_twd97tm2_to_wgs84
from modules.parking_tdx import get_tdx_token as _shared_get_tdx_token
from modules.parking_tdx import parking_cache_key as _shared_parking_cache_key
from modules.parking_tdx import peek_parking_cache as _shared_peek_parking_cache
from modules.parking_tdx import tdx_get as _shared_tdx_get
from modules.parking_food import build_post_parking_food as _shared_build_post_parking_food
from modules.parking_food import build_restaurant_bubble as _shared_build_restaurant_bubble
from modules.parking_flex import build_parking_flex as _shared_build_parking_flex
from modules.parking_sources import get_hsinchu_parking as _shared_get_hsinchu_parking
from modules.parking_sources import get_nearby_parking as _shared_get_nearby_parking
from modules.parking_sources import get_ntpc_lot_parking as _shared_get_ntpc_lot_parking
from modules.parking_sources import get_ntpc_street_parking as _shared_get_ntpc_street_parking
from modules.parking_sources import get_tainan_parking as _shared_get_tainan_parking
from modules.parking_sources import get_taoyuan_parking as _shared_get_taoyuan_parking
from modules.parking_sources import get_tdx_parking as _shared_get_tdx_parking
from modules.parking_sources import get_yilan_parking as _shared_get_yilan_parking

# ─── 環境變數 ──────────────────────────────────────────────
TDX_CLIENT_ID     = os.environ.get("TDX_CLIENT_ID", "")
TDX_CLIENT_SECRET = os.environ.get("TDX_CLIENT_SECRET", "")

# ─── TDX Token 記憶體快取 ──────────────────────────────────
_tdx_token_cache: dict = {"token": "", "expires": 0.0}


def _get_tdx_token() -> str:
    return _shared_get_tdx_token(
        client_id=TDX_CLIENT_ID,
        client_secret=TDX_CLIENT_SECRET,
        token_cache=_tdx_token_cache,
        redis_get=_redis_get,
        redis_set=_redis_set,
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    return _shared_haversine(lat1, lon1, lat2, lon2)


def _tdx_get(path: str, token: str, timeout: int = 20) -> list:
    return _shared_tdx_get(path, token, timeout=timeout)


# 台灣各縣市座標框（lat_min, lat_max, lon_min, lon_max, tdx_city）
# 越小的框排越前面，讓 min(area) 選最精確的城市
# TDX 實測可用城市名稱（2026-04 驗證）：
#   直轄市/省轄市不加 County：Taipei, Keelung, Hsinchu, Chiayi, Taichung, Tainan, Kaohsiung, Taoyuan
#   縣需要加 County：HsinchuCounty, MiaoliCounty, ChanghuaCounty, NantouCounty,
#                    YunlinCounty, ChiayiCounty, PingtungCounty, HualienCounty, TaitungCounty, PenghuCounty
#   NewTaipei：API 存在但目前無資料（count=0）

# 各縣市行政中心座標（用於城市框重疊時的決勝）


def _coords_to_tdx_city(lat: float, lon: float) -> str:
    return _shared_coords_to_tdx_city(lat, lon)


# 城市停車資料快取（避免同一次請求重複拉 API）
_tdx_lots_cache:  dict = {}   # city -> (timestamp, [lots])
_tdx_avail_cache: dict = {}   # city -> (timestamp, {pid: avail})
_TDX_CACHE_TTL = 90           # 快取 90 秒（即時性夠用）

# 停車結果快取（座標格子，約 2km×2km，共用結果避免重複計算）
_parking_result_cache: dict = {}   # "lat2_lon2" -> (timestamp, messages)
_PARKING_RESULT_TTL = 180          # 3 分鐘


def _peek_parking_cache(lat: float, lon: float):
    return _shared_peek_parking_cache(
        lat,
        lon,
        redis_get=_redis_get,
        result_cache=_parking_result_cache,
        ttl=_PARKING_RESULT_TTL,
    )


def _parking_cache_key(lat: float, lon: float) -> str:
    return _shared_parking_cache_key(lat, lon)


def _get_tdx_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_tdx_parking(
        lat,
        lon,
        radius,
        get_tdx_token=_get_tdx_token,
        coords_to_tdx_city=_coords_to_tdx_city,
        tdx_get=_tdx_get,
        haversine=_haversine,
        redis_get=_redis_get,
        redis_set=_redis_set,
        tdx_lots_cache=_tdx_lots_cache,
        tdx_avail_cache=_tdx_avail_cache,
        tdx_cache_ttl=_TDX_CACHE_TTL,
    )


def _twd97tm2_to_wgs84(x: float, y: float):
    return _shared_twd97tm2_to_wgs84(x, y)


_NTPC_LOT_STATIC: dict = {}  # ID -> {name, addr, fare, total, lat, lon}


def _get_ntpc_lot_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_ntpc_lot_parking(
        lat,
        lon,
        radius,
        ntpc_lot_static=_NTPC_LOT_STATIC,
        redis_get=_redis_get,
        redis_set=_redis_set,
        haversine=_haversine,
        twd97tm2_to_wgs84=_twd97tm2_to_wgs84,
    )


def _get_ntpc_street_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_ntpc_street_parking(lat, lon, radius, haversine=_haversine)


def _get_tainan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_tainan_parking(lat, lon, radius, haversine=_haversine)


def _get_yilan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_yilan_parking(
        lat,
        lon,
        radius,
        get_tdx_token=_get_tdx_token,
        tdx_get=_tdx_get,
        redis_get=_redis_get,
        redis_set=_redis_set,
        haversine=_haversine,
    )


def _get_hsinchu_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_hsinchu_parking(lat, lon, radius, redis_get=_redis_get, redis_set=_redis_set, haversine=_haversine)


def _get_taoyuan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    return _shared_get_taoyuan_parking(lat, lon, radius, redis_get=_redis_get, redis_set=_redis_set, haversine=_haversine)


def _get_nearby_parking(lat: float, lon: float, radius: int = 1500) -> dict:
    return _shared_get_nearby_parking(
        lat,
        lon,
        radius,
        coords_to_tdx_city=_coords_to_tdx_city,
        get_yilan_parking=_get_yilan_parking,
        get_ntpc_street_parking=_get_ntpc_street_parking,
        get_ntpc_lot_parking=_get_ntpc_lot_parking,
        get_taoyuan_parking=_get_taoyuan_parking,
        get_hsinchu_parking=_get_hsinchu_parking,
        get_tainan_parking=_get_tainan_parking,
        get_tdx_parking=_get_tdx_parking,
    )


def _build_restaurant_bubble(r: dict, lat: float, lon: float, city: str,
                              eaten_set: set, subtitle: str = "") -> dict:
    return _shared_build_restaurant_bubble(
        r,
        lat,
        lon,
        city,
        eaten_set,
        haversine=_haversine,
        places_photo_url=_places_photo_url,
        subtitle=subtitle,
    )


def _build_post_parking_food(city: str, lat: float = None, lon: float = None,
                              user_id: str = "") -> list:
    try:
        import webhook as _wh
        get_eaten = _wh._get_eaten
        build_food_restaurant_flex = _wh.build_food_restaurant_flex
        restaurant_cache = _wh._RESTAURANT_CACHE
        bib_gourmand = _wh._BIB_GOURMAND
    except Exception:
        return []

    return _shared_build_post_parking_food(
        city,
        lat,
        lon,
        user_id,
        google_places_api_key=GOOGLE_PLACES_API_KEY,
        nearby_places_google=_nearby_places_google,
        places_photo_url=_places_photo_url,
        haversine=_haversine,
        get_eaten=get_eaten,
        build_food_restaurant_flex=build_food_restaurant_flex,
        restaurant_cache=restaurant_cache,
        bib_gourmand=bib_gourmand,
    )


def build_parking_flex(lat: float, lon: float, city: str = "") -> list:
    return _shared_build_parking_flex(
        lat,
        lon,
        city,
        tdx_client_id=TDX_CLIENT_ID,
        parking_cache_key=_parking_cache_key,
        redis_get=_redis_get,
        redis_set=_redis_set,
        parking_result_cache=_parking_result_cache,
        parking_result_ttl=_PARKING_RESULT_TTL,
        get_nearby_parking=_get_nearby_parking,
    )
