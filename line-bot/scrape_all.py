"""
生活超級助理 — 全自動活動爬蟲
================================
來源優先級：
  1. Accupass（最多、最全，Selenium headless）
  2. KKTIX（演出/展覽，Selenium non-headless 繞過 Cloudflare）
  3. 台南市文化局（官方品質，requests）
  4. 台南市美術館（展覽，requests）

執行方式：python scrape_all.py
建議排程：每週五 18:00 執行
輸出：accupass_cache.json（webhook.py 自動讀取）
"""

import sys, io, json, re, os, time
from datetime import datetime
from urllib.parse import quote

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import requests
except ImportError:
    print("[ERROR] 需要安裝：pip install selenium requests")
    sys.exit(1)

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "accupass_cache.json")
TODAY = datetime.now()
START_DATE = TODAY.strftime("%Y-%m-%d")

# ── 城市清單 ──────────────────────────────────────────
CITIES = ["台南", "台北", "台中", "高雄", "新北", "桃園", "新竹", "宜蘭", "花蓮", "嘉義"]

# ── 垃圾過濾（這些出現就直接丟掉）────────────────────
BLOCKLIST = [
    "心理諮商", "口腔", "吞嚥", "跨境電商", "直銷", "保險", "投資",
    "房地產", "講座", "說明會", "招募", "招生", "課程報名", "職涯",
    "民防", "防災", "醫療", "復健", "語言學習", "英語學習", "日語",
    "考試", "證照", "健身私教", "健身課", "瑜珈課", "皮拉提斯課",
    "場地租借", "會議室", "辦公室", "營業登記",
    # 交友/聯誼活動（容易混入吃喝玩樂分類）
    "交友", "聯誼", "單身", "未婚", "相親", "配對", "脫單", "派約",
    "Speed Dating", "NPC練愛", "歌友會", "練愛",
    # Threads 系統垃圾文字
    "掃描即可下載", "Instagram 帳號", "忘記密碼", "使用 Instagram",
    "下載應用程式", "Threads", "登入", "繼續 ©",
]

# ── 分類關鍵詞（順序即優先級，越上面越優先）──────────
CATEGORY_MAP = {
    # 表演音樂放最前面，避免被誠品/書店等文青關鍵詞搶走
    "表演音樂": [
        "音樂", "演唱", "樂團", "演奏", "歌謠", "livehouse", "live house",
        "音樂會", "爵士", "古典", "演出", "open mic", "喜劇", "脫口秀",
        "傳唱", "音樂節", "band", "演唱會", "相聲", "說唱",
    ],
    # 文青咖啡：導覽/散步/老屋/書店 + 繪畫課/水彩課也算文青體驗
    "文青咖啡": [
        "導覽", "散步", "老屋", "文創", "書店", "誠品", "巷弄", "古蹟",
        "走讀", "府城", "老街", "人文", "歷史", "茶道", "茶藝",
        "水彩", "油畫", "素描", "色鉛筆", "粉彩", "繪畫", "畫課",
        "服裝畫", "肌理畫", "炭筆",
    ],
    # 親子同樂：兒童 + 家庭手作體驗
    "親子同樂": [
        "親子", "兒童", "小朋友", "寶貝", "小孩", "家庭",
        "黏土", "染布", "繪本", "兒童節", "童趣", "童遊",
        "小火柴", "工作坊", "diy",
    ],
    # 市集展覽：市集/展覽/博物館（手作體驗不算，那是親子/文青）
    "市集展覽": [
        "市集", "展覽", "展出", "博物館", "美術館", "特展",
        "聯展", "個展", "藝術節", "燈節", "燈會",
    ],
    # 吃喝玩樂：美食/餐廳/品酒/野餐（嚴格限定吃喝相關）
    "吃喝玩樂": [
        "美食", "餐廳", "品酒", "葡萄酒", "啤酒", "下午茶", "甜點",
        "小吃", "野餐", "美食節", "料理", "廚房", "品鑑", "試飲",
        "饗宴", "宴", "buffet",
    ],
    # 戶外踏青：戶外活動/生態/農場
    "戶外踏青": [
        "戶外", "踏青", "健行", "登山", "自行車", "農場", "田野",
        "海邊", "溪流", "露營", "生態", "賞花", "賞鳥", "採果",
        "觀星", "夜遊", "步道",
    ],
}


def is_blocked(text: str) -> bool:
    """檢查是否為不相關活動（課程/商業/醫療等）"""
    return any(kw in text for kw in BLOCKLIST)


def is_expired(date_str: str) -> bool:
    """判斷活動是否已過期（只看開始日期）"""
    if not date_str:
        return False  # 沒日期的保留
    # 嘗試解析 "2026.04.08" 或 "04/08" 格式
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", date_str)
    if m:
        try:
            event_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return event_date.date() < TODAY.date()
        except Exception:
            return False
    # 只有月/日格式，今年判斷
    m2 = re.search(r"(\d{2})[./](\d{2})", date_str)
    if m2:
        try:
            month, day = int(m2.group(1)), int(m2.group(2))
            event_date = datetime(TODAY.year, month, day)
            return event_date.date() < TODAY.date()
        except Exception:
            return False
    return False


def classify(text: str) -> str:
    """依關鍵詞分類，優先級由上到下"""
    text_lower = text.lower()
    for cat, kws in CATEGORY_MAP.items():
        if any(kw in text_lower for kw in kws):
            return cat
    return None  # 無法分類 → 丟棄


def make_headless_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=zh-TW")
    return webdriver.Chrome(options=opts)


def make_stealth_driver():
    """繞過 Cloudflare；CI 環境自動改用 headless（無顯示器）"""
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=zh-TW")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36")
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# ══════════════════════════════════════════════════════
# 來源 0：漫步時光 strolltimes.com（全台，純 requests）
# ══════════════════════════════════════════════════════

import urllib.request as _ur

_STROLL_CITY_MAP = {
    "changhua": "彰化", "chiayi": "嘉義", "hualien": "花蓮",
    "kaohsiung": "高雄", "keelung": "基隆", "miaoli": "苗栗",
    "nantou": "南投", "newtaipei": "新北", "penghu": "澎湖",
    "pingtung": "屏東", "taichung": "台中", "tainan": "台南",
    "taipei": "台北", "taitung": "台東", "taoyuan": "桃園",
    "yilan": "宜蘭", "yunlin": "雲林", "hsinchu": "新竹",
}
_STROLL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def _stroll_fetch(url: str, timeout: int = 10) -> str:
    req = _ur.Request(url, headers=_STROLL_HEADERS)
    try:
        with _ur.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def scrape_strolltimes() -> dict:
    """
    從漫步時光 search-index.json 抓全台活動。
    純 requests，無需 Selenium。
    回傳 {"台南": {"市集展覽": [...], ...}, "台北": {...}, ...}
    """
    print("\n[漫步時光 strolltimes.com]...")
    body = _stroll_fetch("https://strolltimes.com/search-index.json", timeout=30)
    if not body:
        print("  [ERROR] 無法下載 search-index.json")
        return {}

    try:
        data = json.loads(body)
        docs = data[0]["documents"]
    except Exception as e:
        print(f"  [ERROR] 解析失敗: {e}")
        return {}

    # 只取 /events/{city_en}/{id} 格式的文件
    event_docs = [
        d for d in docs
        if re.match(r"^/events/[a-z]+/\d+$", d.get("u", ""))
    ]
    print(f"  找到 {len(event_docs)} 筆活動文件")

    result = {}  # {city_zh: {cat: [events]}}

    for doc in event_docs:
        url_path = doc["u"]
        title = doc.get("t", "").strip()
        if not title or len(title) < 5:
            continue

        # 解析城市
        m = re.match(r"^/events/([a-z]+)/(\d+)$", url_path)
        if not m:
            continue
        city_en, url_id = m.group(1), m.group(2)
        city_zh = _STROLL_CITY_MAP.get(city_en)
        if not city_zh:
            continue

        # 從 URL ID 解析發布時間（格式：YYMMDD...）
        pub_date_str = url_id[:6]  # YYMMDD
        try:
            pub_date = datetime(2000 + int(pub_date_str[:2]),
                                int(pub_date_str[2:4]),
                                int(pub_date_str[4:6]))
        except Exception:
            pub_date = TODAY

        # 從標題抓活動日期（如 "(4/11)" 或 "（4/11~4/30）"）
        # 用標題末尾的括號日期
        date_short = ""
        date_m = re.search(r"[（(](\d{1,2}/\d{1,2})", title)
        if date_m:
            parts = date_m.group(1).split("/")
            try:
                mo, dy = int(parts[0]), int(parts[1])
                ev_date = datetime(TODAY.year, mo, dy)
                if ev_date.date() < TODAY.date():
                    continue  # 活動已過期
                date_short = f"{mo:02d}/{dy:02d}"
            except Exception:
                pass
        else:
            # 沒有日期的活動：根據發布時間判斷，超過 90 天前發布的跳過
            days_ago = (TODAY - pub_date).days
            if days_ago > 90:
                continue

        # 過濾 BLOCKLIST
        if is_blocked(title):
            continue

        # 取 og:description（批次請求，每城市最多 15 篇）
        full_url = f"https://strolltimes.com{url_path}"
        page = _stroll_fetch(full_url, timeout=8)
        desc_raw = ""
        if page:
            dsc_m = re.search(r'name="description" content="([^"]{10,400})"', page)
            if dsc_m:
                desc_raw = dsc_m.group(1).strip()

        desc = desc_raw[:80] if desc_raw else title[len(title)//2:]

        # 分類
        classify_text = title + " " + desc_raw
        if any(kw in classify_text for kw in ["市集", "展覽", "特展", "燈會", "燈節"]):
            cat = "市集展覽"
        else:
            cat = classify(classify_text) or "市集展覽"

        entry = {
            "name": title[:50],
            "desc": f"{date_short} | {desc}" if date_short else desc,
            "date": date_short,
            "url": full_url,
            "source": "漫步時光",
            "area": city_zh,
        }

        if city_zh not in result:
            result[city_zh] = {cat: [] for cat in CATEGORY_MAP}
        if cat not in result[city_zh]:
            result[city_zh][cat] = []

        # 每城市每分類最多 8 筆
        if len(result[city_zh][cat]) < 8:
            result[city_zh][cat].append(entry)

    # 移除空分類
    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    total = sum(len(e) for cats in result.values() for e in cats.values())
    for city, cats in result.items():
        city_total = sum(len(v) for v in cats.values())
        print(f"  {city}: {city_total} 筆")
    print(f"  → 合計 {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源 0.5：小藝行事曆 yii.tw（全台藝文月曆，純 requests）
# ══════════════════════════════════════════════════════

_YII_CITY_MAP = {
    "taipei":    "台北",
    "taichung":  "台中",
    "kaohsiung": "高雄",
    "tainan":    "台南",
    "taoyuan":   "桃園",
    "hsinchu":   "新竹",
    "yilan":     "宜蘭",
}
_YII_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://yii.tw/",
}


def scrape_yii() -> dict:
    """
    從小藝行事曆 yii.tw 抓各城市藝文月曆活動。
    純 requests，無需 Selenium。HTML server-side rendered。
    """
    print("\n[小藝行事曆 yii.tw]...")
    result = {}

    for city_en, city_zh in _YII_CITY_MAP.items():
        url = f"https://yii.tw/{city_en}/calendar"
        try:
            resp = requests.get(url, headers=_YII_HEADERS, timeout=15)
            html = resp.text
        except Exception as e:
            print(f"  {city_zh}: 連線失敗 {e}")
            continue

        # 按 info-card 切塊
        sections = html.split('class="info-card"')
        city_events = {cat: [] for cat in CATEGORY_MAP}
        count = 0

        for section in sections[1:]:
            # 標題 + 連結：href="/events/..."
            title_m = re.search(
                r'href="(/events/[^"?#]{5,})"[^>]*>\s*([^<]{3,80})\s*</a>',
                section[:800]
            )
            if not title_m:
                continue
            ev_url = "https://yii.tw" + title_m.group(1)
            title = re.sub(r"\s+", " ", title_m.group(2)).strip()
            if not title or len(title) < 4:
                continue

            # 日期
            time_m = re.search(r'class="time"[^>]*>\s*([^<]{3,60})', section[:600])
            date_raw = time_m.group(1).strip() if time_m else ""

            # 地點
            place_m = re.search(r'class="place"[^>]*>\s*([^<]{2,50})', section[:600])
            place = place_m.group(1).strip() if place_m else ""

            # 解析日期、過濾過期
            date_short = ""
            dm = re.search(r"(\d{1,2})/(\d{1,2})", date_raw)
            if dm:
                try:
                    mo, dy = int(dm.group(1)), int(dm.group(2))
                    ev_date = datetime(TODAY.year, mo, dy)
                    if ev_date.date() < TODAY.date():
                        continue
                    date_short = f"{mo:02d}/{dy:02d}"
                except Exception:
                    pass

            if is_blocked(title):
                continue

            desc_parts = [x for x in [date_short, place] if x]
            desc = " | ".join(desc_parts) if desc_parts else title[:40]
            cat_text = title + " " + desc

            if any(kw in cat_text for kw in ["市集", "展覽", "特展", "博物館", "美術館", "藝術節", "燈節", "燈會"]):
                cat = "市集展覽"
            else:
                cat = classify(cat_text) or "市集展覽"

            if len(city_events[cat]) >= 10:
                continue

            city_events[cat].append({
                "name": title[:55],
                "desc": desc,
                "date": date_short,
                "url": ev_url,
                "source": "小藝行事曆",
                "area": city_zh,
            })
            count += 1

        if count > 0:
            result[city_zh] = {k: v for k, v in city_events.items() if v}
            print(f"  {city_zh}: {count} 筆")

    total = sum(len(e) for cats in result.values() for e in cats.values())
    print(f"  → 合計 {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源 0.6：華山1914文創園區（台北，純 requests）
# ══════════════════════════════════════════════════════

_HUASHAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.huashan1914.com/",
}


def scrape_huashan() -> dict:
    """
    從華山1914文創園區官網抓台北展覽/活動（純 requests）。
    主要貢獻：台北 市集展覽
    """
    print("\n[華山1914]...")
    try:
        resp = requests.get(
            "https://www.huashan1914.com/w/huashan1914/event",
            headers=_HUASHAN_HEADERS, timeout=15
        )
        html = resp.text
    except Exception as e:
        print(f"  連線失敗: {e}")
        return {}

    # 抓所有活動連結 + 標題
    # 結構：<a href="/w/huashan1914/event_detail...">...標題...</a>
    events = []
    seen = set()

    # 抓 /w/huashan1914/event 或 /event_ 開頭的連結
    link_blocks = re.findall(
        r'<a\s+[^>]*href="(/w/huashan1914/[^"]*event[^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL | re.IGNORECASE
    )
    for path, inner in link_blocks:
        title = re.sub(r"<[^>]+>", "", inner).strip()
        title = re.sub(r"\s+", " ", title)
        if not title or len(title) < 4 or title in seen:
            continue
        if is_blocked(title):
            continue
        seen.add(title)
        ev_url = "https://www.huashan1914.com" + path
        cat_text = title
        if any(kw in cat_text for kw in ["音樂", "演唱", "演出", "表演", "樂團"]):
            cat = "表演音樂"
        else:
            cat = "市集展覽"
        events.append({
            "name": title[:55],
            "desc": "華山1914文創園區",
            "date": "",
            "url": ev_url,
            "source": "華山1914",
            "area": "台北",
            "_cat": cat,
        })

    result = {}
    for e in events[:20]:
        cat = e.pop("_cat")
        if "台北" not in result:
            result["台北"] = {c: [] for c in CATEGORY_MAP}
        if len(result["台北"].get(cat, [])) < 8:
            result["台北"].setdefault(cat, []).append(e)

    total = sum(len(v) for v in result.get("台北", {}).values())
    print(f"  台北: {total} 筆")
    return {k: {c: v for c, v in cats.items() if v} for k, cats in result.items() if any(cats.values())}


# ══════════════════════════════════════════════════════
# 來源 1：Accupass（主力來源）
# ══════════════════════════════════════════════════════

def scrape_accupass(driver, city: str) -> dict:
    print(f"  [Accupass] {city}...")
    url = f"https://www.accupass.com/search?q={quote(city)}&startDate={START_DATE}"
    driver.get(url)
    time.sleep(6)
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)

    script = (
        "var links=document.querySelectorAll('a[href*=\"/event/\"]');"
        "var res=[];var seen={};"
        "for(var i=0;i<links.length;i++){"
        "  var h=links[i].href.split('?')[0];"
        "  if(seen[h])continue;seen[h]=1;"
        "  var p=links[i].parentElement;"
        "  var txt=p?p.innerText:links[i].innerText;"
        "  res.push([h,txt.substring(0,400)]);"
        "}"
        "return res.slice(0,60);"
    )
    raw = driver.execute_script(script) or []

    result = {cat: [] for cat in CATEGORY_MAP}
    skipped_expired = 0
    skipped_blocked = 0
    skipped_unclass = 0

    for url, text in raw:
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if not lines:
            continue
        date_line, title, tag = "", "", ""
        for line in lines:
            if re.match(r"\d{4}\.", line) and not date_line:
                date_line = line[:25]
            elif line.startswith("#") and not tag:
                tag = line
            elif len(line) > 5 and not title and not re.match(r"\d{4}\.", line):
                title = line[:50]
        if not title:
            title = lines[0][:50]

        # ── 過濾1：已過期 ──
        if is_expired(date_line):
            skipped_expired += 1
            continue

        # ── 過濾2：垃圾活動 ──
        if is_blocked(f"{title} {tag}"):
            skipped_blocked += 1
            continue

        # 正確抓月/日：2026.04.18 → 04/18
        m = re.search(r"\d{4}\.(\d{2})\.(\d{2})", date_line)
        date_short = f"{m.group(1)}/{m.group(2)}" if m else ""

        # ── 過濾3：無法分類 ──
        cat = classify(f"{title} {tag}")
        if cat is None:
            skipped_unclass += 1
            continue

        result[cat].append({
            "name": title,
            "desc": f"{date_short} | {tag}" if date_short else tag,
            "date": date_line,
            "url": url,
            "source": "Accupass",
            "area": city,
        })

    kept = sum(len(v) for v in result.values())
    print(f"    保留 {kept} 筆｜過期丟棄 {skipped_expired}｜垃圾丟棄 {skipped_blocked}｜無分類丟棄 {skipped_unclass}")
    return {k: v for k, v in result.items() if v}


# ══════════════════════════════════════════════════════
# 來源 2：KKTIX（演出/展覽補充）
# ══════════════════════════════════════════════════════

def scrape_kktix(driver, city: str) -> dict:
    print(f"  [KKTIX] {city}...")
    # KKTIX location codes
    loc_map = {"台南": "tainan", "台北": "taipei", "台中": "taichung",
               "高雄": "kaohsiung", "新北": "new-taipei", "桃園": "taoyuan",
               "新竹": "hsinchu", "宜蘭": "yilan", "花蓮": "hualien", "嘉義": "chiayi"}
    loc = loc_map.get(city, "")
    url = f"https://kktix.com/events?l={loc}" if loc else f"https://kktix.com/events?q={quote(city)}"

    driver.get(url)
    time.sleep(7)

    # Check if blocked by Cloudflare
    if "安全驗證" in driver.find_element(By.TAG_NAME, "body").text:
        print(f"    [KKTIX] {city} 被 Cloudflare 擋住，跳過")
        return {}

    script = (
        "var links=document.querySelectorAll('a[href*=\"/events/\"]');"
        "var res=[];var seen={};"
        "for(var i=0;i<links.length;i++){"
        "  var h=links[i].href.split('?')[0];"
        "  if(seen[h]||h.indexOf('/events/')<0)continue;"
        "  seen[h]=1;"
        "  var p=links[i].closest('article,li,[class*=event],[class*=card]');"
        "  var txt=p?p.innerText:links[i].innerText;"
        "  if(txt.trim().length>5) res.push([h,txt.substring(0,300)]);"
        "}"
        "return res.slice(0,30);"
    )
    raw = driver.execute_script(script) or []

    result = {cat: [] for cat in CATEGORY_MAP}
    for url, text in raw:
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        title = lines[0][:50] if lines else ""
        cat_hint = lines[0] if lines else ""  # KKTIX 第一行通常是分類
        date_hint = next((l for l in lines if re.search(r"\d{4}/\d{1,2}/\d{1,2}", l)), "")
        full = " ".join(lines[:3])

        # KKTIX 分類對應
        kktix_cat_map = {"演出": "表演音樂", "展覽": "市集展覽", "親子": "親子同樂",
                         "美食": "吃喝玩樂", "同好": "吃喝玩樂", "學習": "文青咖啡"}
        cat = kktix_cat_map.get(cat_hint, classify(full))

        result[cat].append({
            "name": lines[1][:50] if len(lines) > 1 else title,
            "desc": date_hint[:20] if date_hint else "",
            "date": date_hint,
            "url": url,
            "source": "KKTIX",
            "area": city,
        })
    return {k: v for k, v in result.items() if v}


# ══════════════════════════════════════════════════════
# 來源 3：台南市文化局（官方精選）
# ══════════════════════════════════════════════════════

def scrape_tainan_culture(driver) -> dict:
    print("  [台南文化局]...")
    driver.get("https://culture.tainan.gov.tw/form/index?Parser=2,6,278,276")
    time.sleep(5)

    script = (
        "var items=document.querySelectorAll('.list-item,article,.item,tr');"
        "var res=[];var links=document.querySelectorAll('a[href*=\"cultureActivity\"],a[href*=\"form\"]');"
        "for(var i=0;i<links.length;i++){"
        "  var t=links[i].innerText.trim();"
        "  if(t.length>5) res.push([links[i].href,t.substring(0,100)]);"
        "}"
        "return res.slice(0,20);"
    )
    raw = driver.execute_script(script) or []

    result = {cat: [] for cat in CATEGORY_MAP}
    for url, text in raw:
        cat = classify(text)
        result[cat].append({
            "name": text[:50],
            "desc": "台南市文化局官方活動",
            "date": "",
            "url": url,
            "source": "台南文化局",
            "area": "台南",
        })
    return {k: v for k, v in result.items() if v}


# ══════════════════════════════════════════════════════
# 來源 5：駁二藝術特區（高雄，Selenium）
# ══════════════════════════════════════════════════════

def scrape_pier2(driver) -> dict:
    """駁二藝術特區活動（高雄 市集展覽/表演音樂，Selenium）"""
    print("  [駁二藝術特區]...")
    driver.get("https://pier2.org/activity")
    time.sleep(5)

    script = (
        "var links=document.querySelectorAll('a[href*=\"/activity/\"],a[href*=\"/event/\"]');"
        "var res=[];var seen={};"
        "for(var i=0;i<links.length;i++){"
        "  var h=links[i].href.split('?')[0];"
        "  if(seen[h])continue;seen[h]=1;"
        "  var p=links[i].closest('article,li,.card,[class*=item],[class*=event]')||links[i].parentElement;"
        "  var txt=(p?p.innerText:links[i].innerText).trim();"
        "  if(txt.length>4) res.push([h,txt.substring(0,300)]);"
        "}"
        "return res.slice(0,30);"
    )
    raw = driver.execute_script(script) or []

    items = []
    seen = set()
    for url, text in raw:
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 3]
        if not lines:
            continue
        title = lines[0][:55]
        if title in seen or is_blocked(title):
            continue
        seen.add(title)
        full = " ".join(lines[:4])
        date_m = re.search(r"(\d{1,2})[/.](\d{1,2})", full)
        date_short = ""
        if date_m:
            try:
                mo, dy = int(date_m.group(1)), int(date_m.group(2))
                ev = datetime(TODAY.year, mo, dy)
                if ev.date() < TODAY.date():
                    continue
                date_short = f"{mo:02d}/{dy:02d}"
            except Exception:
                pass

        if any(kw in full for kw in ["音樂", "演唱", "演出", "表演", "樂團"]):
            cat = "表演音樂"
        else:
            cat = "市集展覽"

        items.append({"name": title, "desc": date_short or "駁二藝術特區",
                      "date": date_short, "url": url, "source": "駁二", "area": "高雄", "_cat": cat})

    result = {}
    for e in items[:20]:
        cat = e.pop("_cat")
        if "高雄" not in result:
            result["高雄"] = {c: [] for c in CATEGORY_MAP}
        if len(result["高雄"].get(cat, [])) < 8:
            result["高雄"].setdefault(cat, []).append(e)

    total = sum(len(v) for v in result.get("高雄", {}).values())
    if total:
        print(f"    → {total} 筆")
    return {k: {c: v for c, v in cats.items() if v} for k, cats in result.items() if any(cats.values())}


# ══════════════════════════════════════════════════════
# 來源 4：台南美術館（展覽）
# ══════════════════════════════════════════════════════

def scrape_tnam(driver) -> dict:
    print("  [台南美術館]...")
    driver.get("https://www.tnam.museum/zh-tw/exhibition-list")
    time.sleep(5)

    script = (
        "var cards=document.querySelectorAll('a[href*=\"exhibition\"]');"
        "var res=[];var seen={};"
        "for(var i=0;i<cards.length;i++){"
        "  var h=cards[i].href;"
        "  if(seen[h])continue;seen[h]=1;"
        "  var t=cards[i].innerText.trim();"
        "  if(t.length>5) res.push([h,t.substring(0,150)]);"
        "}"
        "return res.slice(0,10);"
    )
    raw = driver.execute_script(script) or []

    items = []
    for url, text in raw:
        items.append({
            "name": text.split("\n")[0][:50],
            "desc": "台南美術館 | 展覽",
            "date": "",
            "url": url,
            "source": "台南美術館",
            "area": "台南",
        })
    return {"市集展覽": items} if items else {}


# ══════════════════════════════════════════════════════
# Threads 活動帳號（通用爬蟲，不需登入）
# ══════════════════════════════════════════════════════

# 要追蹤的 Threads 帳號設定
THREADS_ACCOUNTS = [
    {
        "username": "tainan_vigor",
        "city": "台南",
        "label": "台南很有式",
        "default_cat": "吃喝玩樂",
        # 帳號簡介關鍵詞（用來跳過個人簡介塊）
        "bio_skip": ["台南活動", "台南式", "台南開幕式", "萬位粉絲"],
    },
    {
        "username": "taipei_gan_ma",
        "city": "台北",
        "label": "台北要幹嘛",
        "default_cat": "市集展覽",
        "bio_skip": ["台北活動", "整理最多", "萬位粉絲", "台北可以幹嘛"],
        "list_post": True,   # 此帳號的貼文為編號清單（一帖多活動）
    },
    {
        "username": "mynii7",
        "city": "台中",
        "label": "倪倪小日常",
        "default_cat": "市集展覽",
        "bio_skip": ["台中生活", "市集", "美食", "景點", "位粉絲"],
    },
    {
        "username": "taichungfans",
        "city": "台中",
        "label": "台中粉",
        "default_cat": "市集展覽",
        "bio_skip": ["台中粉", "萬位粉絲", "台中生活", "位粉絲"],
    },
    {
        "username": "kaohsiungfans",
        "city": "高雄",
        "label": "高雄粉",
        "default_cat": "市集展覽",
        "bio_skip": ["高雄粉", "萬位粉絲", "高雄活動", "位粉絲"],
    },
    {
        "username": "taoyuan_how",
        "city": "桃園",
        "label": "桃園號",
        "default_cat": "市集展覽",
        "bio_skip": ["桃園號", "萬位粉絲", "桃園活動", "位粉絲"],
    },
    # ── 美食＋活動帳號（智慧分類：美食→吃喝玩樂，活動→對應分類）──
    {
        "username": "ovaltine_fooddiary",
        "city": "台北",
        "label": "阿華田食記",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["食記", "阿華田", "位粉絲", "美食日記"],
    },
    {
        "username": "77.food",
        "city": "台北",
        "label": "77美食日記",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["77", "美食", "位粉絲", "連鎖"],
    },
    {
        "username": "taipeifoodie",
        "city": "台北",
        "label": "台北美食家",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["台北美食", "位粉絲", "foodie", "Taipei"],
    },
    {
        "username": "foodiedaily.tw",
        "city": "台北",
        "label": "每日美食",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["美食", "位粉絲", "foodie", "daily"],
    },
    {
        "username": "taipei_meishi",
        "city": "台北",
        "label": "台北美食",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["台北", "美食", "位粉絲"],
    },
    {
        "username": "tainan_style",
        "city": "台南",
        "label": "台南 Style",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["台南", "style", "位粉絲"],
    },
    {
        "username": "kaohsiung_style",
        "city": "高雄",
        "label": "高雄 Style",
        "default_cat": "吃喝玩樂",
        "bio_skip": ["高雄", "style", "位粉絲"],
    },
    {
        "username": "taipeistyle.tw",
        "city": "台北",
        "label": "台北 Style",
        "default_cat": "市集展覽",
        "bio_skip": ["台北", "style", "位粉絲"],
    },
    {
        "username": "kaohsiungtien",
        "city": "高雄",
        "label": "高雄天",
        "default_cat": "市集展覽",
        "bio_skip": ["高雄", "kaohsiung", "位粉絲"],
    },
]


def _parse_numbered_list(post_text: str, post_url: str, city: str, source: str,
                          date_hint: str) -> list:
    """解析編號清單貼文（如台北要幹嘛），一帖拆多筆活動"""
    items = []
    lines = post_text.split("\n")
    # 找 "1. xxx－yyy" 或 "1. xxx\n地點" 格式
    for line in lines:
        m = re.match(r"^\d+[.\、]\s*(.+?)(?:－|—|-)(.+)$", line.strip())
        if m:
            name = m.group(1).strip()[:40]
            location = m.group(2).strip()[:30]
            if len(name) < 3:
                continue
            full = name + " " + location
            if is_blocked(full):
                continue
            if any(kw in full for kw in ["市集", "展覽", "特展", "音樂祭", "藝術節"]):
                cat = "市集展覽"
            else:
                cat = classify(full) or "市集展覽"
            items.append({
                "name": name,
                "desc": f"{date_hint} | {location}" if date_hint else location,
                "date": date_hint,
                "url": post_url,
                "source": source,
                "area": city,
                "_cat": cat,
            })
    return items


def scrape_threads_account(driver, config: dict) -> dict:
    """通用 Threads 帳號爬蟲"""
    username = config["username"]
    city = config["city"]
    label = config["label"]
    url = f"https://www.threads.com/@{username}"
    is_list_post = config.get("list_post", False)
    bio_skip = config.get("bio_skip", [])
    default_cat = config.get("default_cat", "市集展覽")

    print(f"  [{label} @{username}]...")
    driver.get(url)
    time.sleep(6)
    for _ in range(4):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

    # 取貼文連結
    post_links = driver.execute_script(
        "var links=document.querySelectorAll('a[href*=\"/post/\"]');"
        "var res=[];var seen={};"
        "for(var i=0;i<links.length;i++){"
        "  var h=links[i].href.split('?')[0];"
        "  if(h.indexOf('/media')>-1) continue;"
        "  if(seen[h]) continue; seen[h]=1; res.push(h);}"
        "return res.slice(0,25);"
    ) or []

    body_text = driver.find_element("tag name", "body").text
    posts_raw = re.split(rf"\n{username}\n", body_text)
    posts_raw = [p.strip() for p in posts_raw if len(p.strip()) > 20]

    result = {cat: [] for cat in CATEGORY_MAP}
    seen_names = set()
    link_idx = 0

    for post in posts_raw[:20]:
        lines = [l.strip() for l in post.split("\n") if l.strip()]

        # 去掉開頭的時間戳行
        while lines and re.match(r"^\d+[天時分小時]|^\d{4}-\d{1,2}-\d{1,2}|^已釘選$", lines[0]):
            lines = lines[1:]
        if not lines:
            continue

        full_text = " ".join(lines)

        # 跳過帳號簡介塊
        if any(kw in full_text for kw in bio_skip):
            continue
        if is_blocked(full_text):
            continue

        # 取貼文 URL
        post_url = post_links[link_idx] if link_idx < len(post_links) else url
        link_idx += 1

        # 從貼文取日期（如 "4/10~12" 或 "(4/11)"）
        date_short = ""
        dm = re.search(r"(?<!\d)(\d{1,2})[/.](\d{1,2})", full_text)
        if dm:
            try:
                mo, dy = int(dm.group(1)), int(dm.group(2))
                if 1 <= mo <= 12 and 1 <= dy <= 31:
                    ev = datetime(TODAY.year, mo, dy)
                    if ev.date() >= TODAY.date():
                        date_short = f"{mo:02d}/{dy:02d}"
                    else:
                        continue  # 過期
            except Exception:
                pass

        # ── 清單貼文：一帖拆多活動 ──
        if is_list_post:
            numbered = _parse_numbered_list(full_text, post_url, city, label, date_short)
            if numbered:
                for item in numbered:
                    cat = item.pop("_cat")
                    if item["name"] not in seen_names:
                        seen_names.add(item["name"])
                        result[cat].append(item)
                continue  # 這篇已處理完

        # ── 一般貼文：一帖一活動 ──
        # 過濾 Threads 系統垃圾文字
        _threads_trash = [
            "掃描即可下載", "Instagram 帳號", "使用 Instagram", "忘記密碼",
            "下載應用程式", "© 20", "IG主頁", "只要留言", "留言「",
            "獲得活動", "獲得連結",
        ]
        if any(kw in full_text for kw in _threads_trash):
            continue

        bad_prefixes = ["ℹ️", "#", "@"]
        title_candidates = [
            l for l in lines[:6]
            if len(l) > 4
            and not re.match(r"^\d+$", l)
            and not re.match(r"^\d{4}-\d{1,2}-\d{1,2}", l)
            and not any(l.startswith(p) for p in bad_prefixes)
            and not any(kw in l for kw in bio_skip)
        ]
        if not title_candidates:
            continue
        title = title_candidates[0][:50]
        if title in seen_names:
            continue
        # 品質檢查：名稱至少要有中文字，且長度 >= 5
        if len(title) < 5:
            continue
        if not any("\u4e00" <= c <= "\u9fff" for c in title):
            continue
        seen_names.add(title)

        # 地點 & 時間
        loc_m = re.search(r"(?:地[點址]|📍)[  \s：:]*([^\n]{3,25})", full_text)
        location = loc_m.group(1).strip() if loc_m else ""
        time_m = re.search(r"(\d{1,2}:\d{2})\s*[—~～-]\s*(\d{1,2}:\d{2})", full_text)
        time_str = f"{time_m.group(1)}-{time_m.group(2)}" if time_m else ""

        desc_parts = [x for x in [date_short, time_str, location] if x]
        desc = " | ".join(desc_parts) if desc_parts else full_text[len(title):len(title)+60].strip()

        if any(kw in full_text for kw in ["市集", "展覽", "特展"]):
            cat = "市集展覽"
        else:
            cat = classify(full_text) or default_cat

        result[cat].append({
            "name": title,
            "desc": desc,
            "date": date_short,
            "url": post_url,
            "source": label,
            "area": city,
        })

    filtered = {k: v for k, v in result.items() if v}
    total = sum(len(v) for v in filtered.values())
    print(f"    → {total} 筆")
    return filtered


# ══════════════════════════════════════════════════════
# 來源 N：日參見 nisanmi.com（全台手作市集，純 requests）
# ══════════════════════════════════════════════════════

_NISANMI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

_NISANMI_CITY_MAP = {
    "台北": "台北", "新北": "新北", "桃園": "桃園", "新竹": "新竹",
    "台中": "台中", "台南": "台南", "高雄": "高雄", "屏東": "屏東",
    "宜蘭": "宜蘭", "花蓮": "花蓮", "嘉義": "嘉義", "南投": "南投",
    "基隆": "基隆", "苗栗": "苗栗", "彰化": "彰化", "雲林": "雲林",
    "日本": None,  # 海外場次略過
}


def scrape_nisanmi() -> dict:
    """
    從日參見 nisanmi.com 抓手作市集與展覽活動。
    純 requests，無需 Selenium。
    標題格式：【市集。城市】活動名稱 @YYYY/M/D~M/D
    """
    print("\n[日參見 nisanmi.com]...")
    result = {}

    pages = [
        ("https://www.nisanmi.com/category/news/market/", "市集展覽"),
        ("https://www.nisanmi.com/category/news/exhibition/", "市集展覽"),
    ]

    seen = set()

    for page_url, default_cat in pages:
        try:
            resp = requests.get(page_url, headers=_NISANMI_HEADERS, timeout=15)
            html = resp.text
        except Exception as e:
            print(f"  連線失敗 {page_url}: {e}")
            continue

        # 抓所有文章連結 + 標題（WordPress 典型結構）
        # <a href="https://www.nisanmi.com/..." rel="bookmark">標題</a>
        links = re.findall(
            r'<a\s+href="(https://www\.nisanmi\.com/[^"]{10,})"[^>]*rel="bookmark"[^>]*>\s*([^<]{5,120})\s*</a>',
            html
        )
        # 備用：<h2 ...><a href="...">標題</a>
        if not links:
            links = re.findall(
                r'href="(https://www\.nisanmi\.com/[^"?#]{10,})"[^>]*>\s*'
                r'(【[^】]{2,20}】[^<]{5,80})\s*</a>',
                html
            )

        for url, raw_title in links:
            title = re.sub(r"\s+", " ", raw_title).strip()
            if not title or url in seen:
                continue
            seen.add(url)

            # 解析城市：【市集。高雄】或【展覽。台南】
            city_m = re.search(r'【[^。。]*[。．]([^】]{2,4})】', title)
            if not city_m:
                continue
            city_raw = city_m.group(1).strip()
            city = _NISANMI_CITY_MAP.get(city_raw)
            if city is None:  # 海外或無對應城市
                continue

            # 解析活動名稱（去掉前綴和日期後綴）
            name = re.sub(r'^【[^】]+】\s*', '', title)  # 去前綴
            name = re.sub(r'\s*@\d{4}[/\-]\d.*$', '', name).strip()  # 去日期後綴
            if len(name) < 3:
                name = title[:50]

            # 解析日期：@YYYY/M/D 或 @YYYY/M/D~M/D 或 @YYYY/M/D~D
            date_short = ""
            date_m = re.search(r'@(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', title)
            if date_m:
                try:
                    y, mo, dy = int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))
                    ev_date = datetime(y, mo, dy)
                    # 結束日期
                    end_m = re.search(r'~(\d{1,2})[/\-](\d{1,2})', title)
                    if end_m:
                        end_mo, end_dy = int(end_m.group(1)), int(end_m.group(2))
                        end_date = datetime(y, end_mo, end_dy)
                    else:
                        end_day_m = re.search(r'~(\d{1,2})$', title.split('@')[-1])
                        end_date = datetime(y, mo, int(end_day_m.group(1))) if end_day_m else ev_date
                    # 活動已完全結束才略過
                    if end_date.date() < TODAY.date():
                        continue
                    date_short = f"{mo:02d}/{dy:02d}"
                except Exception:
                    pass

            if is_blocked(name):
                continue

            if city not in result:
                result[city] = {cat: [] for cat in CATEGORY_MAP}

            cat = default_cat
            result[city][cat].append({
                "name": name[:55],
                "desc": date_short,
                "date": date_short,
                "url": url,
                "source": "日參見",
                "area": city,
            })

    for city in result:
        result[city] = {k: v for k, v in result[city].items() if v}

    total = sum(len(e) for cats in result.values() for e in cats.values())
    print(f"  → 合計 {total} 筆（{', '.join(f'{c}:{sum(len(v) for v in d.values())}' for c, d in result.items())}）")
    return result


# ══════════════════════════════════════════════════════
# 來源 N+1：好好手感微笑市集 sogoodmarket.com（全台，純 requests）
# ══════════════════════════════════════════════════════

_SOGOOD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

_SOGOOD_CITIES = ["台北", "新北", "桃園", "新竹", "台中", "台南", "高雄",
                  "屏東", "宜蘭", "花蓮", "嘉義", "南投", "基隆", "苗栗", "彰化"]


def scrape_sogoodmarket() -> dict:
    """
    從好好手感微笑市集 sogoodmarket.com 抓市集活動。
    純 requests，列表頁已含日期和地點。
    摘要格式：◢ 日期：M/D㊅ -M/D㊐  ◢ 地點：城市地點名稱
    """
    print("\n[好好市集 sogoodmarket.com]...")
    result = {}

    try:
        resp = requests.get(
            "https://www.sogoodmarket.com/category/market/",
            headers=_SOGOOD_HEADERS, timeout=15
        )
        html = resp.text
    except Exception as e:
        print(f"  連線失敗: {e}")
        return {}

    # 切分文章區塊：以每個 <article 或 entry 為單位
    # 先抓所有連結 + 其後跟著的摘要文字
    # 格式：<a href="URL">標題</a> ... ◢ 日期：... ◢ 地點：...
    # 先用連結切塊
    blocks = re.split(r'(?=<a\s+href="https://www\.sogoodmarket\.com/[^"]{10,}")', html)

    seen = set()

    for block in blocks:
        # 抓文章連結 + 標題
        link_m = re.match(
            r'<a\s+href="(https://www\.sogoodmarket\.com/[^"?#]{10,})"[^>]*>\s*([^<]{4,80})\s*</a>',
            block
        )
        if not link_m:
            continue
        url = link_m.group(1)
        title = re.sub(r"\s+", " ", link_m.group(2)).strip()
        if not title or len(title) < 4 or url in seen:
            continue
        # 跳過非活動連結（導航、頁碼等）
        if any(w in title for w in ["Read more", "閱讀更多", "older", "newer", "←", "→", "分頁"]):
            continue
        seen.add(url)

        # 抓日期：◢ 日期：M/D...
        date_m = re.search(r'◢\s*日期[：:]\s*(\d{1,2})[/月](\d{1,2})', block)
        if not date_m:
            continue
        mo, dy = int(date_m.group(1)), int(date_m.group(2))

        # 抓結束日期（判斷是否過期）
        end_m = re.search(
            r'◢\s*日期[：:][^\n◢]{0,30}[-~～]\s*(\d{1,2})[/月](\d{1,2})',
            block
        )
        try:
            start_date = datetime(TODAY.year, mo, dy)
            if end_m:
                end_date = datetime(TODAY.year, int(end_m.group(1)), int(end_m.group(2)))
            else:
                end_date = start_date
            if end_date.date() < TODAY.date():
                continue
        except Exception:
            continue

        date_short = f"{mo:02d}/{dy:02d}"

        # 抓城市：◢ 地點：城市... 或 ◢ 地址：城市...
        city = ""
        for field in ["地點", "地址"]:
            loc_m = re.search(rf'◢\s*{field}[：:]\s*([^\n<◢]{{3,40}})', block)
            if loc_m:
                loc_text = loc_m.group(1).strip()
                for c in _SOGOOD_CITIES:
                    if loc_text.startswith(c) or c in loc_text[:6]:
                        city = c
                        break
            if city:
                break

        if not city:
            continue

        if is_blocked(title):
            continue

        if city not in result:
            result[city] = {cat: [] for cat in CATEGORY_MAP}

        result[city]["市集展覽"].append({
            "name": title[:55],
            "desc": date_short,
            "date": date_short,
            "url": url,
            "source": "好好市集",
            "area": city,
        })

    for city in result:
        result[city] = {k: v for k, v in result[city].items() if v}

    total = sum(len(e) for cats in result.values() for e in cats.values())
    print(f"  → 合計 {total} 筆（{', '.join(f'{c}:{sum(len(v) for v in d.values())}' for c, d in result.items())}）")
    return result


# ══════════════════════════════════════════════════════
# 來源：熱血系列 RSS（熱血台中 / 熱血台南，純 requests）
# ══════════════════════════════════════════════════════

_HOTBLOOD_SITES = [
    {"name": "熱血台中", "feed": "https://taiwan17go.com/feed/", "city": "台中"},
    {"name": "熱血台南", "feed": "https://decing.tw/feed/", "city": "台南"},
]

# decing.tw 台南周末活動分類頁（直接抓最新整理文）
_DECING_ACTIVITY_CAT = "https://decing.tw/category/%e5%8f%b0%e5%8d%97%e5%91%a8%e6%9c%ab%e6%b4%bb%e5%8b%95/"

# RSS 分類標籤 → 我們的分類
_HOTBLOOD_CAT_MAP = {
    "美食": "吃喝玩樂", "小吃": "吃喝玩樂", "餐廳": "吃喝玩樂",
    "早餐": "吃喝玩樂", "午餐": "吃喝玩樂", "甜點": "吃喝玩樂",
    "吃到飽": "吃喝玩樂", "居酒屋": "吃喝玩樂", "咖啡": "文青咖啡",
    "活動": "市集展覽", "市集": "市集展覽", "展覽": "市集展覽",
    "景點": "戶外踏青", "免費景點": "戶外踏青", "旅遊": "戶外踏青",
    "親子": "親子同樂", "音樂": "表演音樂", "演出": "表演音樂",
}


def _parse_hotblood_roundup(url: str, city: str, post_url: str, site_name: str) -> list:
    """爬「整理」類文章，解析 h2 標題為個別活動"""
    try:
        resp = requests.get(url, headers=_STROLL_HEADERS, timeout=15)
        html = resp.text
    except Exception as e:
        print(f"    無法取得文章頁面: {e}")
        return []

    # 找所有 h2 標題（活動名稱）
    h2_titles = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.DOTALL)
    # 找所有段落（抓日期/地點資訊）
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)

    # 清除 HTML tag
    def strip_html(s):
        return re.sub(r"<[^>]+>", "", s).strip()

    events = []
    para_idx = 0
    for h2_raw in h2_titles:
        name = strip_html(h2_raw).strip()
        # 去掉編號前綴（1. 2. 等）
        name = re.sub(r"^\d+[.\s]+", "", name).strip()
        # 去掉廣告/商品連結（有網址的通常是業配）
        if not name or len(name) < 3 or is_blocked(name):
            continue
        if re.search(r"https?://|廣告|業配|贊助|快閃團|YT|Youtube|YouTube|影片|訂閱|按讚|追蹤", name):
            continue
        # 必須含有中文字
        if not re.search(r"[\u4e00-\u9fff]", name):
            continue

        # 從後續段落抓日期
        date_short = ""
        desc = ""
        for p in paragraphs[para_idx:para_idx + 8]:
            text = strip_html(p)
            if not date_short:
                dm = re.search(r"(\d{1,2})[/.](\d{1,2})", text)
                if dm:
                    try:
                        mo, dy = int(dm.group(1)), int(dm.group(2))
                        if 1 <= mo <= 12 and 1 <= dy <= 31:
                            date_short = f"{mo:02d}/{dy:02d}"
                    except Exception:
                        pass
            if not desc and len(text) > 5:
                desc = text[:40]

        our_cat = classify(name)
        if not our_cat:
            our_cat = "市集展覽"  # 整理文預設是活動

        events.append({
            "name": name[:50],
            "desc": date_short or desc,
            "date": date_short,
            "url": post_url,  # 連到整篇文章
            "source": site_name,
            "area": city,
            "cat": our_cat,
        })

    print(f"    └ 解析到 {len(events)} 個活動")
    return events


def scrape_hotblood_rss() -> dict:
    """從熱血系列 RSS 抓取美食＋活動資訊（純 requests）
    「整理」類文章會進入頁面解析個別活動。
    """
    print("\n[熱血系列 RSS]...")
    result = {}
    total = 0

    for site in _HOTBLOOD_SITES:
        try:
            resp = requests.get(site["feed"], headers=_STROLL_HEADERS, timeout=15)
            html = resp.text
        except Exception as e:
            print(f"  {site['name']}: 連線失敗 {e}")
            continue

        items = re.findall(r"<item>(.*?)</item>", html, re.DOTALL)
        city = site["city"]
        count = 0

        for item in items:
            # 解析標題
            title_m = re.search(r"<title>(.*?)</title>", item)
            if not title_m:
                continue
            title = title_m.group(1).replace("<![CDATA[", "").replace("]]>", "").strip()
            if not title or len(title) < 5:
                continue

            # 解析連結
            link_m = re.search(r"<link>\s*(https?://[^\s<]+)\s*</link>", item)
            url = link_m.group(1) if link_m else ""

            # 解析分類標籤
            cats = re.findall(r"<category><!\[CDATA\[(.*?)\]\]></category>", item)

            # 解析描述
            desc_m = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>", item, re.DOTALL)
            desc_raw = ""
            if desc_m:
                desc_raw = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip()[:60]

            if is_blocked(title):
                continue

            # ── 「整理」類文章：進頁面解析個別活動 ──
            clean_title = re.sub(r"^【[^】]+】\s*", "", title).strip()
            if any(kw in clean_title for kw in ["活動整理", "周末活動", "假日活動", "週末活動"]):
                if url:
                    print(f"  解析整理文: {clean_title[:40]}")
                    sub_events = _parse_hotblood_roundup(url, city, url, site["name"])
                    for ev in sub_events:
                        cat = ev.pop("cat")
                        if city not in result:
                            result[city] = {c: [] for c in CATEGORY_MAP}
                            result[city]["吃喝玩樂"] = []
                        if cat not in result[city]:
                            result[city][cat] = []
                        if len(result[city][cat]) < 15:
                            existing = {e["name"] for e in result[city][cat]}
                            if ev["name"] not in existing:
                                result[city][cat].append(ev)
                                count += 1
                continue  # 不把整理文本身加入

            # ── 一般文章：直接用標題 ──
            # 智慧分類：從 RSS 標籤判斷
            our_cat = None
            for rss_cat in cats:
                for kw, mapped in _HOTBLOOD_CAT_MAP.items():
                    if kw in rss_cat:
                        our_cat = mapped
                        break
                if our_cat:
                    break
            if not our_cat:
                our_cat = classify(title + " " + " ".join(cats))
            if not our_cat:
                our_cat = "吃喝玩樂"

            # 從標題抓日期
            date_short = ""
            dm = re.search(r"(\d{1,2})[/.](\d{1,2})", title)
            if dm:
                try:
                    mo, dy = int(dm.group(1)), int(dm.group(2))
                    if 1 <= mo <= 12 and 1 <= dy <= 31:
                        date_short = f"{mo:02d}/{dy:02d}"
                except Exception:
                    pass

            if city not in result:
                result[city] = {c: [] for c in CATEGORY_MAP}
                result[city]["吃喝玩樂"] = []
            if our_cat not in result[city]:
                result[city][our_cat] = []

            if len(result[city][our_cat]) < 15:
                existing = {e["name"] for e in result[city][our_cat]}
                if clean_title[:50] not in existing:
                    result[city][our_cat].append({
                        "name": clean_title[:50],
                        "desc": date_short or desc_raw[:40],
                        "date": date_short,
                        "url": url,
                        "source": site["name"],
                        "area": city,
                    })
                    count += 1

        if count:
            print(f"  {site['name']}: {count} 筆")
            total += count

    # ── 額外：爬 decing.tw 台南周末活動分類頁最新 2 篇 ──
    try:
        print("  解析 decing.tw 台南周末活動分類頁...")
        resp = requests.get(_DECING_ACTIVITY_CAT, headers=_STROLL_HEADERS, timeout=15)
        post_urls = re.findall(r'href="(https://decing\.tw/[^"]+?)"[^>]*>【台南活動】', resp.text)
        # 去重，只取最新 2 篇
        seen_urls = set()
        post_urls_clean = []
        for u in post_urls:
            if u not in seen_urls:
                seen_urls.add(u)
                post_urls_clean.append(u)
        for post_url in post_urls_clean[:2]:
            print(f"  解析活動整理: {post_url}")
            sub_events = _parse_hotblood_roundup(post_url, "台南", post_url, "熱血台南")
            city = "台南"
            for ev in sub_events:
                cat = ev.pop("cat")
                if city not in result:
                    result[city] = {c: [] for c in CATEGORY_MAP}
                    result[city]["吃喝玩樂"] = []
                if cat not in result[city]:
                    result[city][cat] = []
                if len(result[city][cat]) < 15:
                    existing = {e["name"] for e in result[city][cat]}
                    if ev["name"] not in existing:
                        result[city][cat].append(ev)
                        total += 1
    except Exception as e:
        print(f"  decing.tw 分類頁失敗: {e}")

    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    print(f"  → 合計 {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源：文化部全國藝文活動 JSON API（全台，純 requests）
# ══════════════════════════════════════════════════════

_MOC_CITY_KEYWORDS = [
    "台北", "新北", "桃園", "新竹", "苗栗", "台中", "彰化", "南投",
    "雲林", "嘉義", "台南", "高雄", "屏東", "宜蘭", "花蓮", "台東",
    "澎湖", "金門", "連江", "基隆",
]
# 文化部 category → 我們的分類
_MOC_CAT_MAP = {
    "1": "表演音樂",   # 音樂
    "2": "表演音樂",   # 戲劇
    "3": "表演音樂",   # 舞蹈
    "4": "親子同樂",   # 親子
    "5": "表演音樂",   # 獨立音樂
    "6": "市集展覽",   # 展覽
    "7": "文青咖啡",   # 講座
    "8": "文青咖啡",   # 電影
    "11": "表演音樂",  # 綜藝
    "15": "市集展覽",  # 其他
    "17": "市集展覽",  # 競賽
}


def scrape_moc_api() -> dict:
    """
    從文化部全國藝文活動 JSON API 抓取活動。
    純 requests，無需 Selenium。API 需逐 category 查詢。
    """
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print("\n[文化部全國藝文活動 API]...")
    result = {}
    total_fetched = 0

    for moc_cat, our_cat in _MOC_CAT_MAP.items():
        url = f"https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category={moc_cat}"
        try:
            req = _ur.Request(url, headers=_STROLL_HEADERS)
            with _ur.urlopen(req, timeout=20, context=ctx) as r:
                data = json.loads(r.read())
        except Exception as e:
            print(f"  category {moc_cat}: 失敗 {e}")
            continue

        if not data:
            continue

        count = 0
        for ev in data:
            title = ev.get("title", "").strip()
            if not title or len(title) < 4 or is_blocked(title):
                continue

            for si in ev.get("showInfo", []):
                location = si.get("location", "")
                loc_name = si.get("locationName", "")
                time_str = si.get("time", "")
                end_str = si.get("endTime", "")

                # 解析城市
                city = ""
                # 先從「臺」轉「台」
                loc_norm = location.replace("臺", "台")
                for c in _MOC_CITY_KEYWORDS:
                    if c in loc_norm:
                        city = c
                        break
                if not city:
                    continue

                # 解析日期，過濾已過期
                date_short = ""
                if time_str:
                    dm = re.match(r"(\d{4})/(\d{2})/(\d{2})", time_str)
                    if dm:
                        try:
                            ev_date = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                            # 用 endTime 判斷是否過期
                            if end_str:
                                em = re.match(r"(\d{4})/(\d{2})/(\d{2})", end_str)
                                if em:
                                    end_date = datetime(int(em.group(1)), int(em.group(2)), int(em.group(3)))
                                    if end_date.date() < TODAY.date():
                                        continue
                            elif ev_date.date() < TODAY.date():
                                continue
                            date_short = f"{int(dm.group(2)):02d}/{int(dm.group(3)):02d}"
                        except Exception:
                            pass

                # 描述
                desc_parts = [x for x in [date_short, loc_name[:25]] if x]
                desc = " | ".join(desc_parts) if desc_parts else loc_name[:30]

                if city not in result:
                    result[city] = {cat: [] for cat in CATEGORY_MAP}
                if our_cat not in result[city]:
                    result[city][our_cat] = []

                # 每城市每分類最多 8 筆
                if len(result[city][our_cat]) < 8:
                    # 去重
                    existing = {e["name"] for e in result[city][our_cat]}
                    if title[:50] not in existing:
                        result[city][our_cat].append({
                            "name": title[:50],
                            "desc": desc,
                            "date": date_short,
                            "url": "",  # 文化部 API 沒有活動頁面 URL
                            "source": "文化部",
                            "area": city,
                        })
                        count += 1
                break  # 只取第一個 showInfo

        if count:
            total_fetched += count

    # 清除空分類
    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    for city, cats in sorted(result.items()):
        city_total = sum(len(v) for v in cats.values())
        print(f"  {city}: {city_total} 筆")
    print(f"  → 合計 {total_fetched} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源：tainanoutlook 活動大集合（全台分站，純 requests）
# ══════════════════════════════════════════════════════

_OUTLOOK_SITES = {
    "tpe": {"url": "https://tpe.tainanoutlook.com/", "cities": ["台北", "新北", "基隆"]},
    "tjm": {"url": "https://tjm.tainanoutlook.com/", "cities": ["桃園", "新竹", "苗栗"]},
    "txg": {"url": "https://txg.tainanoutlook.com/", "cities": ["台中", "彰化", "南投"]},
    "chiayi": {"url": "https://chiayi.tainanoutlook.com/", "cities": ["雲林", "嘉義"]},
    "khh": {"url": "https://khh.tainanoutlook.com/", "cities": ["高雄"]},
    "pthg": {"url": "https://pthg.tainanoutlook.com/", "cities": ["屏東"]},
}
_OUTLOOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def scrape_tainanoutlook() -> dict:
    """
    從 tainanoutlook 系列子站抓活動。
    純 requests，所有子站共用同一套 HTML 結構。
    """
    print("\n[tainanoutlook 活動大集合]...")
    result = {}
    total = 0

    for site_key, site_info in _OUTLOOK_SITES.items():
        base_url = site_info["url"]
        site_cities = site_info["cities"]
        try:
            resp = requests.get(base_url, headers=_OUTLOOK_HEADERS, timeout=15)
            html = resp.text
        except Exception as e:
            print(f"  {site_key}: 連線失敗 {e}")
            continue

        # 抓文章區塊：<article> 或 <a href="..."> + 標題
        # 常見格式：<a href="URL">標題</a> + 日期/地點文字
        articles = re.findall(
            r'<a\s+href="(https?://[^"]*tainanoutlook\.com/[^"]{10,})"[^>]*>\s*([^<]{5,100})\s*</a>',
            html
        )

        seen = set()
        site_count = 0

        for url, raw_title in articles:
            title = re.sub(r"\s+", " ", raw_title).strip()
            if not title or len(title) < 5 or url in seen:
                continue
            if any(skip in title for skip in ["Read more", "閱讀更多", "留言", "分享", "搜尋"]):
                continue
            seen.add(url)

            if is_blocked(title):
                continue

            # 從標題或 URL 判斷城市
            city = ""
            for c in site_cities + _MOC_CITY_KEYWORDS:
                if c in title:
                    city = c
                    break
            if not city:
                city = site_cities[0]  # 預設用該站第一個城市

            # 從標題抓日期
            date_short = ""
            dm = re.search(r"(\d{1,2})[/.](\d{1,2})", title)
            if dm:
                try:
                    mo, dy = int(dm.group(1)), int(dm.group(2))
                    if 1 <= mo <= 12 and 1 <= dy <= 31:
                        ev = datetime(TODAY.year, mo, dy)
                        if ev.date() < TODAY.date():
                            continue
                        date_short = f"{mo:02d}/{dy:02d}"
                except Exception:
                    pass

            # 分類
            cat = classify(title) or "市集展覽"

            if city not in result:
                result[city] = {c: [] for c in CATEGORY_MAP}
            if cat not in result[city]:
                result[city][cat] = []

            if len(result[city][cat]) < 8:
                existing = {e["name"] for e in result[city][cat]}
                name = re.sub(r'^【[^】]+】\s*', '', title).strip()[:55]
                if name not in existing:
                    result[city][cat].append({
                        "name": name,
                        "desc": date_short or "",
                        "date": date_short,
                        "url": url,
                        "source": "tainanoutlook",
                        "area": city,
                    })
                    site_count += 1

        if site_count:
            print(f"  {site_key} ({','.join(site_cities)}): {site_count} 筆")
            total += site_count

    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    print(f"  → 合計 {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源：台北旅遊網 Open API（台北，純 requests）
# ══════════════════════════════════════════════════════

_TAIPEI_TOURISM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.travel.taipei/",
}
# 台北旅遊網活動分類 ID → 我們的分類
_TAIPEI_CAT_MAP = {
    "131": "市集展覽",   # 節慶活動
    "132": "市集展覽",   # 展覽
    "133": "表演音樂",   # 演出
    "134": "戶外踏青",   # 戶外活動
    "135": "親子同樂",   # 親子活動
    "136": "吃喝玩樂",   # 美食活動
}


def scrape_taipei_tourism() -> dict:
    """
    從台北旅遊網 Open API 抓台北近期活動。
    純 requests，無需 Selenium。
    回傳 {"台北": {"市集展覽": [...], ...}}
    """
    import ssl, urllib.request as _ur2
    import json as _json
    print("\n[台北旅遊網 Open API]...")
    result = {"台北": {cat: [] for cat in CATEGORY_MAP}}
    total = 0

    # 嘗試各分類 ID
    for cat_id, our_cat in _TAIPEI_CAT_MAP.items():
        url = (
            f"https://www.travel.taipei/open-api/zh-tw/Events"
            f"?categoryIds={cat_id}&top=20&skip=0"
        )
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = _ur2.Request(url, headers=_TAIPEI_TOURISM_HEADERS)
            with _ur2.urlopen(req, timeout=12, context=ctx) as r:
                raw = r.read().decode("utf-8", errors="ignore")
            data = _json.loads(raw)
        except Exception as e:
            print(f"  分類 {cat_id}: 無法取得 ({e})")
            continue

        # API 回傳格式：{"data": [...], "total": N} 或直接 [...]
        events_raw = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(events_raw, list):
            continue

        for ev in events_raw:
            title = (ev.get("Name") or ev.get("name") or ev.get("title") or "").strip()
            if not title or len(title) < 3:
                continue
            if is_blocked(title):
                continue

            # 日期：StartTime / start_date / startDate
            date_raw = (
                ev.get("StartTime") or ev.get("start_date") or
                ev.get("startDate") or ev.get("EndTime") or ""
            )
            date_short = ""
            dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(date_raw))
            if dm:
                try:
                    ev_date = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                    if ev_date.date() < TODAY.date():
                        continue
                    date_short = f"{int(dm.group(2)):02d}/{int(dm.group(3)):02d}"
                except Exception:
                    pass

            desc_raw = (ev.get("Description") or ev.get("description") or
                        ev.get("desc") or "").strip()
            desc = desc_raw[:60] if desc_raw else ""
            location = (ev.get("Location") or ev.get("location") or
                        ev.get("Address") or "台北").strip()[:30]

            desc_text = f"{date_short} | {location}" if date_short else location

            # 分類（先用 API 分類，再靠關鍵詞補強）
            classify_text = title + " " + desc_raw
            cat = classify(classify_text) or our_cat

            # 活動 URL
            ev_id = ev.get("Id") or ev.get("id") or ""
            ev_url = (
                ev.get("Url") or ev.get("url") or
                (f"https://www.travel.taipei/zh-tw/event/detail/{ev_id}" if ev_id else
                 "https://www.travel.taipei/zh-tw/event")
            )

            entry = {
                "name": title[:50],
                "desc": desc_text,
                "date": date_short,
                "url": ev_url,
                "source": "台北旅遊網",
                "area": "台北",
            }
            if cat not in result["台北"]:
                result["台北"][cat] = []
            if len(result["台北"][cat]) < 8:
                result["台北"][cat].append(entry)
                total += 1

    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    print(f"  台北: {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 來源：健行筆記 + 運動筆記（戶外/運動活動，純 requests）
# ══════════════════════════════════════════════════════

_HIKING_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://hiking.biji.co/",
}

_HIKING_CITY_KEYWORDS = {
    "台北": ["台北", "北市", "北投", "木柵", "士林", "文山", "陽明山"],
    "新北": ["新北", "淡水", "三峽", "烏來", "平溪", "瑞芳", "汐止"],
    "台中": ["台中", "中市", "梧棲", "大坑", "霧峰", "太平"],
    "台南": ["台南", "南市", "關廟", "玉井", "左鎮"],
    "高雄": ["高雄", "旗山", "美濃", "茂林", "桃源"],
    "宜蘭": ["宜蘭", "礁溪", "三星", "大同", "南澳"],
    "花蓮": ["花蓮", "秀林", "鳳林", "玉里", "壽豐"],
    "台東": ["台東", "鹿野", "池上", "關山", "綠島"],
    "南投": ["南投", "埔里", "日月潭", "清境", "仁愛", "信義"],
    "嘉義": ["嘉義", "阿里山", "梅山", "竹崎"],
    "新竹": ["新竹", "尖石", "五峰", "橫山"],
    "苗栗": ["苗栗", "三義", "泰安", "獅潭"],
    "桃園": ["桃園", "復興", "石門"],
}


def _guess_hiking_city(text: str) -> str:
    """從活動標題/描述猜測城市"""
    for city, kws in _HIKING_CITY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return city
    return ""


def scrape_hiking() -> dict:
    """
    從健行筆記(hiking.biji.co)和運動筆記(running.biji.co)抓戶外/運動活動。
    純 requests，HTML server-side rendered。
    回傳 {city: {"戶外踏青": [...], ...}}
    """
    import ssl, urllib.request as _ur3
    print("\n[健行筆記 + 運動筆記]...")
    result = {}
    total = 0

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    def _fetch(url):
        req = _ur3.Request(url, headers=_HIKING_HEADERS)
        try:
            with _ur3.urlopen(req, timeout=15, context=ctx) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  [ERROR] {url}: {e}")
            return ""

    # ── 1. 健行筆記活動列表
    hiking_pages = [
        "https://hiking.biji.co/index.php?q=news&act=list&type=activity",
        "https://hiking.biji.co/index.php?q=news&act=list&type=activity&page=2",
    ]
    for page_url in hiking_pages:
        html = _fetch(page_url)
        if not html:
            continue

        # 找活動連結和標題（格式：<a href="/index.php?q=news&id=...">標題</a>）
        entries = re.findall(
            r'href="(/index\.php\?q=news&(?:act=info&)?id=\d+[^"]*)"[^>]*>\s*([^<]{5,80})\s*</a>',
            html
        )
        for path, title in entries:
            title = re.sub(r"\s+", " ", title).strip()
            if not title or len(title) < 4:
                continue
            if is_blocked(title):
                continue

            # 找日期（標題附近通常有 "MM/DD" 或 "YYYY-MM-DD"）
            context_idx = html.find(path)
            nearby = html[max(0, context_idx - 100):context_idx + 400]
            date_short = ""
            dm = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", nearby)
            if dm:
                try:
                    ev_date = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                    if ev_date.date() < TODAY.date():
                        continue
                    date_short = f"{int(dm.group(2)):02d}/{int(dm.group(3)):02d}"
                except Exception:
                    pass
            else:
                dm2 = re.search(r"(\d{1,2})/(\d{1,2})", nearby)
                if dm2:
                    try:
                        mo, dy = int(dm2.group(1)), int(dm2.group(2))
                        ev_date = datetime(TODAY.year, mo, dy)
                        if ev_date.date() < TODAY.date():
                            continue
                        date_short = f"{mo:02d}/{dy:02d}"
                    except Exception:
                        pass

            city = _guess_hiking_city(title)
            if not city:
                city = "全台"
            ev_url = "https://hiking.biji.co" + path

            cat = classify(title) or "戶外踏青"

            entry = {
                "name": title[:50],
                "desc": date_short if date_short else "健行筆記活動",
                "date": date_short,
                "url": ev_url,
                "source": "健行筆記",
                "area": city,
            }
            cities = [city] if city != "全台" else list(_HIKING_CITY_KEYWORDS.keys())[:5]
            for c in cities:
                if c not in result:
                    result[c] = {cat2: [] for cat2 in CATEGORY_MAP}
                if cat not in result[c]:
                    result[c][cat] = []
                existing = {e["name"] for e in result[c][cat]}
                if entry["name"] not in existing and len(result[c][cat]) < 6:
                    result[c][cat].append(entry)
                    total += 1

    # ── 2. 運動筆記活動列表（races/events）
    sports_pages = [
        "https://running.biji.co/index.php?q=event&act=index",
    ]
    for page_url in sports_pages:
        html = _fetch(page_url)
        if not html:
            continue

        # 找賽事連結：href="/index.php?q=event&act=detail&id=..."
        entries = re.findall(
            r'href="(/index\.php\?q=event&act=detail&id=\d+[^"]*)"[^>]*>\s*([^<]{5,80})\s*</a>',
            html
        )
        for path, title in entries:
            title = re.sub(r"\s+", " ", title).strip()
            if not title or len(title) < 4:
                continue
            if is_blocked(title):
                continue

            context_idx = html.find(path)
            nearby = html[max(0, context_idx - 100):context_idx + 400]
            date_short = ""
            dm = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", nearby)
            if dm:
                try:
                    ev_date = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                    if ev_date.date() < TODAY.date():
                        continue
                    date_short = f"{int(dm.group(2)):02d}/{int(dm.group(3)):02d}"
                except Exception:
                    pass

            city = _guess_hiking_city(title)
            if not city:
                city = "全台"
            ev_url = "https://running.biji.co" + path

            # 運動類型分類
            if any(kw in title for kw in ["登山", "健行", "步道", "縱走", "攀岩"]):
                cat = "戶外踏青"
            else:
                cat = "運動健身"

            entry = {
                "name": title[:50],
                "desc": date_short if date_short else "運動筆記賽事",
                "date": date_short,
                "url": ev_url,
                "source": "運動筆記",
                "area": city,
            }
            cities = [city] if city != "全台" else list(_HIKING_CITY_KEYWORDS.keys())[:5]
            for c in cities:
                if c not in result:
                    result[c] = {cat2: [] for cat2 in CATEGORY_MAP}
                if cat not in result[c]:
                    result[c][cat] = []
                existing = {e["name"] for e in result[c][cat]}
                if entry["name"] not in existing and len(result[c][cat]) < 6:
                    result[c][cat].append(entry)
                    total += 1

    result = {
        city: {k: v for k, v in cats.items() if v}
        for city, cats in result.items()
        if any(cats.values())
    }
    for city, cats in result.items():
        city_total = sum(len(v) for v in cats.values())
        if city_total:
            print(f"  {city}: {city_total} 筆")
    print(f"  → 健行/運動 合計 {total} 筆")
    return result


# ══════════════════════════════════════════════════════
# 合併多來源資料
# ══════════════════════════════════════════════════════

def merge_city_data(*dicts) -> dict:
    merged = {cat: [] for cat in CATEGORY_MAP}
    for d in dicts:
        for cat, events in d.items():
            if cat in merged:
                # 去重（依名稱）
                existing = {e["name"] for e in merged[cat]}
                for e in events:
                    if e["name"] not in existing:
                        merged[cat].append(e)
                        existing.add(e["name"])
    return {k: v for k, v in merged.items() if v}


# ══════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("生活超級助理 — 全來源活動爬蟲")
    print(f"抓取 {START_DATE} 之後的活動")
    print("=" * 55)

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": [
            "漫步時光", "小藝行事曆(yii.tw)", "華山1914",
            "Accupass", "Threads(台南很有式/台北要幹嘛/倪倪小日常/台中粉/高雄粉/桃園號/高雄天)",
            "KKTIX", "駁二", "台南文化局", "台南美術館",
            "日參見(nisanmi.com)", "好好市集(sogoodmarket.com)",
            "文化部全國藝文活動", "tainanoutlook活動大集合",
            "台北旅遊網OpenAPI", "健行筆記", "運動筆記",
            "熱血台中(taiwan17go)", "熱血台南(decing.tw)",
            "Threads美食(阿華田/77食/台北美食/每日美食/台南Style/高雄Style/台北Style)",
        ],
        "events": {}
    }

    # ── 漫步時光（純 requests，最快）
    print("\n【漫步時光 — 全台活動（純 requests）】")
    try:
        stroll_data = scrape_strolltimes()
        for city, cats in stroll_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 漫步時光: {e}")

    # ── 小藝行事曆 yii.tw（純 requests）
    print("\n【小藝行事曆 yii.tw — 全台藝文月曆（純 requests）】")
    try:
        yii_data = scrape_yii()
        for city, cats in yii_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] yii.tw: {e}")

    # ── 日參見 nisanmi.com（純 requests）
    print("\n【日參見 nisanmi.com — 全台手作市集（純 requests）】")
    try:
        nisanmi_data = scrape_nisanmi()
        for city, cats in nisanmi_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 日參見: {e}")

    # ── 好好市集 sogoodmarket.com（純 requests）
    print("\n【好好市集 sogoodmarket.com — 全台手作市集（純 requests）】")
    try:
        sogood_data = scrape_sogoodmarket()
        for city, cats in sogood_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 好好市集: {e}")

    # ── 熱血系列 RSS（純 requests）
    print("\n【熱血台中 / 熱血台南 — RSS（純 requests）】")
    try:
        hotblood_data = scrape_hotblood_rss()
        for city, cats in hotblood_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 熱血RSS: {e}")

    # ── 文化部全國藝文活動 API（純 requests）
    print("\n【文化部全國藝文活動 — JSON API（純 requests）】")
    try:
        moc_data = scrape_moc_api()
        for city, cats in moc_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 文化部: {e}")

    # ── tainanoutlook 活動大集合（純 requests）
    print("\n【tainanoutlook 活動大集合 — 全台分站（純 requests）】")
    try:
        outlook_data = scrape_tainanoutlook()
        for city, cats in outlook_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] tainanoutlook: {e}")

    # ── 台北旅遊網 Open API（純 requests）
    print("\n【台北旅遊網 Open API — 台北活動（純 requests）】")
    try:
        taipei_tour_data = scrape_taipei_tourism()
        for city, cats in taipei_tour_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 台北旅遊網: {e}")

    # ── 健行筆記 + 運動筆記（純 requests）
    print("\n【健行筆記 + 運動筆記 — 戶外/運動（純 requests）】")
    try:
        hiking_data = scrape_hiking()
        for city, cats in hiking_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 健行/運動: {e}")

    # ── 華山1914（純 requests）
    print("\n【華山1914 — 台北活動（純 requests）】")
    try:
        hua_data = scrape_huashan()
        for city, cats in hua_data.items():
            if city not in result["events"]:
                result["events"][city] = {}
            result["events"][city] = merge_city_data(
                result["events"].get(city, {}), cats
            )
    except Exception as e:
        print(f"  [ERROR] 華山1914: {e}")

    # ── Accupass + Threads（headless）
    print("\n【Accupass + Threads — headless Chrome】")
    headless = make_headless_driver()
    try:
        for city in CITIES:
            try:
                data = scrape_accupass(headless, city)
                # 合併而非取代（保留漫步時光等來源的資料）
                result["events"][city] = merge_city_data(
                    result["events"].get(city, {}), data
                )
                total = sum(len(v) for v in data.values())
                print(f"  {city}: +{total} 筆")
            except Exception as e:
                print(f"  {city}: [ERROR] {e}")

        # Threads 活動帳號（台南很有式 / 台北要幹嘛 / 倪倪小日常）
        for acct in THREADS_ACCOUNTS:
            try:
                t_data = scrape_threads_account(headless, acct)
                city = acct["city"]
                if city not in result["events"]:
                    result["events"][city] = {}
                result["events"][city] = merge_city_data(
                    result["events"].get(city, {}), t_data
                )
            except Exception as e:
                print(f"  Threads @{acct['username']}: [ERROR] {e}")
    finally:
        headless.quit()

    # ── KKTIX + 台南特殊來源（stealth Chrome）
    print("\n【KKTIX + 台南特殊來源 — stealth Chrome】")
    stealth = make_stealth_driver()
    try:
        # KKTIX 各城市
        for city in CITIES[:6]:  # 主要城市
            try:
                kktix_data = scrape_kktix(stealth, city)
                if city not in result["events"]:
                    result["events"][city] = {}
                result["events"][city] = merge_city_data(
                    result["events"].get(city, {}), kktix_data
                )
                total = sum(len(v) for v in kktix_data.values())
                if total:
                    print(f"  KKTIX {city}: +{total} 筆")
            except Exception as e:
                print(f"  KKTIX {city}: [ERROR] {e}")

        # 駁二藝術特區（高雄）
        try:
            pier2_data = scrape_pier2(stealth)
            for city, cats in pier2_data.items():
                if city not in result["events"]:
                    result["events"][city] = {}
                result["events"][city] = merge_city_data(
                    result["events"].get(city, {}), cats
                )
        except Exception as e:
            print(f"  駁二: [ERROR] {e}")

        # 台南文化局
        try:
            culture_data = scrape_tainan_culture(stealth)
            result["events"]["台南"] = merge_city_data(
                result["events"].get("台南", {}), culture_data
            )
            total = sum(len(v) for v in culture_data.values())
            if total:
                print(f"  台南文化局: +{total} 筆")
        except Exception as e:
            print(f"  台南文化局: [ERROR] {e}")

        # 台南美術館
        try:
            tnam_data = scrape_tnam(stealth)
            result["events"]["台南"] = merge_city_data(
                result["events"].get("台南", {}), tnam_data
            )
            total = sum(len(v) for v in tnam_data.values())
            if total:
                print(f"  台南美術館: +{total} 筆")
        except Exception as e:
            print(f"  台南美術館: [ERROR] {e}")

    finally:
        stealth.quit()

    # ── 儲存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_all = sum(
        len(evs)
        for city in result["events"].values()
        for evs in city.values()
    )
    print(f"\n{'='*55}")
    print(f"✅ 完成！共 {total_all} 筆活動")
    for city, cats in result["events"].items():
        city_total = sum(len(v) for v in cats.values())
        print(f"  {city}: {city_total} 筆 ({', '.join(f'{k}:{len(v)}' for k,v in cats.items())})")
    print(f"儲存 → {OUTPUT_FILE}")
    print(f"時間：{result['updated_at']}")


if __name__ == "__main__":
    main()
