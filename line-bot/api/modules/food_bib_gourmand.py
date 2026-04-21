"""Bib Gourmand Flex builders."""

from __future__ import annotations

import random as _random


def build_bib_gourmand_flex(area: str, bib_gourmand: dict, food_recent: dict, maps_url) -> list:
    """Build Michelin Bib Gourmand recommendation cards."""
    area2 = area[:2] if area else ""
    pool = bib_gourmand.get(area2, [])
    if not pool:
        cities = list(bib_gourmand.keys())
        buttons = [
            {"type": "button", "style": "primary", "color": "#B71C1C", "height": "sm",
             "action": {"type": "message", "label": f"🏅 {city}", "text": f"必比登 {city}"}}
            for city in cities
        ]
        return [{"type": "flex", "altText": "米其林必比登推介",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#B71C1C",
                                "contents": [
                                    {"type": "text", "text": "🏅 米其林必比登推介",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    {"type": "text", "text": "每餐 NT$1,000 以內的超值好味道",
                                     "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                              "contents": [
                                  {"type": "text", "text": "選擇城市 👇", "size": "sm", "color": "#555555"},
                              ] + buttons},
                 }}]

    bib_key = f"bib_{area2}"
    last_bib = set(food_recent.get(bib_key, []))
    fresh_bib = [item for item in pool if item["name"] not in last_bib]
    if len(fresh_bib) < 5:
        fresh_bib = pool
    picks = _random.sample(fresh_bib, min(5, len(fresh_bib)))
    food_recent[bib_key] = [item["name"] for item in picks]

    color = "#B71C1C"
    items = []
    for i, restaurant in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"🏅 {restaurant['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3, "wrap": True},
                {"type": "text", "text": restaurant["type"], "size": "xxs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": restaurant.get("desc", ""), "size": "xs",
             "color": "#555555", "margin": "xs"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": maps_url(restaurant["name"], area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍",
                            "text": f"回報 好吃 {restaurant['name']}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌",
                            "text": f"回報 倒閉 {restaurant['name']}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    return [{"type": "flex", "altText": f"必比登推介 — {area2}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏅 必比登推介（{area2}）",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "米其林認證 · 每餐 NT$1,000 以內",
                                 "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"必比登 {area2}"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍽️ 回主選單",
                                                      "text": "今天吃什麼"}},
                     ]},
                 ]},
             }}]
