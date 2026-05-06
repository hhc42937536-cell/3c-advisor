"""Group dining recommendation Flex builders."""

from __future__ import annotations

import json as _json
import os as _os
import random as _random
import urllib.parse

_PHOTO_PROXY = "https://3c-advisor.vercel.app/api/photo?ref={}"

_TYPE_KEYWORDS: dict[str, list[str]] = {
    "火鍋": ["火鍋", "涮涮鍋", "涮涮", "鍋物", "麻辣鍋"],
    "燒肉": ["燒肉", "燒烤", "烤肉", "韓式燒"],
    "日式": ["日式", "壽司", "拉麵", "居酒屋", "日本料理", "割烹", "丼", "和食"],
    "合菜台菜": ["台菜", "合菜", "辦桌", "海鮮樓", "台灣料理"],
    "西式": ["牛排", "排餐", "義式", "義大利", "法式", "西餐", "漢堡排"],
    "熱炒": ["熱炒", "快炒", "海鮮熱炒"],
    "鍋物": ["薑母鴨", "羊肉爐", "麻辣鍋", "鍋物"],
}

# 聚餐不適合的小吃/輕食關鍵字
_NON_DINING_WORDS = [
    "咖啡", "coffee", "cafe", "café", "冷萃", "手沖", "珈琲",
    "甜點", "蛋糕", "甜食", "冰淇淋", "雪花冰", "剉冰", "冰品", "布丁", "甜湯",
    "早餐", "早午餐", "brunch", "吐司", "蛋餅", "豆漿", "燒餅",
    "奶茶", "珍珠", "飲料", "手搖", "果汁",
    "麵包", "貝果", "可頌",
    "書店", "文具", "選物",
    "小吃", "擔仔麵", "担仔麵", "臭豆腐", "鹽酥雞", "雞排", "炸雞",
    "包子", "饅頭", "水餃", "餃子",
    "米粿", "碗粿", "粿",
    "便當", "自助餐",
    "鹹粥", "米粉湯", "羊肉湯",
    "麥味登", "麥當勞", "肯德基", "摩斯",  # 連鎖速食/早餐
]

# Bib Gourmand 適合聚餐的類型
_BIB_DINING_TYPES = [
    "台菜", "合菜", "海鮮", "燒肉", "烤肉", "火鍋", "鍋物",
    "日式", "壽司", "懷石", "割烹", "居酒屋",
    "西式", "義式", "法式", "牛排",
    "港式", "粵式", "熱炒", "餐廳",
]

# 確定是正式餐廳的關鍵字
_DINING_WORDS = [
    "餐廳", "料理", "restaurant", "食堂",
    "海鮮", "合菜", "台菜",
    "燒肉", "燒烤", "烤肉",
    "火鍋", "鍋物", "薑母鴨", "羊肉爐",
    "牛排", "排餐", "義式", "法式", "西餐",
    "日式", "壽司", "拉麵", "居酒屋", "割烹", "丼",
    "韓式", "韓國",
    "熱炒", "快炒",
    "餐酒館", "酒館",
    "港式", "粵式",
]


def _is_group_dining_venue(r: dict) -> bool:
    """判斷是否適合聚餐（排除咖啡/小吃，優先正式餐廳）。"""
    nm = r.get("name", "")
    nm_lower = nm.lower()
    if any(w.lower() in nm_lower for w in _NON_DINING_WORDS):
        return False
    has_dining_kw = any(w.lower() in nm_lower for w in _DINING_WORDS)
    # 超高評論數（>=1500）大概率是正式店
    big_place = r.get("user_ratings_total", 0) >= 1500
    return has_dining_kw or big_place


def _bib_is_group_dining(r: dict) -> bool:
    """Bib Gourmand 判斷是否適合聚餐（依 type 欄位）。"""
    rtype = r.get("type", "")
    return any(t in rtype for t in _BIB_DINING_TYPES)


_GROUP_DINING_CITIES = [
    "台北", "新北", "桃園", "新竹", "台中", "台南", "高雄", "其他"
]

_GROUP_DINING_TYPES = {
    "火鍋": {"emoji": "🍲", "color": "#C62828", "note": "可分鍋、顧到每個人口味"},
    "燒肉": {"emoji": "🥩", "color": "#BF360C", "note": "熱鬧氣氛最強、適合慶祝"},
    "日式": {"emoji": "🍣", "color": "#1565C0", "note": "壽司/割烹/居酒屋皆宜"},
    "合菜台菜": {"emoji": "🥘", "color": "#2E7D32", "note": "大圓桌共享，長輩最愛"},
    "西式": {"emoji": "🍽️", "color": "#4527A0", "note": "排餐/義式，正式感強"},
    "熱炒": {"emoji": "🍺", "color": "#E65100", "note": "平價下酒、台味十足"},
    "鍋物": {"emoji": "🥘", "color": "#6A1B9A", "note": "薑母鴨/羊肉爐，秋冬必吃"},
    "不限": {"emoji": "🍴", "color": "#455A64", "note": "幫我推薦最適合的"},
}

_GROUP_SEARCH_TEMPLATES = {
    "火鍋": "{city} 火鍋 聚餐 推薦 包廂 高評價",
    "燒肉": "{city} 燒肉 聚餐 推薦 包廂 高評價",
    "日式": "{city} 日式料理 聚餐 推薦 包廂",
    "合菜台菜": "{city} 台菜 合菜 聚餐 推薦 大圓桌",
    "西式": "{city} 西餐 排餐 聚餐 推薦 包廂",
    "熱炒": "{city} 熱炒 海鮮 聚餐 推薦 高評價",
    "鍋物": "{city} 薑母鴨 羊肉爐 聚餐 推薦",
    "不限": "{city} 聚餐 推薦 包廂 高評價 必吃",
}

_GROUP_BOOKING_TIPS = {
    "火鍋": ["✅ 確認是否可分鍋（素食/葷食同桌）", "✅ 問有無包廂或半包廂", "✅ 人多可問有無固定套餐"],
    "燒肉": ["✅ 確認是桌邊烤還是個人烤", "✅ 生日通常有驚喜服務，記得告知", "✅ 提前訂位，熱門店假日爆滿"],
    "日式": ["✅ 告知有無海鮮過敏", "✅ 居酒屋通常不適合帶長輩", "✅ 高檔割烹建議事先告知人數"],
    "合菜台菜": ["✅ 確認圓桌人數上限（通常 8-12 人）", "✅ 可請店家推薦合菜套餐", "✅ 長輩場合首選"],
    "西式": ["✅ 正式場合建議著裝整齊", "✅ 提前預約，部分店家需訂金", "✅ 問有無無麩質/素食選項"],
    "熱炒": ["✅ 人數多可包場，記得詢問", "✅ 下酒菜齊全，適合輕鬆聚會", "✅ 結帳通常可以分開"],
    "鍋物": ["✅ 秋冬旺季要提前預約", "✅ 確認補湯是否免費", "✅ 薑母鴨建議中午吃不燥熱"],
    "不限": ["✅ 先確認人數再訂位", "✅ 有特殊需求（壽星/長輩）提前告知", "✅ 訂位時詢問有無停車場"],
}


def _load_city_pool(city: str) -> list:
    """Load restaurant candidates from restaurant_db.json for the given city."""
    try:
        here = _os.path.dirname(_os.path.abspath(__file__))
        db_path = _os.path.join(here, "..", "..", "restaurant_db.json")
        with open(db_path, encoding="utf-8") as f:
            db = _json.load(f)
        return db.get("by_city", {}).get(city[:2], [])
    except Exception:
        return []


def _make_restaurant_card(r: dict, color: str, tag: str = "") -> dict:
    """Build a Flex bubble card for a single restaurant."""
    name = r.get("name", "")
    addr = r.get("addr", "") or r.get("address", "")
    rating = r.get("rating", 0)
    reviews = r.get("user_ratings_total", 0)
    photo = r.get("photo_ref", "")
    place_id = r.get("place_id", "")
    lat, lng = r.get("lat"), r.get("lng")
    desc = r.get("desc", "")

    if place_id:
        nav_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    elif lat and lng:
        nav_url = (
            f"https://www.google.com/maps/search/{urllib.parse.quote(name)}"
            f"/@{lat},{lng},17z"
        )
    else:
        nav_url = f"https://www.google.com/maps/search/{urllib.parse.quote(name)}"

    label = (f"{tag} " if tag else "") + name
    rating_text = f"{'★' * int(rating)}{'☆' * (5 - int(rating))} {rating}" if rating else ""

    body_contents: list = []
    if desc:
        body_contents.append(
            {"type": "text", "text": desc, "color": "#555555", "size": "xs", "wrap": True, "maxLines": 2}
        )
    if addr:
        body_contents.append(
            {"type": "text", "text": addr, "color": "#888888", "size": "xs", "wrap": True, "maxLines": 2}
        )
    if reviews:
        body_contents.append(
            {"type": "text", "text": f"📝 {reviews} 則評論", "color": "#AAAAAA", "size": "xs"}
        )
    if not body_contents:
        body_contents.append({"type": "text", "text": "點擊導航查看詳情", "color": "#AAAAAA", "size": "xs"})

    bub: dict = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": color,
            "paddingAll": "10px",
            "contents": [
                {"type": "text", "text": label, "color": "#FFFFFF",
                 "size": "sm", "weight": "bold", "wrap": True, "maxLines": 2},
                *(
                    [{"type": "text", "text": rating_text, "color": "#FFD700", "size": "xs"}]
                    if rating_text else []
                ),
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "paddingAll": "10px",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "8px",
            "contents": [
                {"type": "button", "style": "primary", "color": color, "height": "sm",
                 "action": {"type": "uri", "label": "📍 導航前往", "uri": nav_url}},
            ],
        },
    }
    if photo:
        bub["hero"] = {
            "type": "image",
            "url": _PHOTO_PROXY.format(photo),
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }
    return bub


def build_group_dining_message(text: str, bib_gourmand: dict) -> list:
    """Route group-dining text into city, type, or result cards."""
    text_s = text.strip()
    city_found, type_found = "", ""
    for city in _GROUP_DINING_CITIES:
        if city in text_s:
            city_found = city
            break
    for dining_type in _GROUP_DINING_TYPES:
        if dining_type in text_s:
            type_found = dining_type
            break
    if city_found and type_found:
        return _build_group_result(city_found, type_found, bib_gourmand)
    if city_found:
        return _build_group_type_picker(city_found)
    return _build_group_city_picker()


def _build_group_city_picker() -> list:
    city_btns = []
    row = []
    for i, city in enumerate(_GROUP_DINING_CITIES):
        row.append({
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "flex": 1,
            "action": {"type": "message", "label": city, "text": f"聚餐 {city}"},
        })
        if len(row) == 4 or i == len(_GROUP_DINING_CITIES) - 1:
            city_btns.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row})
            row = []
    return [{
        "type": "flex",
        "altText": "🍽️ 聚餐餐廳推薦",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1A1F3A",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "🍽️ 聚餐餐廳推薦", "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                    {"type": "text", "text": "朋友聚會、家庭圓桌、公司聚餐都適用", "color": "#8892B0", "size": "xs", "margin": "xs"},
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "📍 在哪個城市聚餐？", "size": "sm", "weight": "bold", "color": "#333333"},
                ] + city_btns,
            },
        },
    }]


def _build_group_type_picker(city: str) -> list:
    type_rows = []
    items = list(_GROUP_DINING_TYPES.items())
    for i in range(0, len(items), 2):
        row_contents = []
        for dining_type, info in items[i:i + 2]:
            row_contents.append({
                "type": "box",
                "layout": "vertical",
                "flex": 1,
                "backgroundColor": info["color"] + "22",
                "cornerRadius": "12px",
                "paddingAll": "12px",
                "spacing": "xs",
                "action": {"type": "message", "label": dining_type, "text": f"聚餐 {city} {dining_type}"},
                "contents": [
                    {"type": "text", "text": info["emoji"], "size": "xxl", "align": "center"},
                    {"type": "text", "text": dining_type, "size": "sm", "weight": "bold", "align": "center", "color": info["color"]},
                    {"type": "text", "text": info["note"], "size": "xxs", "align": "center", "color": "#888888", "wrap": True},
                ],
            })
        type_rows.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row_contents})
    return [{
        "type": "flex",
        "altText": f"🍽️ {city} 聚餐類型",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1A1F3A",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": f"🍽️ {city} 聚餐", "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                    {"type": "text", "text": "想吃哪一種？", "color": "#8892B0", "size": "xs", "margin": "xs"},
                ],
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px", "contents": type_rows},
        },
    }]


def _build_group_result(city: str, dining_type: str, bib_gourmand: dict) -> list:
    """Build a carousel of restaurant cards for group dining."""
    info = _GROUP_DINING_TYPES.get(dining_type, _GROUP_DINING_TYPES["不限"])
    color = info["color"]

    # ── 1. Bib Gourmand ──
    bib_pool = bib_gourmand.get(city[:2], [])
    # 針對特定類型，用關鍵字篩選 Bib Gourmand
    kws = _TYPE_KEYWORDS.get(dining_type, [])
    if kws:
        bib_picks = [
            r for r in bib_pool
            if any(kw in r.get("name", "") or kw in r.get("type", "") for kw in kws)
        ][:3]
    else:
        # 不限：只選適合聚餐類型的 Bib（排除純小吃）
        bib_picks = [r for r in bib_pool if _bib_is_group_dining(r)][:3]

    # ── 2. restaurant_db ──
    pool = _load_city_pool(city)
    max_cards = max(1, 11 - len(bib_picks))  # 保留 1 張 nav 卡，總計 ≤ 12

    if kws:
        # 特定類型：先按類型關鍵字篩選
        typed_pool = [r for r in pool if any(kw in r.get("name", "") for kw in kws)]
        typed_filtered = sorted(
            [r for r in typed_pool if r.get("rating", 0) >= 4.0],
            key=lambda r: (-r.get("rating", 0), -r.get("user_ratings_total", 0)),
        )[:max_cards]
        # 不足 3 筆：補聚餐適合的高評分餐廳
        if len(typed_filtered) < 3:
            seen_pids = {r.get("place_id") for r in typed_filtered}
            fallback = sorted(
                [r for r in pool if _is_group_dining_venue(r)
                 and r.get("rating", 0) >= 4.3
                 and r.get("user_ratings_total", 0) >= 200
                 and r.get("place_id") not in seen_pids],
                key=lambda r: (-r.get("rating", 0), -r.get("user_ratings_total", 0)),
            )[:max_cards - len(typed_filtered)]
            typed = typed_filtered + fallback
        else:
            typed = typed_filtered
    else:
        # 不限：只要是適合聚餐的餐廳
        typed = sorted(
            [r for r in pool if _is_group_dining_venue(r)
             and r.get("rating", 0) >= 4.3
             and r.get("user_ratings_total", 0) >= 200],
            key=lambda r: (-r.get("rating", 0), -r.get("user_ratings_total", 0)),
        )[:max_cards]

    # ── 3. Build bubbles ──
    bubbles: list[dict] = []
    for r in bib_picks:
        bubbles.append(_make_restaurant_card(r, "#B71C1C", "🏅"))
    for r in typed:
        bubbles.append(_make_restaurant_card(r, color))

    # ── 4. Fallback 單張提示卡（無資料時）──
    if not bubbles:
        query_str = _GROUP_SEARCH_TEMPLATES.get(dining_type, "{city} 聚餐").format(city=city)
        gmap_url = "https://www.google.com/maps/search/" + urllib.parse.quote(query_str)
        bubbles.append({
            "type": "bubble", "size": "kilo",
            "body": {"type": "box", "layout": "vertical", "paddingAll": "16px", "contents": [
                {"type": "text", "text": f"目前沒有 {city} {dining_type} 的餐廳資料", "wrap": True, "color": "#555555"},
            ]},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "8px", "contents": [
                {"type": "button", "style": "primary", "color": color, "height": "sm",
                 "action": {"type": "uri", "label": "🗺️ Google Maps 搜尋", "uri": gmap_url}},
            ]},
        })

    # ── 5. 尾端導航卡 ──
    tips = _GROUP_BOOKING_TIPS.get(dining_type, _GROUP_BOOKING_TIPS["不限"])
    eztable_url = f"https://www.eztable.com.tw/restaurants/?q={urllib.parse.quote(city + ' ' + dining_type)}"
    nav_bub = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": color, "paddingAll": "10px",
            "contents": [
                {"type": "text", "text": "📋 訂位小提醒", "color": "#FFFFFF", "size": "sm", "weight": "bold"},
            ],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "10px",
            "contents": [
                {"type": "text", "text": tip, "size": "xs", "color": "#555555", "wrap": True}
                for tip in tips
            ],
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "8px",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "uri", "label": "📅 EZTABLE 訂位", "uri": eztable_url}},
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "message", "label": "← 換類型", "text": f"聚餐 {city}"}},
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "message", "label": "換城市", "text": "聚餐"}},
                ]},
            ],
        },
    }
    bubbles.append(nav_bub)

    return [{
        "type": "flex",
        "altText": f"🍽️ {city} {dining_type} 聚餐推薦",
        "contents": {"type": "carousel", "contents": bubbles[:12]},
    }]
