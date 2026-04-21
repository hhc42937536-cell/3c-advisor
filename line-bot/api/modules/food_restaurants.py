"""Restaurant search and Flex builders for food recommendations."""

from __future__ import annotations

import json
import random as _random
import urllib.parse
import urllib.request


def text_search_places(query: str, google_places_api_key: str, max_results: int = 5) -> list:
    """Google Places Text Search — 用關鍵字搜名店（不需座標）"""
    if not google_places_api_key:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
            f"?query={urllib.parse.quote(query)}"
            "&language=zh-TW"
            f"&key={google_places_api_key}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = []
        for p in data.get("results", [])[:max_results]:
            photo_ref = (p.get("photos") or [{}])[0].get("photo_reference", "")
            loc = p.get("geometry", {}).get("location", {})
            results.append({
                "name":               p.get("name", ""),
                "addr":               p.get("formatted_address", ""),
                "rating":             p.get("rating", 0),
                "user_ratings_total": p.get("user_ratings_total", 0),
                "lat":                loc.get("lat"),
                "lng":                loc.get("lng"),
                "place_id":           p.get("place_id", ""),
                "photo_ref":          photo_ref,
                "open_now":           (p.get("opening_hours") or {}).get("open_now"),
                "_source":            "text_search",
            })
        return results
    except Exception as e:
        print(f"[text_search] error: {e}")
        return []


def places_photo_url(photo_ref: str, google_places_api_key: str, max_width: int = 400) -> str:
    """產生 Google Places 照片 URL"""
    if not photo_ref or not google_places_api_key:
        return ""
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photo_reference={photo_ref}"
        f"&key={google_places_api_key}"
    )


def build_restaurant_bubble(r: dict, lat, lon, city: str, eaten_set: set, haversine, photo_url_builder, subtitle: str = "") -> dict:
    """單間餐廳 Flex Bubble（含照片 hero、評分、導航、吃過了按鈕）"""
    name = r.get("name", "")
    addr = r.get("addr", "") or r.get("town", "")
    rating = r.get("rating", 0)
    reviews = r.get("user_ratings_total", 0)
    eaten = name in eaten_set

    dist_str = ""
    dist_m = r.get("dist")
    if dist_m is None and lat and lon and r.get("lat") and r.get("lng"):
        dist_m = haversine(lat, lon, r["lat"], r["lng"])
    if dist_m is not None:
        walk_min = max(1, round(dist_m / 80))
        if dist_m < 1000:
            dist_str = f"步行約{walk_min}分鐘（{int(dist_m)}m）"
        else:
            dist_str = f"步行約{walk_min}分鐘（{dist_m/1000:.1f}km）"

    if r.get("lat") and r.get("lng"):
        gmap_uri = f"https://maps.google.com/?q={r['lat']},{r['lng']}&query={urllib.parse.quote(name)}"
    elif r.get("place_id"):
        gmap_uri = f"https://maps.google.com/?q=place_id:{r['place_id']}"
    else:
        gmap_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(name + ' ' + city)}"

    tag = subtitle
    if not tag:
        if rating >= 4.5 and reviews >= 100:
            tag = "🔥 Google 高評分"
        elif rating >= 4.3:
            tag = "⭐ 評價優良"
        else:
            tag = "👥 在地人推薦"

    if rating >= 4.5 and reviews >= 100:
        rating_color = "#E53935"
        rating_str = f"★{rating}  ({reviews}則)"
    elif rating >= 4.0:
        rating_color = "#F57C00"
        rating_str = f"★{rating}  ({reviews}則)" if reviews else f"★{rating}"
    elif rating:
        rating_color = "#888888"
        rating_str = f"★{rating}"
    else:
        rating_color = "#888888"
        rating_str = ""

    safe_name = name or "未命名餐廳"
    safe_tag  = tag  or "👥 在地推薦"
    safe_dist = dist_str or (addr[:20] if addr else (city[:2] if city else "附近美食"))
    safe_addr = addr[:28] if addr else ""

    body_contents = [
        {"type": "text", "text": safe_tag, "size": "xxs", "weight": "bold",
         "color": "#B8860B" if "必比登" in safe_tag else "#E65100", "margin": "none"},
        {"type": "text", "text": safe_name, "size": "md", "weight": "bold",
         "wrap": True, "maxLines": 2,
         "color": "#3D2B1F" if not eaten else "#AAAAAA", "margin": "xs"},
        {"type": "text", "text": safe_dist, "size": "xs",
         "color": "#1565C0", "wrap": False, "margin": "xs"},
    ]
    if rating_str:
        body_contents.append(
            {"type": "text", "text": rating_str, "size": "xs",
             "color": rating_color, "margin": "xxs"}
        )
    if safe_addr:
        body_contents.append(
            {"type": "text", "text": safe_addr, "size": "xxs",
             "color": "#AAAAAA", "wrap": True, "maxLines": 1, "margin": "xxs"}
        )

    eaten_data = f"ate:{name}:{city[:5]}"
    bubble: dict = {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "none",
            "paddingAll": "14px", "contents": body_contents,
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "10px",
            "contents": [
                {"type": "button", "style": "primary", "height": "sm",
                 "color": "#FF6B35",
                 "action": {"type": "uri", "label": "📍 導航前往", "uri": gmap_uri}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "postback",
                            "label": "🍽 吃過這間" if not eaten else "📅 7天內去過",
                            "data": eaten_data,
                            "displayText": f"記住！{name} 吃過了"}},
            ],
        },
    }
    photo_url = ""
    if r.get("photo_ref"):
        photo_url = photo_url_builder(r["photo_ref"])
    if photo_url:
        bubble["hero"] = {
            "type": "image", "url": photo_url,
            "size": "full", "aspectRatio": "20:13", "aspectMode": "cover",
        }
    return bubble


def build_food_restaurant_flex(area: str, food_type: str, restaurant_cache: dict, food_recent: dict, food_fallback, maps_url, tw_meal_period) -> list:
    """從觀光署餐廳資料推薦在地餐廳"""
    area2 = area[:2] if area else ""
    pool = restaurant_cache.get(area, restaurant_cache.get(area2, []))
    if not pool:
        return build_food_flex("便當", area)
    if food_type:
        typed = [r for r in pool if food_type in r.get("type", "")]
        if len(typed) >= 3:
            pool = typed
    rest_key = f"rest_{area}_{food_type}"
    last_rest = set(food_recent.get(rest_key, []))
    fresh_rest = [p for p in pool if p["name"] not in last_rest]
    if len(fresh_rest) < 5:
        fresh_rest = pool
    picks = _random.sample(fresh_rest, min(5, len(fresh_rest)))
    food_recent[rest_key] = [p["name"] for p in picks]
    period, meal_label = tw_meal_period()
    area_label = f"（{area}）" if area else ""
    color = "#6D4C41"
    type_icons = {
        "中式": "🍚", "日式": "🍣", "西式": "🍝", "素食": "🥬",
        "海鮮": "🦐", "小吃": "🧆", "火鍋": "🍲", "地方特產": "⭐", "其他": "🍴",
    }
    items = []
    for i, r in enumerate(picks):
        rtype = r.get("type", "其他")
        icon = type_icons.get(rtype, "🍴")
        desc_raw = r.get("desc", "")
        desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
        addr = r.get("addr", "")
        town = r.get("town", "")
        sub_info = f"{icon}{rtype}"
        if town:
            sub_info += f" · {town}"
        rname = r['name']
        items += [
            {"type": "text", "text": f"• {rname}", "weight": "bold",
             "size": "sm", "color": color, "wrap": True, "maxLines": 2},
            {"type": "text", "text": sub_info, "size": "xxs", "color": "#888888", "margin": "xs"},
            {"type": "text", "text": desc, "size": "xs", "color": "#555555", "wrap": True,
             "margin": "xs", "maxLines": 2} if desc else {"type": "filler"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": maps_url(rname, area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍", "text": f"回報 好吃 {rname}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌", "text": f"回報 倒閉 {rname}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})
    available_types = list({r.get("type", "") for r in restaurant_cache.get(area, restaurant_cache.get(area2, []))})
    type_buttons = []
    for t in ["小吃", "中式", "日式", "海鮮", "火鍋"][:3]:
        if t in available_types:
            type_buttons.append(
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": f"{type_icons.get(t,'🍴')} {t}",
                            "text": f"餐廳 {t} {area}"}}
            )
    footer_contents = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "color": color, "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                         "text": f"餐廳 {food_type} {area}"}},
            {"type": "button", "style": "secondary", "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🍽️ 品項推薦",
                                         "text": f"吃什麼 便當 {area}"}},
        ]},
    ]
    if type_buttons:
        footer_contents.append(
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": type_buttons}
        )
    return [{"type": "flex", "altText": f"在地餐廳推薦{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏪 {meal_label}{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text",
                                 "text": "在地餐廳推薦" + (f" · {food_type}" if food_type else ""),
                                 "color": "#FFFFFFCC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": footer_contents},
             }}]
