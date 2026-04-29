"""
用 Google Places Nearby Search 爬各城市餐廳，補齊 restaurant_db.json
每個城市設 4-8 個鄰里中心點，每點最多抓 3 頁（60 筆），去重後存檔。

用法：
    GOOGLE_PLACES_API_KEY=xxx python scrape_nearby_restaurants.py [城市名]
    不指定城市則爬全部。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(_DIR, "restaurant_db.json")
API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

# ── 各城市鄰里中心點 (lat, lng, 描述) ──────────────────────────
CITY_POINTS = {
    "台北": [
        (25.0330, 121.5654, "信義區"),
        (25.0478, 121.5170, "中山區"),
        (25.0442, 121.5314, "大安區"),
        (25.0569, 121.5291, "中正區松江"),
        (25.0280, 121.5065, "萬華區"),
        (25.0697, 121.5147, "士林區"),
        (25.0582, 121.5468, "松山區"),
        (25.0127, 121.5386, "文山區"),
    ],
    "新北": [
        (25.0169, 121.4627, "板橋"),
        (25.0133, 121.6622, "新店"),
        (25.0891, 121.6672, "汐止"),
        (24.9774, 121.5733, "中和"),
        (25.1225, 121.6637, "三重"),
        (25.0702, 121.4556, "土城"),
    ],
    "桃園": [
        (24.9936, 121.3010, "桃園區"),
        (24.9561, 121.2247, "中壢區"),
        (25.0695, 121.3098, "蘆竹區"),
    ],
    "新竹": [
        (24.8066, 120.9686, "東區"),
        (24.7881, 120.9970, "竹北"),
        (24.8320, 120.9882, "北區"),
    ],
    "台中": [
        (24.1477, 120.6736, "中區"),
        (24.1654, 120.6464, "西屯區"),
        (24.1878, 120.6530, "北屯區"),
        (24.1312, 120.6574, "南區"),
        (24.1550, 120.6868, "北區"),
        (24.0988, 120.6948, "大里區"),
        (24.1785, 120.6218, "西區"),
    ],
    "台南": [
        (22.9999, 120.2269, "中西區"),
        (22.9896, 120.2188, "東區仁和路"),
        (23.0152, 120.2126, "東區裕農"),
        (22.9904, 120.1941, "中西老街"),
        (23.0386, 120.2291, "北區"),
        (22.9568, 120.2031, "南區"),
        (22.9991, 120.1617, "安平區"),
        (23.0612, 120.3083, "永康區"),
    ],
    "高雄": [
        (22.6273, 120.3014, "前金區"),
        (22.6155, 120.3169, "苓雅區"),
        (22.6512, 120.2883, "三民區"),
        (22.5954, 120.3071, "旗津"),
        (22.7242, 120.3278, "楠梓區"),
        (22.6419, 120.3418, "前鎮區"),
        (22.6647, 120.3043, "左營區"),
    ],
    "基隆": [
        (25.1283, 121.7419, "仁愛區"),
        (25.1398, 121.7610, "信義區"),
    ],
    "嘉義": [
        (23.4800, 120.4491, "東區"),
        (23.4701, 120.4410, "西區"),
    ],
    "屏東": [
        (22.6726, 120.4879, "屏東市"),
    ],
    "宜蘭": [
        (24.7571, 121.7543, "宜蘭市"),
        (24.6972, 121.7380, "羅東鎮"),
    ],
    "花蓮": [
        (23.9910, 121.6055, "花蓮市"),
    ],
    "台東": [
        (22.7583, 121.1444, "台東市"),
    ],
}

KEYWORDS = ["餐廳 小吃 美食", "早餐 早午餐", "咖啡 甜點"]
RADIUS = 1000   # 每個點搜 1km，多點覆蓋整個城市
MAX_PAGES = 3
SLEEP_BETWEEN_PAGES = 2.1   # Google 規定
SLEEP_BETWEEN_POINTS = 0.5


def nearby_search(lat: float, lng: float, keyword: str,
                  max_pages: int = MAX_PAGES) -> list:
    results = []
    url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={RADIUS}"
        f"&keyword={urllib.parse.quote(keyword)}"
        "&language=zh-TW"
        f"&key={API_KEY}"
    )
    for page in range(max_pages):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ScrapeBot/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            for p in data.get("results", []):
                loc = p.get("geometry", {}).get("location", {})
                if not loc:
                    continue
                photo_ref = (p.get("photos") or [{}])[0].get("photo_reference", "")
                results.append({
                    "name": p.get("name", ""),
                    "addr": p.get("vicinity", ""),
                    "rating": p.get("rating", 0),
                    "user_ratings_total": p.get("user_ratings_total", 0),
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "place_id": p.get("place_id", ""),
                    "photo_ref": photo_ref,
                    "open_now": (p.get("opening_hours") or {}).get("open_now"),
                })
            token = data.get("next_page_token", "")
            if not token:
                break
            time.sleep(SLEEP_BETWEEN_PAGES)
            url = (
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                f"?pagetoken={urllib.parse.quote(token)}&key={API_KEY}"
            )
        except Exception as e:
            print(f"    [err] page {page}: {e}")
            break
    return results


def scrape_city(city: str, points: list) -> list:
    seen_ids: set = set()
    all_results = []
    for lat, lng, label in points:
        for kw in KEYWORDS:
            results = nearby_search(lat, lng, kw)
            added = 0
            for r in results:
                pid = r.get("place_id", "")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)
                all_results.append(r)
                added += 1
            try:
                print(f"  {label} [{kw[:4]}] +{added} (累計 {len(all_results)})")
            except UnicodeEncodeError:
                print(f"  [{kw[:4]}] +{added} (cumul {len(all_results)})")
            time.sleep(SLEEP_BETWEEN_POINTS)
    return all_results


def main():
    if not API_KEY:
        print("ERROR: 缺少 GOOGLE_PLACES_API_KEY")
        sys.exit(1)

    target_cities = sys.argv[1:] or list(CITY_POINTS.keys())

    # 載入現有資料庫
    try:
        existing = json.load(open(OUTPUT_FILE, encoding="utf-8"))
    except Exception:
        existing = {"by_city": {}}
    by_city = existing.get("by_city", {})

    for city in target_cities:
        if city not in CITY_POINTS:
            print(f"不支援城市: {city}")
            continue
        try:
            print(f"\n=== {city} ===")
        except UnicodeEncodeError:
            print(f"\n=== (city) ===")
        results = scrape_city(city, CITY_POINTS[city])
        by_city[city] = results
        # 每個城市爬完就先存檔，避免中途失敗全部遺失
        existing["by_city"] = by_city
        existing["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        existing["total"] = sum(len(v) for v in by_city.values())
        json.dump(existing, open(OUTPUT_FILE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        try:
            print(f"  -> {len(results)} 筆，已存檔")
        except UnicodeEncodeError:
            print(f"  -> {len(results)} records saved")

    print(f"\nDone. Total: {existing['total']}")


if __name__ == "__main__":
    main()
