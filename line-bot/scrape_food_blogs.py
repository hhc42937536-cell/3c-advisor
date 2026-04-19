"""
食記部落格爬蟲 — Dcard 美食/旅遊板 + PTT 食記板
=================================================
輸出：food_blog_cache.json
結構：
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "by_city": {
      "台北": {
        "souvenir": [{"title": "...", "url": "...", "source": "Dcard"}],
        "trending": [{"title": "...", "url": "...", "source": "PTT/food"}]
      }, ...
    }
  }

執行：python scrape_food_blogs.py
排程：GitHub Actions 每天 07:00 TST
"""

import sys, io, json, os, re, time
import urllib.request
import urllib.error
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "food_blog_cache.json")

CITIES: list[str] = [
    "台北", "新北", "基隆", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
    "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
    "澎湖", "金門", "連江", "綠島", "蘭嶼",
]

SOUVENIR_KW: list[str] = ["伴手禮", "必買", "名產", "特產", "禮盒", "手信"]
TRENDING_KW: list[str] = ["必吃", "推薦", "新開", "打卡", "排隊", "人氣", "網紅", "美食", "好吃", "隱藏版"]
_YEAR_RE = re.compile(r"20\d\d")


def _detect_cities(text: str) -> list[str]:
    return [c for c in CITIES if c in text]


def _classify_mode(text: str) -> str | None:
    """回傳 'souvenir' / 'trending' / None"""
    if any(kw in text for kw in SOUVENIR_KW):
        return "souvenir"
    if any(kw in text for kw in TRENDING_KW):
        return "trending"
    if _YEAR_RE.search(text):
        return "trending"
    return None


# ── 爬蟲函式 ──────────────────────────────────────────────────────────────────

def _dcard_board(board: str, limit: int = 50) -> list[dict]:
    """Dcard 指定板熱門文章"""
    url = f"https://www.dcard.tw/_api/forums/{board}/posts?popular=true&limit={limit}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://www.dcard.tw/f/{board}",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        posts = []
        for post in data:
            title = post.get("title", "").strip()
            excerpt = post.get("excerpt", "").strip()
            post_id = post.get("id", "")
            if not title or not post_id:
                continue
            posts.append({
                "title": title[:80],
                "snippet": excerpt[:120],
                "url": f"https://www.dcard.tw/f/{board}/p/{post_id}",
                "source": f"Dcard/{board}",
            })
        print(f"[Dcard/{board}] {len(posts)} 篇")
        return posts
    except Exception as e:
        print(f"[Dcard/{board}] 錯誤: {e}")
        return []


def _ptt_board(board: str, limit: int = 20) -> list[dict]:
    """爬 PTT 指定板最新文章列表"""
    url = f"https://www.ptt.cc/bbs/{board}/index.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": "over18=1",
    }
    try:
        import ssl
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        entries = re.findall(
            r'<div class="title">\s*<a[^>]*href="(/bbs/' + re.escape(board) + r'/[^"]+)"[^>]*>([^<]+)</a>',
            html,
        )
        blocklist = ["公告", "刪除", "水桶", "置底", "徵求"]
        posts = []
        for href, raw_title in entries:
            raw_title = raw_title.strip()
            if any(b in raw_title for b in blocklist):
                continue
            clean = re.sub(r"^\[[\w/]+\]\s*", "", raw_title)
            if len(clean) > 4:
                posts.append({
                    "title": clean[:80],
                    "snippet": "",
                    "url": f"https://www.ptt.cc{href}",
                    "source": f"PTT/{board}",
                })
            if len(posts) >= limit:
                break
        print(f"[PTT/{board}] {len(posts)} 篇")
        return posts
    except Exception as e:
        print(f"[PTT/{board}] 錯誤: {e}")
        return []


# ── 分類 ──────────────────────────────────────────────────────────────────────

def _categorize(posts: list[dict]) -> dict[str, dict[str, list]]:
    """依城市 + 類型（souvenir/trending）分桶，每桶上限 10 筆"""
    result: dict[str, dict[str, list]] = {
        city: {"souvenir": [], "trending": []} for city in CITIES
    }
    seen_urls: set[str] = set()

    for post in posts:
        combined = post["title"] + " " + post.get("snippet", "")
        cities = _detect_cities(combined)
        mode = _classify_mode(combined)
        if not cities or not mode:
            continue
        url = post["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        entry = {"title": post["title"], "url": url, "source": post["source"]}
        for city in cities:
            bucket = result[city][mode]
            if len(bucket) < 10:
                bucket.append(entry)

    return result


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 50)
    print(f"食記部落格爬蟲 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_posts: list[dict] = []

    # Dcard 美食 + 旅遊板
    for board in ("food", "travel"):
        all_posts.extend(_dcard_board(board, limit=50))
        time.sleep(1)

    # PTT 食記、生活省錢
    for board in ("food", "Lifeismoney", "TaipeiFood"):
        all_posts.extend(_ptt_board(board, limit=20))
        time.sleep(1)

    print(f"\n共 {len(all_posts)} 篇，開始分類...")
    by_city = _categorize(all_posts)

    total = sum(len(v["souvenir"]) + len(v["trending"]) for v in by_city.values())
    print(f"分類完成：{total} 筆有效資料")
    for city, modes in by_city.items():
        s, t = len(modes["souvenir"]), len(modes["trending"])
        if s or t:
            print(f"  {city}: 伴手禮 {s} | 趨勢 {t}")

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "by_city": by_city,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已寫入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
