"""
食記部落格爬蟲 v3 — 進入文章提取店家名稱
==========================================
流程：
  1. Google News RSS → 取得文章 URL 列表
  2. 進入每篇文章，用 HTML parser 抽取 h2/h3/bold/「」內的店家名稱
  3. 存成結構化資料（店名 + 簡述），不存文章連結（避免侵權/導流）

輸出：food_blog_cache.json
結構：
  {
    "updated_at": "YYYY-MM-DD HH:MM",
    "by_city": {
      "台中": {
        "trending": [{"name": "某某咖啡", "desc": "台中人氣打卡店"}],
        "souvenir": [{"name": "太陽餅", "desc": "台中必買伴手禮"}]
      }
    }
  }

執行：python scrape_food_blogs.py
排程：GitHub Actions 每天 07:00 TST
"""

import sys, io, json, os, re, time
import urllib.request
import urllib.parse
from datetime import datetime
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(_DIR, "food_blog_cache.json")
SOURCES_FILE = os.path.join(_DIR, "api", "data", "food_blog_sources.json")

CITIES: list[str] = [
    "台北", "新北", "基隆", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
    "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
    "澎湖", "金門", "連江",
]

SOUVENIR_KW = ["伴手禮", "必買", "名產", "特產", "禮盒", "手信", "帶回家", "必帶"]
TRENDING_KW = ["必吃", "推薦", "新開", "打卡", "排隊", "人氣", "網紅", "美食",
               "好吃", "隱藏版", "爆紅", "熱門", "話題", "限定"]

_BUCKET_LIMIT = 30
_ARTICLES_PER_BUCKET = 6   # 每城市每模式最多抓幾篇文章
_STORES_PER_ARTICLE = 6    # 每篇文章最多抽幾家店

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# ── 雜訊過濾詞（這些出現在標題/bold 裡代表不是店名）─────────────────────────
_JUNK_WORDS = {
    "更多", "相關", "廣告", "全部", "回到", "點此", "本文", "作者",
    "轉載", "來源", "版權", "目錄", "推薦", "必買", "必吃", "伴手禮",
    "最新流行", "美食推薦", "購物指南", "延伸閱讀", "參考資料",
    "資料來源", "注意事項", "免責聲明", "訂閱電子報", "無留言",
    "你也許", "留言", "分享", "標籤", "分類", "食尚玩家", "線上商城",
    "住宿", "周邊", "景點", "清單曝光", "曝光", "旅遊", "瀏覽器",
    "app", "APP", "心意", "送禮", "自用", "都加分",
}
# 單獨出現時不是店名的通用詞
_GENERIC_ONLY = {
    "咖啡廳", "火鍋", "餐廳", "小吃", "美食", "夜市", "便當", "拉麵",
    "甜點", "飲料", "燒烤", "壽司", "早餐", "早午餐", "下午茶",
    "台北美食", "台中美食", "台南美食", "高雄美食", "新竹美食",
    "特色美食", "在地美食", "隱藏美食", "人氣美食",
}
# 代表這是描述句而非店名的關鍵詞（忽略大小寫）
_SENTENCE_PATTERNS = re.compile(
    r"只有|都在|這裡|也有|都可|就是|一定|不能|不會|可以|如何|怎麼|"
    r"&nbsp|&amp|&lt|&gt|&quot|\+餐廳|\+店|都加分|兼具|為主|旅遊|"
    r"youtube|facebook|instagram|tiktok|系列套餐|套餐$",
    re.IGNORECASE,
)
# 出現即排除的單詞（非店名）
_SINGLE_JUNK = {
    "品項", "價錢", "地址", "電話", "評分", "營業", "停車", "交通",
    "捷運", "公車", "步行", "訂位", "官網", "菜單", "重箱", "重箱系列",
}



def _fetch_url(url: str, timeout: int = 12) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        print(f"    ✗ fetch {url[:60]}: {e}")
        return None


# ── HTML 解析器：抽取標題/bold/引號裡的店家候選名稱 ──────────────────────────

class _ArticleParser(HTMLParser):
    """從文章 HTML 中抽取 h2/h3/h4、strong/b、li 文字"""

    def __init__(self) -> None:
        super().__init__()
        self.headings: list[str] = []
        self.bolds: list[str] = []
        self.list_items: list[str] = []
        self.full_parts: list[str] = []
        self._cur_h: list[str] | None = None
        self._cur_b: list[str] | None = None
        self._cur_li: list[str] | None = None
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
            self._skip = True
        elif tag in ("h2", "h3", "h4"):
            self._cur_h = []
        elif tag in ("strong", "b"):
            self._cur_b = []
        elif tag == "li":
            self._cur_li = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
            self._skip = False
        elif tag in ("h2", "h3", "h4") and self._cur_h is not None:
            t = "".join(self._cur_h).strip()
            if t:
                self.headings.append(t)
            self._cur_h = None
        elif tag in ("strong", "b") and self._cur_b is not None:
            t = "".join(self._cur_b).strip()
            if t:
                self.bolds.append(t)
            self._cur_b = None
        elif tag == "li" and self._cur_li is not None:
            t = "".join(self._cur_li).strip()
            if t:
                self.list_items.append(t)
            self._cur_li = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        d = data.strip()
        if not d:
            return
        self.full_parts.append(d)
        if self._cur_h is not None:
            self._cur_h.append(d)
        if self._cur_b is not None:
            self._cur_b.append(d)
        if self._cur_li is not None:
            self._cur_li.append(d)


def _clean_text(s: str) -> str:
    """移除 HTML entities 和多餘空白"""
    s = re.sub(r"&nbsp;?", " ", s)
    s = re.sub(r"&amp;?", "&", s)
    s = re.sub(r"&[a-z]+;", "", s)
    # 去除尾部的「  blog名稱」（兩個以上空格後面的）
    s = re.sub(r"\s{2,}.+$", "", s)
    return s.strip()


def _is_valid_name(name: str) -> bool:
    """判斷是否為有效店名/商品名"""
    name = _clean_text(name)
    if not name or len(name) < 2 or len(name) > 15:
        return False
    if not re.search(r"[\u4e00-\u9fff]", name):
        return False
    if any(j.lower() in name.lower() for j in _JUNK_WORDS):
        return False
    if name in _GENERIC_ONLY or name in _SINGLE_JUNK:
        return False
    if _SENTENCE_PATTERNS.search(name):
        return False
    # 含大量英文（如 YouTube跟著xxx、品牌handle）
    ascii_ratio = sum(1 for c in name if c.isascii() and c.isalpha()) / max(len(name), 1)
    if ascii_ratio > 0.4:
        return False
    # 含城市名稱 + 單字（如「台中美食」→ 太泛）
    if re.match(r"^(台北|新北|台中|台南|高雄|桃園|新竹|基隆|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|台東|澎湖|金門|連江)(美食|小吃|餐廳|景點|旅遊)?$", name):
        return False
    # 過濾純描述句
    if re.search(r"[的了也都很是就在有].*[的了也都很是就在有]", name):
        return False
    # 含全形＋分隔多項食材/口味（不是店名）
    if "＋" in name or "+" in name:
        return False
    # 「平價/超值/排隊 + 食品種類」= 描述語，不是店名
    if re.match(r"^(平價|超值|高CP|排隊人氣|人氣|熱門|超人氣|爆紅|網紅|隱藏版|私房|在地|必吃|口味|新開|超推|台式|日式|韓式|港式|義式)", name):
        return False
    # 純食品種類結尾（無前綴店名特徵）
    if re.match(r"^[\w\s]{1,4}(蛋糕|吐司|泡芙|塔|派|捲|卷|餅|糕|酥|凍|布丁|慕斯|冰淇淋|冰品|飲品|果汁)$", name):
        return False
    return True


def _extract_store_names(html: str, city: str) -> list[str]:
    """從 HTML 內容抽取店家/商品名稱候選列表"""
    p = _ArticleParser()
    try:
        p.feed(html)
    except Exception:
        pass

    candidates: list[str] = []

    # h2/h3 標題（listicle 文章最常見 = 店名）
    for h in p.headings:
        h = re.sub(r"^\s*\d+[.\s、．。]+", "", h)  # 去開頭數字
        h = re.sub(r"[【】\[\]《》〈〉]", "", h)    # 去括號
        candidates.append(h.strip())

    # bold/strong 文字
    for b in p.bolds:
        b = re.sub(r"^\s*\d+[.\s、]+", "", b)
        candidates.append(b.strip())

    # li 清單（有些文章用清單列店名）
    for li in p.list_items:
        li = re.sub(r"^\s*\d+[.\s、]+", "", li)
        if len(li) <= 20:
            candidates.append(li.strip())

    # 全文「」書名號內容
    full = " ".join(p.full_parts)
    candidates.extend(re.findall(r"「([^」]{2,15})」", full))

    # 數字清單項目（① ② 或 1. 2.）
    candidates.extend(re.findall(
        r"(?:^|[\n\r])\s*[①②③④⑤⑥⑦⑧⑨⑩\d][.、）\)]\s*([^\n\r]{2,20})",
        full, re.MULTILINE,
    ))

    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        name = _clean_text(name)
        if not _is_valid_name(name):
            continue
        if re.search(r"https?://|www\.", name):
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(name)

    return result[:_STORES_PER_ARTICLE]


def _classify_mode(title: str) -> str:
    if any(kw in title for kw in SOUVENIR_KW):
        return "souvenir"
    return "trending"


# ── Google News RSS → 從標題/摘要直接抽店名（不 follow redirect）───────────

def _google_news_stores(city: str, mode: str) -> list[dict]:
    """從 Google News RSS 標題和描述直接抽取店家名稱，不需抓全文"""
    q = f"{city} 伴手禮 必買 推薦" if mode == "souvenir" else f"{city} 美食 必吃 人氣 推薦"
    encoded = urllib.parse.quote(q)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    raw = _fetch_url(url)
    if not raw:
        return []

    mode_label = "必買伴手禮" if mode == "souvenir" else "人氣美食"
    stores: list[dict] = []
    seen: set[str] = set()

    try:
        root = ET.fromstring(raw.decode("utf-8", errors="ignore"))
        for item in root.findall(".//item")[:20]:
            title = re.sub(r"<[^>]+>", "", item.findtext("title") or "")
            desc  = re.sub(r"<[^>]+>", "", item.findtext("description") or "")
            combined = title + " " + desc

            # 抽 「」引號內店名
            quoted = re.findall(r"[「『]([^」』]{2,15})[」』]", combined)
            # 抽數字清單（如「1. 某某店」）
            numbered = re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩\d][.、\)]\s*([^\s、。，,]{2,15})", combined)
            # 抽冒號後的清單（如「推薦：A、B、C」）
            after_colon = re.findall(r"[：:]\s*([^\s,，。！]+(?:[、,，][^\s,，。！]+)*)", combined)
            colon_items: list[str] = []
            for seg in after_colon:
                colon_items.extend(re.split(r"[、,，]", seg))

            candidates = quoted + numbered + colon_items
            for name in candidates:
                name = _clean_text(name)
                if not _is_valid_name(name):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                stores.append({"name": name, "desc": f"{city} {mode_label}・Google News 精選"})
                if len(stores) >= _BUCKET_LIMIT:
                    return stores
    except Exception:
        pass

    return stores


# ── 部落格 RSS → 文章 URL 列表 ───────────────────────────────────────────────

def _blog_article_urls(site_url: str) -> list[str]:
    base = site_url.rstrip("/")
    for rss_path in ("/feed", "/feed/", "/rss", "/rss.xml", "/atom.xml", "/index.xml"):
        raw = _fetch_url(base + rss_path, timeout=10)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw.decode("utf-8", errors="ignore"))
            urls = []
            for item in root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                link = item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or ""
                if link:
                    urls.append(link)
            if urls:
                return urls[:_ARTICLES_PER_BUCKET]
        except Exception:
            continue
    return []


# ── 主流程：抓文章 → 抽店名 ──────────────────────────────────────────────────

def _scrape_stores(article_url: str, city: str, mode: str, source: str) -> list[dict]:
    """進入文章，抽取店家名稱，回傳結構化資料"""
    raw = _fetch_url(article_url, timeout=15)
    if not raw:
        return []
    html = raw.decode("utf-8", errors="ignore")
    names = _extract_store_names(html, city)
    if not names:
        return []

    mode_label = "必買伴手禮" if mode == "souvenir" else "人氣美食"
    return [
        {"name": name, "desc": f"{city} {mode_label}・{source} 推薦"}
        for name in names
    ]


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 50)
    print(f"食記爬蟲 v3（店家提取模式）— {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    by_city: dict[str, dict[str, list]] = {
        city: {"souvenir": [], "trending": []} for city in CITIES
    }
    seen_names: dict[str, set] = {city: set() for city in CITIES}

    def _add_stores(city: str, mode: str, stores: list[dict]) -> None:
        bucket = by_city[city][mode]
        ns = seen_names[city]
        for s in stores:
            name = s["name"]
            if name in ns or len(bucket) >= _BUCKET_LIMIT:
                continue
            ns.add(name)
            bucket.append(s)

    # ── Step 1: Google News RSS 標題/摘要抽取店名 ────────────────────────────
    print("\n── Google News RSS 標題摘要抽取 ──")
    for city in CITIES:
        for mode in ("trending", "souvenir"):
            stores = _google_news_stores(city, mode)
            _add_stores(city, mode, stores)
            t = len(by_city[city][mode])
            print(f"  {city}/{mode}: {t} 家")
            time.sleep(0.3)

    # ── Step 2: 部落格 RSS ────────────────────────────────────────────────────
    print("\n── 部落格 RSS → 進入文章抽取店家 ──")
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            sources_data = json.load(f)
        blogs = sources_data.get("blogs", [])
        for blog in blogs:
            site_url = (blog.get("url") or "").strip()
            name = blog.get("name", "部落格")
            blog_cities = blog.get("cities", [])
            if not site_url or not site_url.startswith("http") or not blog_cities:
                continue
            article_urls = _blog_article_urls(site_url)
            if not article_urls:
                continue
            print(f"  {name}（{', '.join(blog_cities[:3])}）: {len(article_urls)} 篇文章")
            for url in article_urls:
                # 依文章 URL 判斷 mode，無法判斷預設 trending
                raw = _fetch_url(url, timeout=15)
                if not raw:
                    time.sleep(0.5)
                    continue
                html = raw.decode("utf-8", errors="ignore")
                # 從 og:title 或 title tag 推斷 mode
                title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
                title_text = title_m.group(1) if title_m else ""
                mode = _classify_mode(title_text)
                names = _extract_store_names(html, blog_cities[0])
                stores = [
                    {"name": n, "desc": f"{c} {'必買伴手禮' if mode == 'souvenir' else '人氣美食'}・{name} 推薦"}
                    for c in blog_cities for n in names
                ]
                for city in blog_cities:
                    city_stores = [s for s in stores if s["desc"].startswith(city)]
                    _add_stores(city, mode, city_stores)
                time.sleep(0.6)
    except Exception as e:
        print(f"部落格來源載入失敗: {e}")

    # ── 統計 ──────────────────────────────────────────────────────────────────
    total = sum(len(v["souvenir"]) + len(v["trending"]) for v in by_city.values())
    print(f"\n分類完成：{total} 家店資料")
    for city in CITIES:
        s = len(by_city[city]["souvenir"])
        t = len(by_city[city]["trending"])
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
