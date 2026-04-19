"""
餐廳資料庫建構爬蟲
==================
流程：
  1. 讀 food_blog_cache.json（部落格店名，每天更新）
  2. 每家店呼叫 Google Places Text Search 補座標 + 評分 + 行政區
  3. 去重（同城市同 place_id 只存一筆）、過濾低評分（< 3.5）
  4. 存成 restaurant_db.json，按城市索引

輸出結構：
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "total": 數量,
    "by_city": {
      "台中": [
        {
          "name": "春水堂",
          "city": "台中",
          "district": "西區",
          "lat": 24.15,
          "lng": 120.67,
          "rating": 4.3,
          "user_ratings_total": 1500,
          "addr": "台中市西區...",
          "place_id": "ChIJ...",
          "photo_ref": "...",
          "mode": "trending"
        },
        ...
      ]
    }
  }

排程：GitHub Actions 每週日 23:00 UTC（台灣時間週一 07:00）
執行：GOOGLE_PLACES_API_KEY=xxx python scrape_restaurant_db.py
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
BLOG_CACHE = os.path.join(_DIR, "food_blog_cache.json")
OUTPUT_FILE = os.path.join(_DIR, "restaurant_db.json")

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

# 評分門檻：低於此值不收入資料庫
MIN_RATING = 3.5

# Google Places 每秒限速（免費方案約 1 req/s）
RATE_LIMIT_SEC = 0.6

_DISTRICT_RE = re.compile(r"[市縣](.{2,4}[區鄉鎮市])")


def _extract_district(addr: str, city2: str) -> str:
    """從 Google 回傳的地址字串中萃取行政區。"""
    # 先在城市名之後找行政區
    idx = addr.find(city2)
    if idx != -1:
        m = _DISTRICT_RE.search(addr[idx:])
        if m:
            return m.group(1)
    m = _DISTRICT_RE.search(addr)
    return m.group(1) if m else ""


def _text_search(query: str) -> dict | None:
    """呼叫 Google Places Text Search，回傳第一筆結果或 None。"""
    if not GOOGLE_PLACES_API_KEY:
        return None
    url = (
        "https://maps.googleapis.com/maps/api/place/textsearch/json"
        f"?query={urllib.parse.quote(query)}"
        "&language=zh-TW"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RestaurantDB/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = data.get("results", [])
        if not results:
            return None
        p = results[0]
        loc = p.get("geometry", {}).get("location", {})
        photo_ref = (p.get("photos") or [{}])[0].get("photo_reference", "")
        return {
            "place_id":           p.get("place_id", ""),
            "name":               p.get("name", ""),
            "addr":               p.get("formatted_address", ""),
            "rating":             p.get("rating", 0),
            "user_ratings_total": p.get("user_ratings_total", 0),
            "lat":                loc.get("lat"),
            "lng":                loc.get("lng"),
            "photo_ref":          photo_ref,
        }
    except Exception as e:
        print(f"  ✗ Places API error for '{query}': {e}")
        return None


def _load_blog_cache() -> dict:
    try:
        with open(BLOG_CACHE, encoding="utf-8") as f:
            return json.load(f).get("by_city", {})
    except Exception as e:
        print(f"✗ 無法讀取 food_blog_cache.json: {e}")
        return {}


def _load_existing_db() -> dict:
    """讀取現有資料庫（增量更新用）。"""
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f).get("by_city", {})
    except Exception:
        return {}


def build() -> None:
    if not GOOGLE_PLACES_API_KEY:
        print("✗ 缺少 GOOGLE_PLACES_API_KEY，中止。")
        sys.exit(1)

    blog = _load_blog_cache()
    existing = _load_existing_db()

    # 建立現有資料庫的 place_id 索引，避免重複查詢
    existing_ids: set[str] = set()
    for city_list in existing.values():
        for store in city_list:
            if store.get("place_id"):
                existing_ids.add(store["place_id"])

    by_city: dict[str, list] = {c: list(v) for c, v in existing.items()}
    new_count = 0
    skip_count = 0
    total_queries = sum(
        len(posts)
        for city_data in blog.values()
        for posts in city_data.values()
    )
    print(f"城市數：{len(blog)}　待查詢店家：{total_queries}（含既有資料庫可跳過）")

    for city2, modes in blog.items():
        city_ids = {s.get("place_id") for s in by_city.get(city2, []) if s.get("place_id")}
        for mode, posts in modes.items():
            for post in posts:
                name = post.get("name") or post.get("title", "")
                if not name:
                    continue

                # 先嘗試用名稱比對現有資料，避免重查
                if any(s["name"] == name for s in by_city.get(city2, [])):
                    skip_count += 1
                    continue

                print(f"  查詢 [{city2}/{mode}] {name} ...", end=" ", flush=True)
                result = _text_search(f"{city2} {name}")
                time.sleep(RATE_LIMIT_SEC)

                if not result:
                    print("無結果")
                    continue

                pid = result.get("place_id", "")
                rating = result.get("rating") or 0

                # 低評分跳過
                if rating and rating < MIN_RATING:
                    print(f"評分 {rating} 過低，略過")
                    skip_count += 1
                    continue

                # 全域去重（同 place_id）
                if pid and pid in existing_ids:
                    print(f"已存在（{result['name']}），略過")
                    skip_count += 1
                    continue

                district = _extract_district(result.get("addr", ""), city2)
                store = {
                    "name":               result["name"],
                    "city":               city2,
                    "district":           district,
                    "lat":                result["lat"],
                    "lng":                result["lng"],
                    "rating":             rating,
                    "user_ratings_total": result.get("user_ratings_total", 0),
                    "addr":               result.get("addr", ""),
                    "place_id":           pid,
                    "photo_ref":          result.get("photo_ref", ""),
                    "mode":               mode,
                }
                by_city.setdefault(city2, []).append(store)
                if pid:
                    existing_ids.add(pid)
                    city_ids.add(pid)
                new_count += 1
                print(f"✓  {result['name']}  評分 {rating}  {district}")

    # 每城市按評分降序排列
    for city2 in by_city:
        by_city[city2].sort(key=lambda s: s.get("rating", 0), reverse=True)

    total = sum(len(v) for v in by_city.values())
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total":      total,
        "by_city":    by_city,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完成！新增 {new_count} 筆，略過 {skip_count} 筆，共 {total} 筆。")
    print(f"輸出：{OUTPUT_FILE}")


if __name__ == "__main__":
    build()
