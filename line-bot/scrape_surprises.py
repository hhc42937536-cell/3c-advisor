"""
今日小驚喜爬蟲 — KKBOX 新歌 + PTT + Dcard + Threads 好康
=============================================================
輸出：surprise_cache.json（webhook.py 早安摘要使用）

來源：
  1. KKBOX 華語新歌榜（HTML 爬蟲）
  2. PTT Lifeismoney 板（HTML，熱門優惠文）
  3. Dcard 省錢板（JSON API）
  4. Threads 好康帳號（非官方 HTML parse，失敗時自動跳過）

執行：python scrape_surprises.py
排程：GitHub Actions 每天 06:00 TST
"""

import sys, io, json, os, re, time
import urllib.request
import urllib.error
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "surprise_cache.json")

SENSITIVE_KW = [
    "政治", "選舉", "立委", "總統", "政黨", "藍白", "藍綠", "統獨", "中國", "台獨", "革命",
    "戰爭", "軍事", "攻擊", "恐怖", "爆炸", "槍", "砍", "殺", "自殺", "死亡", "命案",
    "性侵", "性騷", "偷拍", "外流", "裸", "情色", "約炮", "成人", "18禁",
    "仇恨", "歧視", "種族", "移工", "身障", "宗教", "炎上", "公審", "霸凌",
    "詐騙手法", "毒品", "大麻", "賭博", "博弈", "血", "屍", "遺體",
]

SAFE_TOPIC_KW = [
    "美食", "咖啡", "手搖", "飲料", "旅遊", "景點", "展覽", "電影", "影集", "音樂",
    "影城", "動漫", "演唱會", "巡演", "新歌", "開幕", "限定活動",
    "穿搭", "保養", "生活", "上班", "通勤", "寵物", "貓", "狗", "省錢", "優惠",
    "超商", "全家", "711", "全聯", "職場", "午餐", "晚餐", "早餐", "台北", "台中",
    "台南", "高雄", "桃園", "新竹",
]

LIFE_DEAL_KW = [
    "咖啡", "手搖", "飲料", "茶", "早餐", "午餐", "晚餐", "餐", "美食", "甜點", "冰品", "冰棒",
    "全家", "7-11", "711", "萊爾富", "OK", "超商", "全聯", "家樂福",
    "麥當勞", "肯德基", "摩斯", "漢堡王", "必勝客", "星巴克", "路易莎", "cama",
    "加油", "油價", "電影", "影城", "展覽", "市集", "活動", "買一送一", "優惠券",
]

DEAL_BLOCK_KW = [
    "pCloud", "雲端", "記憶卡", "SSD", "硬碟", "電通", "螢幕", "耳機", "鍵盤", "滑鼠",
    "抽獎", "集中文", "贈送", "捐血", "會考", "考生", "未滿1元", "信用卡核卡", "開箱",
    "可樂", "大瓶", "美廉社", "優惠券領取",
]


def is_life_deal(title: str) -> bool:
    text = re.sub(r"\s+", " ", title or "").strip()
    if len(text) < 4:
        return False
    if text in {"必勝客優惠", "全家優惠", "麥當勞優惠", "肯德基優惠"}:
        return False
    if any(word.lower() in text.lower() for word in DEAL_BLOCK_KW):
        return False
    return any(word.lower() in text.lower() for word in LIFE_DEAL_KW)


def scrape_ptt_excerpt(url: str, headers: dict, ctx, timeout: int = 8) -> str:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'<div id="main-content"[^>]*>(.*?)<span class="f2">--', html_text, re.S)
        content = m.group(1) if m else html_text
        content = re.sub(r'<div class="article-metaline.*?</div>', '', content, flags=re.S)
        content = re.sub(r'<div class="article-metaline-right.*?</div>', '', content, flags=re.S)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = py_html.unescape(content)
        lines = [re.sub(r"\s+", " ", line).strip() for line in content.splitlines()]
        lines = [
            line for line in lines
            if len(line) >= 8
            and not line.startswith(("※", "發信站", "Sent from", "http://", "https://"))
            and "PTT" not in line[:20]
        ]
        return "；".join(lines[:2])[:90]
    except Exception:
        return ""


def is_safe_topic(text: str) -> bool:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) < 8:
        return False
    if any(word.lower() in text.lower() for word in SENSITIVE_KW):
        return False
    # 有安全關鍵字優先收；沒有也可留短日常句，但避免太像個人情緒文。
    if any(word in text for word in SAFE_TOPIC_KW):
        return True
    return len(text) <= 48 and not any(mark in text for mark in ["?", "？", "求助", "抱怨", "吵架"])


def scrape_kkbox_new_songs(limit=10):
    """爬 KKBOX 華語新歌日榜（從頁面內嵌 JS 變數 chart 抓資料）"""
    print("[KKBOX] 開始爬新歌榜...")
    url = "https://kma.kkbox.com/charts/daily/newrelease?cate=297&lang=tc&terr=tw"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        songs = []
        # KKBOX 把排行榜資料放在 JS 變數: var chart = [{...}, ...]
        m = re.search(r'var\s+chart\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
        if m:
            chart_data = json.loads(m.group(1))
            for entry in chart_data[:limit]:
                name = entry.get("song_name", "").strip()
                artist = entry.get("artist_name", "").strip()
                if name and artist:
                    # 截斷過長的歌手名（多人合作時很長）
                    if len(artist) > 20:
                        parts = re.split(r'[,、/]', artist)
                        artist = parts[0].strip() + " 等"
                    songs.append({"name": name, "artist": artist})

        print(f"[KKBOX] 抓到 {len(songs)} 首新歌")
        return songs

    except Exception as e:
        print(f"[KKBOX] 錯誤: {e}")
        return []


def scrape_ptt_deals(limit=10):
    """爬 PTT Lifeismoney（省錢板）熱門文章"""
    print("[PTT] 開始爬優惠文...")
    url = "https://www.ptt.cc/bbs/Lifeismoney/index.html"
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

        deals = []
        # PTT 文章標題格式：<div class="title"><a href="...">標題</a></div>
        entries = re.findall(
            r'<div class="title">\s*<a[^>]*href="(/bbs/Lifeismoney/[^"]+)"[^>]*>([^<]+)</a>',
            html
        )

        # 過濾掉公告、已刪除文章
        blocklist = ["公告", "刪除", "水桶", "置底", "徵求", "問題"]
        for href, title in entries:
            title = title.strip()
            if any(b in title for b in blocklist):
                continue
            # 移除標題前綴 [情報] [優惠] 等，但保留內容
            clean = re.sub(r'^\[[\w]+\]\s*', '', title)
            if clean and len(clean) > 4 and is_life_deal(clean):
                full_url = f"https://www.ptt.cc{href}"
                deals.append({
                    "title": clean[:60],
                    "url": full_url,
                    "tag": re.findall(r'\[([\w]+)\]', title)[0] if re.findall(r'\[([\w]+)\]', title) else "",
                    "desc": scrape_ptt_excerpt(full_url, headers, ctx),
                })
            if len(deals) >= limit:
                break

        print(f"[PTT] 抓到 {len(deals)} 篇優惠文")
        return deals

    except Exception as e:
        print(f"[PTT] 錯誤: {e}")
        return []


def scrape_dcard_deals(limit=10):
    """爬 Dcard 省錢板熱門文章（使用官方內部 JSON API）"""
    print("[Dcard] 開始爬省錢板...")
    url = "https://www.dcard.tw/_api/forums/money/posts?popular=true&limit=30"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.dcard.tw/f/money",
        "Accept": "application/json",
    }
    blocklist = ["請問", "問卦", "求問", "問題", "徵求", "心得分享", "分享心得",
                 "開箱", "試用", "閒聊", "心情", "求助", "有人用過"]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))

        deals = []
        for post in data:
            title = post.get("title", "").strip()
            post_id = post.get("id", "")
            if not title or not post_id:
                continue
            if any(b in title for b in blocklist):
                continue
            if not is_life_deal(title):
                continue
            if len(title) < 5:
                continue
            deals.append({
                "title": title[:60],
                "url": f"https://www.dcard.tw/f/money/p/{post_id}",
                "tag": "Dcard",
            })
            if len(deals) >= limit:
                break

        print(f"[Dcard] 抓到 {len(deals)} 篇文章")
        return deals
    except Exception as e:
        print(f"[Dcard] 錯誤: {e}")
        return []


def scrape_dcard_topics(limit=20):
    """爬 Dcard 熱門日常話題，過濾敏感議題後作為上班破冰素材。"""
    print("[Dcard topics] 開始爬熱門話題...")
    urls = [
        ("閒聊", "https://www.dcard.tw/_api/forums/talk/posts?popular=true&limit=30"),
        ("美食", "https://www.dcard.tw/_api/forums/food/posts?popular=true&limit=30"),
        ("旅遊", "https://www.dcard.tw/_api/forums/travel/posts?popular=true&limit=30"),
        ("電影", "https://www.dcard.tw/_api/forums/movie/posts?popular=true&limit=30"),
        ("穿搭", "https://www.dcard.tw/_api/forums/dressup/posts?popular=true&limit=30"),
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.dcard.tw/",
        "Accept": "application/json",
    }
    topics = []
    seen = set()
    for label, url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            for post in data:
                title = re.sub(r"\s+", " ", post.get("title", "")).strip()
                post_id = post.get("id", "")
                if not title or not post_id or title in seen:
                    continue
                if not is_safe_topic(title):
                    continue
                seen.add(title)
                topics.append({
                    "title": title[:70],
                    "url": f"https://www.dcard.tw/f/{post.get('forumAlias') or label}/p/{post_id}",
                    "tag": f"Dcard {label}",
                })
                if len(topics) >= limit:
                    print(f"[Dcard topics] 抓到 {len(topics)} 筆")
                    return topics
            time.sleep(0.5)
        except Exception as e:
            print(f"[Dcard topics] {label} 失敗（跳過）: {e}")
    print(f"[Dcard topics] 抓到 {len(topics)} 筆")
    return topics


# Threads 好康帳號清單
_THREADS_ACCOUNTS = [
    "info.talk_tw",           # 好康情報誌：速食/超商即時優惠
    "group_buying_information",  # 團購資訊整理：免費兌換/限時折扣
]

_THREADS_DEAL_KW = ["優惠", "折扣", "特價", "買一送一", "免費", "好康", "打折", "半價", "兌換", "限定", "送"]


def scrape_threads_deals(limit_per_account: int = 5) -> list:
    """抓 Threads 好康帳號最新貼文（非官方 HTML parse，失敗時靜默跳過）
    Threads 無公開 API，此方式隨時可能因版面更新而失效。
    """
    print("[Threads] 開始抓即時好康帳號...")
    headers = {
        # 模擬 Android 裝置，取得較精簡的 HTML 回應
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.threads.net/",
    }

    all_deals = []
    for account in _THREADS_ACCOUNTS:
        try:
            url = f"https://www.threads.net/@{account}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            posts = []
            # Threads 在 HTML 內嵌 JSON-LD 或 __bbox.require 結構
            # 嘗試抓出 "text" 欄位中的貼文內容
            text_candidates = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.){10,120})"', html)
            for raw in text_candidates:
                try:
                    text = raw.encode().decode("unicode_escape") if "\\u" in raw else raw
                except Exception:
                    text = raw
                text = text.strip()
                if len(text) < 8:
                    continue
                # 過濾含優惠關鍵字的貼文
                if any(kw in text for kw in _THREADS_DEAL_KW) and is_life_deal(text):
                    posts.append({
                        "title": text[:60],
                        "url": url,
                        "tag": "Threads",
                    })
                if len(posts) >= limit_per_account:
                    break

            print(f"[Threads] @{account}: {len(posts)} 筆")
            all_deals.extend(posts)
            time.sleep(1)

        except Exception as e:
            print(f"[Threads] @{account} 失敗（跳過）: {e}")

    print(f"[Threads] 共 {len(all_deals)} 筆即時好康")
    return all_deals


def scrape_threads_topics(limit_per_account: int = 5) -> list:
    """抓 Threads 可聊話題。
    Threads 沒有公開 API，這裡只把能從公開頁 HTML 抓到的短貼文整理成候選話題。
    """
    print("[Threads] 開始抓昨日/近期可聊話題...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.threads.net/",
    }
    accounts = [
        "info.talk_tw",
        "today.line.me",
        "niusnews",
        "ttshow.tw",
    ]
    blocklist = ["抽獎", "得獎", "私訊", "連結在", "留言", "追蹤"]
    topics = []
    seen = set()
    for account in accounts:
        try:
            url = f"https://www.threads.net/@{account}"
            text_candidates = []
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            text_candidates.extend(re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.){14,180})"', html))
            reader_url = "https://r.jina.ai/http://r.jina.ai/http://" + url
            reader_req = urllib.request.Request(reader_url, headers={"User-Agent": headers["User-Agent"]})
            with urllib.request.urlopen(reader_req, timeout=20) as resp:
                markdown = resp.read().decode("utf-8", errors="ignore")
            lines = [re.sub(r"\s+", " ", line).strip() for line in markdown.splitlines()]
            for idx, line in enumerate(lines):
                if re.match(r"\[\d+[hm]\]\(https://www\.threads\.net/@", line):
                    for candidate in lines[idx + 1:idx + 6]:
                        if not candidate or candidate.startswith(("![", "[@", "#", "Photo", "Translate", "追蹤")):
                            continue
                        if 14 <= len(candidate) <= 180:
                            text_candidates.append(candidate)
                        break
            for raw in text_candidates:
                try:
                    text = raw.encode().decode("unicode_escape") if "\\u" in raw else raw
                except Exception:
                    text = raw
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 12 or any(word in text for word in blocklist) or not is_safe_topic(text):
                    continue
                key = text[:30]
                if key in seen:
                    continue
                seen.add(key)
                topics.append({
                    "title": text[:70],
                    "url": url,
                    "tag": f"Threads @{account}",
                })
                if len(topics) >= limit_per_account * len(accounts):
                    break
            print(f"[Threads topics] @{account}: {len(topics)} 累計")
            time.sleep(1)
        except Exception as e:
            print(f"[Threads topics] @{account} 失敗（跳過）: {e}")
    print(f"[Threads topics] 共 {len(topics)} 筆")
    return topics


def main():
    print("=" * 50)
    print(f"今日小驚喜爬蟲 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    previous = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, encoding="utf-8") as f:
                previous = json.load(f)
        except Exception:
            previous = {}

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "songs": [],
        "deals": [],
        "topics": [],
    }

    # 爬 KKBOX
    result["songs"] = scrape_kkbox_new_songs(limit=10) or previous.get("songs", [])
    time.sleep(1)

    # 爬 PTT + Dcard，合併去重後最多保留 20 筆
    ptt = scrape_ptt_deals(limit=12)
    time.sleep(1)
    dcard = scrape_dcard_deals(limit=10)
    time.sleep(1)

    # 爬 Threads 即時好康（非官方，失敗不影響整體）
    threads = scrape_threads_deals()
    threads_topics = scrape_threads_topics()
    dcard_topics = scrape_dcard_topics()

    # 合併：Threads 最新鮮放最前，再接 PTT、Dcard，標題去重
    seen_titles = set()
    merged = []
    for d in threads + ptt + dcard:
        t = d.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            merged.append(d)
    previous_deals = [deal for deal in previous.get("deals", []) if is_life_deal(deal.get("title", ""))]
    result["deals"] = merged[:25] or previous_deals
    topic_seen = set()
    topics = []
    for topic in threads_topics + dcard_topics:
        title = topic.get("title", "").strip()
        if title and title not in topic_seen and is_safe_topic(title):
            topic_seen.add(title)
            topics.append(topic)
    result["topics"] = topics[:20] or previous.get("topics", [])
    if not topics and previous.get("topics"):
        print("[topics] 本次抓取失敗，保留上一版社群話題快取")
    if not merged and previous.get("deals"):
        print("[deals] 本次抓取失敗，保留上一版優惠快取")

    # 寫出
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已寫入 {OUTPUT_FILE}")
    print(f"   新歌: {len(result['songs'])} 首")
    print(f"   好康: {len(result['deals'])} 篇（Threads {len(threads)} + PTT {len(ptt)} + Dcard {len(dcard)}）")
    print(f"   話題: {len(result['topics'])} 篇（Threads {len(threads_topics)} + Dcard {len(dcard_topics)}，已過濾敏感議題）")


if __name__ == "__main__":
    main()
