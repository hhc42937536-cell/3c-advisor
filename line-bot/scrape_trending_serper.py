"""
scrape_trending_serper.py — 用 Serper（Google 搜尋）預取 22 城市的
  ‧ 必買伴手禮（souvenir）
  ‧ 最新流行店家（trending）

輸出：line-bot/trending_stores_cache.json
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "by_city": {
      "宜蘭": {
        "souvenir": [{"name":"奕順軒","desc":"...","url":"...","rating":4.5,"addr":"..."}],
        "trending": [...]
      },
      ...
    }
  }

Serper 優先取 `places`（Google Maps 結果，等同手動搜尋的地圖卡），
再從 `organic` title/snippet 補充文字提及的店名（最多3筆）。
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(_DIR, "trending_stores_cache.json")
SERPER_KEY = os.environ.get("SERPER_API_KEY", "")

_CITIES = [
    "台北", "新北", "基隆", "桃園", "新竹", "苗栗",
    "台中", "彰化", "南投", "雲林",
    "嘉義", "台南", "高雄", "屏東",
    "宜蘭", "花蓮", "台東",
    "澎湖", "金門", "連江",
]

_YEAR = datetime.now().year

# 連鎖品牌去重：純中文前3字
def _brand3(name: str) -> str:
    for sep in ['|', '｜', '·', '•', '-', '－']:
        name = name.split(sep)[0]
    name = re.sub(r'[（(【\[].*', '', name).strip()
    cjk = re.sub(r'[^\u4e00-\u9fff]', '', name)
    return cjk[:3]


def _serper_search(query: str) -> dict:
    """呼叫 Serper.dev，回傳原始 JSON；失敗回傳 {}"""
    if not SERPER_KEY:
        return {}
    payload = json.dumps({
        "q": query,
        "gl": "tw",
        "hl": "zh-tw",
        "num": 10,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [Serper] 失敗: {e}")
        return {}


def _extract_from_organic(organic: list, city: str, limit: int = 3) -> list[dict]:
    """從 organic 結果的 title/snippet 提取可能的店名（補充用）"""
    # 常見店名候選：2-6個中文字後接「老店|名店|必吃|推薦|伴手禮|特產」
    pattern = re.compile(r'([\u4e00-\u9fff]{2,8}(?:老店|名店|必吃|推薦|伴手禮|特產|禮盒|糕餅|餅舖|糕點|烘焙))')
    skip = {"必買", "特產", "伴手禮", "推薦", "名店", "老店", "以下", "台灣", "全台", "在地", "地方"}

    seen_bk: set[str] = set()
    results: list[dict] = []
    for item in organic:
        text = item.get("title", "") + " " + item.get("snippet", "")
        for m in pattern.finditer(text):
            raw = m.group(1)
            name = re.sub(r'(?:老店|名店|必吃|推薦|伴手禮|特產|禮盒|糕餅|餅舖|糕點|烘焙)$', '', raw).strip()
            if not name or name in skip or len(name) < 2:
                continue
            bk = _brand3(name)
            if bk in seen_bk:
                continue
            seen_bk.add(bk)
            results.append({
                "name": name,
                "desc": item.get("snippet", "")[:60],
                "url": item.get("link", ""),
                "rating": 0,
                "addr": city,
                "_source": "organic",
            })
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break
    return results


def _fetch_city_mode(city: str, mode: str) -> list[dict]:
    """搜尋單一城市 + 模式，回傳去重後的店家清單。"""
    year = _YEAR
    if mode == "souvenir":
        query = f"{year} {city} 必買 伴手禮"
    else:
        # 「新開幕 年度推薦」比「最新流行 必吃」更容易找到近年才開的店
        query = f"{year} {city} 新開幕 年度推薦 美食"

    print(f"  搜尋：{query}")
    data = _serper_search(query)
    if not data:
        return []

    seen_pids: set[str] = set()
    seen_bk: set[str] = set()
    stores: list[dict] = []

    def _add(entry: dict) -> None:
        pid = entry.get("place_id", "")
        bk = _brand3(entry.get("name", ""))
        if not entry.get("name"):
            return
        if (pid and pid in seen_pids) or (bk and bk in seen_bk):
            return
        if pid:
            seen_pids.add(pid)
        if bk:
            seen_bk.add(bk)
        stores.append(entry)

    # ── 1. Serper `places` 結果（Google Maps 地圖卡，最精確）────────────────
    for p in data.get("places", []):
        name = p.get("title", "").strip()
        if not name:
            continue
        _add({
            "name":   name,
            "desc":   p.get("category", "") or p.get("address", ""),
            "url":    p.get("website", "") or p.get("link", ""),
            "rating": p.get("rating", 0),
            "addr":   p.get("address", ""),
            "_source": "places",
        })

    # ── 2. Organic 補充（最多3筆）────────────────────────────────────────────
    for s in _extract_from_organic(data.get("organic", []), city, limit=3):
        # 確保不重複
        _add(s)

    print(f"    → {len(stores)} 筆（places: {sum(1 for s in stores if s.get('_source')=='places')}，organic: {sum(1 for s in stores if s.get('_source')=='organic')}）")
    return stores


def build() -> None:
    if not SERPER_KEY:
        print("✗ 缺少 SERPER_API_KEY，中止。")
        sys.exit(1)

    # 讀取既有快取（增量更新，已有的城市若距今 < 3 天則跳過）
    existing: dict = {}
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        pass

    by_city: dict = existing.get("by_city", {})
    updated_at_str = existing.get("updated_at", "")
    # 判斷上次更新時間（若 < 3 天則全城市都快取中，仍可手動觸發覆蓋）
    try:
        last_update = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M")
        days_since = (datetime.now() - last_update).days
    except Exception:
        days_since = 999

    print(f"距上次更新 {days_since} 天。開始爬取...")

    for city in _CITIES:
        city_data = by_city.get(city, {})
        print(f"\n[{city}]")
        for mode in ("souvenir", "trending"):
            stores = _fetch_city_mode(city, mode)
            if stores:
                city_data[mode] = stores
            time.sleep(1.2)  # Serper rate limit
        by_city[city] = city_data

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "by_city": by_city,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(
        len(v.get(m, []))
        for v in by_city.values()
        for m in ("souvenir", "trending")
    )
    print(f"\n✅ 完成！共 {len(by_city)} 城市，{total} 筆店家。")
    print(f"輸出：{OUTPUT_FILE}")


if __name__ == "__main__":
    build()
