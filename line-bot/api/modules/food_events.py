"""Food event Flex builders."""

from __future__ import annotations


_OFFICIAL_DOMAINS = (
    "accupass.com", "kktix.com", "kktix.cc",
    "huashan1914.com", "pier2.org", "tnam.museum",
    ".gov.tw", "travel.taipei", "culture.tw",
)


def _is_official_url(url: str) -> bool:
    return any(domain in url for domain in _OFFICIAL_DOMAINS)


def build_live_food_events(area: str, accupass_cache: dict) -> list:
    """Build food-event cards from the cached Accupass crawler result."""
    area2 = area[:2] if area else ""
    city_cache = accupass_cache.get(area, accupass_cache.get(area2, {}))
    events = city_cache.get("吃喝玩樂", [])
    if not events:
        return []
    picks = events[:4]
    color = "#D84315"
    items = []
    for i, event in enumerate(picks):
        url = event.get("url", "")
        source_label = event.get("source", "")
        show_source = source_label and (not url or not _is_official_url(url))
        link_uri = url if url else "https://www.accupass.com"
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {event.get('name','')}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 4, "wrap": True},
                {"type": "text", "text": "🆕", "size": "xs", "color": "#888888", "flex": 0},
            ]},
            {"type": "text", "text": event.get("desc", ""), "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            *([{"type": "text", "text": f"來源：{source_label}", "size": "xxs",
                "color": "#AAAAAA", "margin": "xs"}] if show_source else []),
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📅 查看活動詳情", "uri": link_uri}},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    area_label = f"（{area}）" if area else ""
    return [{"type": "flex", "altText": f"本週美食活動{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🎉 本週美食活動{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "Accupass 即時更新 · 吃喝玩樂精選",
                                 "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": "🍽️ 回到今天吃什麼",
                                 "text": "今天吃什麼"}},
                 ]},
             }}]
