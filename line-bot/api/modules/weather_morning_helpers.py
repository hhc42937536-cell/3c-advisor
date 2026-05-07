"""Selection helpers for morning weather summaries."""

from __future__ import annotations

import datetime as _dt
import hashlib


def bot_invite_text(line_bot_id: str) -> str:
    """Build the LINE bot invite suffix."""
    if line_bot_id:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{line_bot_id}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"


def day_city_hash(doy: int, city: str, salt: int = 0) -> int:
    key = f"{doy}:{city}:{salt}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


def day_user_city_hash(doy: int, city: str, user_id: str, salt: int = 0) -> int:
    key = f"{doy}:{city}:{user_id}:{salt}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


def get_national_deal(
    city: str,
    user_id: str,
    *,
    special_deals: dict,
    weekly_deals: dict,
    surprises_fallback: list,
    surprise_cache: dict,
) -> tuple:
    """每日固定好康：優先顯示符合今天星期的早餐/咖啡/食物優惠。"""
    today = _dt.date.today()
    doy = today.timetuple().tm_yday
    weekday = today.weekday()

    special = special_deals.get((today.month, today.day))
    if special:
        return special

    weekly = weekly_deals.get(weekday, [])
    if weekly:
        return weekly[day_user_city_hash(doy, city, user_id, 1) % len(weekly)]

    return surprises_fallback[day_user_city_hash(doy, city, user_id, 9) % len(surprises_fallback)]


def get_city_local_deal(
    city: str,
    user_id: str,
    *,
    accupass_cache: dict,
    city_local_deals: dict,
    generic_local_deals: list,
    city_local_tips: dict,
    generic_local_tips: list,
) -> tuple:
    """Pick a city-specific activity, deal, or local tip."""
    today = _dt.date.today()
    doy = today.timetuple().tm_yday

    if accupass_cache:
        city_data = accupass_cache.get(city, {})
        city_events = []
        for events in city_data.values():
            if isinstance(events, list):
                city_events.extend(events)
        if city_events:
            event = city_events[day_user_city_hash(doy, city, user_id, 4) % len(city_events)]
            return ("🎉", f"{city}近期活動", f"{event.get('name', '精彩活動')}，有空去看看～")

    deal_pool = city_local_deals.get(city, generic_local_deals)
    tip_pool = city_local_tips.get(city, generic_local_tips)
    combined = deal_pool + tip_pool
    return combined[day_user_city_hash(doy, city, user_id, 5) % len(combined)]


def get_trending_topic(
    city: str,
    user_id: str,
    *,
    surprise_cache: dict,
) -> tuple:
    """今日熱話：從 surprise_cache 取 PTT/網路好康，回傳 (icon, title, body, url)。"""
    today = _dt.date.today()
    doy = today.timetuple().tm_yday

    deals = surprise_cache.get("deals", []) if surprise_cache else []
    if deals:
        deal = deals[day_user_city_hash(doy, city, user_id, 3) % len(deals)]
        tag = deal.get("tag", "網路")
        title = deal.get("title", "")
        if len(title) > 32:
            title = title[:30] + "…"
        return ("🔥", f"今日熱話（{tag}）", title, deal.get("url", ""))

    return ("📰", "今日熱話", "今天暫無熱門消息", "")


def get_morning_actions(morning_actions: list) -> list:
    """Pick four deterministic daily morning actions."""
    doy = _dt.date.today().timetuple().tm_yday
    count = len(morning_actions)
    indices = [(doy * 4 + i) % count for i in range(4)]
    seen, result = set(), []
    for idx in indices:
        while idx in seen:
            idx = (idx + 1) % count
        seen.add(idx)
        result.append(morning_actions[idx])
    return result
