"""
scrape_group_dining.py — 從 愛食記(ifoodie.tw) 爬各城市 × 料理類型的聚餐餐廳
=====================================================================
輸出：group_dining_cache.json
結構：
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "by_city": {
      "台南": {
        "燒肉": [{"name":"..","storeName":"..","rating":4.8,"addr":"..","lat":..,"lng":..,"cover":".."}],
        "火鍋": [...],
        ...
      }
    }
  }

執行：python scrape_group_dining.py
排程：每週一次（活動性資料，不需每天更新）
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(_DIR, "group_dining_cache.json")

# ── 城市清單（ifoodie 使用的名稱 → 對應的短名，存檔用）────────────
# 格式：(ifoodie查詢名, 存檔key)
CITIES: list[tuple[str, str]] = [
    ("台北",   "台北"),
    ("新北市", "新北"),
    ("桃園",   "桃園"),
    ("新竹",   "新竹"),
    ("苗栗",   "苗栗"),
    ("台中",   "台中"),
    ("彰化",   "彰化"),
    ("南投",   "南投"),
    ("雲林",   "雲林"),
    ("嘉義",   "嘉義"),
    ("台南",   "台南"),
    ("高雄",   "高雄"),
    ("屏東",   "屏東"),
    ("宜蘭",   "宜蘭"),
    ("花蓮",   "花蓮"),
    ("台東",   "台東"),
    ("基隆",   "基隆"),
]

# ── 類型 → ifoodie 分類關鍵字 ────────────────────────────
CATEGORY_MAP: dict[str, str] = {
    "火鍋":    "火鍋",
    "燒肉":    "燒肉",
    "日式":    "日式料理",
    "合菜台菜": "台菜",
    "西式":    "西式料理",
    "熱炒":    "熱炒",
    "鍋物":    "薑母鴨",
    "不限":    "合菜",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _find_restaurant_list(obj: object, depth: int = 0) -> list:
    """Recursively find the restaurant list in Next.js __NEXT_DATA__ JSON."""
    if depth > 7:
        return []
    if isinstance(obj, list) and len(obj) >= 2:
        if obj and isinstance(obj[0], dict) and "lng" in obj[0] and "rating" in obj[0]:
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _find_restaurant_list(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj[:5]:
            r = _find_restaurant_list(item, depth + 1)
            if r:
                return r
    return []


def scrape_ifoodie(city: str, category: str) -> list[dict]:
    """Scrape ifoodie.tw for restaurants in city × category. Returns list of dicts."""
    url = (
        f"https://ifoodie.tw/explore/{urllib.parse.quote(city)}"
        f"/list/{urllib.parse.quote(category)}"
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"    [fetch error] {city}/{category}: {e}")
        return []

    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        print(f"    [no __NEXT_DATA__] {city}/{category}")
        return []

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"    [json error] {city}/{category}: {e}")
        return []

    raw = _find_restaurant_list(data)
    result = []
    for r in raw:
        name = r.get("storeName") or r.get("name") or ""
        if not name:
            continue
        entry = {
            "name": name,
            "rating": r.get("rating") or 0,
            "review_cnt": r.get("reviewCnt") or r.get("visitCnt") or 0,
            "addr": r.get("address") or "",
            "lat": r.get("lat"),
            "lng": r.get("lng"),
            "cover": r.get("coverUrl") or "",
            "url": f"https://ifoodie.tw/restaurant/{r['id']}" if r.get("id") else "",
            "categories": r.get("categories") or [],
            "avg_price": r.get("avgPrice") or 0,
        }
        result.append(entry)
    return result


def main() -> None:
    # Load existing cache to update incrementally
    existing: dict = {}
    if os.path.exists(OUTPUT):
        try:
            existing = json.load(open(OUTPUT, encoding="utf-8"))
        except Exception:
            pass

    by_city: dict[str, dict[str, list]] = existing.get("by_city", {})
    total = 0

    for ifoodie_city, save_key in CITIES:
        if save_key not in by_city:
            by_city[save_key] = {}
        print(f"\n【{save_key}（查詢名：{ifoodie_city}）】")
        for dining_type, ifoodie_cat in CATEGORY_MAP.items():
            print(f"  {dining_type} ({ifoodie_cat}) ...", end=" ", flush=True)
            rests = scrape_ifoodie(ifoodie_city, ifoodie_cat)
            by_city[save_key][dining_type] = rests
            print(f"{len(rests)} 筆")
            total += len(rests)
            time.sleep(1.0)  # polite delay

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": total,
        "by_city": by_city,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共 {total} 筆，存至 {OUTPUT}")


if __name__ == "__main__":
    main()
