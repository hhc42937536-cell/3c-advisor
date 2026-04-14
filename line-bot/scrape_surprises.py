"""
今日小驚喜爬蟲 — KKBOX 新歌 + PTT 優惠
========================================
輸出：surprise_cache.json（webhook.py 早安摘要使用）

來源：
  1. KKBOX 華語新歌榜（HTML 爬蟲）
  2. PTT Lifeismoney 板（JSON API，熱門優惠文）

執行：python scrape_surprises.py
排程：GitHub Actions 每天 06:00 TST
"""

import sys, io, json, os, re, time
import urllib.request
import urllib.error
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "surprise_cache.json")


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


def main():
    print("=" * 50)
    print(f"今日小驚喜爬蟲 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "songs": [],
        "deals": [],
    }

    # 爬 KKBOX
    result["songs"] = scrape_kkbox_new_songs(limit=10)
    time.sleep(1)

    # 爬 PTT + Dcard，合併去重後最多保留 20 筆
    ptt = scrape_ptt_deals(limit=12)
    time.sleep(1)
    dcard = scrape_dcard_deals(limit=10)

    # 合併：先 PTT 後 Dcard，標題去重
    seen_titles = set()
    merged = []
    for d in ptt + dcard:
        t = d.get("title", "").strip()
        if t and t not in seen_titles:
            seen_titles.add(t)
            merged.append(d)
    result["deals"] = merged[:20]

    # 寫出
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已寫入 {OUTPUT_FILE}")
    print(f"   新歌: {len(result['songs'])} 首")
    print(f"   優惠: {len(result['deals'])} 篇（PTT {len(ptt)} + Dcard {len(dcard)}）")


if __name__ == "__main__":
    main()
