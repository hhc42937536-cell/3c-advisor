"""
食物相關功能模組
包含：今天吃什麼、聚餐推薦、必比登推介、城市特色小吃、餐廳回饋
"""


# ── 外部工具（utils 模組）──
from utils.line_api import push_message
from modules.food_group_dining import build_group_dining_message as _shared_build_group_dining_message
from modules.food_router import build_food_message as _shared_build_food_message
from modules.food_events import build_live_food_events as _shared_build_live_food_events
from modules.food_recommendations import build_food_flex as _shared_build_food_flex
from modules.food_recommendations import filter_food_by_time as _shared_filter_food_by_time
from modules.food_bib_gourmand import build_bib_gourmand_flex as _shared_build_bib_gourmand_flex
from modules.food_menu_builders import build_food_area_picker as _shared_build_food_area_picker
from modules.food_menu_builders import build_food_entry_city_picker as _shared_build_food_entry_city_picker
from modules.food_menu_builders import build_food_entry_region_picker as _shared_build_food_entry_region_picker
from modules.food_menu_builders import build_food_menu as _shared_build_food_menu
from modules.food_menu_builders import build_food_region_picker as _shared_build_food_region_picker
from modules.food_menu_builders import build_food_special_picker as _shared_build_food_special_picker
from modules.food_menu_builders import build_food_type_picker as _shared_build_food_type_picker
from modules.food_specialties import build_city_specialties as _shared_build_city_specialties
from modules.food_specialties import build_specialty_shops as _shared_build_specialty_shops
from modules.food_specialties import build_trending_specialty as _shared_build_trending_specialty
from modules.food_specialties import build_trending_by_district as _shared_build_trending_by_district
from modules.food_specialties import build_new_shops as _shared_build_new_shops
from modules.food_restaurants import build_food_restaurant_flex as _shared_build_food_restaurant_flex
from modules.food_restaurants import build_restaurant_bubble as _shared_build_restaurant_bubble
from modules.food_restaurants import places_photo_url as _shared_places_photo_url
from modules.food_restaurants import text_search_places as _shared_text_search_places
from modules.food_utils import (
    _get_accupass_cache,
    _haversine,
    _maps_url,
    _tw_meal_period,
)
from handlers.feedback_routes import build_feedback_intro
from handlers.feedback_routes import handle_food_feedback as _shared_handle_food_feedback
from handlers.feedback_routes import handle_general_report as _shared_handle_general_report
from handlers.feedback_routes import handle_user_suggestion as _shared_handle_user_suggestion
from modules.food_data import _ALL_CITIES
from modules.food_data import _ALL_FOOD_KEYWORDS
from modules.food_data import _BIB_GOURMAND
from modules.food_data import _CITY_SPECIALTIES
from modules.food_data import _FOOD_DB
from modules.food_data import _STYLE_KEYWORDS
from modules.food_data import _AREA_REGIONS
from modules.food_runtime import ADMIN_USER_ID
from modules.food_runtime import GOOGLE_PLACES_API_KEY
from modules.food_runtime import _RESTAURANT_CACHE
from modules.food_runtime import _food_recent
from modules.food_runtime import _get_user_city
from modules.food_runtime import _redis_get
from modules.food_runtime import _redis_set
from modules.food_runtime import _set_user_city
from modules.food_runtime import _tw_season

# --- Food utilities -----------------------------------------------------


def _filter_food_by_time(pool: list, period: str, city: str = "") -> list:
    return _shared_filter_food_by_time(pool, period, season=_tw_season(city))


# --- Restaurant search wrappers ------------------------------------------

def _text_search_places(query: str, max_results: int = 5) -> list:
    return _shared_text_search_places(query, GOOGLE_PLACES_API_KEY, max_results=max_results)


def _places_photo_url(photo_ref: str, max_width: int = 400) -> str:
    return _shared_places_photo_url(photo_ref, GOOGLE_PLACES_API_KEY, max_width=max_width)


def _build_restaurant_bubble(r: dict, lat, lon, city: str,
                              eaten_set: set, subtitle: str = "") -> dict:
    return _shared_build_restaurant_bubble(
        r, lat, lon, city, eaten_set, _haversine, _places_photo_url, subtitle=subtitle
    )


def build_food_restaurant_flex(area: str, food_type: str = "") -> list:
    return _shared_build_food_restaurant_flex(
        area,
        food_type,
        _RESTAURANT_CACHE,
        _food_recent,
        build_food_flex,
        _maps_url,
        _tw_meal_period,
    )


# --- Group dining wrappers ------------------------------------------------

def build_group_dining_message(text: str) -> list:
    """????????"""
    return _shared_build_group_dining_message(text, _BIB_GOURMAND)


# --- Bib Gourmand builders ------------------------------------------------

def build_bib_gourmand_flex(area: str = "") -> list:
    return _shared_build_bib_gourmand_flex(area, _BIB_GOURMAND, _food_recent, _maps_url)
# --- Feedback wrappers ---------------------------------------------------

def handle_food_feedback(text: str, user_id: str = "") -> list:
    return _shared_handle_food_feedback(
        text, user_id, admin_user_id=ADMIN_USER_ID, push_message=push_message
    )


def handle_general_report(text: str, user_id: str = "") -> list:
    return _shared_handle_general_report(
        text, user_id, admin_user_id=ADMIN_USER_ID, push_message=push_message
    )


def handle_user_suggestion(text: str, user_id: str, display_name: str = "") -> list:
    return _shared_handle_user_suggestion(
        text,
        user_id,
        display_name,
        admin_user_id=ADMIN_USER_ID,
        push_message=push_message,
    )


# --- Food recommendation builders ----------------------------------------

def build_food_flex(style: str, area: str = "") -> list:
    return _shared_build_food_flex(
        style,
        area,
        _FOOD_DB,
        _food_recent,
        _tw_meal_period,
        _tw_season,
        _maps_url,
    )


def build_live_food_events(area: str) -> list:
    return _shared_build_live_food_events(area, _get_accupass_cache())


# --- Food menu wrappers ---------------------------------------------------

def build_food_menu(city: str = "", user_id: str = "") -> list:
    if user_id:
        _redis_set(f"food_locate:{user_id}", "1", ttl=180)
    return _shared_build_food_menu(city)


def build_food_type_picker(city: str = "") -> list:
    return _shared_build_food_type_picker(city)


def build_food_special_picker(city: str = "") -> list:
    return _shared_build_food_special_picker(city)


def _build_food_entry_region_picker(user_id: str = "") -> list:
    if user_id:
        _redis_set(f"food_locate:{user_id}", "1", ttl=180)
    return _shared_build_food_entry_region_picker(_AREA_REGIONS)


def _build_food_entry_city_picker(region: str) -> list:
    return _shared_build_food_entry_city_picker(region, _AREA_REGIONS, _ALL_CITIES)


def build_food_region_picker(style: str) -> list:
    return _shared_build_food_region_picker(style, _AREA_REGIONS)


def build_food_area_picker(style: str, region: str = "") -> list:
    return _shared_build_food_area_picker(style, region, _AREA_REGIONS, _ALL_CITIES)


# --- City specialty wrappers ---------------------------------------------

def build_city_specialties(city: str) -> list:
    return _shared_build_city_specialties(
        city, _CITY_SPECIALTIES, _tw_season, build_food_restaurant_flex,
        text_search_places=_text_search_places,
        places_photo_url=_places_photo_url,
        redis_get=_redis_get,
        redis_set=_redis_set,
    )


def build_trending_specialty(city: str, mode: str) -> list:
    return _shared_build_trending_specialty(
        city, mode, _text_search_places, _build_restaurant_bubble,
        redis_get=_redis_get, redis_set=_redis_set,
    )


def build_trending_by_district(district: str, city2: str, mode: str) -> list:
    return _shared_build_trending_by_district(
        district, city2, mode, _text_search_places, _build_restaurant_bubble,
        redis_get=_redis_get, redis_set=_redis_set,
    )


def build_specialty_shops(city: str, food_name: str) -> list:
    return _shared_build_specialty_shops(
        city, food_name, _text_search_places, _build_restaurant_bubble
    )


def build_new_shops(city: str) -> list:
    return _shared_build_new_shops(
        city, _text_search_places, _build_restaurant_bubble,
        redis_get=_redis_get, redis_set=_redis_set,
    )


# ─── 地區/城市選擇器 ──────────────────────────────────────


# ─── 主路由 ──────────────────────────────────────────────
def build_food_message(text: str, user_id: str = None) -> list:
    return _shared_build_food_message(
        text,
        user_id,
        all_cities=_ALL_CITIES,
        area_regions=_AREA_REGIONS,
        style_keywords=_STYLE_KEYWORDS,
        redis_set=_redis_set,
        get_user_city=_get_user_city,
        set_user_city=_set_user_city,
        tw_meal_period=_tw_meal_period,
        build_bib_gourmand_flex=build_bib_gourmand_flex,
        build_food_restaurant_flex=build_food_restaurant_flex,
        build_food_area_picker=build_food_area_picker,
        build_food_region_picker=build_food_region_picker,
        build_food_flex=build_food_flex,
        build_live_food_events=build_live_food_events,
        build_food_special_picker=build_food_special_picker,
        build_city_specialties=build_city_specialties,
        build_food_type_picker=build_food_type_picker,
        build_food_menu=build_food_menu,
        build_food_entry_city_picker=_build_food_entry_city_picker,
        build_food_entry_region_picker=_build_food_entry_region_picker,
        build_trending_specialty=build_trending_specialty,
        build_trending_by_district=build_trending_by_district,
        build_new_shops=build_new_shops,
    )
