import json
import os
import urllib.parse
import urllib.request

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")


def nearby_places(lat: float, lng: float, radius: int = 1500,
                  keyword: str = "餐廳 小吃 美食") -> list:
    """Google Places Nearby Search — 回傳半徑內餐廳清單"""
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            f"?location={lat},{lng}&radius={radius}"
            f"&keyword={urllib.parse.quote(keyword)}"
            "&language=zh-TW"
            f"&key={GOOGLE_PLACES_API_KEY}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = []
        for p in data.get("results", []):
            photo_ref = (p.get("photos") or [{}])[0].get("photo_reference", "")
            plat = p["geometry"]["location"]["lat"]
            plng = p["geometry"]["location"]["lng"]
            results.append({
                "name":               p.get("name", ""),
                "addr":               p.get("vicinity", ""),
                "rating":             p.get("rating", 0),
                "user_ratings_total": p.get("user_ratings_total", 0),
                "lat":                plat,
                "lng":                plng,
                "place_id":           p.get("place_id", ""),
                "photo_ref":          photo_ref,
                "open_now":           (p.get("opening_hours") or {}).get("open_now"),
                "_source":            "google",
            })
        print(f"[places] got {len(results)} results within {radius}m")
        return results
    except Exception as e:
        print(f"[places] error: {e}")
        return []


def text_search(query: str, max_results: int = 5) -> list:
    """Google Places Text Search — 用關鍵字搜名店（不需座標）"""
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
            f"?query={urllib.parse.quote(query)}"
            "&language=zh-TW"
            f"&key={GOOGLE_PLACES_API_KEY}"
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
        print(f"[text_search] '{query}' -> {len(results)} results")
        return results
    except Exception as e:
        print(f"[text_search] error: {e}")
        return []


def photo_url(photo_ref: str, max_width: int = 400) -> str:
    """組合 Google Places Photo URL"""
    if not photo_ref or not GOOGLE_PLACES_API_KEY:
        return ""
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photo_reference={photo_ref}"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )
