"""
文章自動探索爬蟲
================
流程：
  1. 對 22 縣市 × 2 類別（伴手禮/最新流行），用 Google Custom Search API 搜尋
  2. 取前 10 筆結果，過濾商業/新聞網站，保留部落格文章
  3. 抓文章內容，抽取店家名稱
  4. 合併到 food_blog_cache.json（計次累加，保留既有資料）

執行：
  GOOGLE_PLACES_API_KEY=xxx GOOGLE_CSE_ID=xxx python scrape_article_discovery.py

排程：GitHub Actions 每週六 22:00 UTC（日 06:00 TST），在 food_blog 爬蟲之前執行
"""

import json, os, re, sys, time, io
import urllib.parse, urllib.request
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_DIR = os.path.dirname(os.path.abspath(__file__))
BLOG_CACHE   = os.path.join(_DIR, "food_blog_cache.json")
SOURCES_FILE = os.path.join(_DIR, "api", "data", "food_blog_sources.json")

API_KEY    = os.environ.get("GOOGLE_PLACES_API_KEY", "")
SERPER_KEY = os.environ.get("SERPER_API_KEY", "")

CITIES = [
    "台北", "新北", "基隆", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
    "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
    "澎湖", "金門", "連江",
]

# 商業/新聞/入口網站，不爬
_SKIP_DOMAINS = {
    "ettoday.net", "udn.com", "ltn.com.tw", "chinatimes.com", "tvbs.com.tw",
    "setn.com", "storm.mg", "businesstoday.com.tw", "cw.com.tw",
    "youtube.com", "facebook.com", "instagram.com", "threads.net",
    "google.com", "wikipedia.org", "taiwan.net.tw", "tripadvisor.com",
    "booking.com", "airbnb.com", "agoda.com",
}

# 偏好的部落格域名特徵
_BLOG_HINTS = (".tw", "blog", "life", "food", "eat", "travel", "go", "trip")

SOUVENIR_KW = ["伴手禮", "必買", "名產", "特產"]
TRENDING_KW  = ["美食", "必吃", "人氣", "推薦", "新開"]

# 每次搜尋最多取幾篇文章
MAX_RESULTS_PER_QUERY = 10
# 每篇文章最多抽幾家店
STORES_PER_ARTICLE = 20
# Custom Search 每日 100 次免費，22城市×2=44次，留有餘裕
SEARCH_RATE_SEC  = 1.0
SCRAPE_RATE_SEC  = 0.8

_YEAR = datetime.now().year

_JUNK_WORDS = {
    "更多", "相關", "廣告", "全部", "回到", "點此", "本文", "作者",
    "轉載", "來源", "版權", "目錄", "推薦", "必買", "必吃", "伴手禮",
    "最新流行", "美食推薦", "延伸閱讀", "參考資料", "免責聲明",
}
_GENERIC_ONLY = {
    "咖啡廳", "火鍋", "餐廳", "小吃", "美食", "夜市", "便當", "拉麵",
    "甜點", "飲料", "燒烤", "壽司", "早餐", "早午餐", "下午茶",
}
_SENTENCE_PATTERNS = re.compile(
    r"只有|都在|這裡|也有|都可|就是|一定|不能|不會|可以|如何|怎麼|"
    r"&nbsp|&amp|youtube|facebook|instagram|tiktok|套餐$|"
    r"^除了|^不只|^此外|^另外|^其中|^其實|^其他|^還有|^加上|^包括|^包含",
    re.IGNORECASE,
)


def _is_valid_name(name: str) -> bool:
    name = name.strip()
    if not name or len(name) < 2 or len(name) > 15:
        return False
    if not re.search(r"[\u4e00-\u9fff]", name):
        return False
    if any(j in name for j in _JUNK_WORDS):
        return False
    if name in _GENERIC_ONLY:
        return False
    if _SENTENCE_PATTERNS.search(name):
        return False
    if re.search(r"(以外|之外|以上|以下|之類|等等)[^店館坊屋廳樓]?$", name):
        return False
    if re.search(r"[捲餅糕酥凍塔派粉麵飯粥湯]外$", name):
        return False
    if re.match(r"^(台北|新北|台中|台南|高雄|桃園|新竹|基隆|嘉義|宜蘭|花蓮|台東)(美食|小吃|餐廳)?$", name):
        return False
    return True


def _fetch(url: str, timeout: int = 12) -> bytes | None:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; LifeUTurn/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        print(f"    ✗ fetch error: {e}")
        return None


def _google_search(query: str) -> list[str]:
    """呼叫 Serper.dev Google Search API，回傳文章 URL 列表。"""
    import json as _json
    payload = _json.dumps({
        "q": query,
        "gl": "tw",
        "hl": "zh-tw",
        "num": 10,
        "tbs": "qdr:y",  # 限定近一年
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={
                "X-API-KEY": SERPER_KEY,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = _json.loads(r.read().decode("utf-8"))
        urls = []
        for item in data.get("organic", []):
            link = item.get("link", "")
            domain = urllib.parse.urlparse(link).netloc.lower().lstrip("www.")
            if any(skip in domain for skip in _SKIP_DOMAINS):
                continue
            urls.append(link)
        return urls[:MAX_RESULTS_PER_QUERY]
    except Exception as e:
        print(f"    ✗ search error: {e}")
        return []


def _extract_stores(html: str, city: str) -> list[str]:
    """從 HTML 抽取店家名稱候選。"""
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.headings, self.bolds = [], []
            self._h, self._b, self._skip = None, None, False
        def handle_starttag(self, tag, attrs):
            if tag in ("script","style","nav","footer","header","aside"):
                self._skip = True
            elif tag in ("h2","h3","h4"): self._h = []
            elif tag in ("strong","b"):   self._b = []
        def handle_endtag(self, tag):
            if tag in ("script","style","nav","footer","header","aside"):
                self._skip = False
            elif tag in ("h2","h3","h4") and self._h is not None:
                t = "".join(self._h).strip()
                if t: self.headings.append(t)
                self._h = None
            elif tag in ("strong","b") and self._b is not None:
                t = "".join(self._b).strip()
                if t: self.bolds.append(t)
                self._b = None
        def handle_data(self, data):
            if self._skip: return
            d = data.strip()
            if self._h is not None: self._h.append(d)
            if self._b is not None: self._b.append(d)

    p = _P()
    try: p.feed(html)
    except: pass

    full_text = re.sub(r"<[^>]+>", " ", html)
    candidates = []
    for h in p.headings:
        h = re.sub(r"^\s*\d+[.\s、．]+", "", h)
        candidates.append(h.strip())
    for b in p.bolds:
        candidates.append(b.strip())
    candidates.extend(re.findall(r"「([^」]{2,15})」", full_text))
    candidates.extend(re.findall(
        r"(?:^|[\n\r])\s*[①②③④⑤⑥⑦⑧⑨⑩\d][.、）)]\s*([^\n\r]{2,20})",
        full_text, re.MULTILINE,
    ))

    seen, result = set(), []
    for name in candidates:
        name = re.sub(r"\s+", "", name.strip())
        name = re.sub(r"^\d+[.\s、]+", "", name)
        if not _is_valid_name(name) or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result[:STORES_PER_ARTICLE]


def _load_cache() -> dict:
    try:
        with open(BLOG_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"updated_at": "", "by_city": {}}


def main() -> None:
    if not SERPER_KEY:
        print("✗ 缺少 SERPER_API_KEY")
        sys.exit(1)

    cache = _load_cache()
    by_city: dict = cache.get("by_city", {})

    # 確保每個城市有基本結構
    for city in CITIES:
        by_city.setdefault(city, {"souvenir": {}, "trending": {}})
        for mode in ("souvenir", "trending"):
            # 相容舊格式（list → dict）
            if isinstance(by_city[city][mode], list):
                old = by_city[city][mode]
                by_city[city][mode] = {
                    item["name"]: {**item, "count": item.get("count", 1),
                                   "sources": item.get("sources", [])}
                    for item in old if item.get("name")
                }

    total_new = 0

    for city in CITIES:
        for mode in ("souvenir", "trending"):
            kw_list = SOUVENIR_KW if mode == "souvenir" else TRENDING_KW
            query = f"{city} {' '.join(kw_list[:2])} {_YEAR} 推薦 部落格"
            print(f"\n[{city}/{mode}] 搜尋：{query}")

            urls = _google_search(query)
            print(f"  → 找到 {len(urls)} 篇文章")
            time.sleep(SEARCH_RATE_SEC)

            bucket: dict = by_city[city][mode]

            for url in urls:
                raw = _fetch(url)
                if not raw:
                    time.sleep(SCRAPE_RATE_SEC)
                    continue
                html = raw.decode("utf-8", errors="ignore")
                names = _extract_stores(html, city)
                if not names:
                    time.sleep(SCRAPE_RATE_SEC)
                    continue

                # 從 URL 取來源名稱
                domain = urllib.parse.urlparse(url).netloc.lstrip("www.")
                source = domain.split(".")[0]

                for name in names:
                    if name in bucket:
                        bucket[name]["count"] += 1
                        if source not in bucket[name].get("sources", []):
                            bucket[name].setdefault("sources", []).append(source)
                    else:
                        bucket[name] = {
                            "name": name, "count": 1,
                            "sources": [source], "desc": "",
                        }
                        total_new += 1

                print(f"  ✓ {domain[:30]:30} → {', '.join(names[:4])}")
                time.sleep(SCRAPE_RATE_SEC)

    # 轉回 list 格式（按 count 降序），產生有意義的 desc
    by_city_list: dict = {}
    for city in CITIES:
        by_city_list[city] = {}
        for mode in ("souvenir", "trending"):
            items = sorted(by_city[city][mode].values(),
                           key=lambda x: x["count"], reverse=True)
            result_items = []
            for item in items:
                srcs = item.get("sources", [])
                if len(srcs) >= 2:
                    desc = f"{item['count']} 個來源提及・{'、'.join(srcs[:3])}"
                elif srcs:
                    desc = f"{srcs[0]} 推薦"
                else:
                    desc = item.get("desc", "")
                result_items.append({
                    "name":    item["name"],
                    "count":   item["count"],
                    "sources": srcs,
                    "desc":    desc,
                })
            by_city_list[city][mode] = result_items

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "by_city": by_city_list,
    }
    with open(BLOG_CACHE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！新增 {total_new} 家店，已寫入 {BLOG_CACHE}")


if __name__ == "__main__":
    main()
