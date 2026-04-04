"""
LINE Bot Webhook — 3C 推薦小幫手
=================================
Vercel Serverless Function (Python)
處理所有 LINE 訊息，根據內容路由到不同模組。

目前模組：
  - 3C 推薦小幫手（問答式推薦手機/筆電/平板）

未來可擴充：
  - 更多工具模組（只要加 handler 函數就好）
"""

import json
import os
import re
import hashlib
import hmac
import urllib.request
from http.server import BaseHTTPRequestHandler

# ─── LINE 設定（從環境變數讀取）────────────────────
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
# 產品資料來源（你的 GitHub Pages）
PRODUCTS_URL = os.environ.get("PRODUCTS_URL", "https://hhc42937536-cell.github.io/3c-advisor/products.json")

# ─── 產品資料快取 ─────────────────────────────────
_products_cache = {"data": None, "ts": 0}

def load_products():
    """從 GitHub Pages 載入最新產品資料（快取 10 分鐘）"""
    import time
    now = time.time()
    if _products_cache["data"] and now - _products_cache["ts"] < 600:
        return _products_cache["data"]
    try:
        req = urllib.request.Request(PRODUCTS_URL, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            _products_cache["data"] = data
            _products_cache["ts"] = now
            return data
    except Exception:
        return _products_cache["data"] or {"laptop": [], "phone": [], "tablet": [], "desktop": []}


# ─── LINE API 工具 ────────────────────────────────
def reply_message(reply_token, messages):
    """回覆使用者訊息"""
    print(f"[reply] token={reply_token[:20]}... ACCESS_TOKEN={'SET' if CHANNEL_ACCESS_TOKEN else 'EMPTY'} msgs={len(messages)}")
    if not CHANNEL_ACCESS_TOKEN or not reply_token:
        print(f"[reply] SKIPPED: token={'empty' if not reply_token else 'ok'}, access_token={'empty' if not CHANNEL_ACCESS_TOKEN else 'ok'}")
        return
    data = json.dumps({
        "replyToken": reply_token,
        "messages": messages[:5],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/reply",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[reply] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[reply] ERROR: {e}")
        if hasattr(e, 'read'):
            print(f"[reply] BODY: {e.read().decode('utf-8','ignore')}")


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽名"""
    if not CHANNEL_SECRET:
        return True  # 開發模式跳過驗證
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256)
    import base64
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode("utf-8"), signature)


# ─── 3C 推薦模組 ─────────────────────────────────

# 關鍵字 → 裝置類別
DEVICE_KEYWORDS = {
    "phone": ["手機", "phone", "iphone", "三星", "samsung", "pixel", "小米", "oppo", "vivo", "sony"],
    "laptop": ["筆電", "筆記型電腦", "laptop", "notebook", "macbook", "電腦"],
    "tablet": ["平板", "tablet", "ipad", "surface"],
}

# 關鍵字 → 用途偏好
USE_KEYWORDS = {
    "拍照": ["拍照", "相機", "攝影", "鏡頭", "自拍"],
    "遊戲": ["遊戲", "電競", "打game", "lol", "原神", "steam"],
    "追劇": ["追劇", "netflix", "youtube", "影片", "看劇"],
    "長輩": ["長輩", "爸媽", "阿公", "阿嬤", "爺爺", "奶奶", "媽媽", "爸爸", "老人"],
    "學生": ["學生", "上課", "作業", "報告", "念書"],
    "工作": ["工作", "辦公", "上班", "文書", "word", "excel"],
    "輕薄": ["輕薄", "輕巧", "好攜帶", "輕的"],
}


def parse_budget(text: str) -> int:
    """從文字中解析預算，回傳最大金額"""
    # "2萬" → 20000
    m = re.search(r"(\d+)\s*萬", text)
    if m:
        return int(m.group(1)) * 10000
    # "20000" 或 "20,000"
    m = re.search(r"(\d{4,6})", text.replace(",", ""))
    if m:
        val = int(m.group(1))
        if val >= 3000:
            return val
    # 模糊描述
    if any(w in text for w in ["便宜", "省錢", "預算少", "入門", "便宜點"]):
        return 15000
    if any(w in text for w in ["中等", "一般", "普通"]):
        return 30000
    if any(w in text for w in ["好一點", "品質好", "不差錢"]):
        return 60000
    # 不限預算 → 回傳超大值，篩選時等同全部顯示
    if any(w in text for w in ["不限預算", "不限", "隨便", "都可以", "沒差", "高階", "最好", "旗艦", "5萬以上", "無限"]):
        return 999999
    return 0  # 未指定預算


def detect_device(text: str) -> str:
    """偵測使用者想買什麼裝置"""
    text_lower = text.lower()
    for device, keywords in DEVICE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return device
    return ""


def detect_use(text: str) -> list:
    """偵測使用者的用途偏好"""
    text_lower = text.lower()
    uses = []
    for use, keywords in USE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            uses.append(use)
    return uses


def filter_products(products: list, budget: int, uses: list) -> list:
    """根據預算和用途篩選並排序產品"""
    results = []
    for p in products:
        price = int(re.sub(r"[^0-9]", "", p.get("price", "0")))
        if 0 < budget < 999999 and price > budget * 1.2:
            continue
        if price < 3000:
            continue

        # 計算匹配分數
        score = 0
        name_lower = (p.get("name", "") + p.get("pros", "")).lower()

        if "拍照" in uses and any(w in name_lower for w in ["鏡頭", "攝影", "相機", "拍照", "pixel", "蔡司"]):
            score += 10
        if "遊戲" in uses and any(w in name_lower for w in ["電競", "rog", "gaming", "rtx", "效能"]):
            score += 10
        if "長輩" in uses and price < 20000:
            score += 5
        if "學生" in uses and price < 35000:
            score += 3
        if "輕薄" in uses and any(w in name_lower for w in ["輕", "薄", "air", "slim"]):
            score += 8

        results.append({**p, "_score": score, "_price": price})

    # 排序：匹配分數高 → 價格低
    results.sort(key=lambda x: (-x["_score"], x["_price"]))
    return results[:5]


def spec_to_plain_line(p: dict) -> str:
    """簡短白話規格（一行版）"""
    parts = []
    cpu = p.get("cpu", "")
    if cpu and cpu != "詳見商品頁":
        if re.search(r"ultra 7|ultra 9|m4|m3|ryzen 9|i9|snapdragon 8 elite", cpu, re.I):
            parts.append("超快處理器")
        elif re.search(r"ultra 5|m2|ryzen 7|i7|snapdragon 8", cpu, re.I):
            parts.append("很快的處理器")
        else:
            parts.append("夠用的處理器")

    ram = p.get("ram", "")
    if ram and ram != "—":
        ram_num = int(re.sub(r"[^0-9]", "", ram) or 0)
        if ram_num >= 16:
            parts.append(f"{ram_num}GB大記憶體")
        elif ram_num >= 8:
            parts.append(f"{ram_num}GB記憶體")

    ssd = p.get("ssd", "")
    if ssd and ssd != "—":
        parts.append(f"{ssd}儲存")

    return " / ".join(parts) if parts else "詳見商品頁"


def build_product_flex(p: dict, rank: int) -> dict:
    """建立單個產品的 Flex Message bubble"""
    price = p.get("price", "")
    brand = p.get("brand", "")
    name = p.get("name", "")[:30]
    tag = p.get("tag", "")
    pros = p.get("pros", "")[:40]
    cons = p.get("cons", "")[:30]
    spec_line = spec_to_plain_line(p)
    url = p.get("url", "")

    # 比價連結
    search_q = urllib.request.pathname2url(f"{brand} {name}")
    pchome_url = f"https://ecshweb.pchome.com.tw/search/v3.3/?q={search_q}"

    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank] if rank < 5 else ""

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#FF8C42",
            "contents": [
                {"type": "text", "text": f"{medal} {brand}", "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                {"type": "text", "text": name, "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": price, "size": "xl", "weight": "bold", "color": "#3E2723"},
                {"type": "text", "text": f"📖 {spec_line}", "size": "xs", "color": "#8D6E63", "wrap": True},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"👍 {pros}", "size": "xs", "color": "#4CAF50", "wrap": True, "margin": "md"},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {
                    "type": "button", "style": "primary", "color": "#FF8C42",
                    "action": {"type": "uri", "label": "🛒 去比價", "uri": url or pchome_url},
                },
                {
                    "type": "button", "style": "secondary",
                    "action": {"type": "uri", "label": "🔍 PChome 搜尋", "uri": pchome_url},
                },
            ]
        }
    }

    if cons and cons != "規格詳見商品頁":
        bubble["body"]["contents"].append(
            {"type": "text", "text": f"⚠️ {cons}", "size": "xs", "color": "#FF9800", "wrap": True}
        )

    return bubble


def build_recommendation_message(device: str, budget: int, uses: list) -> list:
    """根據條件建立推薦回覆"""
    db = load_products()

    # 裝置對應
    device_map = {"phone": "phone", "laptop": "laptop", "tablet": "tablet"}
    key = device_map.get(device, "phone")
    products = db.get(key, [])

    if not products:
        return [{"type": "text", "text": "抱歉，目前沒有找到相關產品資料 😅\n請稍後再試，或到網站版查看：\nhttps://hhc42937536-cell.github.io/3c-advisor/"}]

    # 篩選
    filtered = filter_products(products, budget, uses)

    if not filtered:
        budget_hint = "不限預算" if budget >= 999999 else f"NT${budget:,}"
        return [{"type": "text", "text": f"在{budget_hint}條件下沒有找到適合的產品 😅\n\n請到網站版看更多選擇 👇\nhttps://hhc42937536-cell.github.io/3c-advisor/"}]

    # 組合 Flex carousel
    device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板"}.get(device, "產品")
    if budget >= 999999:
        budget_text = "（不限預算）"
    elif budget > 0:
        budget_text = f"（預算 NT${budget:,} 以內）"
    else:
        budget_text = ""
    use_text = f"（{', '.join(uses)}）" if uses else ""

    bubbles = [build_product_flex(p, i) for i, p in enumerate(filtered)]

    messages = [
        {"type": "text", "text": f"幫你找到 {len(filtered)} 款推薦{device_name}{budget_text}{use_text} 👇"},
        {
            "type": "flex",
            "altText": f"推薦{device_name}{budget_text}",
            "contents": {
                "type": "carousel",
                "contents": bubbles
            }
        }
    ]

    return messages


# ─── 對話路由 ─────────────────────────────────────

def build_welcome_message() -> list:
    """歡迎訊息 + 快速選單"""
    return [{
        "type": "flex",
        "altText": "歡迎使用3C 推薦小幫手！",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#FF8C42",
                "contents": [
                    {"type": "text", "text": "🛍️ 3C 推薦小幫手", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "你的 3C 選購好朋友！", "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text", "text": "你可以直接跟我說：", "size": "sm", "color": "#8D6E63"},
                    {"type": "text", "text": "📱 「推薦 2 萬以內的手機」", "size": "sm", "color": "#3E2723"},
                    {"type": "text", "text": "💻 「學生用的筆電推薦」", "size": "sm", "color": "#3E2723"},
                    {"type": "text", "text": "📟 「給長輩用的平板」", "size": "sm", "color": "#3E2723"},
                    {"type": "text", "text": "📷 「拍照好的手機 3 萬」", "size": "sm", "color": "#3E2723"},
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "或是點下面的按鈕快速開始 👇", "size": "xs", "color": "#8D6E63", "margin": "md"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#FF8C42",
                     "action": {"type": "message", "label": "📱 推薦手機", "text": "推薦手機"}},
                    {"type": "button", "style": "primary", "color": "#5B9BD5",
                     "action": {"type": "message", "label": "💻 推薦筆電", "text": "推薦筆電"}},
                    {"type": "button", "style": "primary", "color": "#4CAF50",
                     "action": {"type": "message", "label": "📟 推薦平板", "text": "推薦平板"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "uri", "label": "🌐 開啟網站版", "uri": "https://hhc42937536-cell.github.io/3c-advisor/"}},
                ]
            }
        }
    }]


def build_ask_budget_message(device: str) -> list:
    """詢問預算"""
    device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板"}.get(device, "產品")
    return [{
        "type": "flex",
        "altText": f"請問{device_name}預算大概多少？",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text", "text": f"💰 {device_name}預算大概多少呢？", "size": "md", "weight": "bold", "color": "#3E2723"},
                    {"type": "text", "text": "點一個最接近的，或直接打數字", "size": "xs", "color": "#8D6E63"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💰 1 萬以內（省錢）", "text": f"{device_name} 1萬以內"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "👍 1~3 萬（夠用）", "text": f"{device_name} 3萬以內"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "⭐ 3~5 萬（品質好）", "text": f"{device_name} 5萬以內"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🏆 5 萬以上（買好的）", "text": f"{device_name} 不限預算"}},
                ]
            }
        }
    }]


def handle_text_message(text: str) -> list:
    """主路由：分析文字，決定回覆什麼"""
    text = text.strip()
    text_lower = text.lower()

    # 1. 打招呼 / 幫助
    greetings = ["你好", "嗨", "hi", "hello", "哈囉", "安安", "開始", "幫助", "help", "選單", "功能"]
    if any(text_lower == g or text_lower.startswith(g) for g in greetings):
        return build_welcome_message()

    # 2. 偵測裝置類別
    device = detect_device(text)
    budget = parse_budget(text)
    uses = detect_use(text)

    # 3. 有裝置但沒預算 → 詢問預算
    if device and not budget and not uses:
        # 只說了「推薦手機」沒其他資訊
        return build_ask_budget_message(device)

    # 4. 有裝置 + 有預算或用途 → 直接推薦
    if device:
        return build_recommendation_message(device, budget, uses)

    # 5. 有預算但沒說裝置 → 猜是手機（最常見）
    if budget:
        return build_recommendation_message("phone", budget, uses)

    # 6. 有用途關鍵字但沒裝置 → 依用途猜裝置
    if uses:
        if any(u in uses for u in ["遊戲"]):
            return build_recommendation_message("phone", 0, uses)
        return build_recommendation_message("phone", 0, uses)

    # 7. 完全看不懂 → 友善引導
    return [{
        "type": "text",
        "text": "嗨！我是 3C 推薦小幫手 🛍️\n\n你可以跟我說像是：\n📱「推薦 2 萬的手機」\n💻「學生用的筆電」\n📟「給爸媽的平板」\n\n我會幫你找到最適合的！"
    }]


# ─── Vercel Handler ───────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """健康檢查用"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "bot": "3C 推薦小幫手"}).encode())

    def do_POST(self):
        """接收 LINE Webhook"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 驗證簽名
        signature = self.headers.get("X-Line-Signature", "")
        if CHANNEL_SECRET and not verify_signature(body, signature):
            self.send_response(403)
            self.end_headers()
            return

        # 回 200（LINE 要求 1 秒內回應）
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

        # 處理事件
        try:
            data = json.loads(body.decode("utf-8"))
            events = data.get("events", [])
            print(f"[webhook] received {len(events)} events")

            for event in events:
                print(f"[webhook] event type={event.get('type')}")

                # 加好友或解除封鎖 → 發送歡迎訊息
                if event.get("type") == "follow":
                    reply_token = event.get("replyToken", "")
                    reply_message(reply_token, build_welcome_message())
                    continue

                # 文字訊息
                if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
                    reply_token = event.get("replyToken", "")
                    user_text = event["message"]["text"]
                    print(f"[webhook] user said: {user_text}")
                    messages = handle_text_message(user_text)
                    reply_message(reply_token, messages)

        except Exception as e:
            print(f"[webhook] ERROR: {e}")
            import traceback
            traceback.print_exc()
