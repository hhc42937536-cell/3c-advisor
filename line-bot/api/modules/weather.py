"""
modules/weather.py — 天氣＋穿搭建議 ＋ 早安摘要
================================================
從 webhook.py 提取的獨立模組。

對外接口：
  build_weather_message(text, user_id="")   → list[dict]
  build_morning_summary(text, user_id="")   → list[dict]
  build_weather_region_picker()             → list[dict]
  build_weather_city_picker(region="")      → list[dict]
"""

import os
import re

from utils.redis import redis_get as _redis_get, redis_set as _redis_set
from modules.weather_morning_data import (
    _CITY_LOCAL_DEALS,
    _CITY_LOCAL_TIPS,
    _GENERIC_LOCAL_DEALS,
    _GENERIC_LOCAL_TIPS,
    _MORNING_ACTIONS,
    _SPECIAL_DEALS,
    _SURPRISES_FALLBACK,
    _WEEKLY_DEALS,
)
from modules.weather_flex import build_weather_flex as _shared_build_weather_flex
from modules.weather_fetchers import fetch_aqi as _shared_fetch_aqi
from modules.weather_fetchers import fetch_cwa_weather as _shared_fetch_cwa_weather
from modules.weather_fetchers import fetch_quick_oil as _shared_fetch_quick_oil
from modules.weather_fetchers import fetch_quick_rates as _shared_fetch_quick_rates
from modules.weather_cache import get_accupass_cache as _shared_get_accupass_cache
from modules.weather_cache import get_surprise_cache as _shared_get_surprise_cache
from modules.weather_cache import load_accupass_cache as _shared_load_accupass_cache
from modules.weather_cache import load_surprise_cache as _shared_load_surprise_cache
from modules.weather_morning_helpers import bot_invite_text as _shared_bot_invite_text
from modules.weather_morning_helpers import day_city_hash as _shared_day_city_hash
from modules.weather_morning_helpers import day_user_city_hash as _shared_day_user_city_hash
from modules.weather_morning_helpers import get_city_local_deal as _shared_get_city_local_deal
from modules.weather_morning_helpers import get_morning_actions as _shared_get_morning_actions
from modules.weather_morning_helpers import get_national_deal as _shared_get_national_deal
from modules.weather_advice import estimate_uvi as _shared_estimate_uvi
from modules.weather_advice import outfit_advice as _shared_outfit_advice
from modules.weather_advice import wx_icon as _shared_wx_icon
from modules.weather_pickers import build_morning_city_picker as _shared_build_morning_city_picker
from modules.weather_pickers import build_weather_city_picker as _shared_build_weather_city_picker
from modules.weather_pickers import build_weather_region_picker as _shared_build_weather_region_picker

# ─── 環境變數 ──────────────────────────────────────────────
_CWA_KEY = os.environ.get("CWA_API_KEY", "")
_MOE_KEY = os.environ.get("MOE_API_KEY", "")
LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")

# ─── 城市 / 地區資料 ─────────────────────────────────────
_AREA_REGIONS = {
    "北部": ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部": ["台中", "彰化", "南投", "雲林"],
    "南部": ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}
_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]

_CWA_CITY_MAP = {
    "台北": "臺北市", "台中": "臺中市", "台南": "臺南市", "高雄": "高雄市",
    "新北": "新北市", "桃園": "桃園市", "基隆": "基隆市",
    "新竹": "新竹縣", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "嘉義": "嘉義縣",
    "屏東": "屏東縣", "宜蘭": "宜蘭縣", "花蓮": "花蓮縣",
    "台東": "臺東縣", "澎湖": "澎湖縣", "金門": "金門縣", "連江": "連江縣",
}

_WEATHER_CITIES = _ALL_CITIES

_AQI_STATION = {
    "台北": "中正", "台中": "西屯", "台南": "台南", "高雄": "前金",
    "新北": "板橋", "桃園": "桃園", "新竹": "新竹", "苗栗": "苗栗",
    "彰化": "彰化", "嘉義": "嘉義", "屏東": "屏東", "宜蘭": "宜蘭",
    "花蓮": "花蓮", "台東": "台東", "基隆": "基隆", "澎湖": "馬公",
    "南投": "南投", "雲林": "斗六", "金門": "金門", "連江": "馬祖",
}

# ─── 早安摘要資料 ──────────────────────────────────────────








# ─── 驚喜快取（module 層級 lazy-load）─────────────────────


def _load_surprise_cache() -> dict:
    return _shared_load_surprise_cache()


def _get_surprise_cache() -> dict:
    return _shared_get_surprise_cache()


def _load_accupass_cache() -> dict:
    return _shared_load_accupass_cache()


def _get_accupass_cache() -> dict:
    return _shared_get_accupass_cache()


# ─── 工具函式 ──────────────────────────────────────────────

def _bot_invite_text() -> str:
    return _shared_bot_invite_text(LINE_BOT_ID)


def _day_city_hash(doy: int, city: str, salt: int = 0) -> int:
    return _shared_day_city_hash(doy, city, salt)


def _day_user_city_hash(doy: int, city: str, user_id: str, salt: int = 0) -> int:
    return _shared_day_user_city_hash(doy, city, user_id, salt)


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


# ─── 天氣 API 函式 ─────────────────────────────────────────

def _fetch_cwa_weather(city: str) -> dict:
    return _shared_fetch_cwa_weather(
        city,
        cwa_key=_CWA_KEY,
        cwa_city_map=_CWA_CITY_MAP,
        redis_get=_redis_get,
        redis_set=_redis_set,
    )


def _wx_icon(wx: str) -> str:
    return _shared_wx_icon(wx)


def _outfit_advice(max_t: int, min_t: int, pop: int) -> tuple:
    return _shared_outfit_advice(max_t, min_t, pop)


def _fetch_aqi(city: str) -> dict:
    return _shared_fetch_aqi(city, moe_key=_MOE_KEY, aqi_station=_AQI_STATION)


def _estimate_uvi(wx: str, max_t: int) -> dict:
    return _shared_estimate_uvi(wx, max_t)


def _fetch_quick_oil() -> dict:
    return _shared_fetch_quick_oil(redis_get=_redis_get, redis_set=_redis_set)


def _fetch_quick_rates() -> dict:
    return _shared_fetch_quick_rates(redis_get=_redis_get, redis_set=_redis_set)


def _get_national_deal(city: str, user_id: str = "") -> tuple:
    return _shared_get_national_deal(
        city,
        user_id,
        special_deals=_SPECIAL_DEALS,
        weekly_deals=_WEEKLY_DEALS,
        surprises_fallback=_SURPRISES_FALLBACK,
        surprise_cache=_get_surprise_cache(),
    )


def _get_city_local_deal(city: str, user_id: str = "") -> tuple:
    return _shared_get_city_local_deal(
        city,
        user_id,
        accupass_cache=_get_accupass_cache(),
        city_local_deals=_CITY_LOCAL_DEALS,
        generic_local_deals=_GENERIC_LOCAL_DEALS,
        city_local_tips=_CITY_LOCAL_TIPS,
        generic_local_tips=_GENERIC_LOCAL_TIPS,
    )


def _get_morning_actions() -> list:
    return _shared_get_morning_actions(_MORNING_ACTIONS)


# ─── 主要 Flex 建構函式 ────────────────────────────────────
def build_weather_flex(city: str, user_id: str = "") -> list:
    return _shared_build_weather_flex(
        city,
        user_id,
        fetch_cwa_weather=_fetch_cwa_weather,
        fetch_aqi=_fetch_aqi,
        outfit_advice=_outfit_advice,
        wx_icon=_wx_icon,
        estimate_uvi=_estimate_uvi,
        bot_invite_text=_bot_invite_text,
    )


def build_weather_region_picker() -> list:
    return _shared_build_weather_region_picker(_AREA_REGIONS)


def build_weather_city_picker(region: str = "") -> list:
    return _shared_build_weather_city_picker(region, _AREA_REGIONS, _ALL_CITIES)


def _build_morning_city_picker() -> list:
    return _shared_build_morning_city_picker()


def build_morning_summary(text: str, user_id: str = "") -> list:
    return _shared_build_morning_summary(
        text,
        user_id,
        all_cities=_ALL_CITIES,
        line_bot_id=LINE_BOT_ID,
        morning_actions=_MORNING_ACTIONS,
        get_user_city=_get_user_city,
        set_user_city=_set_user_city,
        build_morning_city_picker=_build_morning_city_picker,
        fetch_cwa_weather=_fetch_cwa_weather,
        fetch_quick_rates=_fetch_quick_rates,
        fetch_quick_oil=_fetch_quick_oil,
        wx_icon=_wx_icon,
        outfit_advice=_outfit_advice,
        get_national_deal=_get_national_deal,
        get_city_local_deal=_get_city_local_deal,
    )


def build_weather_message(text: str, user_id: str = "") -> list:
    """天氣模組主路由"""
    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        _set_user_city(user_id, city_m.group(1))
        return build_weather_flex(city_m.group(1), user_id=user_id)

    for r in _AREA_REGIONS:
        if r in text:
            return build_weather_city_picker(r)

    return build_weather_region_picker()
