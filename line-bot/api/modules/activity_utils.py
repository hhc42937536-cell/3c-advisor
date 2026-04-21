"""Activity cache, date, map, and user-state helpers."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import urllib.parse

from utils.redis import redis_set as _redis_set_raw


def _load_accupass_cache() -> dict:
    """載入 Accupass 爬蟲快取（accupass_cache.json）"""
    try:
        # line-bot/ 根目錄（api/modules/ 上兩層）
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_path = os.path.join(base, "accupass_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", {})
    except Exception:
        return {}


_ACCUPASS_CACHE = None


def _get_accupass_cache() -> dict:
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        _ACCUPASS_CACHE = _load_accupass_cache()
    return _ACCUPASS_CACHE


def _maps_url(keyword: str, area: str = "", **_kw) -> str:
    """產生 Google Maps 搜尋連結"""
    if area:
        q = urllib.parse.quote(f"{area} {keyword}")
    else:
        q = urllib.parse.quote(f"{keyword} 附近")
    return f"https://www.google.com/maps/search/{q}/"


def _set_user_city(user_id: str, city: str) -> None:
    """將用戶城市偏好存入 Redis（90 天）"""
    if user_id and city:
        _redis_set(f"user_city:{user_id}", city, ttl=86400 * 90)


def _parse_event_date(date_str: str):
    """解析活動日期字串，回傳 date 物件；失敗回傳 None"""
    if not date_str:
        return None
    # 支援範圍格式：取結束日期（例如 "04/10-04/13" 取 "04/13"）
    range_m = re.search(r'(\d{1,2})[/\-.](\d{1,2})\s*[~～\-–]\s*(\d{1,2})[/\-.](\d{1,2})', date_str)
    if range_m:
        try:
            end_date = _dt.date(
                _dt.date.today().year,
                int(range_m.group(3)), int(range_m.group(4))
            )
            return end_date
        except ValueError:
            pass
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%m/%d", "%m.%d"):
        try:
            cleaned = re.split(r'[\s(（~～]', date_str)[0].strip()
            d = _dt.datetime.strptime(cleaned, fmt)
            if fmt in ("%m/%d", "%m.%d"):
                d = d.replace(year=_dt.date.today().year)
            return d.date()
        except ValueError:
            continue
    return None


def _is_event_past(date_str: str) -> bool:
    """判斷活動是否已過期（結束日在 3 天前以上）
    - 3 天緩衝：保留本週末還在進行的活動
    - 無日期 → 保留（可能是長期展覽）
    - 超過 60 天前開始且無明確結束日 → 視為過期
    """
    today = _dt.date.today()
    d = _parse_event_date(date_str)
    if d is None:
        return False  # 無法解析 → 保留
    # 超過 3 天前（含）視為過期
    return d < (today - _dt.timedelta(days=3))


def _parse_event_weekday(date_str: str) -> str:
    """嘗試從活動日期字串解析星期幾，回傳 '五'/'六'/'日' 或空字串"""
    if not date_str:
        return ""
    d = _parse_event_date(date_str)
    if d:
        return {4: "五", 5: "六", 6: "日"}.get(d.weekday(), "")
    # 嘗試從括號裡直接抓 (六) (日) 等
    m = re.search(r'[（(]([\u4e00-\u9fff])[)）]', date_str)
    if m and m.group(1) in ("五", "六", "日"):
        return m.group(1)
    return ""


def _get_coming_weekend_label() -> str:
    """回傳最近週末的日期標示，例如 '4/11(五)–4/13(日)'"""
    today = _dt.date.today()
    wd = today.weekday()  # 0=Mon
    days_until_fri = (4 - wd) % 7
    if days_until_fri == 0 and wd == 4:
        days_until_fri = 0
    elif wd in (5, 6):
        days_until_fri = 0  # 已經是週末
    fri = today + _dt.timedelta(days=days_until_fri)
    if wd == 5:
        fri = today - _dt.timedelta(days=1)
    elif wd == 6:
        fri = today - _dt.timedelta(days=2)
    sun = fri + _dt.timedelta(days=2)
    return f"{fri.month}/{fri.day}(五)–{sun.month}/{sun.day}(日)"
