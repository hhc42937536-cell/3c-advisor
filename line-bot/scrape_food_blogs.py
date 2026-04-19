"""
食記部落格爬蟲 v2 — Google News RSS + 部落格 RSS
=================================================
來源優先級：
  1. Google News RSS（公開、穩定、全台覆蓋）
  2. food_blog_sources.json 中有 URL 的部落格 RSS

輸出：food_blog_cache.json
結構：
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "by_city": {
      "台北": {
        "souvenir": [{"title": "...", "url": "...", "source": "Google News"}],
        "trending": [...]
      }, ...
    }
  }

執行：python scrape_food_blogs.py
排程：GitHub Actions 每天 07:00 TST
"""

import sys, io, json, os, re, time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from xml.etree import ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(_DIR, "food_blog_cache.json")
SOURCES_FILE = os.path.join(_DIR, "api", "data", "food_blog_sources.json")

CITIES: list[str] = [
    "台北", "新北", "基隆", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
    "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
    "澎湖", "金門",
]

SOUVENIR_KW: list[str] = ["伴手禮", "必買", "名產", "特產", "禮盒", "手信", "帶回家", "必帶"]
TRENDING_KW: list[str] = [
    "必吃", "推薦", "新開", "打卡", "排隊", "人氣", "網紅", "美食",
    "好吃", "隱藏版", "爆紅", "熱門", "新品", "限定", "話題",
]
_YEAR_RE = re.compile(r"20\d\d")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def _detect_cities(text: str) -> list[str]:
    return [c for c in CITIES if c in text]


def _classify_mode(text: str) -> str | None:
    if any(kw in text for kw in SOUVENIR_KW):
        return "souvenir"
    if any(kw in text for kw in TRENDING_KW):
        return "trending"
    if _YEAR_RE.search(text):
        return "trending"
    return None


def _clean_html(raw: str) -> str:
    """移除 HTML 標籤"""
    return re.sub(r"<[^>]+>", "", raw or "").strip()


def _fetch_url(url: str, timeout: int = 12) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        print(f"  fetch error {url[:60]}: {e}")
        return None


# ── 1. Google News RSS ────────────────────────────────────────────────────────

def _google_news_rss(city: str, mode: str) -> list[dict]:
    """Google News RSS：依城市 + 模式查詢"""
    if mode == "souvenir":
        q = f"{city} 伴手禮 必買 推薦"
    else:
        q = f"{city} 美食 推薦 必吃 人氣"

    encoded = urllib.parse.quote(q)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    raw = _fetch_url(url)
    if not raw:
        return []

    posts = []
    try:
        root = ET.fromstring(raw.decode("utf-8", errors="ignore"))
        items = root.findall(".//item")
        for item in items[:20]:
            title = _clean_html(item.findtext("title") or "")
            link  = item.findtext("link") or ""
            desc  = _clean_html(item.findtext("description") or "")
            if not title or not link:
                continue
            posts.append({
                "title":   title[:100],
                "snippet": desc[:150],
                "url":     link,
                "source":  "Google News",
            })
    except Exception as e:
        print(f"  RSS parse error: {e}")

    print(f"  [Google News] {city}/{mode}: {len(posts)} 篇")
    return posts


# ── 2. 部落格 RSS ─────────────────────────────────────────────────────────────

def _blog_rss(site_url: str, name: str, forced_cities: list[str] | None = None) -> list[dict]:
    """嘗試 /feed, /rss, /atom.xml 等常見 RSS 路徑"""
    base = site_url.rstrip("/")
    candidates = [
        f"{base}/feed",
        f"{base}/feed/",
        f"{base}/rss",
        f"{base}/rss.xml",
        f"{base}/atom.xml",
        f"{base}/index.xml",
    ]
    for rss_url in candidates:
        raw = _fetch_url(rss_url, timeout=10)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw.decode("utf-8", errors="ignore"))
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if not items:
                continue
            posts = []
            for item in items[:15]:
                title = _clean_html(
                    item.findtext("title")
                    or item.findtext("{http://www.w3.org/2005/Atom}title")
                    or ""
                )
                link = (
                    item.findtext("link")
                    or item.findtext("{http://www.w3.org/2005/Atom}link")
                    or ""
                )
                desc = _clean_html(
                    item.findtext("description")
                    or item.findtext("{http://www.w3.org/2005/Atom}summary")
                    or ""
                )
                if not title:
                    continue
                # 若部落格來源有城市標記，強制在 snippet 加入城市名讓分類抓得到
                city_hint = " ".join(forced_cities) if forced_cities else ""
                posts.append({
                    "title":        title[:100],
                    "snippet":      (city_hint + " " + desc)[:200],
                    "url":          link or site_url,
                    "source":       name,
                    "_forced_cities": forced_cities or [],
                })
            if posts:
                print(f"  [Blog RSS] {name}: {len(posts)} 篇  ({rss_url})")
                return posts
        except Exception:
            continue
    return []


# ── 3. 分類 ───────────────────────────────────────────────────────────────────

_BUCKET_LIMIT = 30


def _categorize(posts: list[dict]) -> dict[str, dict[str, list]]:
    result: dict[str, dict[str, list]] = {
        city: {"souvenir": [], "trending": []} for city in CITIES
    }
    seen_urls: set[str] = set()

    for post in posts:
        combined = post["title"] + " " + post.get("snippet", "")
        # 優先用部落格來源標記的城市，其次靠關鍵字偵測
        forced = post.get("_forced_cities", [])
        cities = forced if forced else _detect_cities(combined)
        mode = _classify_mode(combined)
        if not cities:
            continue
        # 無法分類 trending/souvenir 的部落格文章，預設為 trending
        if not mode:
            mode = "trending"
        url = post["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        entry = {"title": post["title"], "url": url, "source": post["source"]}
        for city in cities:
            if city not in result:
                continue
            bucket = result[city][mode]
            if len(bucket) < _BUCKET_LIMIT:
                bucket.append(entry)

    return result


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 50)
    print(f"食記部落格爬蟲 v2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_posts: list[dict] = []

    # ── Step 1: Google News RSS（每縣市 × 兩種模式）──
    print("\n── Google News RSS ──")
    for city in CITIES:
        for mode in ("trending", "souvenir"):
            posts = _google_news_rss(city, mode)
            # 直接帶城市標記進 snippet，讓後續分類更準確
            for p in posts:
                if city not in p["title"] and city not in p.get("snippet", ""):
                    p["title"] = f"[{city}] " + p["title"]
            all_posts.extend(posts)
            time.sleep(0.5)

    # ── Step 2: 部落格 RSS（有 URL 且 verify:true 的來源）──
    print("\n── 部落格 RSS ──")
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            sources_data = json.load(f)
        blogs = sources_data.get("blogs", [])
        for blog in blogs:
            url = (blog.get("url") or "").strip()
            name = blog.get("name", "部落格")
            cities = blog.get("cities", [])
            if not url or not url.startswith("http"):
                continue
            posts = _blog_rss(url, name, forced_cities=cities if cities else None)
            all_posts.extend(posts)
            time.sleep(0.8)
    except Exception as e:
        print(f"載入 blog sources 失敗: {e}")

    # ── Step 3: 分類 ──
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
