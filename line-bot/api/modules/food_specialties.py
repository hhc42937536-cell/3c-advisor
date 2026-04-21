"""City specialty food builders."""

from __future__ import annotations

import urllib.parse


def build_city_specialties(city: str, city_specialties: dict, tw_season, restaurant_fallback) -> list:
    """第一步：城市特色清單（點按後搜名店）"""
    city2 = city[:2] if city else ""
    season = tw_season(city2)
    pool = city_specialties.get(city, city_specialties.get(city2, []))
    if not pool:
        return restaurant_fallback(city)
    items = [p for p in pool if p.get("s", "") in ("", season)]
    if not items:
        items = pool

    def _bubble(item):
        tag = ("🌞 夏季限定" if item.get("s") == "hot"
               else ("🧥 冬季限定" if item.get("s") == "cold" else "🗺️ 在地特色"))
        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "10px",
                "contents": [
                    {"type": "text", "text": item["name"],
                     "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
                    {"type": "text", "text": tag,
                     "color": "#8892B0", "size": "xxs", "margin": "xs"},
                ]},
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": item["desc"],
                     "size": "sm", "color": "#444444", "wrap": True},
                ]},
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#FF6B35", "height": "sm",
                     "action": {"type": "message", "label": "🏆 找名店推薦",
                                "text": f"特色名店 {city2} {item['name']}"}},
                ]},
        }

    bubbles = [_bubble(item) for item in items[:8]]
    return [{"type": "flex", "altText": f"{city2} 特色美食",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_specialty_shops(city: str, food_name: str, text_search_places, restaurant_bubble_builder) -> list:
    """第二步：用 Google Places Text Search 搜該城市的食物名店"""
    city2 = city[:2] if city else ""
    query = f"{city2} {food_name}"
    shops = text_search_places(query, max_results=5)
    if not shops:
        gmap_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/"
        return [{"type": "text",
                 "text": f"搜尋「{query}」名店中...\n目前無法取得即時資料，點下方連結用 Google Maps 搜尋 👇\n{gmap_uri}"}]
    eaten_set: set = set()
    bubbles = []
    for r in shops:
        r["dist"] = None
        b = restaurant_bubble_builder(r, None, None, city2, eaten_set,
                                     subtitle=f"🏆 {city2}{food_name}名店")
        bubbles.append(b)
    return [{"type": "flex", "altText": f"{query} 名店推薦",
             "contents": {"type": "carousel", "contents": bubbles}}]
