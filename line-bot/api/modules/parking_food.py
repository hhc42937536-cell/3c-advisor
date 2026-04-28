"""Food recommendation cards shown after a parking lookup."""

from __future__ import annotations

import random
import urllib.parse


def build_restaurant_bubble(
    restaurant: dict,
    lat: float,
    lon: float,
    city: str,
    eaten_set: set,
    *,
    haversine,
    places_photo_url,
    subtitle: str = "",
) -> dict:
    """Build one restaurant Flex bubble."""
    name = restaurant.get("name", "")
    addr = restaurant.get("addr", "") or restaurant.get("town", "")
    rating = restaurant.get("rating", 0)
    reviews = restaurant.get("user_ratings_total", 0)
    eaten = name in eaten_set

    dist_str = ""
    dist_m = restaurant.get("dist")
    if dist_m is None and lat and lon and restaurant.get("lat") and restaurant.get("lng"):
        dist_m = haversine(lat, lon, restaurant["lat"], restaurant["lng"])
    if dist_m is not None:
        walk_min = max(1, round(dist_m / 80))
        if dist_m < 1000:
            dist_str = f"步行約{walk_min}分鐘（{int(dist_m)}m）"
        else:
            dist_str = f"步行約{walk_min}分鐘（{dist_m/1000:.1f}km）"

    if restaurant.get("lat") and restaurant.get("lng"):
        gmap_uri = (
            f"https://maps.google.com/?q={restaurant['lat']},{restaurant['lng']}"
            f"&query={urllib.parse.quote(name)}"
        )
    elif restaurant.get("place_id"):
        gmap_uri = f"https://maps.google.com/?q=place_id:{restaurant['place_id']}"
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
    safe_tag = tag or "👥 在地推薦"
    safe_dist = dist_str or (addr[:20] if addr else (city[:2] if city else "附近美食"))
    safe_addr = addr[:28] if addr else ""
    body_contents = [
        {"type": "text", "text": safe_tag, "size": "xxs", "weight": "bold",
         "color": "#B8860B" if "必比登" in safe_tag else "#E65100", "margin": "none"},
        {"type": "text", "text": safe_name, "size": "md", "weight": "bold",
         "wrap": True, "maxLines": 2, "color": "#3D2B1F" if not eaten else "#AAAAAA",
         "margin": "xs"},
        {"type": "text", "text": safe_dist, "size": "xs",
         "color": "#1565C0", "wrap": False, "margin": "xs"},
    ]
    if rating_str:
        body_contents.append({"type": "text", "text": rating_str, "size": "xs",
                              "color": rating_color, "margin": "xxs"})
    if safe_addr:
        body_contents.append({"type": "text", "text": safe_addr, "size": "xxs",
                              "color": "#AAAAAA", "wrap": True, "maxLines": 1, "margin": "xxs"})

    eaten_data = f"ate:{name}:{city[:5]}"
    bubble: dict = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "none",
            "paddingAll": "14px",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "paddingAll": "10px",
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

    photo = ""
    if restaurant.get("photo_ref"):
        photo = places_photo_url(restaurant["photo_ref"])
    if photo:
        bubble["hero"] = {
            "type": "image",
            "url": photo,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }
    return bubble


def build_post_parking_food(
    city: str,
    lat: float = None,
    lon: float = None,
    user_id: str = "",
    *,
    google_places_api_key: str,
    nearby_places_google,
    places_photo_url,
    haversine,
    get_eaten,
    build_food_restaurant_flex,
    restaurant_cache: dict,
    bib_gourmand: dict,
) -> list:
    """Build nearby food cards after parking."""
    city2 = city[:2] if city else ""
    eaten_set = get_eaten(user_id) if user_id else set()
    picks = []

    if lat and lon and google_places_api_key:
        google_places = nearby_places_google(lat, lon, radius=1500, max_pages=1)
        for restaurant in google_places:
            if restaurant.get("lat") and restaurant.get("lng"):
                restaurant["dist"] = haversine(lat, lon, restaurant["lat"], restaurant["lng"])
            else:
                restaurant["dist"] = 9999
        google_places.sort(key=lambda item: item["dist"])
        fresh = [item for item in google_places if item["name"] not in eaten_set]
        stale = [item for item in google_places if item["name"] in eaten_set]
        picks = (fresh + stale)[:8]

    if not picks:
        pool = restaurant_cache.get(city, restaurant_cache.get(city2, []))
        if lat and lon and pool:
            for radius in (500, 1000, 2000, 3000):
                candidates = []
                for restaurant in pool:
                    if restaurant.get("lat") and restaurant.get("lng"):
                        distance = haversine(lat, lon, restaurant["lat"], restaurant["lng"])
                        if distance <= radius:
                            candidates.append((distance, restaurant))
                if len(candidates) >= 3:
                    candidates.sort(key=lambda item: item[0])
                    flat = [restaurant for _, restaurant in candidates[:8]]
                    fresh = [item for item in flat if item["name"] not in eaten_set]
                    stale = [item for item in flat if item["name"] in eaten_set]
                    picks = fresh + stale
                    break
        if not picks and pool:
            picks = random.sample(pool, min(5, len(pool)))

    bib_pool = bib_gourmand.get(city2, [])
    if lat and lon and bib_pool:
        bib_with_dist = []
        for item in bib_pool:
            if item.get("lat") and item.get("lng"):
                distance = haversine(lat, lon, float(item["lat"]), float(item["lng"]))
                if distance <= 3000:
                    bib_with_dist.append((distance, item))
        bib_with_dist.sort(key=lambda item: item[0])
        bib_pool_near = [item for _, item in bib_with_dist]
        if not bib_pool_near:  # 沒座標資料，直接用城市全部
            bib_pool_near = bib_pool
    else:
        bib_pool_near = bib_pool
    bib_picks = random.sample(bib_pool_near, min(3, len(bib_pool_near))) if bib_pool_near else []
    for item in bib_picks:
        item.setdefault("_source", "bib")

    all_picks = bib_picks + picks
    if not all_picks:
        return build_food_restaurant_flex(city)

    bubbles = []
    for restaurant in all_picks[:5]:
        subtitle = "⭐ 米其林必比登" if restaurant.get("_source") == "bib" else ""
        bubbles.append(build_restaurant_bubble(
            restaurant,
            lat,
            lon,
            city,
            eaten_set,
            haversine=haversine,
            places_photo_url=places_photo_url,
            subtitle=subtitle,
        ))

    more_bubble = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "justifyContent": "center",
            "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "還想看更多？", "size": "sm",
                 "weight": "bold", "align": "center", "color": "#666666"},
                {"type": "text", "text": "重新分享位置可抽不同餐廳",
                 "size": "xxs", "align": "center", "color": "#AAAAAA", "margin": "xs"},
                {"type": "button", "style": "primary", "color": "#FF6B35",
                 "margin": "md",
                 "action": {"type": "message", "label": "📍 換一組（重新定位）",
                            "text": "📍 我要分享位置找美食"}},
                {"type": "button", "style": "secondary", "margin": "sm",
                 "action": {"type": "message", "label": "🍜 在地餐廳全覽",
                            "text": f"在地餐廳 {city2}"}},
            ],
        },
    }
    bubbles.append(more_bubble)

    count_str = f"找到 {len(all_picks)} 間" if all_picks else ""
    alt = f"{city2}附近美食推薦 🍜  {count_str}"
    return [{"type": "flex", "altText": alt,
             "contents": {"type": "carousel", "contents": bubbles}}]
