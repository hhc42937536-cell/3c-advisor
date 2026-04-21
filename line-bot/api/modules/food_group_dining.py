"""Group dining recommendation Flex builders."""

from __future__ import annotations

import random as _random
import urllib.parse


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
    """Build a final group-dining recommendation card."""
    info = _GROUP_DINING_TYPES.get(dining_type, _GROUP_DINING_TYPES["不限"])
    color = info["color"]
    emoji = info["emoji"]
    bib_pool = bib_gourmand.get(city[:2], [])
    bib_picks = _random.sample(bib_pool, min(3, len(bib_pool))) if bib_pool else []
    query_str = _GROUP_SEARCH_TEMPLATES.get(dining_type, "{city} 聚餐").format(city=city)
    gmap_url = "https://www.google.com/maps/search/" + urllib.parse.quote(query_str)
    gmap_url_pkg = "https://maps.google.com/?q=" + urllib.parse.quote(f"{city} {dining_type} 聚餐 包廂")
    google_rank_url = f"https://www.google.com/search?q={urllib.parse.quote(f'{city} {dining_type} 聚餐 推薦 排名 必吃')}"
    walker_url = f"https://www.walkerland.com.tw/search?keyword={urllib.parse.quote(f'{city} {dining_type} 聚餐')}&sort=rating"
    ipeen_url = f"https://www.ipeen.com.tw/search/all/{urllib.parse.quote(city)}/0-0-0-0/1?q={urllib.parse.quote(dining_type + ' 聚餐')}"
    eztable_url = f"https://www.eztable.com.tw/restaurants/?q={urllib.parse.quote(city + ' ' + dining_type)}"
    tip_items = [
        {"type": "text", "text": tip, "size": "xs", "color": "#555555", "wrap": True}
        for tip in _GROUP_BOOKING_TIPS.get(dining_type, _GROUP_BOOKING_TIPS["不限"])
    ]
    share_text = f"🍽️ {city} {dining_type} 聚餐\n朋友來找餐廳，用「生活優轉」幫你選！\n{gmap_url_pkg}"
    share_url = "https://line.me/R/share?text=" + urllib.parse.quote(share_text)
    bib_section = []
    if bib_picks:
        bib_section = [
            {"type": "text", "text": "🏅 必比登精選（米其林認證）", "weight": "bold", "size": "sm", "color": "#B71C1C"},
            {"type": "text", "text": "品質有保證，可作為聚餐起點", "size": "xs", "color": "#888888", "margin": "xs"},
        ] + [
            {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
             "action": {"type": "uri", "label": f"🏅 {restaurant['name']}", "uri": restaurant["url"]}}
            for restaurant in bib_picks
        ] + [{"type": "separator", "margin": "md"}]
    return [{
        "type": "flex",
        "altText": f"🍽️ {city} {dining_type} 聚餐推薦",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": color,
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": f"{emoji} {city} {dining_type} 聚餐", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": info["note"], "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "16px",
                "contents": bib_section + [
                    {"type": "text", "text": "📋 訂位前確認", "weight": "bold", "size": "sm", "color": "#333333",
                     "margin": "md" if bib_picks else "none"},
                ] + tip_items + [
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "🔍 依評價找更多餐廳", "weight": "bold", "size": "sm", "color": "#333333", "margin": "md"},
                    {"type": "text", "text": "按評價排序，快速鎖定高分店家", "size": "xs", "color": "#888888"},
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "paddingAll": "12px",
                "contents": [
                    {"type": "button", "style": "primary", "color": color, "height": "sm",
                     "action": {"type": "uri", "label": "⭐ 網友推薦排行", "uri": google_rank_url}},
                    {"type": "button", "style": "primary", "color": color, "height": "sm",
                     "action": {"type": "uri", "label": f"🗺️ Google Maps 找{dining_type}", "uri": gmap_url}},
                    {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                        {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "📝 窩客島評價", "uri": walker_url}},
                        {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "📅 EZTABLE訂位", "uri": eztable_url}},
                    ]},
                    {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                        {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "🍽️ 愛評網", "uri": ipeen_url}},
                    ]},
                    {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                        {"type": "button", "style": "link", "flex": 1, "height": "sm",
                         "action": {"type": "message", "label": "← 換類型", "text": f"聚餐 {city}"}},
                        {"type": "button", "style": "link", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "📤 揪朋友", "uri": share_url}},
                    ]},
                ],
            },
        },
    }]
