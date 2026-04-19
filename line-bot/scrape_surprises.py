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


def scrape_apple_music_chart(limit: int = 15) -> list[dict]:
    """Apple Music 台灣熱門歌曲排行（公開 JSON API，無需認證）。"""
    print("[Apple Music] 開始抓台灣排行榜...")
    url = "https://rss.applemarketingtools.com/api/v2/tw/music/most-played/25/songs.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        songs = []
        for entry in data.get("feed", {}).get("results", [])[:limit]:
            name = entry.get("name", "").strip()
            artist = entry.get("artistName", "").strip()
            if name and artist:
                if len(artist) > 20:
                    artist = artist[:18] + "…"
                songs.append({"name": name, "artist": artist})
        print(f"[Apple Music] 抓到 {len(songs)} 首")
        return songs
    except Exception as e:
        print(f"[Apple Music] 錯誤: {e}")
        return []


def scrape_kkbox_new_songs(limit: int = 15) -> list[dict]:
    """KKBOX 已改用 JS 渲染，保留函式供向後相容，直接回傳空列表。"""
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
            if clean and len(clean) > 4:
                deals.append({
                    "title": clean[:60],
                    "url": f"https://www.ptt.cc{href}",
                    "tag": re.findall(r'\[([\w]+)\]', title)[0] if re.findall(r'\[([\w]+)\]', title) else "",
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
                    text = raw.encode().decode("unicode_escape")
                except Exception:
                    text = raw
                text = text.strip()
                if len(text) < 8:
                    continue
                # 過濾含優惠關鍵字的貼文
                if any(kw in text for kw in _THREADS_DEAL_KW):
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


def scrape_deals_via_serper(limit: int = 20) -> list[dict]:
    """用 Serper.dev 搜尋台灣近期即時優惠（MUJI特賣、百貨周年慶等）。"""
    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        print("[Serper] 缺少 SERPER_API_KEY，跳過")
        return []

    import urllib.parse as _up

    _DEAL_QUERIES = [
        "台灣 特賣 優惠 限時 折扣 本週",
        "百貨公司 周年慶 特賣 優惠",
        "品牌 大特價 開幕優惠 台灣",
    ]
    _SKIP_DOMAINS = {"youtube.com", "facebook.com", "instagram.com", "wikipedia.org"}
    _DEAL_KW = {"特賣", "優惠", "折扣", "特價", "限時", "買一送一", "周年慶", "開幕", "大降價", "狂殺"}

    seen, results = set(), []
    for query in _DEAL_QUERIES:
        payload = json.dumps({
            "q": query, "gl": "tw", "hl": "zh-tw",
            "num": 10, "tbs": "qdr:w",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                "https://google.serper.dev/search",
                data=payload,
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            for item in data.get("organic", []):
                title = item.get("title", "").strip()
                url = item.get("link", "")
                snippet = item.get("snippet", "")
                domain = urllib.request.Request(url).full_url if url else ""
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.lstrip("www.")
                except Exception:
                    pass
                if any(s in domain for s in _SKIP_DOMAINS):
                    continue
                if not any(k in title or k in snippet for k in _DEAL_KW):
                    continue
                if title in seen:
                    continue
                seen.add(title)
                results.append({"title": title[:60], "url": url, "tag": "優惠"})
            time.sleep(0.5)
        except Exception as e:
            print(f"[Serper] 查詢失敗: {e}")

    print(f"[Serper] 找到 {len(results)} 筆即時優惠")
    return results[:limit]


def scrape_songs_via_serper(limit: int = 15) -> list[dict]:
    """用 Serper 搜尋台灣近期熱門新歌。"""
    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        return []

    payload = json.dumps({
        "q": f"台灣 華語 熱門新歌 排行榜 {datetime.now().strftime('%Y年%m月')}",
        "gl": "tw", "hl": "zh-tw", "num": 5, "tbs": "qdr:m",
    }).encode("utf-8")

    songs = []
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))

        # 從 snippet 裡用正則抽「歌名 - 歌手」或「歌名／歌手」格式
        seen = set()
        for item in data.get("organic", []):
            snippet = item.get("snippet", "") + " " + item.get("title", "")
            for m in re.finditer(r'[《〈「]([^》〉」]{2,20})[》〉」][^\S\r\n]*[-–—/／]\s*([^\s,，、。！\n]{2,15})', snippet):
                name, artist = m.group(1).strip(), m.group(2).strip()
                if name not in seen and len(name) >= 2:
                    seen.add(name)
                    songs.append({"name": name, "artist": artist})
        print(f"[Serper歌單] 抓到 {len(songs)} 首")
    except Exception as e:
        print(f"[Serper歌單] 失敗: {e}")

    return songs[:limit]


def main():
    print("=" * 50)
    print(f"今日小驚喜爬蟲 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "songs": [],
        "deals": [],
    }

    # 歌單：Apple Music 台灣排行榜，失敗才用 Serper 備援
    result["songs"] = scrape_apple_music_chart(limit=15)
    if not result["songs"]:
        print("[歌單] Apple Music 失敗，改用 Serper")
        result["songs"] = scrape_songs_via_serper(limit=15)
    time.sleep(1)

    # 優惠：Serper 即時優惠為主，PTT/Dcard 補充
    serper_deals = scrape_deals_via_serper(limit=20)
    time.sleep(1)
    ptt = scrape_ptt_deals(limit=8)
    time.sleep(1)
    dcard = scrape_dcard_deals(limit=8)
    time.sleep(1)
    threads = scrape_threads_deals()

    seen_titles: set = set()
    merged: list = []
    for d in serper_deals + threads + ptt + dcard:
        t = d.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            merged.append(d)
    result["deals"] = merged[:25]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已寫入 {OUTPUT_FILE}")
    print(f"   新歌: {len(result['songs'])} 首")
    print(f"   優惠: {len(result['deals'])} 筆（Serper {len(serper_deals)} + PTT {len(ptt)} + Dcard {len(dcard)} + Threads {len(threads)}）")


if __name__ == "__main__":
    main()
