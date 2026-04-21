"""General food recommendation builders."""

from __future__ import annotations

import random as _random
import urllib.parse


def filter_food_by_time(pool: list, period: str, season: str) -> list:
    """Filter foods by meal period and season; fallback to the original pool."""
    if period == "M":
        ok = [item for item in pool if item.get("m", "") in ("", "M")]
    elif period == "D":
        ok = [item for item in pool if item.get("m", "") in ("", "D")]
        if len(ok) < 3:
            ok = [item for item in pool if item.get("m", "") in ("", "D", "N")]
    else:
        ok = [item for item in pool if item.get("m", "") in ("", "D", "N")]
    seasonal = [item for item in ok if item.get("s", "") in ("", season)]
    return seasonal if seasonal else ok if ok else pool


def build_food_flex(
    style: str,
    area: str,
    food_db: dict,
    food_recent: dict,
    tw_meal_period,
    tw_season,
    maps_url,
) -> list:
    """Randomly pick three food items and build a recommendation card."""
    pool = food_db.get(style, food_db["便當"])
    period, meal_label = tw_meal_period()
    filtered = filter_food_by_time(pool, period, season=tw_season(area[:2] if area else ""))
    last = set(food_recent.get(style, []))
    fresh = [item for item in filtered if item["name"] not in last]
    if len(fresh) < 3:
        fresh = filtered
    picks = _random.sample(fresh, min(3, len(fresh)))
    food_recent[style] = [item["name"] for item in picks]
    area_label = f"（{area}附近）" if area else ""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32"}
    color = colors.get(style, "#FF8C42")
    icons = {"便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗"}
    icon = icons.get(style, "🍽️")
    items = []
    for i, item in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {item['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3},
                {"type": "text", "text": item["price"], "size": "xs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": item["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📍 Google Maps 搜附近",
                        "uri": maps_url(item["key"], area, open_now=True)}},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})
    style_list = list(food_db.keys())
    style_index = style_list.index(style) if style in style_list else 0
    next_style = style_list[(style_index + 1) % len(style_list)]
    share_names = "、".join([item["name"] for item in picks])
    share_text = f"🍽️ 今天吃{style}！\n推薦：{share_names}\n\n用「生活優轉」3秒決定吃什麼 👆"
    share_url = "https://line.me/R/share?text=" + urllib.parse.quote(share_text)
    return [{"type": "flex", "altText": f"今天吃什麼 — {icon}{style}版",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🍽️ {meal_label}{area_label}",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": f"{icon} {style}版推薦",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"吃什麼 {style} {area}"}},
                         {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": f"換{next_style}版",
                                                      "text": f"吃什麼 {next_style} {area}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🌤️ 今日天氣", "text": "天氣"}},
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🗓️ 近期活動", "text": "周末去哪"}},
                     ]},
                     {"type": "button", "style": "link", "height": "sm",
                      "action": {"type": "uri", "label": "📤 分享推薦給朋友", "uri": share_url}},
                 ]},
             }}]
