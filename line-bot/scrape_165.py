"""
165 反詐騙官網爬蟲
===================
爬取最新詐騙手法排行，更新 api/data/fraud_patterns.json 的 trends 區塊。
patterns（關鍵字庫）保留不動，只更新 trends 排行。

執行：python scrape_165.py
排程：每月 1 日 06:00 台灣時間
"""

import sys, io, json, os, re, urllib.request, urllib.error, ssl
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(BASE, "api", "data", "fraud_patterns.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

EMOJI_MAP = {
    "投資": "📈", "購物": "🛒", "AI": "🤖", "深偽": "🤖",
    "愛情": "💕", "交友": "💕", "公務": "🏛️", "機關": "🏛️",
    "求職": "💼", "打工": "💼", "簡訊": "📱", "釣魚": "📱",
    "遊戲": "🎮", "點數": "🎮", "解除": "🛒", "假冒": "🏛️",
}


def _emoji(name: str) -> str:
    for k, v in EMOJI_MAP.items():
        if k in name:
            return v
    return "⚠️"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
        return r.read().decode("utf-8", errors="replace")


def scrape_165_news() -> list[dict]:
    """爬 165 最新消息，擷取詐騙類型關鍵字組成 trends。"""
    print("[165] 爬取最新詐騙新聞...")
    url = "https://165.npa.gov.tw/#/articles/C"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[165] 失敗: {e}")
        return []

    # 擷取標題文字
    titles = re.findall(r'<[^>]*title[^>]*>([^<]{4,40})</[^>]*>', html, re.IGNORECASE)
    titles += re.findall(r'"title"\s*:\s*"([^"]{4,40})"', html)
    titles = list(dict.fromkeys(t.strip() for t in titles if any(
        k in t for k in ["詐騙", "詐欺", "詐財", "假冒", "投資", "釣魚", "勒索"]
    )))[:8]

    return [{"rank": i+1, "name": t[:12], "emoji": _emoji(t),
             "desc": t, "sign": "請提高警覺，勿輕易轉帳或提供個資"}
            for i, t in enumerate(titles)]


def scrape_npa_stats() -> list[dict]:
    """爬警政署防詐統計頁，取詐騙類型排行。"""
    print("[警政署] 爬取詐騙統計...")
    url = "https://www.npa.gov.tw/ch/app/folder/query?pagenum=1&size=10&module=wps_02&id=2&keyword=%E8%A9%90%E9%A8%99"
    try:
        html = fetch(url)
        items = re.findall(r'<td[^>]*>([^<]{4,30}詐[^<]{0,20})</td>', html)
        items = list(dict.fromkeys(items))[:8]
        if items:
            return [{"rank": i+1, "name": t[:12], "emoji": _emoji(t),
                     "desc": t, "sign": "請提高警覺"}
                    for i, t in enumerate(items)]
    except Exception as e:
        print(f"[警政署] 失敗: {e}")
    return []


def load_existing() -> dict:
    try:
        with open(OUTPUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"patterns": [], "trends": []}


def main() -> None:
    print(f"{'='*50}")
    print(f"165 防詐爬蟲 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    existing = load_existing()

    # 嘗試爬新資料
    trends = scrape_165_news() or scrape_npa_stats()

    if not trends:
        print("⚠️  無法取得新資料，保留現有 trends 不變")
        trends = existing.get("trends", [])
    else:
        print(f"✅ 取得 {len(trends)} 筆詐騙手法")

    existing["trends"] = trends
    existing["updated_at"] = datetime.now().strftime("%Y-%m-%d")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✅ 已更新 {OUTPUT}")


if __name__ == "__main__":
    main()
