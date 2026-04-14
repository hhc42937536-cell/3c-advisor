"""
LINE Bot Webhook — 生活優轉 LifeUturn
=================================
Vercel Serverless Function (Python)
處理所有 LINE 訊息，根據內容路由到不同模組。

目前模組：
  - 3C 推薦（問答式推薦手機/筆電/平板）

未來可擴充：
  - 更多工具模組（只要加 handler 函數就好）
"""

import json
import os
import re
import hashlib
import hmac
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

# ─── LINE 設定（從環境變數讀取）────────────────────
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
# 產品資料來源（你的 GitHub Pages）
PRODUCTS_URL = os.environ.get("PRODUCTS_URL", "https://hhc42937536-cell.github.io/3c-advisor/products.json")
# LINE Bot ID（用於分享邀請連結，格式：@xxxxxxxx，可在 LINE Developers 查到）
LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")  # 開發者 LINE userId，用於接收回饋通知

# ─── Supabase 數據記錄 ────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def log_usage(user_id: str, feature: str, sub_action: str = None, city: str = None, is_success: bool = True):
    """記錄匿名使用統計到 Supabase（不影響用戶體驗，失敗也不中斷）"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        import hashlib
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        data = {"uid_hash": uid_hash, "feature": feature}
        if sub_action: data["sub_action"] = sub_action
        if city:       data["city"] = city
        data["is_success"] = is_success
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/linebot_usage_logs",
            data=body,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"[log] {e}")  # 寫入失敗不影響 bot 正常運作

def _bot_invite_text() -> str:
    """生成 bot 邀請文字（有 ID 就附連結，沒有就純文字）"""
    if LINE_BOT_ID:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{LINE_BOT_ID}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"

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
    if not messages:  # None 或空清單 → 靜默略過（例如 tab: 切換訊息）
        print(f"[reply] SKIPPED: messages is None/empty")
        return
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


def push_message(user_id: str, messages: list):
    """主動推送訊息給用戶（不需要 reply token）"""
    if not messages or not user_id or not CHANNEL_ACCESS_TOKEN:
        return
    data = json.dumps({
        "to": user_id,
        "messages": messages[:5],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[push] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[push] ERROR: {e}")
        if hasattr(e, 'read'):
            print(f"[push] BODY: {e.read().decode('utf-8','ignore')}")


def _broadcast_message(text: str):
    """廣播訊息給所有好友（LINE Messaging API broadcast）"""
    if not CHANNEL_ACCESS_TOKEN:
        return
    data = json.dumps({
        "messages": [{"type": "text", "text": text}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/broadcast",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[broadcast] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[broadcast] ERROR: {e}")
        if hasattr(e, 'read'):
            print(f"[broadcast] BODY: {e.read().decode('utf-8','ignore')}")


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽名"""
    if not CHANNEL_SECRET:
        return True  # 開發模式跳過驗證
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256)
    import base64
    return hmac.compare_digest(base64.b64encode(mac.digest()).decode("utf-8"), signature)


# ─── 3C 推薦模組 ─────────────────────────────────

# 關鍵字 → 裝置類別（laptop 放最前，避免 vivobook 被 vivo(phone) 誤判）
DEVICE_KEYWORDS = {
    "laptop":  ["筆電", "筆記型電腦", "laptop", "notebook", "macbook", "vivobook", "zenbook",
                "thinkpad", "ideapad", "swift", "inspiron", "pavilion",
                "asus", "華碩", "lenovo", "聯想", "hp", "dell", "acer", "宏碁", "msi", "微星"],
    "tablet":  ["平板", "tablet", "ipad", "surface", "galaxy tab", "matepad"],
    "desktop": ["桌機", "桌上型電腦", "桌電", "desktop", "主機", "電腦主機", "組裝電腦"],
    "phone":   ["手機", "phone", "iphone", "三星", "samsung", "galaxy", "pixel", "小米", "redmi",
                "紅米", "oppo", "vivo", "sony", "zenfone", "realme", "motorola"],
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
        # 桌機用 total_price，其他用 price
        price_str = p.get("price") or p.get("total_price", "0")
        price = int(re.sub(r"[^0-9]", "", price_str))
        if 0 < budget < 999999 and price > budget * 1.2:
            continue
        if price < 1000:   # 桌機配件不篩掉（桌機最低約 16000）
            continue

        # 計算匹配分數
        score = 0
        name_lower = (p.get("name", "") + p.get("pros", "")).lower()
        for_user = p.get("for_user", [])  # 桌機用此欄位

        if "拍照" in uses and any(w in name_lower for w in ["鏡頭", "攝影", "相機", "拍照", "pixel", "蔡司"]):
            score += 10
        if "遊戲" in uses:
            if any(w in name_lower for w in ["電競", "rog", "gaming", "rtx", "效能"]):
                score += 10
            if "game" in for_user:
                score += 10
        if "工作" in uses:
            if "work" in for_user:
                score += 8
            if any(w in name_lower for w in ["thinkpad", "商務", "business"]):
                score += 5
        if "創作" in uses:
            if "create" in for_user:
                score += 8
            if any(w in name_lower for w in ["pro", "studio", "create", "creator", "m3", "m4", "rtx"]):
                score += 5
        if "追劇" in uses:
            # OLED 螢幕、大螢幕、音效優先
            if any(w in name_lower for w in ["oled", "amoled", "螢幕", "display", "音效", "dolby"]):
                score += 8
            if price < 20000:   # 追劇不需要太貴
                score += 3
        if "閱讀" in uses:
            # 平板輕薄、長續航優先
            if any(w in name_lower for w in ["mini", "air", "輕", "薄", "slim", "oled"]):
                score += 8
            if price < 25000:
                score += 3
        if "學習" in uses or "學生" in uses:
            if "student" in for_user:
                score += 6
        if "長輩" in uses:
            if "senior" in for_user:
                score += 6
            elif price < 20000:
                score += 5
        if "學生" in uses and price < 35000:
            score += 3
        if "輕薄" in uses and any(w in name_lower for w in ["輕", "薄", "air", "slim"]):
            score += 8
        if "日常" in uses or "一般" in uses:
            if "general" in for_user:
                score += 5
            if budget >= 999999 and price <= 50000:
                score += 2

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
    """建立單個產品的 Flex Message bubble（支援手機/筆電/平板/桌機）"""
    import urllib.parse
    # 桌機用 total_price，其他用 price
    price = p.get("price") or p.get("total_price", "")
    brand = p.get("brand", "")
    name  = p.get("name", "")[:30]
    tag   = p.get("tag", "")
    pros  = p.get("pros", "")[:40]
    cons  = p.get("cons", "")[:30]
    spec_line = spec_to_plain_line(p)
    is_desktop = bool(p.get("total_price") or p.get("motherboard"))

    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank] if rank < 5 else ""
    header_label = "🖥️ 自組推薦配置" if is_desktop else brand

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#8D6E63" if is_desktop else "#FF8C42",
            "contents": [
                {"type": "text", "text": f"{medal} {header_label}", "color": "#FFFFFF",
                 "size": "sm", "weight": "bold"},
                {"type": "text", "text": name, "color": "#FFFFFF",
                 "size": "md", "weight": "bold", "wrap": True},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": price, "size": "xl", "weight": "bold", "color": "#3E2723"},
                {"type": "text", "text": f"📖 {spec_line}", "size": "xs", "color": "#8D6E63", "wrap": True},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"👍 {pros}", "size": "xs", "color": "#4CAF50",
                 "wrap": True, "margin": "md"},
            ]
        },
        "footer": _build_product_footer(p, is_desktop, brand, name)
    }

    if cons and cons != "規格詳見商品頁":
        bubble["body"]["contents"].append(
            {"type": "text", "text": f"⚠️ {cons}", "size": "xs", "color": "#FF9800", "wrap": True}
        )

    return bubble


def _build_product_footer(p: dict, is_desktop: bool, brand: str, name: str) -> dict:
    """產品卡片底部按鈕（桌機和一般產品分開處理）"""
    import urllib.parse
    price = p.get("price") or p.get("total_price", "")
    pros  = p.get("pros", "")[:40]
    device_icon = "🖥️" if is_desktop else ("💻" if any(w in name.lower() for w in ["book","pad","tab"]) else "📱")

    if is_desktop:
        # 桌機：連結到網站配置頁 + 詢問組裝
        website_url = "https://hhc42937536-cell.github.io/3c-advisor/"
        _share_text = (
            f"🖥️ 幫你找到這組桌機配置！\n{name}\n💰 {price}\n👍 {pros}"
            f"{_bot_invite_text()}"
        )
        _share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
        return {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#8D6E63", "height": "sm",
                 "action": {"type": "uri", "label": "🖥️ 查看完整規格建議", "uri": website_url}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "❓ 這配置適合我嗎？",
                            "text": f"這款適合我嗎 桌機 {name}"}},
                {"type": "button", "style": "link", "height": "sm",
                 "action": {"type": "uri", "label": "📤 分享給朋友", "uri": _share_url}},
            ]
        }
    else:
        # 一般產品：四大電商平台
        search_q   = urllib.parse.quote(f"{brand} {name}")
        pchome_url = f"https://ecshweb.pchome.com.tw/search/v3.3/?q={search_q}"
        momo_url   = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={search_q}"
        yahoo_url  = f"https://tw.buy.yahoo.com/search/product?p={search_q}"
        shopee_url = f"https://shopee.tw/search?keyword={search_q}"
        _share_text = (
            f"{device_icon} 幫你找到這款！\n{brand} {name}\n💰 {price}\n👍 {pros}"
            f"{_bot_invite_text()}"
        )
        _share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
        return {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {
                    "type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#0066CC", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "PChome", "uri": pchome_url}},
                        {"type": "button", "style": "primary", "color": "#CC0000", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "momo", "uri": momo_url}},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#6600AA", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "Yahoo!", "uri": yahoo_url}},
                        {"type": "button", "style": "primary", "color": "#EE4D2D", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "蝦皮", "uri": shopee_url}},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                         "action": {"type": "message", "label": "❓ 這款適合我嗎？",
                                    "text": f"這款適合我嗎 {brand} {name}"}},
                        {"type": "button", "style": "link", "flex": 1, "height": "sm",
                         "action": {"type": "uri", "label": "📤 分享", "uri": _share_url}},
                    ]
                },
            ]
        }


def _suitability_verdict(found: dict, device: str) -> tuple:
    """根據產品規格給出適合度評語，回傳 (verdict_text, verdict_color)"""
    if not found:
        return ("告訴我用途，我幫你分析！", "#8D6E63")
    price_str = found.get("price", "NT$0")
    price = int(re.sub(r"[^0-9]", "", price_str) or 0)
    name_lower = (found.get("name","") + found.get("pros","")).lower()
    tag = found.get("tag","")

    # 旗艦高規
    if any(w in name_lower for w in ["m4", "ultra 9", "i9", "rtx 5090", "rtx 5080"]) or price > 60000:
        return ("🏆 旗艦高規，預算夠的話非常值得", "#1565C0")
    # 電競強機
    if any(w in name_lower for w in ["rog", "gaming", "rtx", "電競"]):
        return ("🎮 電競效能強，不打遊戲有點浪費", "#6A1B9A")
    # 高CP值
    if any(w in name_lower for w in ["ultra 5", "ultra 7", "ryzen 7", "i7", "m3"]) and price < 45000:
        return ("⭐ 高CP值，規格與價格都剛好", "#2E7D32")
    # 入門親民
    if price < 12000:
        return ("💰 入門款，預算有限的好選擇", "#E65100")
    # 主流推薦
    return ("👍 主流選擇，大多數人用都沒問題", "#FF8C42")


def _device_checklist(device: str, found: dict) -> list:
    """回傳裝置專屬選購重點（3條 Flex text）"""
    checklists = {
        "phone": [
            "📱 確認記憶體：日常 8GB 夠用，多工/拍影片建議 12GB+",
            "🔋 確認電池：5000mAh 以上才能撐一整天",
            "📸 確認相機：主鏡頭畫素不是唯一重點，看感光元件大小",
        ],
        "laptop": [
            "⚖️ 確認重量：常帶出門建議 1.5kg 以下",
            "🔋 確認電池：實際續航通常比官方數字少 30%",
            "🖥️ 確認螢幕：文書用 FHD 就夠，設計/剪片建議 2K OLED",
        ],
        "tablet": [
            "✏️ 確認觸控筆：Apple Pencil 只相容特定型號，買前確認",
            "📶 確認版本：WiFi 版比 LTE 版便宜約 $3000，看需不需要行動網路",
            "🔌 確認充電：iPad 用 USB-C 還是 Lightning，影響配件選購",
        ],
        "desktop": [
            "🔌 確認電源：確保插座穩壓，建議加 UPS 不斷電系統",
            "🌡️ 確認散熱：主機放置位置需要通風，避免塞在密閉空間",
            "🖥️ 螢幕另計：套裝機通常不含螢幕，記得預留螢幕預算",
        ],
    }
    items = checklists.get(device, checklists["phone"])
    return [{"type": "text", "text": item, "size": "xs", "color": "#555555",
             "wrap": True, "margin": "sm"} for item in items]


def build_suitability_message(product_name: str) -> list:
    """'這款適合我嗎' → 顯示產品分析 + 選購重點 + 引導用途問卷"""
    import urllib.parse

    # 偵測裝置類型
    device = detect_device(product_name)
    device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板", "desktop": "桌機"}.get(device, "產品")

    # 從 products.json 最長前綴比對找產品
    db = load_products()
    found = None
    if device:
        search_lower = product_name.lower()
        best_len = 0
        for p in db.get(device, []):
            p_name = p.get("name", "").lower()
            check_len = min(len(p_name), 40)
            for l in range(check_len, 9, -1):
                if p_name[:l] in search_lower:
                    if l > best_len:
                        best_len = l
                        found = p
                    break

    search_q  = urllib.parse.quote(product_name)
    biggo_url = f"https://biggo.com.tw/s/{search_q}"

    # 適合度評語
    verdict_text, verdict_color = _suitability_verdict(found, device)

    # body 內容
    if found:
        pros  = found.get("pros", "")
        cons  = found.get("cons", "")
        price = found.get("price", "") or found.get("total_price", "")
        tag   = found.get("tag", "")
        budget_val = int(re.sub(r"[^0-9]", "", price) or 30000)
        body_contents = [
            # 價格 + 評語
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": price, "size": "xl", "weight": "bold",
                 "color": "#FF8C42", "flex": 2},
                {"type": "text", "text": tag, "size": "xxs", "color": "#FFFFFF",
                 "backgroundColor": verdict_color, "align": "center",
                 "offsetTop": "4px", "wrap": True, "flex": 3,
                 "adjustMode": "shrink-to-fit"},
            ]},
            # 評語
            {"type": "text", "text": verdict_text, "size": "sm", "weight": "bold",
             "color": verdict_color, "wrap": True, "margin": "sm"},
            {"type": "separator", "margin": "md"},
            # 優缺點
            {"type": "text", "text": "👍 優點", "weight": "bold", "size": "sm",
             "margin": "md", "color": "#2E7D32"},
            {"type": "text", "text": pros or "詳見商品頁", "size": "xs",
             "color": "#4CAF50", "wrap": True},
        ]
        if cons and cons != "規格詳見商品頁":
            body_contents += [
                {"type": "text", "text": "⚠️ 要注意", "weight": "bold", "size": "sm",
                 "margin": "md", "color": "#E65100"},
                {"type": "text", "text": cons, "size": "xs", "color": "#FF9800", "wrap": True},
            ]
        # 選購重點 checklist
        body_contents += [
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": f"📋 買{device_name}前要確認", "weight": "bold",
             "size": "sm", "margin": "md", "color": "#3E2723"},
        ] + _device_checklist(device, found)
    else:
        budget_val = 30000
        body_contents = [
            {"type": "text", "text": verdict_text, "size": "sm", "weight": "bold",
             "color": verdict_color, "wrap": True},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": f"📋 買{device_name}前要確認", "weight": "bold",
             "size": "sm", "margin": "md", "color": "#3E2723"},
        ] + _device_checklist(device, found)

    # 根據裝置類型選用途按鈕
    use_buttons_map = {
        "手機": [("📸 拍照攝影", "拍照"), ("🎮 玩遊戲", "遊戲"), ("📺 追劇看片", "追劇"), ("💼 工作文書", "工作")],
        "筆電": [("💼 工作文書", "工作"), ("🎮 玩遊戲", "遊戲"), ("🎬 影片剪輯", "創作"), ("📚 上課學習", "學習")],
        "平板": [("📖 閱讀", "閱讀"), ("📺 追劇", "追劇"), ("✏️ 繪圖筆記", "創作"), ("📚 學習", "學習")],
        "桌機": [("💼 辦公文書", "工作"), ("🎮 玩遊戲", "遊戲"), ("🎬 影片剪輯", "創作"), ("🏠 家用多功能", "日常")],
    }
    use_btns = use_buttons_map.get(device_name, use_buttons_map["手機"])
    dk = device_name if device_name != "產品" else "手機"
    colors = ["#FF8C42", "#E07838", "#C96830", "#A05820"]

    def _btn(label, use, color):
        return {"type": "button", "style": "primary", "color": color, "flex": 1, "height": "sm",
                "action": {"type": "message", "label": label, "text": f"{dk}|自己|{use}|{budget_val}"}}

    return [{
        "type": "flex", "altText": f"這款適合我嗎？{product_name[:20]}",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#3E2723",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "❓ 這款適合我嗎？", "color": "#FFFFFF",
                     "size": "md", "weight": "bold"},
                    {"type": "text", "text": product_name[:40], "color": "#FFCC80",
                     "size": "xs", "wrap": True, "margin": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "paddingAll": "16px",
                "contents": body_contents
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": f"你買{device_name}主要用來做什麼？",
                     "size": "sm", "weight": "bold", "color": "#3E2723"},
                    {"type": "text", "text": "點選後幫你找同預算內最佳選擇 👇",
                     "size": "xs", "color": "#8D6E63"},
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [_btn(use_btns[0][0], use_btns[0][1], colors[0]),
                                  _btn(use_btns[1][0], use_btns[1][1], colors[1])]},
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [_btn(use_btns[2][0], use_btns[2][1], colors[2]),
                                  _btn(use_btns[3][0], use_btns[3][1], colors[3])]},
                    {"type": "button", "style": "secondary", "height": "sm",
                     "action": {"type": "uri", "label": "💰 BigGo 跨平台比價", "uri": biggo_url}},
                ]
            }
        }
    }]


def build_recommendation_message(device: str, budget: int, uses: list) -> list:
    """根據條件建立推薦回覆"""
    db = load_products()

    # 裝置對應
    device_map = {"phone": "phone", "laptop": "laptop", "tablet": "tablet", "desktop": "desktop"}
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
    device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板", "desktop": "桌機"}.get(device, "產品")
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


# ─── 健康小幫手 ──────────────────────────────────────

def parse_height_weight(text: str):
    """從文字解析身高(cm)和體重(kg)，回傳 (height, weight) 或 (None, None)"""
    m = re.search(r'(\d{2,3})\s*(?:cm|公分)', text, re.I)
    h = float(m.group(1)) if m else None
    m2 = re.search(r'(\d{2,3}(?:\.\d)?)\s*(?:kg|公斤|公)', text, re.I)
    w = float(m2.group(1)) if m2 else None
    if not h:
        m = re.search(r'身高\s*(\d{2,3})', text)
        h = float(m.group(1)) if m else None
    if not w:
        m2 = re.search(r'體重\s*(\d{2,3})', text)
        w = float(m2.group(1)) if m2 else None
    if not h or not w:
        nums = re.findall(r'\d+(?:\.\d)?', text)
        if len(nums) >= 2:
            a, b = float(nums[0]), float(nums[1])
            if 100 <= a <= 220 and 20 <= b <= 200:
                h, w = a, b
    return h, w


def build_bmi_flex(height: float, weight: float) -> list:
    bmi = round(weight / ((height / 100) ** 2), 1)
    if bmi < 18.5:
        status, bmi_color = "體重過輕 😟", "#1565C0"
        advice = "建議增加蛋白質攝取（蛋、雞胸肉、豆腐），每週做 2-3 次重量訓練增肌。"
    elif bmi < 24:
        status, bmi_color = "體重正常 ✅", "#43A047"
        advice = "繼續保持！每週 150 分鐘有氧運動 + 均衡飲食，維持現況最重要。"
    elif bmi < 27:
        status, bmi_color = "體重過重 ⚠️", "#F9A825"
        advice = "建議每天減少 300-500 大卡攝取，多走路爬樓梯。循序漸進比激烈節食有效。"
    elif bmi < 30:
        status, bmi_color = "輕度肥胖 🔴", "#FF6B35"
        advice = "建議諮詢營養師制定飲食計畫，配合有氧運動（走路/游泳/騎車）。"
    else:
        status, bmi_color = "中重度肥胖 🚨", "#C62828"
        advice = "建議諮詢醫師評估健康風險，可考慮專業減重門診協助。"

    ideal_low  = round(18.5 * (height / 100) ** 2, 1)
    ideal_high = round(24   * (height / 100) ** 2, 1)
    ACCENT = "#43A047"

    return [{"type": "flex", "altText": f"BMI 計算結果：{bmi}", "contents": {
        "type": "bubble",
        "header": {"type": "box", "layout": "horizontal",
                   "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                   "contents": [
                       {"type": "image",
                        "url": "https://3c-advisor.vercel.app/liff/images/dumbbell.jpg",
                        "flex": 0, "size": "72px",
                        "aspectRatio": "1:1", "aspectMode": "fit"},
                       {"type": "box", "layout": "vertical", "width": "4px",
                        "cornerRadius": "4px", "backgroundColor": ACCENT,
                        "margin": "md", "contents": []},
                       {"type": "box", "layout": "vertical", "flex": 1,
                        "paddingStart": "12px", "contents": [
                            {"type": "text", "text": "💪 BMI 健康分析",
                             "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            {"type": "text", "text": f"身高 {int(height)} cm｜體重 {weight} kg",
                             "color": "#8892B0", "size": "xs", "margin": "xs"},
                        ]},
                   ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "md",
                 "backgroundColor": "#FFFFFF",
                 "contents": [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "BMI 指數", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": str(bmi), "size": "xxl", "weight": "bold",
                 "color": bmi_color, "flex": 1, "align": "end"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "健康狀態", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": status, "size": "sm", "weight": "bold",
                 "color": bmi_color, "flex": 3, "align": "end", "wrap": True},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "理想體重", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": f"{ideal_low}～{ideal_high} kg",
                 "size": "sm", "color": ACCENT, "flex": 3, "align": "end"},
            ]},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": "💡 建議", "weight": "bold", "size": "sm", "color": "#1A1F3A"},
            {"type": "text", "text": advice, "size": "xs", "color": "#555555", "wrap": True},
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                   "backgroundColor": "#FFFFFF",
                   "contents": [
            {"type": "button", "style": "primary", "color": ACCENT, "height": "sm",
             "action": {"type": "message", "label": "🥗 健康減重方法", "text": "減肥方法"}},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "😴 改善睡眠", "text": "睡眠改善"}},
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "🍽️ 健康吃什麼", "text": "吃什麼 輕食"}},
            ]},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📤 分享 BMI 結果給朋友",
                        "uri": "https://line.me/R/share?text=" + urllib.parse.quote(
                            f"💪 我的 BMI 是 {bmi}（{status}）\n"
                            f"理想體重：{ideal_low}～{ideal_high} kg\n\n"
                            f"用「生活優轉」幫你算算！"
                        )}},
        ]},
    }}]


def build_sleep_advice() -> list:
    return [{"type":"flex","altText":"睡眠改善指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#1A237E","contents":[
            {"type":"text","text":"😴 睡眠改善指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"科學方法讓你一覺好眠","color":"#C5CAE9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"🌙 睡前 1 小時","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 手機調暗或開護眼模式\n• 避免咖啡、茶、可樂\n• 洗溫水澡（37-40°C）幫助放鬆","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🛏️ 臥室環境","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 溫度 18-22°C 最易入睡\n• 完全遮光（眼罩或遮光窗簾）\n• 可用白噪音 App 或風扇聲","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"⏰ 最關鍵的習慣","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 固定時間起床（包括週末！）\n• 下午 3 點後避免午睡超過 20 分鐘\n• 睡前焦慮→寫「明天待辦清單」清空腦袋","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🚨 要看醫生的情況","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"超過 3 週還是睡不好、打呼嚴重（可能睡眠呼吸中止症）→ 建議看家醫科或睡眠門診","size":"xs","color":"#C62828","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1A237E","height":"sm",
             "action":{"type":"message","label":"😰 壓力大怎麼辦？","text":"壓力紓解"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🏃 運動建議","text":"減肥方法"}},
        ]}
    }}]


def build_diet_advice() -> list:
    return [{"type":"flex","altText":"健康減重指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#2E7D32","contents":[
            {"type":"text","text":"🥗 健康減重指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"不節食也能瘦，科學方法最有效","color":"#C8E6C9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"📐 核心觀念：熱量赤字","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"每天少吃 300-500 大卡 = 每週減 0.3-0.5 公斤\n太快減反而掉肌肉、容易復胖","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🍽️ 飲食原則","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"✅ 優先吃：蛋白質（雞胸/豆腐/蛋）、蔬菜、全穀\n❌ 少吃：含糖飲料、精緻澱粉、油炸物\n💡 技巧：先吃蔬菜和蛋白質，最後才吃飯","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🏃 運動選擇","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"初學者：每天快走 30 分鐘就夠了！\n進階：有氧（燃脂）+ 重訓（維持肌肉）\n最重要的運動：你能持續做的那種","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"❌ 常見錯誤","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"• 不吃早餐（讓你下午更餓亂吃）\n• 只靠運動不控飲食（效果很慢）\n• 喝代餐（停喝就復胖）","size":"xs","color":"#C62828","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#2E7D32","height":"sm",
             "action":{"type":"message","label":"📊 幫我算 BMI","text":"幫我算BMI"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"😴 睡眠改善","text":"睡眠改善"}},
        ]}
    }}]


def build_stress_advice() -> list:
    return [{"type":"flex","altText":"壓力紓解指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#6A1B9A","contents":[
            {"type":"text","text":"😰 壓力紓解指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"科學方法讓你找回平靜","color":"#E1BEE7","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"⚡ 立即舒緩（5 分鐘內）","weight":"bold","size":"sm","color":"#6A1B9A"},
            {"type":"text","text":"• 4-7-8 呼吸法：吸氣4秒→憋氣7秒→呼氣8秒，做 3 次\n• 走到戶外吹風 5 分鐘\n• 喝一杯溫開水","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"📅 長期習慣","weight":"bold","size":"sm","color":"#6A1B9A"},
            {"type":"text","text":"• 每天 30 分鐘運動（最強壓力解藥）\n• 睡前寫「3 件今天的好事」\n• 限制看新聞/社群的時間","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🆘 需要專業協助的情況","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"持續 2 週以上的憂鬱、焦慮、失眠影響生活 → 建議諮詢身心科或心理師\n\n📞 安心專線：1925（24小時免費）","size":"xs","color":"#C62828","wrap":True},
        ]}
    }}]


# ── 食物熱量資料庫（台灣常見外食，每份 kcal）──
_CALORIE_DB = {
    # 飯麵主食
    "白飯": {"cal": 280, "unit": "一碗", "note": "約200g"},
    "滷肉飯": {"cal": 510, "unit": "一碗", "note": "含肥肉燥"},
    "雞肉飯": {"cal": 380, "unit": "一碗", "note": "嘉義式"},
    "牛肉麵": {"cal": 550, "unit": "一碗", "note": "紅燒"},
    "排骨便當": {"cal": 780, "unit": "一個", "note": "炸排骨＋三菜"},
    "雞腿便當": {"cal": 820, "unit": "一個", "note": "炸雞腿＋三菜"},
    "控肉飯": {"cal": 580, "unit": "一碗", "note": "滷五花"},
    "乾麵": {"cal": 380, "unit": "一碗", "note": "加肉燥"},
    "水餃": {"cal": 450, "unit": "10顆", "note": "高麗菜豬肉"},
    "鍋貼": {"cal": 520, "unit": "10顆", "note": "煎的比水餃高"},
    "炒飯": {"cal": 620, "unit": "一盤", "note": "蛋炒飯"},
    "拉麵": {"cal": 650, "unit": "一碗", "note": "豚骨"},
    "鍋燒意麵": {"cal": 480, "unit": "一碗", "note": ""},
    "涼麵": {"cal": 430, "unit": "一盤", "note": "含麻醬"},
    "肉粽": {"cal": 520, "unit": "一顆", "note": "南部粽"},
    "碗粿": {"cal": 320, "unit": "一碗", "note": ""},
    "米粉湯": {"cal": 350, "unit": "一碗", "note": ""},
    # 小吃
    "蚵仔煎": {"cal": 480, "unit": "一份", "note": "含醬料"},
    "臭豆腐": {"cal": 400, "unit": "一份", "note": "炸的"},
    "鹽酥雞": {"cal": 550, "unit": "一份", "note": "約200g"},
    "蔥油餅": {"cal": 350, "unit": "一片", "note": "加蛋"},
    "割包": {"cal": 380, "unit": "一個", "note": ""},
    "肉圓": {"cal": 320, "unit": "一顆", "note": "彰化炸的"},
    "麵線": {"cal": 350, "unit": "一碗", "note": "大腸麵線"},
    "胡椒餅": {"cal": 380, "unit": "一個", "note": ""},
    "蛋餅": {"cal": 280, "unit": "一份", "note": "原味"},
    "飯糰": {"cal": 420, "unit": "一個", "note": "傳統"},
    "蘿蔔糕": {"cal": 220, "unit": "一份", "note": "煎的"},
    "滷味": {"cal": 350, "unit": "一份", "note": "中份"},
    # 飲料
    "珍珠奶茶": {"cal": 650, "unit": "一杯700ml", "note": "全糖"},
    "珍奶": {"cal": 650, "unit": "一杯700ml", "note": "全糖"},
    "奶茶": {"cal": 380, "unit": "一杯700ml", "note": "全糖"},
    "紅茶": {"cal": 200, "unit": "一杯700ml", "note": "半糖"},
    "綠茶": {"cal": 150, "unit": "一杯700ml", "note": "半糖"},
    "美式咖啡": {"cal": 10, "unit": "一杯", "note": "黑咖啡"},
    "拿鐵": {"cal": 180, "unit": "一杯", "note": "全脂鮮奶"},
    "豆漿": {"cal": 120, "unit": "一杯", "note": "無糖"},
    "可樂": {"cal": 140, "unit": "一罐330ml", "note": ""},
    "啤酒": {"cal": 150, "unit": "一罐330ml", "note": ""},
    # 其他
    "薑母鴨": {"cal": 800, "unit": "一人份", "note": "含湯底"},
    "火鍋": {"cal": 700, "unit": "一人份", "note": "不含飲料"},
    "韓式炸雞": {"cal": 600, "unit": "一份", "note": ""},
    "燒肉": {"cal": 750, "unit": "一人份", "note": "吃到飽約1200"},
    "披薩": {"cal": 280, "unit": "一片", "note": ""},
    "漢堡": {"cal": 520, "unit": "一個", "note": "速食店"},
    "薯條": {"cal": 380, "unit": "中份", "note": ""},
    "雞排": {"cal": 630, "unit": "一片", "note": "夜市大雞排"},
}


def build_calorie_result(query: str) -> list:
    """查詢食物熱量"""
    query_clean = query.replace("熱量", "").replace("卡路里", "").replace("多少", "").strip()
    # 模糊搜尋
    matches = []
    for name, info in _CALORIE_DB.items():
        if query_clean in name or name in query_clean:
            matches.append((name, info))
    if not matches:
        # 嘗試部分匹配
        for name, info in _CALORIE_DB.items():
            if any(c in name for c in query_clean if len(c.strip()) > 0):
                matches.append((name, info))

    if not matches:
        return [{"type": "text", "text": f"🔍 找不到「{query_clean}」的熱量資料\n\n"
                 "試試看這些關鍵字：\n"
                 "• 主食：滷肉飯、牛肉麵、排骨便當\n"
                 "• 小吃：蚵仔煎、鹽酥雞、雞排\n"
                 "• 飲料：珍珠奶茶、拿鐵、豆漿\n\n"
                 "或直接問「珍奶熱量多少」"}]

    items = []
    for name, info in matches[:5]:
        cal = info["cal"]
        # 換算需要運動多久消耗（慢跑 8kcal/min）
        run_min = round(cal / 8)
        bar_len = min(cal // 50, 12)
        bar = "🟩" * min(bar_len, 5) + "🟨" * min(max(bar_len - 5, 0), 4) + "🟥" * max(bar_len - 9, 0)
        note = f"（{info['note']}）" if info.get("note") else ""
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"🍽️ {name}", "weight": "bold",
                 "size": "md", "color": "#2E7D32", "flex": 3},
                {"type": "text", "text": f"{cal} kcal", "weight": "bold",
                 "size": "md", "color": "#C62828", "flex": 2, "align": "end"},
            ]},
            {"type": "text", "text": f"{info['unit']}{note}", "size": "xs",
             "color": "#888888", "margin": "xs"},
            {"type": "text", "text": bar, "size": "xs", "margin": "xs"},
            {"type": "text", "text": f"🏃 需慢跑約 {run_min} 分鐘消耗", "size": "xs",
             "color": "#555555", "margin": "xs"},
        ]
        if len(matches) > 1:
            items.append({"type": "separator", "margin": "md"})

    return [{"type": "flex", "altText": f"食物熱量查詢",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#2E7D32",
                            "contents": [
                                {"type": "text", "text": "🔥 食物熱量查詢",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "text", "text": "💡 小提示：微糖 = 全糖的70%熱量、去冰不影響熱量",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]


# ── 運動消耗計算（每分鐘 kcal，以 60kg 為基準）──
_EXERCISE_DB = {
    "跑步": 10, "慢跑": 8, "快走": 5, "走路": 3.5, "散步": 3,
    "游泳": 9, "騎車": 7, "腳踏車": 7, "自行車": 7,
    "瑜珈": 4, "重訓": 6, "健身": 6, "有氧": 7,
    "籃球": 8, "羽球": 7, "桌球": 5, "網球": 8,
    "跳繩": 11, "拳擊": 10, "爬山": 7, "登山": 7,
    "爬樓梯": 8, "跳舞": 6, "打掃": 3.5, "拖地": 3,
    "棒球": 5, "足球": 8, "排球": 5,
}


def build_exercise_result(text: str) -> list:
    """計算運動消耗熱量"""
    # 解析運動類型
    exercise = ""
    cal_per_min = 0
    for name, cpm in _EXERCISE_DB.items():
        if name in text:
            exercise = name
            cal_per_min = cpm
            break
    if not exercise:
        return [{"type": "text", "text": "🏃 支援的運動類型：\n\n"
                 "• 有氧：跑步、慢跑、快走、游泳、騎車、跳繩\n"
                 "• 球類：籃球、羽球、網球、排球\n"
                 "• 其他：瑜珈、重訓、爬山、跳舞\n\n"
                 "輸入格式：「跑步 30分鐘」或「游泳 1小時」"}]

    # 解析時間
    minutes = 30  # 預設
    m = re.search(r'(\d+)\s*分', text)
    if m:
        minutes = int(m.group(1))
    else:
        m2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:小時|hr)', text, re.I)
        if m2:
            minutes = int(float(m2.group(1)) * 60)

    total_cal = round(cal_per_min * minutes)
    # 換算食物
    food_equiv = []
    if total_cal >= 650:
        food_equiv.append("一杯全糖珍奶 🧋")
    elif total_cal >= 500:
        food_equiv.append("一個排骨便當 🍱")
    elif total_cal >= 350:
        food_equiv.append("一碗滷肉飯 🍚")
    elif total_cal >= 200:
        food_equiv.append("一杯拿鐵 ☕")
    else:
        food_equiv.append("一份蘿蔔糕 🥞")

    return [{"type": "flex", "altText": f"運動消耗：{exercise} {minutes}分鐘",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#1565C0",
                            "contents": [
                                {"type": "text", "text": f"🏃 運動熱量消耗",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": exercise, "size": "lg", "weight": "bold",
                          "color": "#1565C0", "flex": 2},
                         {"type": "text", "text": f"{minutes} 分鐘", "size": "lg",
                          "color": "#333333", "flex": 2, "align": "end"},
                     ]},
                     {"type": "separator"},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "消耗熱量", "size": "sm", "color": "#888888", "flex": 2},
                         {"type": "text", "text": f"🔥 {total_cal} kcal", "size": "md",
                          "weight": "bold", "color": "#C62828", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "約等於吃掉", "size": "sm", "color": "#888888", "flex": 2},
                         {"type": "text", "text": food_equiv[0], "size": "sm",
                          "color": "#555555", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "每分鐘消耗", "size": "xs", "color": "#AAAAAA", "flex": 2},
                         {"type": "text", "text": f"{cal_per_min} kcal/min（以60kg計）", "size": "xs",
                          "color": "#AAAAAA", "flex": 3, "align": "end"},
                     ]},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💡 體重越重消耗越高，此為 60kg 估算值",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]


def build_water_intake(weight: float) -> list:
    """每日建議喝水量"""
    ml = round(weight * 30)
    cups = round(ml / 250)
    return [{"type": "flex", "altText": f"每日喝水量建議",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#0288D1",
                            "contents": [
                                {"type": "text", "text": "💧 每日喝水量建議",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "text", "text": f"體重 {weight:.0f} kg", "size": "sm", "color": "#888888"},
                     {"type": "text", "text": f"💧 建議每日 {ml:,} ml", "size": "lg",
                      "weight": "bold", "color": "#0288D1"},
                     {"type": "text", "text": f"約 {cups} 杯水（250ml/杯）", "size": "sm", "color": "#555555"},
                     {"type": "separator"},
                     {"type": "text", "text": "⏰ 建議分配：\n"
                      "• 起床：250ml\n• 上午：500ml\n• 午餐前：250ml\n"
                      "• 下午：500ml\n• 晚餐前：250ml\n• 睡前少量",
                      "size": "xs", "color": "#555555", "wrap": True},
                 ]},
             }}]


def build_health_menu() -> list:
    ACCENT = "#43A047"
    return [{"type": "flex", "altText": "健康小幫手",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "image",
                                 "url": "https://3c-advisor.vercel.app/liff/images/dumbbell.jpg",
                                 "flex": 0, "size": "72px",
                                 "aspectRatio": "1:1", "aspectMode": "fit"},
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": ACCENT,
                                 "margin": "md", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "💪 健康小幫手",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "你的隨身健康顧問",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "想了解什麼？直接問或點下方 👇",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "📊 BMI", "text": "幫我算BMI"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔥 食物熱量", "text": "食物熱量查詢"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動消耗", "text": "運動消耗計算"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💧 喝水量", "text": "每日喝水量"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🥗 減重", "text": "減肥方法"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "😴 睡眠", "text": "睡眠改善"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "😰 壓力紓解", "text": "壓力紓解"}},
                 ]},
             }}]


def build_health_message(text: str) -> list:
    """健康小幫手主路由"""
    # ── 食物熱量查詢 ──
    if any(w in text for w in ["熱量", "卡路里", "幾卡", "幾大卡"]):
        return build_calorie_result(text)
    if "食物熱量" in text:
        return [{"type": "text", "text": "🔥 輸入食物名稱查熱量\n\n"
                 "例如：\n「珍珠奶茶熱量」\n「排骨便當幾卡」\n「雞排熱量多少」"}]

    # ── 運動消耗計算 ──
    if any(w in text for w in ["運動消耗", "運動熱量"]):
        return build_exercise_result(text)
    has_exercise = any(ex in text for ex in _EXERCISE_DB.keys())
    has_time = bool(re.search(r'\d+\s*(?:分|小時|hr)', text, re.I))
    if has_exercise and has_time:
        return build_exercise_result(text)

    # ── 喝水量 ──
    if "喝水" in text:
        m = re.search(r'(\d{2,3}(?:\.\d)?)\s*(?:kg|公斤)', text, re.I)
        if m:
            return build_water_intake(float(m.group(1)))
        m2 = re.search(r'體重\s*(\d{2,3})', text)
        if m2:
            return build_water_intake(float(m2.group(1)))
        return [{"type": "text", "text": "💧 請告訴我你的體重\n\n例如：「喝水 65公斤」"}]

    # ── BMI ──
    height, weight = parse_height_weight(text)
    if height and weight and 100 <= height <= 220 and 20 <= weight <= 200:
        return build_bmi_flex(height, weight)
    if any(w in text for w in ["bmi", "BMI", "幫我算", "算一下"]):
        return [{"type":"text","text":"請告訴我你的身高和體重 😊\n\n例如：\n「我身高 170cm，體重 75kg」\n「170公分 65公斤」"}]

    # ── 其他 ──
    if any(w in text for w in ["失眠", "睡不著", "睡不好", "睡眠", "一直醒"]):
        return build_sleep_advice()
    if any(w in text for w in ["減肥", "瘦身", "減重", "變瘦", "肥胖"]):
        return build_diet_advice()
    if any(w in text for w in ["壓力", "焦慮", "心情不好", "很煩", "紓壓"]):
        return build_stress_advice()
    return build_health_menu()


# ─── 金錢小幫手 ──────────────────────────────────────

def build_budget_plan(salary: int) -> list:
    need = int(salary * 0.5)
    want = int(salary * 0.3)
    save = int(salary * 0.2)
    return [{"type":"flex","altText":f"月薪 {salary:,} 預算規劃","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#E65100","contents":[
            {"type":"text","text":"💰 月薪預算規劃","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":f"月薪 NT${salary:,} — 50/30/20 法則","color":"#FFE0B2","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"md","contents":[
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"🏠 必要支出 50%","weight":"bold","size":"sm","color":"#C62828","flex":3},
                {"type":"text","text":f"NT${need:,}","size":"lg","weight":"bold","color":"#C62828","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"房租、水電、三餐、交通、基本保險","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"🎉 享樂支出 30%","weight":"bold","size":"sm","color":"#E65100","flex":3},
                {"type":"text","text":f"NT${want:,}","size":"lg","weight":"bold","color":"#E65100","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"娛樂、購物、外食、旅遊","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"💎 儲蓄/投資 20%","weight":"bold","size":"sm","color":"#2E7D32","flex":3},
                {"type":"text","text":f"NT${save:,}","size":"lg","weight":"bold","color":"#2E7D32","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"緊急備用金 → 定期定額 ETF → 目標存款","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"text","text":"💡 最有效的存錢方法","weight":"bold","size":"sm","color":"#3E2723"},
            {"type":"text","text":f"薪水入帳當天，馬上轉 NT${save:,} 到另一個帳戶，剩下的才用於生活。\n\n🎯 第一目標：存滿 NT${save*6:,}（6個月緊急備用金）","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1565C0","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 保險要買哪些？","text":"保險建議"}},
        ]}
    }}]


CREDIT_CARDS_DB = {
    "現金回饋": [
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付/網購/外送 6%", "tags":["行動支付","網購","外送"]},
        {"bank":"滙豐", "name":"Live+現金回饋卡", "fee":"首年免，次年NT$2,000", "cashback":"國內4.88%、海外5.88%", "tags":["海外","通用"]},
        {"bank":"玉山", "name":"U Bear信用卡", "fee":"首年免，次年NT$3,000", "cashback":"影音訂閱/網購 10%", "tags":["網購","影音訂閱"]},
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"海外/網購最高7.5%", "tags":["海外","網購"]},
        {"bank":"永豐", "name":"幣倍卡", "fee":"首年免，次年NT$3,000", "cashback":"海外10%、國內5%", "tags":["海外","通用"]},
        {"bank":"永豐", "name":"DAWAY卡", "fee":"首年免，次年NT$3,000", "cashback":"LINE Pay 最高6%", "tags":["行動支付","LINE Pay"]},
        {"bank":"遠東商銀", "name":"快樂信用卡", "fee":"首年免，次年NT$2,000", "cashback":"悠遊加值5%、通用2%", "tags":["交通","大眾運輸"]},
        {"bank":"遠東商銀", "name":"遠東樂家+卡", "fee":"首年免，次年NT$2,000", "cashback":"寵物/親子商店最高10%", "tags":["親子","寵物","生活"]},
        {"bank":"第一銀行", "name":"iLEO卡", "fee":"首年免，次年NT$1,200", "cashback":"海外/行動支付最高13%", "tags":["海外","行動支付"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"行動支付3.8%、加油3.3%", "tags":["行動支付","加油"]},
        {"bank":"玉山", "name":"Pi拍錢包信用卡", "fee":"首年免，次年NT$3,000", "cashback":"Pi幣回饋最高5%、保費有回饋", "tags":["通用","保費"]},
    ],
    "網購外送": [
        {"bank":"中國信託", "name":"foodpanda卡", "fee":"首年免，次年NT$1,800", "cashback":"外送平台最高30%", "tags":["外送","餐飲"]},
        {"bank":"中國信託", "name":"LINE Pay卡", "fee":"條件免年費", "cashback":"指定商店最高16%、韓國30%", "tags":["行動支付","海外"]},
        {"bank":"玉山", "name":"U Bear信用卡", "fee":"首年免，次年NT$3,000", "cashback":"影音/網購10%", "tags":["網購","影音訂閱"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付/網購/外送6%", "tags":["外送","網購"]},
    ],
    "加油交通": [
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"加油最高7.5%", "tags":["加油"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付加油6%", "tags":["加油","行動支付"]},
        {"bank":"遠東商銀", "name":"快樂信用卡", "fee":"首年免，次年NT$2,000", "cashback":"悠遊加值5%", "tags":["大眾運輸","悠遊卡"]},
        {"bank":"遠東商銀", "name":"遠東樂行卡", "fee":"首年免，次年NT$2,000", "cashback":"計程車/Uber 3%、加油折扣", "tags":["計程車","Uber","加油"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"加油3.3%", "tags":["加油"]},
    ],
    "海外旅遊": [
        {"bank":"滙豐", "name":"Live+現金回饋卡", "fee":"首年免，次年NT$2,000", "cashback":"海外5.88%現金回饋", "tags":["海外","旅遊"]},
        {"bank":"永豐", "name":"幣倍卡", "fee":"首年免，次年NT$3,000", "cashback":"海外10%雙幣無手續費", "tags":["海外","旅遊"]},
        {"bank":"第一銀行", "name":"iLEO卡", "fee":"首年免，次年NT$1,200", "cashback":"海外最高13%", "tags":["海外"]},
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"海外7.5%", "tags":["海外","旅遊"]},
        {"bank":"第一銀行", "name":"御璽商旅卡", "fee":"條件免，次年NT$2,000", "cashback":"旅遊15%、海外3%", "tags":["旅遊","商務"]},
    ],
    "餐飲美食": [
        {"bank":"中國信託", "name":"foodpanda卡", "fee":"首年免，次年NT$1,800", "cashback":"外送30%、餐飲5%", "tags":["外送","餐飲"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付餐飲6%", "tags":["餐飲","行動支付"]},
        {"bank":"第一銀行", "name":"一卡通聯名卡", "fee":"首年免，次年NT$300", "cashback":"早餐店最高5%、超商3.5%", "tags":["早餐","超商"]},
    ],
    "保費繳稅": [
        {"bank":"永豐", "name":"保倍卡", "fee":"首年免，次年NT$3,000", "cashback":"保費1.2%無上限現金回饋", "tags":["保費"]},
        {"bank":"玉山", "name":"Pi拍錢包信用卡", "fee":"首年免，次年NT$3,000", "cashback":"保費有Pi幣回饋", "tags":["保費"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"保費/繳稅有回饋", "tags":["保費","繳稅"]},
    ],
}

_CC_CATEGORY_EMOJI = {
    "現金回饋": "💰",
    "網購外送": "🛒",
    "加油交通": "⛽",
    "海外旅遊": "✈️",
    "餐飲美食": "🍽️",
    "保費繳稅": "📋",
}


def build_credit_card_menu() -> list:
    # 每個類別各自顏色
    _CC_COLORS = {
        "現金回饋": "#E65100", "網購外送": "#AD1457",
        "加油交通": "#1565C0", "海外旅遊": "#00695C",
        "餐飲美食": "#6A1B9A", "保費繳稅": "#37474F",
    }
    # 2 欄 3 行排列
    cats = list(_CC_CATEGORY_EMOJI.items())
    rows = []
    for i in range(0, len(cats), 2):
        pair = cats[i:i+2]
        row_items = []
        for cat, emoji in pair:
            color = _CC_COLORS.get(cat, "#1565C0")
            row_items.append({
                "type": "box", "layout": "vertical",
                "flex": 1, "spacing": "xs",
                "backgroundColor": color,
                "cornerRadius": "12px",
                "paddingAll": "14px",
                "action": {"type": "message", "label": f"{emoji} {cat}", "text": f"信用卡推薦:{cat}"},
                "contents": [
                    {"type": "text", "text": emoji, "size": "xxl", "align": "center"},
                    {"type": "text", "text": cat, "color": "#FFFFFF", "size": "sm",
                     "weight": "bold", "align": "center", "margin": "sm"},
                ]
            })
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row_items})

    return [{"type": "flex", "altText": "💳 信用卡推薦比較", "contents": {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#0D47A1", "paddingAll": "16px",
                   "contents": [
            {"type": "text", "text": "💳 信用卡推薦", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
            {"type": "text", "text": "選你最常刷的類別，推最划算的卡", "color": "#90CAF9",
             "size": "xs", "margin": "sm"},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "paddingAll": "14px",
                 "contents": rows},
    }}]


def build_credit_card_result(category: str) -> list:
    category = category.strip()
    print(f"[cc_result] category={repr(category)}")
    cards = CREDIT_CARDS_DB.get(category, [])[:4]
    if not cards:
        return [{"type": "text", "text": f"找不到「{category}」的信用卡資料，請重新選擇類別。"}]
    emoji = _CC_CATEGORY_EMOJI.get(category, "💳")
    bubbles = []
    for card in cards:
        tags_text = "  ".join(f"#{t}" for t in card.get("tags", []))
        apply_url = (f"https://www.google.com/search?q="
                     + urllib.parse.quote(f"{card['bank']} {card['name']} 申辦"))
        bubbles.append({
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "vertical",
                       "backgroundColor": "#1565C0", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": card["bank"],
                            "color": "#90CAF9", "size": "xs"},
                           {"type": "text", "text": card["name"],
                            "color": "#FFFFFF", "size": "md",
                            "weight": "bold", "wrap": True},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                     "paddingAll": "14px", "contents": [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": "💰 回饋", "size": "xs",
                     "color": "#888888", "flex": 2},
                    {"type": "text", "text": card["cashback"], "size": "sm",
                     "weight": "bold", "color": "#0D47A1",
                     "flex": 5, "wrap": True},
                ]},
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": "📅 年費", "size": "xs",
                     "color": "#888888", "flex": 2},
                    {"type": "text", "text": card["fee"], "size": "xs",
                     "color": "#555555", "flex": 5, "wrap": True},
                ]},
                {"type": "text", "text": tags_text, "size": "xxs",
                 "color": "#1565C0", "wrap": True, "margin": "sm"},
            ]},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "10px",
                       "contents": [
                {"type": "button", "style": "primary", "color": "#1565C0",
                 "height": "sm",
                 "action": {"type": "uri", "label": "🔍 Google 搜尋申辦",
                            "uri": apply_url}},
            ]},
        })

    return [{"type": "flex", "altText": f"{emoji} {category} 推薦信用卡",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_credit_card_advice() -> list:
    return build_credit_card_menu()


def build_insurance_guide() -> list:
    return [{"type":"flex","altText":"保險購買指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#4527A0","contents":[
            {"type":"text","text":"🛡️ 保險購買指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"哪些必買？哪些不必要？","color":"#D1C4E9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"✅ 這 4 種最值得買","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"① 🏥 實支實付醫療險 — 住院手術費用報銷\n② 💪 意外險 — 便宜但保障高\n③ 🎗️ 重大疾病險 — 癌症/心臟病治療費\n④ ☠️ 定期壽險 — 有家人依賴才需要","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"⚠️ 這些先不用急著買","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"• 儲蓄險（報酬率不如 ETF）\n• 投資型保單（費用高、結構複雜）\n• 終身壽險（非常貴、不划算）","size":"xs","color":"#E65100","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"💡 新鮮人保險購買順序","weight":"bold","size":"sm","color":"#4527A0"},
            {"type":"text","text":"① 先存緊急備用金（3-6 個月支出）\n② 買意外險（最便宜，先保基本）\n③ 買實支實付醫療險\n④ 有穩定收入後考慮重大疾病險\n\n💰 預算參考：月薪 10% 以內用於保費","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#4527A0","height":"sm",
             "action":{"type":"message","label":"💰 月薪預算規劃","text":"存錢方法"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
        ]}
    }}]


def build_saving_tips() -> list:
    return [{"type":"flex","altText":"存錢方法大全","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#E65100","contents":[
            {"type":"text","text":"💰 存錢方法大全","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"讓錢自動幫你存","color":"#FFE0B2","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"🥇 最有效：先存後花","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"薪水入帳當天，馬上轉 20% 到另一個帳戶（高利活存），剩下才用於生活。\n👉 設定「自動轉帳」，連想都不用想","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"📱 記帳 App 推薦","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"• Moneybook 記帳城市（台灣人最愛）\n• CWMoney（介面簡單好上手）\n• 麻布記帳（可連結銀行自動匯入）\n\n記帳是讓你知道錢去哪了，不是讓你痛苦的","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🎯 3 個存錢目標","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"① 緊急備用金：3-6 個月薪水\n② 定期定額 ETF（0050/00878）\n③ 短期目標：旅遊基金、換手機基金","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1565C0","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 要買哪些保險？","text":"保險建議"}},
        ]}
    }}]


_CURRENCY_NAMES = {
    "USD": "🇺🇸 美元", "JPY": "🇯🇵 日圓", "EUR": "🇪🇺 歐元",
    "GBP": "🇬🇧 英鎊", "AUD": "🇦🇺 澳幣", "CAD": "🇨🇦 加幣",
    "HKD": "🇭🇰 港幣", "SGD": "🇸🇬 新幣", "CHF": "🇨🇭 瑞士法郎",
    "CNY": "🇨🇳 人民幣", "KRW": "🇰🇷 韓元", "THB": "🇹🇭 泰銖",
    "SEK": "🇸🇪 瑞典克朗", "NZD": "🇳🇿 紐幣", "ZAR": "🇿🇦 南非幣",
    "MYR": "🇲🇾 馬幣", "PHP": "🇵🇭 菲律賓比索", "IDR": "🇮🇩 印尼盾",
    "VND": "🇻🇳 越南盾",
}
_CURRENCY_ALIAS = {
    "美元": "USD", "美金": "USD", "usd": "USD",
    "日圓": "JPY", "日幣": "JPY", "日元": "JPY", "jpy": "JPY",
    "歐元": "EUR", "eur": "EUR",
    "英鎊": "GBP", "gbp": "GBP",
    "澳幣": "AUD", "aud": "AUD",
    "港幣": "HKD", "hkd": "HKD",
    "人民幣": "CNY", "cny": "CNY", "rmb": "CNY",
    "韓元": "KRW", "韓幣": "KRW", "krw": "KRW",
    "泰銖": "THB", "thb": "THB",
    "新幣": "SGD", "新加坡幣": "SGD", "sgd": "SGD",
    "加幣": "CAD", "cad": "CAD",
    "紐幣": "NZD", "nzd": "NZD",
    "越南盾": "VND", "vnd": "VND",
    "馬幣": "MYR", "myr": "MYR",
}


# ── 信用卡回饋比較（2025 主流卡片）──
_CREDIT_CARDS = [
    {"name": "LINE Pay 聯名卡", "bank": "中國信託", "cashback": "LINE POINTS 3%",
     "best_for": "LINE Pay 消費", "annual_fee": "免年費", "note": "日常消費好用"},
    {"name": "街口聯名卡", "bank": "聯邦銀行", "cashback": "街口幣 6%",
     "best_for": "街口支付綁定", "annual_fee": "免年費", "note": "超商/外送最高6%"},
    {"name": "Pi 拍錢包信用卡", "bank": "玉山銀行", "cashback": "P幣 2.5%",
     "best_for": "國內一般消費", "annual_fee": "免年費", "note": "國內最高2.5%無腦刷"},
    {"name": "Costco 聯名卡", "bank": "國泰世華", "cashback": "現金回饋 1%",
     "best_for": "Costco 購物", "annual_fee": "免年費", "note": "Costco 會員必備"},
    {"name": "玉山 U Bear 卡", "bank": "玉山銀行", "cashback": "UBear 5%",
     "best_for": "網購/外送", "annual_fee": "免年費", "note": "指定網購通路5%"},
    {"name": "永豐 DAWHO 卡", "bank": "永豐銀行", "cashback": "現金回饋 3%",
     "best_for": "國內外消費", "annual_fee": "免年費", "note": "國內外3%、新戶8%"},
    {"name": "台新 FlyGo 卡", "bank": "台新銀行", "cashback": "現金回饋 2.8%",
     "best_for": "海外消費", "annual_fee": "免年費", "note": "海外最高2.8%免手續費"},
    {"name": "匯豐現金回饋卡", "bank": "匯豐銀行", "cashback": "現金回饋 3%",
     "best_for": "加油/搭車", "annual_fee": "免年費", "note": "交通3%、國內1.22%"},
]


def build_credit_card_compare(query: str = "") -> list:
    """舊函數導向新版"""
    return build_credit_card_menu()


def build_oil_price() -> list:
    """查詢本週中油油價"""
    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://www.cpc.com.tw/GetOilPriceJson.aspx?type=TodayOilPriceString",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=_ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return [{"type": "text", "text": "⚠️ 無法取得油價資料，請稍後再試"}]

    date = data.get("PriceUpdate", "")
    p92 = data.get("sPrice1", "?")
    p95 = data.get("sPrice2", "?")
    p98 = data.get("sPrice3", "?")
    diesel = data.get("sPrice5", "?")
    lpg = data.get("sPrice6", "?")

    return [{"type": "flex", "altText": f"本週油價 92:{p92} 95:{p95} 98:{p98}",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#FF6F00",
                            "contents": [
                                {"type": "text", "text": "⛽ 本週油價",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"中油牌價 · 更新日期 {date}",
                                 "color": "#FFE0B2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "92 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p92}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "95 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p95}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "98 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p98}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "separator"},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "超級柴油", "size": "sm", "color": "#888888", "flex": 3},
                         {"type": "text", "text": f"NT${diesel}/公升", "size": "sm",
                          "color": "#888888", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "液化石油氣", "size": "sm", "color": "#888888", "flex": 3},
                         {"type": "text", "text": f"NT${lpg}/公斤", "size": "sm",
                          "color": "#888888", "flex": 3, "align": "end"},
                     ]},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💡 中油每週日 24:00 公告新油價",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]


def build_exchange_rate(query: str = "") -> list:
    """查詢台灣銀行即時匯率"""
    import csv as _csv
    # 下載即時匯率
    try:
        req = urllib.request.Request(
            "https://rate.bot.com.tw/xrt/flcsv/0/day",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8-sig")
    except Exception:
        return [{"type": "text", "text": "⚠️ 無法取得匯率資料，請稍後再試"}]

    lines = raw.strip().split("\n")
    reader = _csv.reader(lines)
    rates = {}
    for row in reader:
        if len(row) < 14 or row[0] == "幣別":
            continue
        code = row[0].strip()
        try:
            cash_buy = float(row[2]) if row[2].strip() else 0
            cash_sell = float(row[12]) if row[12].strip() else 0
            spot_buy = float(row[3]) if row[3].strip() else 0
            spot_sell = float(row[13]) if row[13].strip() else 0
        except (ValueError, IndexError):
            continue
        rates[code] = {
            "cash_buy": cash_buy, "cash_sell": cash_sell,
            "spot_buy": spot_buy, "spot_sell": spot_sell,
        }

    # 判斷要查哪個幣別
    target = ""
    query_lower = query.lower()
    for alias, code in _CURRENCY_ALIAS.items():
        if alias in query_lower:
            target = code
            break
    if not target:
        for code in rates:
            if code.lower() in query_lower:
                target = code
                break

    # 如果有指定幣別 → 顯示單一幣別詳情
    if target and target in rates:
        r = rates[target]
        name = _CURRENCY_NAMES.get(target, target)
        items = [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": name, "size": "lg", "weight": "bold",
                 "color": "#E65100", "flex": 3},
                {"type": "text", "text": target, "size": "sm",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "separator", "margin": "md"},
            {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                {"type": "text", "text": "", "flex": 2, "size": "xs"},
                {"type": "text", "text": "買入", "flex": 2, "size": "xs", "color": "#888888", "align": "center"},
                {"type": "text", "text": "賣出", "flex": 2, "size": "xs", "color": "#888888", "align": "center"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "💵 現金", "flex": 2, "size": "sm"},
                {"type": "text", "text": f"{r['cash_buy']:.2f}" if r['cash_buy'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#2E7D32"},
                {"type": "text", "text": f"{r['cash_sell']:.2f}" if r['cash_sell'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#C62828"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "🏦 即期", "flex": 2, "size": "sm"},
                {"type": "text", "text": f"{r['spot_buy']:.2f}" if r['spot_buy'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#2E7D32"},
                {"type": "text", "text": f"{r['spot_sell']:.2f}" if r['spot_sell'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#C62828"},
            ]},
        ]
        # 換算
        if r['spot_sell'] > 0:
            amount_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:元|塊|萬)?', query)
            foreign_amt = float(amount_m.group(1)) if amount_m and float(amount_m.group(1)) > 0 else 100
            if "萬" in query and amount_m:
                foreign_amt *= 10000
            twd = round(foreign_amt * r['spot_sell'])
            items += [
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"💱 {target} {foreign_amt:,.0f} ≈ NT${twd:,}（即期賣出）",
                 "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
            ]

        return [{"type": "flex", "altText": f"匯率查詢 {target}",
                 "contents": {
                     "type": "bubble",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                                "contents": [
                                    {"type": "text", "text": "💱 台灣銀行匯率",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                     "footer": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": "💡 買入＝你賣外幣給銀行 / 賣出＝你跟銀行買外幣",
                          "size": "xxs", "color": "#888888", "wrap": True},
                     ]},
                 }}]

    # 沒指定幣別 → 顯示常用幣別總覽
    hot = ["USD", "JPY", "EUR", "GBP", "AUD", "CNY", "KRW", "HKD", "SGD", "THB"]
    items = []
    for code in hot:
        if code not in rates:
            continue
        r = rates[code]
        name = _CURRENCY_NAMES.get(code, code)
        sell = r['spot_sell'] or r['cash_sell']
        items.append({"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": name, "size": "xs", "flex": 3},
            {"type": "text", "text": f"{sell:.2f}" if sell else "-",
             "size": "xs", "flex": 2, "align": "end", "color": "#C62828"},
            {"type": "button", "style": "link", "height": "sm", "flex": 1,
             "action": {"type": "message", "label": "詳細",
                        "text": f"匯率 {code}"}},
        ]})

    return [{"type": "flex", "altText": "今日匯率",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "contents": [
                                {"type": "text", "text": "💱 台灣銀行今日匯率",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "即期賣出（你買外幣的價格）",
                                 "color": "#FFE0B2", "size": "xxs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": items},
             }}]


def build_money_menu() -> list:
    ACCENT = "#F9A825"
    return [{"type": "flex", "altText": "金錢小幫手",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "image",
                                 "url": "https://3c-advisor.vercel.app/liff/images/coin.jpg",
                                 "flex": 0, "size": "72px",
                                 "aspectRatio": "1:1", "aspectMode": "fit"},
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": ACCENT,
                                 "margin": "md", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "💰 金錢小幫手",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "你的隨身財務顧問",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "💡 告訴我你的月薪，幫你規劃預算",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "直接輸入：「月薪 3 萬怎麼規劃」",
                      "size": "xs", "color": "#8892B0", "margin": "sm", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💰 存錢方法", "text": "存錢方法"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🛡️ 保險", "text": "保險建議"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💳 信用卡", "text": "信用卡推薦"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💱 匯率", "text": "匯率查詢"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "⛽ 本週油價", "text": "油價"}},
                 ]},
             }}]


def _spend_card(amount: int = 0) -> list:
    """信用卡 vs 現金建議卡片"""
    installment = ""
    if amount >= 3000:
        m3  = int(amount / 3)
        m6  = int(amount / 6)
        m12 = int(amount / 12)
        installment = f"\n分期參考（0 利率）：\n• 3 期 ≈ 每月 NT${m3:,}\n• 6 期 ≈ 每月 NT${m6:,}\n• 12 期 ≈ 每月 NT${m12:,}"

    return [{"type": "flex", "altText": "刷卡還是付現？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#1A2D50"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💳 刷卡還是付現？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "這樣判斷最省錢",
                      "color": "#AABBDD", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "✅ 刷卡比較划算",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "• 有 1% 以上現金回饋\n• 有 0 利率分期（金額 > 3000）\n• 當月有滿額禮\n• 保固或購物保障較好",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "✅ 付現比較好",
                      "size": "sm", "weight": "bold", "color": "#C62828"},
                     {"type": "text",
                      "text": "• 夜市、攤販、傳統市場\n• 你容易忘繳卡費（循環利息 15%！）\n• 店家加收刷卡手續費\n• 這個月已超出預算",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     *([{"type": "separator", "margin": "sm"},
                        {"type": "text", "text": installment, "size": "sm",
                         "color": "#555555", "wrap": True}] if installment else []),
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "40+ 提醒：信用卡讓你月底才感受到痛苦。如果「不知道錢去哪了」，先付現 2 個月試試。",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "primary", "color": "#1A2D50",
                      "height": "sm",
                      "action": {"type": "message", "label": "💰 金錢小幫手",
                                 "text": "金錢小幫手"}},
                 ]},
             }}]


def _spend_overspent() -> list:
    """這週花太多了怎麼辦"""
    return [{"type": "flex", "altText": "這週花太多怎麼辦？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💸 這週花太多了？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "不用焦慮，這樣處理",
                      "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "40+ 最常見的三個超支陷阱",
                      "size": "sm", "weight": "bold", "color": "#333333"},
                     {"type": "text",
                      "text": "1️⃣ 外食＋飲料 — 每天多花 150 元，一個月就多 4500\n"
                              "2️⃣ 網購衝動 — 加購物車就忘記，月底一次扣\n"
                              "3️⃣ 訂閱服務 — 忘記取消的 Netflix/Spotify/健身房",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "今天開始能做的 3 件事",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "✅ 剩下這週改付現金，讓自己感受到「錢在減少」\n"
                              "✅ 把非必要消費延到下週再決定\n"
                              "✅ 今晚花 5 分鐘，把這週最大的 3 筆支出寫下來",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text",
                      "text": "告訴我這週花最多的是什麼，我幫你分析值不值得 😊",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "看省錢小技巧",
                                     "text": "省錢建議"}},
                         {"type": "button", "style": "link", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "💰 金錢小幫手",
                                     "text": "金錢小幫手"}},
                     ]},
                 ]},
             }}]


def build_spending_decision(text: str) -> list:
    """消費決策輔助：自然語言輸入，自動解析品項＋金額"""

    # ── 花太多了 ──
    if any(w in text for w in ["花太多", "超支", "這週花", "本週花", "花太兇", "錢不夠了"]):
        return _spend_overspent()

    # ── 信用卡 vs 現金（帶金額時顯示分期試算）──
    if any(w in text for w in ["信用卡還是現金", "刷卡還是現金", "刷卡或現金",
                                "信用卡刷好嗎", "刷卡好嗎"]):
        nums = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]{2,}", text)]
        return _spend_card(int(max(nums)) if nums else 0)

    # ── 品項行情表 ──
    _ITEM_RANGES = [
        (["電視", "tv", "液晶"],                          3000,  60000, "電視",   None),
        (["iphone", "手機", "android", "三星", "samsung","pixel","小米"], 5000, 50000, "手機", "推薦手機"),
        (["筆電", "laptop", "macbook", "電腦", "notebook"],15000, 80000, "筆電",  "推薦筆電"),
        (["ipad", "平板", "tablet"],                       5000,  40000, "平板",   "推薦平板"),
        (["airpods", "耳機"],                              500,   15000, "耳機",   None),
        (["冷氣", "冰箱", "洗衣機", "烘衣機"],            10000, 80000, "大家電", None),
        (["沙發", "床", "書桌", "椅子", "家具"],           3000,  50000, "家具",   None),
        (["包包", "皮包", "名牌包"],                       1000,  30000, "包包",   None),
        (["球鞋", "運動鞋", "鞋"],                          500,  15000, "鞋子",   None),
        (["外套", "衣服", "上衣", "褲"],                    300,   8000, "衣物",   None),
        (["火鍋", "燒肉", "牛排", "壽司", "餐廳", "吃飯", "料理"], 100, 800, "餐飲（每人）", None),
        (["咖啡", "飲料", "下午茶"],                         50,    300, "飲品",   None),
        (["機票", "飯店", "住宿", "旅遊"],                 3000,  50000, "旅遊",   None),
        (["課程", "線上課", "補習"],                        500,  30000, "課程",   None),
        (["保險"],                                         3000,  30000, "年繳保險",None),
    ]

    def _match_item(s):
        sl = s.lower()
        for kws, lo, hi, label, rec_cmd in _ITEM_RANGES:
            if any(k in sl for k in kws):
                return lo, hi, label, rec_cmd
        return None, None, None, None

    # ── 解析金額（取最大的數字，避免「iPhone 16」的 16 被誤判）──
    nums = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]{2,}", text)]
    amount = max(nums) if nums else 0

    # ── 解析品項（去掉觸發詞和數字後剩下的）──
    item = text
    for kw in ["這個划算嗎", "這支", "這台", "這款", "这个", "划算嗎", "划算",
               "值得買嗎", "值得買", "要買嗎", "該買嗎", "值得嗎", "要不要買",
               "可以買嗎", "買得起嗎", "好嗎", "貴嗎", "太貴嗎", "消費決策",
               "信用卡刷", "刷", "元", "塊", "元的"]:
        item = item.replace(kw, " ")
    # 移除所有數字
    item = re.sub(r"\d[\d,]*", " ", item)
    item = re.sub(r"\s+", " ", item).strip()

    # 沒金額 → 引導
    if amount == 0:
        return [{"type": "flex", "altText": "消費決策小幫手",
                 "contents": {"type": "bubble",
                     "styles": {"header": {"backgroundColor": "#1A2D50"}},
                     "header": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": "🤔 消費決策小幫手",
                          "color": "#FFFFFF", "size": "md", "weight": "bold"},
                         {"type": "text", "text": "直接用日常語言問我就好",
                          "color": "#AABBDD", "size": "xs", "margin": "xs"},
                     ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                              "contents": [
                         {"type": "text", "text": "這樣問我就懂：",
                          "size": "sm", "weight": "bold", "color": "#333333"},
                         {"type": "text",
                          "text": "「這支手機 20000 划算嗎？」\n「iPhone 16 買 28900 值得嗎？」\n「要不要買這台筆電 35000？」\n「冷氣 25000 太貴嗎？」",
                          "size": "sm", "color": "#555555", "wrap": True, "margin": "xs"},
                     ]},
                     "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                                "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                             {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                              "action": {"type": "message", "label": "手機 20000",
                                         "text": "這支手機 20000 划算嗎？"}},
                             {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                              "action": {"type": "message", "label": "筆電 35000",
                                         "text": "要不要買這台筆電 35000？"}},
                         ]},
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "💳 刷卡還是現金？",
                                     "text": "信用卡還是現金"}},
                     ]},
                 }}]

    # ── 有金額 → 分析 ──
    lo, hi, cat_label, rec_cmd = _match_item(item)
    display_item = item if item else (cat_label or "這項商品")

    # 月薪基準：用 5 萬（低估）和 6 萬（高估）兩個數字
    sal_lo, sal_hi = 50000, 60000
    pct_lo = int(amount / sal_hi * 100)   # 用 6 萬算，顯示較小
    pct_hi = int(amount / sal_lo * 100)   # 用 5 萬算，顯示較大

    # 工時換算（時薪約 250，5 萬月薪 / 20 天 / 8h）
    hours = amount / 250
    hours_str = f"{hours:.0f} 小時" if hours < 8 else f"{hours/8:.1f} 天"

    # 行情判斷
    if lo is not None:
        if amount < lo * 0.75:
            verdict = "價格偏低，留意品質"
            color = "#E65100"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格比行情低很多，建議確認是否為平行輸入、展示品或二手品，購買前先確認保固條件。"
        elif amount <= hi * 1.1:
            color = "#2E7D32"
            pct = (amount - lo) / (hi - lo) if hi > lo else 0.5
            pos = "入門款" if pct < 0.25 else ("中段" if pct < 0.65 else "中高段")
            verdict = f"價格合理（{pos}）"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格在{cat_label}市場屬於{pos}。建議上 BigGo 確認是近期最低價再下手，不急的話等雙11或週年慶可再省 10%。"
        else:
            verdict = "價格偏高"
            color = "#C62828"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格高出正常行情。建議等雙11 / 週年慶 / 品牌促銷，或考慮上一代同規格機型，功能差不多但便宜不少。"
    else:
        market = ""
        if amount <= 1000:
            verdict, color, tip = "小額，不用太糾結", "#2E7D32", "只要是你真正需要的，買就對了。"
        elif amount <= 5000:
            verdict, color, tip = "中等消費，建議先比價", "#E65100", "先上蝦皮、momo 比價，同樣的東西通常能省 10–20%。"
        elif amount <= 20000:
            verdict, color, tip = "大額，建議睡一晚再決定", "#C62828", "等 24 小時再買。隔天還是很想要，代表是真正需要。確認有無 0 利率分期。"
        else:
            verdict, color, tip = "重大支出，謹慎評估", "#B71C1C", "確認緊急備用金（建議 3–6 個月生活費）不受影響，再考慮是否購買。"

    # 月薪佔比解讀
    if pct_hi <= 15:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，財務壓力小"
        sal_color = "#2E7D32"
    elif pct_hi <= 40:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，在合理範圍"
        sal_color = "#E65100"
    else:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，比例偏高"
        sal_color = "#C62828"

    # 40+ 角度建議 + 衝動消費提醒
    _impulse_cats = ("衣物", "鞋子", "包包")
    if cat_label in ("手機", "筆電", "平板"):
        advice_40 = "40+ 觀點：工具類消費值得投資，但功能夠用就好，不需要追最新款。前一代機型通常便宜 20–30%，但規格差距很小。"
    elif cat_label in ("大家電", "家具"):
        advice_40 = "40+ 觀點：耐用品值得買好一點，便宜貨折舊快，長期反而更貴。品牌售後服務也很重要。"
    elif cat_label in ("餐飲（每人）", "飲品"):
        advice_40 = "40+ 觀點：偶爾好好吃一頓是生活品質的一部分，不用有罪惡感。但如果是日常習慣，要注意每月餐飲佔總支出的比例。"
    elif cat_label == "課程":
        advice_40 = "40+ 觀點：投資自己的技能是報酬率最高的消費。但要確認課程有完課率（買了沒看等於白花）。"
    elif cat_label == "旅遊":
        monthly_cost = int(amount / 12)
        advice_40 = f"40+ 觀點：旅遊是很值得的體驗消費。若預算緊，可以拆成每月存 NT${monthly_cost:,}，半年後再出發，體驗相同但財務壓力小很多。"
    elif cat_label == "年繳保險":
        monthly = int(amount / 12)
        advice_40 = f"40+ 重點：保險的關鍵不是「划不划算」，而是「保障夠不夠」。這份保險每月等於 NT${monthly:,}。40+ 優先順序：醫療 > 失能 > 壽險。"
    elif cat_label in _impulse_cats:
        advice_40 = f"40+ 提醒：這類消費衝動比例高。建議先放購物車 24 小時，隔天還是很想買再出手。統計上衝動消費 70% 隔天就後悔了。"
    else:
        advice_40 = "40+ 觀點：先確認是「需要」還是「想要」。30 天後還想買，代表是真正的需求。"

    body_items = [
        # 金額＋佔比區塊
        {"type": "box", "layout": "horizontal",
         "backgroundColor": "#F5F7FA", "cornerRadius": "8px", "paddingAll": "md",
         "contents": [
             {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                 {"type": "text", "text": f"NT${int(amount):,}",
                  "size": "xxl", "weight": "bold", "color": color},
                 {"type": "text", "text": f"≈ 工作 {hours_str}",
                  "size": "xs", "color": "#888888"},
             ]},
             {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                 {"type": "text", "text": sal_label, "size": "xs",
                  "color": sal_color, "wrap": True, "align": "end"},
             ]},
         ]},
        # 行情參考
        *([{"type": "text", "text": f"市場行情：{market}", "size": "xs",
            "color": "#888888", "margin": "xs"}] if market else []),
        {"type": "separator", "margin": "sm"},
        # 判斷結果
        {"type": "text", "text": verdict, "size": "lg",
         "weight": "bold", "color": color, "margin": "sm"},
        {"type": "text", "text": tip, "size": "sm",
         "color": "#444444", "wrap": True},
        {"type": "separator", "margin": "sm"},
        # 40+ 觀點
        {"type": "text", "text": advice_40, "size": "sm",
         "color": "#555555", "wrap": True, "margin": "sm"},
    ]

    footer_rows = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
            {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
             "action": {"type": "message", "label": "再問一個",
                        "text": "這個划算嗎"}},
            {"type": "button", "style": "link", "flex": 1, "height": "sm",
             "action": {"type": "message", "label": "刷卡或現金？",
                        "text": "信用卡還是現金"}},
        ]},
    ]
    if rec_cmd:
        footer_rows.append(
            {"type": "button", "style": "primary", "color": "#1A2D50",
             "height": "sm", "margin": "sm",
             "action": {"type": "message",
                        "label": f"找 CP 值高的{cat_label}",
                        "text": rec_cmd}}
        )

    return [{"type": "flex",
             "altText": f"{display_item} NT${int(amount):,} — {verdict}",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": color}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text",
                      "text": f"🤔 {display_item} 值得買嗎？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "務實評估，幫你做決定",
                      "color": "#FFFFFF", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical",
                          "spacing": "sm", "contents": body_items},
                 "footer": {"type": "box", "layout": "vertical",
                            "spacing": "sm", "contents": footer_rows},
             }}]


def build_money_message(text: str) -> list:
    """金錢小幫手主路由"""
    print(f"[build_money_message] v2026-04-13 text={text}")
    # ── 油價查詢 ──
    if any(w in text for w in ["油價", "加油", "汽油", "柴油", "92", "95", "98"]):
        return build_oil_price()

    # ── 匯率查詢 ──
    if any(w in text for w in ["匯率", "換匯", "外幣", "美金", "日圓", "日幣",
                                "歐元", "英鎊", "韓元", "韓幣", "人民幣", "泰銖"]):
        return build_exchange_rate(text)

    # 月薪解析
    salary = 0
    m = re.search(r'月薪\s*(\d+)|薪水\s*(\d+)|薪資\s*(\d+)', text)
    if m:
        salary = int(next(g for g in m.groups() if g))
    else:
        m2 = re.search(r'(\d+)\s*萬', text)
        if m2:
            salary = int(m2.group(1)) * 10000
        else:
            m3 = re.search(r'(\d{4,6})', text.replace(",",""))
            if m3:
                val = int(m3.group(1))
                if 15000 <= val <= 300000:
                    salary = val

    if salary >= 15000 and any(w in text for w in ["月薪","薪水","薪資","規劃","怎麼存","如何存","預算"]):
        return build_budget_plan(salary)
    if any(w in text for w in ["信用卡比較", "信用卡推薦", "哪張卡", "回饋", "信用卡使用"]):
        return build_credit_card_menu()
    if any(w in text for w in ["信用卡","循環利息","最低應繳","刷卡"]):
        return build_credit_card_menu()
    if any(w in text for w in ["保險","醫療險","壽險","意外險","重大疾病"]):
        return build_insurance_guide()
    if any(w in text for w in ["存錢","儲蓄","記帳","理財","怎麼存"]):
        return build_saving_tips()
    return build_money_menu()


# ─── 聚餐推薦 ─────────────────────────────────────────

_GROUP_DINING_CITIES = [
    "台北", "新北", "桃園", "新竹", "台中", "台南", "高雄", "其他"
]

_GROUP_DINING_TYPES = {
    "火鍋":   {"emoji": "🍲", "color": "#C62828", "note": "可分鍋、顧到每個人口味"},
    "燒肉":   {"emoji": "🥩", "color": "#BF360C", "note": "熱鬧氣氛最強、適合慶祝"},
    "日式":   {"emoji": "🍣", "color": "#1565C0", "note": "壽司/割烹/居酒屋皆宜"},
    "合菜台菜": {"emoji": "🥘", "color": "#2E7D32", "note": "大圓桌共享，長輩最愛"},
    "西式":   {"emoji": "🍽️", "color": "#4527A0", "note": "排餐/義式，正式感強"},
    "熱炒":   {"emoji": "🍺", "color": "#E65100", "note": "平價下酒、台味十足"},
    "鍋物":   {"emoji": "🥘", "color": "#6A1B9A", "note": "薑母鴨/羊肉爐，秋冬必吃"},
    "不限":   {"emoji": "🍴", "color": "#455A64", "note": "幫我推薦最適合的"},
}

_GROUP_SEARCH_TEMPLATES = {
    "火鍋":     "{city} 火鍋 包廂 聚餐 評分高",
    "燒肉":     "{city} 燒肉 聚餐 包廂 評分高",
    "日式":     "{city} 日式料理 聚餐 包廂",
    "合菜台菜": "{city} 台菜 合菜 聚餐 大圓桌",
    "西式":     "{city} 西餐 排餐 聚餐 包廂",
    "熱炒":     "{city} 熱炒 海鮮 聚餐 評分高",
    "鍋物":     "{city} 薑母鴨 羊肉爐 聚餐",
    "不限":     "{city} 聚餐 包廂 評分高 必吃",
}


def build_group_dining_message(text: str) -> list:
    """聚餐推薦主路由"""
    text_s = text.strip()

    # ── 步驟 3：城市 + 類型都有 → 直接給搜尋結果 ──
    # 格式：「聚餐 台北 火鍋」
    city_found, type_found = "", ""
    for c in _GROUP_DINING_CITIES:
        if c in text_s:
            city_found = c
            break
    for t in _GROUP_DINING_TYPES:
        if t in text_s:
            type_found = t
            break

    if city_found and type_found:
        return _build_group_result(city_found, type_found)

    # ── 步驟 2：有城市 → 問類型 ──
    if city_found:
        return _build_group_type_picker(city_found)

    # ── 步驟 1：沒有城市 → 先問城市 ──
    return _build_group_city_picker()


def _build_group_city_picker() -> list:
    city_btns = []
    row = []
    for i, c in enumerate(_GROUP_DINING_CITIES):
        row.append({
            "type": "button", "style": "secondary", "height": "sm", "flex": 1,
            "action": {"type": "message", "label": c, "text": f"聚餐 {c}"}
        })
        if len(row) == 4 or i == len(_GROUP_DINING_CITIES) - 1:
            city_btns.append({"type": "box", "layout": "horizontal",
                               "spacing": "sm", "contents": row})
            row = []

    return [{"type": "flex", "altText": "🍽️ 聚餐餐廳推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                             "contents": [
                                 {"type": "text", "text": "🍽️ 聚餐餐廳推薦",
                                  "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                 {"type": "text",
                                  "text": "朋友聚會、家庭圓桌、公司聚餐都適用",
                                  "color": "#8892B0", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "16px",
                          "contents": [
                              {"type": "text", "text": "📍 在哪個城市聚餐？",
                               "size": "sm", "weight": "bold", "color": "#333333"},
                          ] + city_btns},
             }}]


def _build_group_type_picker(city: str) -> list:
    type_rows = []
    items = list(_GROUP_DINING_TYPES.items())
    for i in range(0, len(items), 2):
        pair = items[i:i+2]
        row_contents = []
        for t, info in pair:
            row_contents.append({
                "type": "box", "layout": "vertical", "flex": 1,
                "backgroundColor": info["color"] + "22",
                "cornerRadius": "12px", "paddingAll": "12px",
                "spacing": "xs",
                "action": {"type": "message", "label": t,
                            "text": f"聚餐 {city} {t}"},
                "contents": [
                    {"type": "text", "text": info["emoji"],
                     "size": "xxl", "align": "center"},
                    {"type": "text", "text": t, "size": "sm",
                     "weight": "bold", "align": "center",
                     "color": info["color"]},
                    {"type": "text", "text": info["note"], "size": "xxs",
                     "align": "center", "color": "#888888", "wrap": True},
                ]
            })
        type_rows.append({"type": "box", "layout": "horizontal",
                           "spacing": "sm", "contents": row_contents})

    return [{"type": "flex", "altText": f"🍽️ {city} 聚餐類型",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                             "contents": [
                                 {"type": "text", "text": f"🍽️ {city} 聚餐",
                                  "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                 {"type": "text", "text": "想吃哪一種？",
                                  "color": "#8892B0", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "14px", "contents": type_rows},
             }}]


def _build_group_result(city: str, dining_type: str) -> list:
    """城市 + 類型 → 搜尋建議卡 + 常見品牌/關鍵字"""
    import urllib.parse as _up

    info = _GROUP_DINING_TYPES.get(dining_type, _GROUP_DINING_TYPES["不限"])
    color = info["color"]
    emoji = info["emoji"]

    # Google Maps 搜尋（聚餐包廂）
    query_str = _GROUP_SEARCH_TEMPLATES.get(dining_type, "{city} 聚餐").format(city=city)
    gmap_url = "https://www.google.com/maps/search/" + _up.quote(query_str)
    gmap_url_pkg = ("https://maps.google.com/?q=" + _up.quote(f"{city} {dining_type} 聚餐 包廂"))

    # 食評網站
    ipeen_url   = f"https://www.ipeen.com.tw/search/all/{_up.quote(city)}/0-0-0-0/1?q={_up.quote(dining_type + ' 聚餐')}"
    eztable_url = f"https://www.eztable.com.tw/restaurants/?q={_up.quote(city + ' ' + dining_type)}"

    # 聚餐小建議
    tips = {
        "火鍋":     ["✅ 確認是否可分鍋（素食/葷食同桌）", "✅ 問有無包廂或半包廂", "✅ 人多可問有無固定套餐"],
        "燒肉":     ["✅ 確認是桌邊烤還是個人烤", "✅ 生日通常有驚喜服務，記得告知", "✅ 提前訂位，熱門店假日爆滿"],
        "日式":     ["✅ 告知有無海鮮過敏", "✅ 居酒屋通常不適合帶長輩", "✅ 高檔割烹建議事先告知人數"],
        "合菜台菜": ["✅ 確認圓桌人數上限（通常 8-12 人）", "✅ 可請店家推薦合菜套餐", "✅ 長輩場合首選"],
        "西式":     ["✅ 正式場合建議著裝整齊", "✅ 提前預約，部分店家需訂金", "✅ 問有無無麩質/素食選項"],
        "熱炒":     ["✅ 人數多可包場，記得詢問", "✅ 下酒菜齊全，適合輕鬆聚會", "✅ 結帳通常可以分開"],
        "鍋物":     ["✅ 秋冬旺季要提前預約", "✅ 確認補湯是否免費", "✅ 薑母鴨建議中午吃不燥熱"],
        "不限":     ["✅ 先確認人數再訂位", "✅ 有特殊需求（壽星/長輩）提前告知", "✅ 訂位時詢問有無停車場"],
    }
    tip_list = tips.get(dining_type, tips["不限"])
    tip_items = [{"type": "text", "text": t, "size": "xs",
                  "color": "#555555", "wrap": True} for t in tip_list]

    # 分享文字
    share_text = f"🍽️ {city} {dining_type} 聚餐\n朋友來找餐廳，用「生活優轉」幫你選！\n{gmap_url_pkg}"
    share_url  = "https://line.me/R/share?text=" + _up.quote(share_text)

    return [{"type": "flex", "altText": f"🍽️ {city} {dining_type} 聚餐推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": color, "paddingAll": "16px",
                             "contents": [
                                 {"type": "text",
                                  "text": f"{emoji} {city} {dining_type} 聚餐",
                                  "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                 {"type": "text", "text": info["note"],
                                  "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "16px",
                          "contents": [
                              {"type": "text", "text": "📋 訂位前確認",
                               "weight": "bold", "size": "sm", "color": "#333333"},
                          ] + tip_items + [
                              {"type": "separator", "margin": "md"},
                              {"type": "text", "text": "🔍 直接搜尋餐廳",
                               "weight": "bold", "size": "sm",
                               "color": "#333333", "margin": "md"},
                              {"type": "text",
                               "text": "以下平台都有真實評價 + 線上訂位",
                               "size": "xs", "color": "#888888"},
                          ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                             "paddingAll": "12px",
                             "contents": [
                                 {"type": "button", "style": "primary",
                                  "color": color, "height": "sm",
                                  "action": {"type": "uri",
                                             "label": f"🗺️ Google Maps 找{dining_type}",
                                             "uri": gmap_url}},
                                 {"type": "box", "layout": "horizontal",
                                  "spacing": "sm", "contents": [
                                      {"type": "button", "style": "secondary",
                                       "flex": 1, "height": "sm",
                                       "action": {"type": "uri",
                                                  "label": "🍽️ 愛評網",
                                                  "uri": ipeen_url}},
                                      {"type": "button", "style": "secondary",
                                       "flex": 1, "height": "sm",
                                       "action": {"type": "uri",
                                                  "label": "📅 EZTABLE",
                                                  "uri": eztable_url}},
                                  ]},
                                 {"type": "box", "layout": "horizontal",
                                  "spacing": "sm", "contents": [
                                      {"type": "button", "style": "link",
                                       "flex": 1, "height": "sm",
                                       "action": {"type": "message",
                                                  "label": "← 換類型",
                                                  "text": f"聚餐 {city}"}},
                                      {"type": "button", "style": "link",
                                       "flex": 1, "height": "sm",
                                       "action": {"type": "uri",
                                                  "label": "📤 揪朋友",
                                                  "uri": share_url}},
                                  ]},
                             ]},
             }}]


# ─── 今天吃什麼 ──────────────────────────────────────

import random as _random

# ── 食物關鍵字分類（入口觸發 + 分類解析共用）──
_STYLE_KEYWORDS = {
    "便當": ["便當", "排骨", "雞腿", "控肉", "滷肉飯", "自助餐",
             "燒臘", "豬腳", "雞肉飯", "焢肉", "魯肉飯", "飯", "燒肉飯", "咖哩飯"],
    "麵食": ["麵", "拉麵", "牛肉麵", "乾麵", "河粉", "義大利",
             "鍋燒", "涼麵", "麵線", "切仔", "米粉", "粄條", "刀削", "餛飩", "炒麵",
             "擔仔麵", "陽春麵", "酸辣"],
    "小吃": ["小吃", "蚵仔", "臭豆腐", "肉圓", "鹽酥雞", "雞排", "滷味", "水餃", "鍋貼",
             "鹹水雞", "潤餅", "蔥油餅", "蔥抓餅", "大腸包小腸", "豬血糕", "碗粿",
             "米糕", "筒仔米糕", "麻糬", "地瓜球", "春捲", "炸物", "香腸",
             "關東煮", "雞蛋糕", "車輪餅", "紅豆餅", "章魚燒"],
    "火鍋": ["火鍋", "麻辣", "薑母鴨", "羊肉爐", "豆腐鍋",
             "涮涮鍋", "鍋物", "石頭鍋", "酸菜白肉", "牛奶鍋", "藥膳", "螃蟹鍋",
             "壽喜燒", "泡菜鍋", "麻油雞"],
    "日韓": ["日式", "日韓", "壽司", "丼飯", "韓式", "燒肉", "居酒屋", "咖哩",
             "生魚片", "定食", "韓式炸雞", "拌飯", "炸豬排", "天婦羅",
             "烏龍", "味噌", "鰻魚", "炸蝦", "石鍋", "部隊鍋", "年糕"],
    "早午餐": ["早午餐", "早餐", "蛋餅", "飯糰", "燒餅", "吐司", "三明治",
               "豆漿", "蘿蔔糕", "粥", "漢堡", "鬆餅", "可頌", "brunch",
               "法式吐司", "班尼迪克蛋", "歐姆蛋"],
    "飲料甜點": ["飲料", "甜點", "珍奶", "珍珠", "蛋糕", "咖啡", "豆花", "冰", "果汁", "奶茶",
                 "仙草", "愛玉", "抹茶", "冰淇淋", "芋圓", "手搖", "茶", "可可",
                 "鬆餅", "銅鑼燒", "甜湯", "紅豆湯", "花生湯", "湯圓"],
    "輕食": ["輕食", "沙拉", "健康", "低卡", "減脂", "清爽", "優格", "燕麥",
             "水煮餐", "蔬食", "素食", "無糖", "蛋白質", "健身餐", "貝果"],
}
# 扁平化所有食物關鍵字（供入口觸發用）
# 排除太通用的短詞，避免誤觸（這些詞仍用於分類解析）
_FOOD_TRIGGER_SKIP = {"麵", "飯", "冰", "茶", "粥", "健康", "早餐", "清爽"}
_ALL_FOOD_KEYWORDS = set()
for _kws in _STYLE_KEYWORDS.values():
    _ALL_FOOD_KEYWORDS.update(w for w in _kws if w not in _FOOD_TRIGGER_SKIP)

# 食物推薦庫（食物類型分類，像 foodpanda 的直覺式選擇）
# m: "M"=早餐限定  "D"=午餐以後  "N"=晚餐消夜限定  ""=全天
_FOOD_DB = {
    "便當": [
        {"name": "排骨便當", "desc": "炸得香脆大排骨，台式便當之王", "price": "~100–140元", "key": "排骨便當", "m": "D"},
        {"name": "雞腿便當", "desc": "滷雞腿或炸雞腿，便當店人氣王", "price": "~100–140元", "key": "雞腿便當", "m": "D"},
        {"name": "控肉飯", "desc": "油亮滷汁入口即化，淋白飯上超滿足", "price": "~80–130元", "key": "控肉飯", "m": "D"},
        {"name": "焢肉飯", "desc": "厚切五花肉滷到透亮，經典台式", "price": "~80–120元", "key": "焢肉飯", "m": "D"},
        {"name": "燒臘雙拼飯", "desc": "港式叉燒鴨配油飯，大份量", "price": "~100–150元", "key": "燒臘飯", "m": "D"},
        {"name": "自助餐", "desc": "自選菜色打包走，外食族日常主食", "price": "~75–120元", "key": "自助餐便當", "m": "D"},
        {"name": "豬腳飯", "desc": "滷豬腳膠質滿滿，配酸菜解膩", "price": "~100–150元", "key": "豬腳飯", "m": "D"},
        {"name": "雞肉飯", "desc": "嘉義式雞肉飯，油蔥雞汁超香", "price": "~40–70元", "key": "雞肉飯", "m": "D"},
        {"name": "滷肉飯", "desc": "台灣庶民之光，便宜飽足又療癒", "price": "~35–60元", "key": "滷肉飯", "m": "D"},
        {"name": "超商便當", "desc": "加熱90秒上桌，不用挑不用等", "price": "~55–90元", "key": "超商便當", "m": ""},
        {"name": "咖哩飯", "desc": "日式濃厚咖哩淋白飯，配福神漬超搭", "price": "~100–160元", "key": "咖哩飯", "m": "D"},
        {"name": "燒肉飯", "desc": "炭烤醬燒肉片鋪飯上，鹹香停不下來", "price": "~90–130元", "key": "燒肉飯", "m": "D"},
        {"name": "魯肉飯＋排骨湯", "desc": "滷肉飯加碗排骨湯，台灣人的日常奢華", "price": "~70–100元", "key": "魯肉飯", "m": "D"},
    ],
    "麵食": [
        {"name": "牛肉麵", "desc": "大塊牛腱＋濃郁湯底，台灣魂料理", "price": "~120–200元", "key": "牛肉麵", "m": "D"},
        {"name": "日式拉麵", "desc": "濃厚豚骨湯底，叉燒入口即化", "price": "~200–300元", "key": "拉麵", "m": "D"},
        {"name": "乾麵＋貢丸湯", "desc": "麵攤2分鐘上桌，台灣最快一餐", "price": "~60–85元", "key": "乾麵", "m": "D"},
        {"name": "鍋燒意麵", "desc": "魚板貢丸意麵，暖胃又滿足", "price": "~70–110元", "key": "鍋燒意麵", "m": "D"},
        {"name": "切仔麵", "desc": "湯清麵Q配黑白切，快又飽", "price": "~70–100元", "key": "切仔麵", "m": "D"},
        {"name": "義大利麵", "desc": "白醬紅醬青醬任選，簡餐店好選擇", "price": "~150–250元", "key": "義大利麵", "m": "D"},
        {"name": "涼麵", "desc": "夏天消暑首選，醬汁控制就很清爽", "price": "~60–80元", "key": "涼麵", "m": "D"},
        {"name": "蚵仔麵線", "desc": "滑溜麵線配大腸蚵仔，5分鐘吃完", "price": "~50–75元", "key": "蚵仔麵線", "m": "D"},
        {"name": "越南河粉", "desc": "清湯底蔬菜多，飽足感意外高", "price": "~100–140元", "key": "越南河粉", "m": "D"},
        {"name": "魚片湯麵", "desc": "清湯不油，腸胃弱也能吃", "price": "~100–130元", "key": "魚片湯麵", "m": "D"},
        {"name": "擔仔麵", "desc": "台南經典，肉燥蝦仁小碗精緻", "price": "~50–80元", "key": "擔仔麵", "m": "D"},
        {"name": "米粉湯", "desc": "清湯米粉配黑白切，台式速食", "price": "~40–70元", "key": "米粉湯", "m": "D"},
        {"name": "炒麵", "desc": "醬油炒麵加荷包蛋，簡單但超香", "price": "~50–80元", "key": "炒麵", "m": "D"},
        {"name": "餛飩湯麵", "desc": "薄皮大餡鮮肉餛飩，湯鮮麵Q", "price": "~70–100元", "key": "餛飩麵", "m": "D"},
        {"name": "刀削麵", "desc": "手削厚實麵條，嚼勁十足配牛肉", "price": "~100–150元", "key": "刀削麵", "m": "D"},
    ],
    "小吃": [
        {"name": "蚵仔煎", "desc": "鮮蚵配甜辣醬，夜市經典第一名", "price": "~60–80元", "key": "蚵仔煎", "m": "D"},
        {"name": "臭豆腐", "desc": "台灣魔力食物，聞著考驗吃著上癮", "price": "~60–100元", "key": "臭豆腐", "m": "D"},
        {"name": "肉圓", "desc": "蒸的炸的各有風味，一顆解饞", "price": "~40–60元", "key": "肉圓", "m": "D"},
        {"name": "鹽酥雞", "desc": "夜市靈魂，九層塔蒜頭辣粉缺一不可", "price": "~80–150元", "key": "鹽酥雞", "m": "N"},
        {"name": "雞排", "desc": "超大炸雞排，外酥內嫩一口咬下超爽", "price": "~70–90元", "key": "雞排", "m": "N"},
        {"name": "滷味", "desc": "夾了就走，雞腿海帶豆干自己配", "price": "~80–130元", "key": "滷味攤", "m": "N"},
        {"name": "水餃", "desc": "20顆水餃＋酸辣湯，10分鐘搞定", "price": "~65–90元", "key": "水餃店", "m": "D"},
        {"name": "鍋貼", "desc": "煎得金黃配蛋花湯，10分鐘飽足", "price": "~70–90元", "key": "鍋貼", "m": "D"},
        {"name": "割包", "desc": "台版漢堡，控肉花生粉酸菜", "price": "~50–80元", "key": "刈包", "m": "D"},
        {"name": "胡椒餅", "desc": "炭烤酥皮包蔥肉，排隊也值得", "price": "~50–60元", "key": "胡椒餅", "m": "D"},
        {"name": "肉粽", "desc": "南部粽北部粽，帶著走的飽足感", "price": "~35–60元", "key": "肉粽", "m": ""},
        {"name": "鹹水雞", "desc": "冰鎮雞肉配蒜蓉醬油，夏天必吃涼食", "price": "~80–150元", "key": "鹹水雞", "m": "N"},
        {"name": "潤餅", "desc": "薄皮包花生粉豆芽蛋酥，清明不限定", "price": "~50–70元", "key": "潤餅", "m": "D"},
        {"name": "蔥油餅", "desc": "煎到金黃酥脆，加蛋更邪惡", "price": "~30–50元", "key": "蔥油餅", "m": "D"},
        {"name": "大腸包小腸", "desc": "糯米腸夾香腸，夜市雙拼經典", "price": "~60–80元", "key": "大腸包小腸", "m": "N"},
        {"name": "豬血糕", "desc": "花生粉香菜醬油膏，外國人怕台灣人愛", "price": "~30–50元", "key": "豬血糕", "m": "D"},
        {"name": "碗粿", "desc": "軟嫩米漿蒸糕配醬油膏，南部經典", "price": "~30–50元", "key": "碗粿", "m": "D"},
        {"name": "筒仔米糕", "desc": "糯米蒸進竹筒，配甜辣醬超對味", "price": "~40–60元", "key": "筒仔米糕", "m": "D"},
        {"name": "地瓜球", "desc": "QQ彈彈炸地瓜球，越吃越涮嘴", "price": "~40–60元", "key": "地瓜球", "m": "D"},
        {"name": "關東煮", "desc": "蘿蔔竹輪魚板，暖呼呼一碗搞定", "price": "~50–80元", "key": "關東煮", "m": "D"},
        {"name": "車輪餅", "desc": "奶油紅豆芋頭，銅板甜點隨買隨吃", "price": "~15–25元", "key": "車輪餅", "m": "D"},
        {"name": "香腸", "desc": "烤得焦香配蒜頭，夜市散步必拿", "price": "~40–60元", "key": "烤香腸", "m": "N"},
    ],
    "火鍋": [
        {"name": "個人小火鍋", "desc": "一個人也能吃，湯底自選料夠多", "price": "~150–250元", "key": "個人小火鍋", "m": "D"},
        {"name": "麻辣鍋", "desc": "又麻又辣出一身汗，壓力全釋放", "price": "~300–500元", "key": "麻辣鍋", "m": "N"},
        {"name": "薑母鴨", "desc": "米酒薑香暖身，秋冬必吃", "price": "~300–450元", "key": "薑母鴨", "m": "N"},
        {"name": "羊肉爐", "desc": "當歸薑片羊肉湯，冬天暖身首選", "price": "~250–400元", "key": "羊肉爐", "m": "N"},
        {"name": "酸菜白肉鍋", "desc": "酸菜湯底配白肉，清爽解膩", "price": "~250–400元", "key": "酸菜白肉鍋", "m": "N"},
        {"name": "韓式豆腐鍋", "desc": "豆腐蔬菜蛋，低卡高蛋白暖胃", "price": "~150–200元", "key": "韓式豆腐鍋", "m": "D"},
        {"name": "海鮮鍋", "desc": "蝦蟹蛤蜊鮮甜湯底，海味滿滿", "price": "~300–500元", "key": "海鮮火鍋", "m": "N"},
        {"name": "涮涮鍋", "desc": "一人一鍋現涮現吃，清湯養生", "price": "~200–350元", "key": "涮涮鍋", "m": "D"},
        {"name": "壽喜燒", "desc": "甜鹹醬汁涮牛肉裹蛋液，日式經典", "price": "~300–500元", "key": "壽喜燒", "m": "N"},
        {"name": "麻油雞", "desc": "麻油薑香暖全身，冬天進補首選", "price": "~200–350元", "key": "麻油雞", "m": "N"},
        {"name": "泡菜鍋", "desc": "韓式辣泡菜配豬肉豆腐，酸辣開胃", "price": "~150–250元", "key": "泡菜鍋", "m": "D"},
        {"name": "牛奶鍋", "desc": "濃郁奶香湯底，小朋友也愛", "price": "~200–300元", "key": "牛奶鍋", "m": "D"},
    ],
    "日韓": [
        {"name": "壽司", "desc": "迴轉壽司或超商壽司，清爽方便", "price": "~60–300元", "key": "壽司", "m": ""},
        {"name": "日式丼飯", "desc": "牛丼親子丼豬排丼，一碗搞定", "price": "~120–200元", "key": "丼飯", "m": "D"},
        {"name": "日式定食", "desc": "烤魚豆腐套餐，蒸煮為主蔬菜豐富", "price": "~150–200元", "key": "日式定食", "m": "D"},
        {"name": "韓式炸雞", "desc": "外酥內嫩甜辣醬，越吃越停不下來", "price": "~200–300元", "key": "韓式炸雞", "m": "N"},
        {"name": "燒肉", "desc": "日式燒肉配飯配味噌湯，超滿足", "price": "~200–400元", "key": "燒肉定食", "m": "N"},
        {"name": "咖哩飯", "desc": "日式咖哩配白飯，一盤解決", "price": "~120–180元", "key": "咖哩飯", "m": "D"},
        {"name": "居酒屋", "desc": "下班小酌串燒配啤酒，辛苦值了", "price": "~300–500元", "key": "居酒屋", "m": "N"},
        {"name": "韓式拌飯", "desc": "石鍋拌飯蔬菜蛋肉均衡，營養滿分", "price": "~150–250元", "key": "韓式拌飯", "m": "D"},
        {"name": "炸豬排", "desc": "厚切酥炸豬排配高麗菜絲，吃完超滿足", "price": "~180–280元", "key": "炸豬排", "m": "D"},
        {"name": "天婦羅", "desc": "炸蝦炸蔬菜輕薄酥脆，沾醬油最對味", "price": "~150–250元", "key": "天婦羅", "m": "D"},
        {"name": "鰻魚飯", "desc": "蒲燒鰻魚配醬汁飯，奢華但值得", "price": "~300–500元", "key": "鰻魚飯", "m": "D"},
        {"name": "生魚片丼", "desc": "新鮮生魚片鋪滿醋飯，海味滿滿", "price": "~200–400元", "key": "生魚片丼", "m": "D"},
        {"name": "韓式炸雞", "desc": "甜辣醬裹酥脆炸雞，配啤酒絕配", "price": "~200–350元", "key": "韓式炸雞", "m": "N"},
        {"name": "部隊鍋", "desc": "泡麵年糕香腸起司大雜燴，韓式暖胃", "price": "~250–400元", "key": "部隊鍋", "m": "N"},
    ],
    "早午餐": [
        {"name": "蛋餅＋豆漿", "desc": "台灣人的晨間能量補給站", "price": "~45–70元", "key": "早餐店", "m": "M"},
        {"name": "飯糰", "desc": "糯米飯糰帶著走，咬一口很扎實", "price": "~35–60元", "key": "飯糰", "m": "M"},
        {"name": "蘿蔔糕", "desc": "煎得金黃，早餐店經典", "price": "~30–50元", "key": "蘿蔔糕", "m": "M"},
        {"name": "蔥抓餅加蛋", "desc": "酥脆又飽足，3分鐘出餐", "price": "~40–55元", "key": "蔥抓餅", "m": "M"},
        {"name": "燒餅油條", "desc": "傳統中式早餐，配鹹豆漿最對味", "price": "~40–60元", "key": "燒餅油條", "m": "M"},
        {"name": "鹹豆漿＋燒餅", "desc": "豆漿配油條燒餅，吃超飽", "price": "~60–90元", "key": "鹹豆漿 燒餅", "m": "M"},
        {"name": "碗粿＋魚丸湯", "desc": "米漿碗粿配熱湯，溫潤不油", "price": "~55–80元", "key": "碗粿", "m": "M"},
        {"name": "漢堡＋奶茶", "desc": "西式早餐店套餐，簡單快速", "price": "~60–100元", "key": "早午餐", "m": "M"},
        {"name": "三明治＋紅茶", "desc": "帶著走的最速配組合", "price": "~50–80元", "key": "三明治", "m": "M"},
        {"name": "粥品", "desc": "清淡好消化，早餐吃粥最養胃", "price": "~50–80元", "key": "粥 台式", "m": "M"},
        {"name": "鬆餅早午餐", "desc": "鬆餅配培根蛋，假日慢慢吃", "price": "~150–250元", "key": "鬆餅 早午餐", "m": "M"},
        {"name": "可頌三明治", "desc": "酥脆可頌夾火腿起司，法式早餐", "price": "~80–130元", "key": "可頌", "m": "M"},
        {"name": "法式吐司", "desc": "蛋液浸吐司煎到金黃，淋蜂蜜楓糖", "price": "~100–180元", "key": "法式吐司", "m": "M"},
    ],
    "飲料甜點": [
        {"name": "珍珠奶茶", "desc": "台灣國飲，心情不好來一杯就解決", "price": "~50–80元", "key": "珍珠奶茶", "m": ""},
        {"name": "咖啡", "desc": "美式拿鐵卡布，提神醒腦必備", "price": "~50–150元", "key": "咖啡廳", "m": ""},
        {"name": "蛋糕甜點", "desc": "蛋糕配咖啡犒賞自己，超療癒", "price": "~100–200元", "key": "蛋糕店", "m": ""},
        {"name": "豆花", "desc": "綿密豆花加花生粉圓，古早味甜品", "price": "~40–60元", "key": "豆花", "m": "D"},
        {"name": "剉冰", "desc": "芒果冰紅豆冰，夏天消暑必吃", "price": "~50–100元", "key": "剉冰", "m": "D"},
        {"name": "鮮奶茶", "desc": "用鮮奶不用奶精，喝起來就是不一樣", "price": "~55–80元", "key": "鮮奶茶", "m": ""},
        {"name": "果汁", "desc": "現打果汁補充維他命，健康解渴", "price": "~50–80元", "key": "現打果汁", "m": ""},
        {"name": "仙草凍飲", "desc": "仙草加鮮奶，清涼退火好選擇", "price": "~45–65元", "key": "仙草", "m": ""},
        {"name": "芋圓燒仙草", "desc": "加了芋圓地瓜圓，每口都是幸福感", "price": "~60–90元", "key": "燒仙草 芋圓", "m": "D"},
        {"name": "愛玉檸檬", "desc": "現搖愛玉配新鮮檸檬汁，夏日必喝", "price": "~40–65元", "key": "愛玉", "m": "D"},
        {"name": "楊枝甘露", "desc": "芒果椰汁西米露，港式甜品經典", "price": "~80–150元", "key": "港式甜品", "m": "D"},
        {"name": "抹茶拿鐵", "desc": "日本宇治抹茶配鮮奶，苦甜平衡剛好", "price": "~80–130元", "key": "抹茶拿鐵", "m": ""},
        {"name": "冰淇淋", "desc": "義式濃縮口味多樣，隨心情換口味", "price": "~80–180元", "key": "冰淇淋", "m": "D"},
        {"name": "紅豆湯＋湯圓", "desc": "冬天暖呼呼甜湯，加湯圓超滿足", "price": "~40–70元", "key": "紅豆湯 湯圓", "m": "D"},
        {"name": "花生湯", "desc": "綿密花生甜湯，古早味暖胃甜品", "price": "~40–60元", "key": "花生湯", "m": "D"},
        {"name": "手搖飲", "desc": "四季春烏龍鮮奶茶，下午三點必來一杯", "price": "~40–70元", "key": "手搖飲", "m": ""},
    ],
    "輕食": [
        {"name": "沙拉", "desc": "雞胸肉沙拉，超商或輕食店都有", "price": "~80–150元", "key": "沙拉 輕食", "m": ""},
        {"name": "御飯糰", "desc": "超商三角飯糰，帶著走最方便", "price": "~25–40元", "key": "御飯糰", "m": ""},
        {"name": "關東煮", "desc": "超商自選配料，控制熱量又暖胃", "price": "~50–80元", "key": "關東煮", "m": ""},
        {"name": "烤地瓜", "desc": "超商健康選擇，飽足感高熱量低", "price": "~35–55元", "key": "烤地瓜", "m": ""},
        {"name": "優格", "desc": "膳食纖維補充站，早餐下午茶都適合", "price": "~40–70元", "key": "優格", "m": ""},
        {"name": "燕麥飲", "desc": "膳食纖維＋低糖，健康族首選", "price": "~30–50元", "key": "燕麥牛奶", "m": ""},
        {"name": "水煮餐", "desc": "健身族最愛，雞胸花椰菜糙米", "price": "~100–150元", "key": "水煮餐", "m": "D"},
        {"name": "蔬食便當", "desc": "素食自助餐，自選蔬菜控制油量", "price": "~80–110元", "key": "素食自助餐", "m": "D"},
        {"name": "貝果", "desc": "嚼勁十足配酪梨或鮪魚，健康又飽足", "price": "~60–120元", "key": "貝果", "m": "M"},
        {"name": "雞胸肉便當", "desc": "低脂高蛋白，健身族外食首選", "price": "~100–150元", "key": "健身餐", "m": "D"},
        {"name": "豆腐料理", "desc": "涼拌豆腐或紅燒豆腐，高蛋白低熱量", "price": "~60–100元", "key": "豆腐料理", "m": "D"},
    ],
}


# ── 米其林必比登推介（由 update_bib_in_webhook.py 自動更新）──
_BIB_GOURMAND = {
    "台北": [
        {"name": "胖塔可", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/pang"},
        {"name": "Tableau by Craig Yang", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tableau-by-craig-yang"},
        {"name": "巷子龍家常菜", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/talking-heads"},
        {"name": "醉楓園小館", "type": "", "desc": "松山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tsui-feng-yuan"},
        {"name": "天下三絕", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tien-hsia-san-chueh"},
        {"name": "小小樹食 (大安路)", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/little-tree-food-da-an-road"},
        {"name": "金賞軒", "type": "", "desc": "松山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/jin-shang-hsuan"},
        {"name": "茂園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/mao-yuan"},
        {"name": "雲川水月", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/clavius"},
        {"name": "鼎泰豐 (信義路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/din-tai-fung-xinyi-road"},
        {"name": "軟食力", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/soft-power"},
        {"name": "雄記蔥抓餅", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiung-chi-scallion-pancake"},
        {"name": "杭州小籠湯包 (大安)", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hang-zhou-xiao-long-bao-da-an"},
        {"name": "雞家莊 (長春路)", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/chi-chia-chuang-changchun-road"},
        {"name": "雙月食品 (青島東路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/shuang-yue-food"},
        {"name": "祥和蔬食 (中正)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/serenity"},
        {"name": "小品雅廚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/xiao-ping-kitchen"},
        {"name": "小酌之家", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiao-cho-chih-chia"},
        {"name": "人和園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/jen-ho-yuan"},
        {"name": "黃記魯肉飯", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/huang-chi-lu-rou-fan"},
        {"name": "隱食家", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/inn-s"},
        {"name": "宋朝", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/song-jhao"},
        {"name": "欣葉小聚 (南港)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/shin-yeh-shiao-ju-nangang"},
        {"name": "無名推車燒餅", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/unnamed-clay-oven-roll"},
        {"name": "老山東牛肉家常麵店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/lao-shan-dong-homemade-noodles"},
        {"name": "吾旺再季", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/wu-wang-tsai-chi"},
        {"name": "賣麵炎仔", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/mai-mien-yen-tsai"},
        {"name": "大橋頭老牌筒仔米糕 (延平北路)", "type": "", "desc": "大同區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/da-qiao-tou-tube-rice-pudding"},
        {"name": "HUGH dessert dining", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hugh"},
        {"name": "阿爸の芋圓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/a-ba-s-taro-ball"},
        {"name": "一甲子餐飲", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/yi-jia-zi"},
        {"name": "客家小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/garden-h"},
        {"name": "永和佳香豆漿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/yonghe-chia-hsiang-soy-milk"},
        {"name": "蔡家牛肉麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/tsai-chia-beef-noodles"},
        {"name": "源芳刈包", "type": "", "desc": "萬華區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/yuan-fang-guabao"},
        {"name": "小王煮瓜", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiao-wang-steamed-minced-pork-with-pickles-in-broth"},
        {"name": "蘇來傳", "type": "", "desc": "萬華區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/su-lai-chuan"},
        {"name": "鍾家原上海生煎包", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/chung-chia-sheng-jian-bao"},
        {"name": "好朋友涼麵", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/good-friend-cold-noodles"},
        {"name": "店小二 (大同北路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/dian-xiao-er-datong-north-road"},
        {"name": "賴岡山羊肉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/lai-kang-shan"},
        {"name": "山東小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/san-tung"},
        {"name": "超人鱸魚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/superman"},
        {"name": "光興腿庫", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/guang-xing-pork-knuckle"},
        {"name": "葉家藥燉排骨", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/yeh-chia-pork-ribs-medicinal-herbs-soup"},
        {"name": "番紅花印度美饌", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/saffron"},
        {"name": "上好雞肉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/shang-hao"},
        {"name": "Lumière", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lumiere-1245897"},
        {"name": "鮨承", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/sushi-noru"},
        {"name": "咩灣裡羊肉店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/baa-wanli-goat"},
        {"name": "肉料理 · 福", "type": "", "desc": "北區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niku-ryouri-fuku"},
        {"name": "大碗公當歸羊肉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/da-one-gone-lamb"},
        {"name": "松竹園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/sung-chu-yuan"},
        {"name": "珍品餐飲坊", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/jhen-pin"},
        {"name": "三姐妹農家樂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/san-chieh-mei-nung-chia-le"},
    ],
    "台中": [
        {"name": "曙光居", "type": "", "desc": "西屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/house-of-dawn"},
        {"name": "可口牛肉麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/ke-kou-beef-noodles"},
        {"name": "裡小樓", "type": "", "desc": "西屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/li-xiao-lou"},
        {"name": "夜間部爌肉飯", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/night-school-braised-pork-rice"},
        {"name": "功夫上海手工魚丸", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/kung-fu-shanghai-fish-ball"},
        {"name": "富狀元豬腳", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-juang-yuan"},
        {"name": "羅家古早味 (南屯)", "type": "", "desc": "南屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/lou-s-nantun"},
        {"name": "繡球", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/ajisai"},
        {"name": "滬舍餘味 (南屯)", "type": "", "desc": "南屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/shanghai-food"},
        {"name": "好菜 (西區)", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/kuisine"},
        {"name": "馨苑 (西區)", "type": "台菜", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/shin-yuan"},
        {"name": "富鼎旺 (中區)", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-din-wang-central"},
        {"name": "富貴亭", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-kuei-ting"},
        {"name": "阿坤麵", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/a-kun-mian"},
        {"name": "上海未名麵點", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/no-name-noodles"},
        {"name": "范記金之園 (中區)", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/chin-chih-yuan"},
        {"name": "醉月樓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/moon-pavilion"},
        {"name": "台中肉員", "type": "", "desc": "南區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/taichung-meatball"},
        {"name": "彭城堂", "type": "台菜", "desc": "太平區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/peng-cheng-tang"},
        {"name": "鳳記鵝肉老店", "type": "", "desc": "沙鹿區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/feng-chi-goose"},
        {"name": "老士官擀麵", "type": "", "desc": "清水區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/lao-shih-kuan-noodles"},
        {"name": "牛稼莊", "type": "", "desc": "東勢區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niou-jia-juang"},
        {"name": "Lumière", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lumiere-1245897"},
        {"name": "鮨承", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/sushi-noru"},
        {"name": "咩灣裡羊肉店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/baa-wanli-goat"},
        {"name": "肉料理 · 福", "type": "", "desc": "北區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niku-ryouri-fuku"},
    ],
    "台南": [
        {"name": "大勇街無名鹹粥", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/dayong-street-no-name-congee"},
        {"name": "吃麵吧", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/jai-mi-ba"},
        {"name": "阿文米粿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-wen-rice-cake"},
        {"name": "無名羊肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/no-name-lamb-soup"},
        {"name": "阿星鹹粥", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-hsing-congee"},
        {"name": "八寶彬圓仔惠 (國華街)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yuan-zai-hui-guohua-street"},
        {"name": "葉家小卷米粉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yeh-jia-calamari-rice-noodle-soup"},
        {"name": "誠實鍋燒意麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/cheng-shi"},
        {"name": "筑馨居", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/zhu-xin-ju"},
        {"name": "黃家蝦捲", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/huang-chia-shrimp-roll"},
        {"name": "一味品", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yi-wei-pin"},
        {"name": "好農家米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/hao-nung-chia-migao"},
        {"name": "小公園擔仔麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/small-park-danzai-noodles"},
        {"name": "博仁堂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/po-jen-tang"},
        {"name": "添厚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/eat-to-fat"},
        {"name": "阿興虱目魚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-xing-shi-mu-yu"},
        {"name": "落成米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lo-cheng-migao"},
        {"name": "福泰飯桌第三代", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/fu-tai-table-third-generation"},
        {"name": "麥謎食驗室", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/bue-mi-lab"},
        {"name": "謝掌櫃", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/xie-shopkeeper"},
        {"name": "西羅殿牛肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/hsi-lo-tien-beef-soup"},
        {"name": "三好一公道當歸鴨", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/san-hao-yi-kung-tao-angelica-duck"},
        {"name": "尚好吃牛肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/shang-hao-chih-beef-soup"},
        {"name": "葉桑生炒鴨肉焿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yeh-san-duck-thick-soup"},
        {"name": "開元紅燒土魠魚羮", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/kaiyuan-fried-spanish-mackerel-thick-soup"},
        {"name": "鮮蒸蝦仁肉圓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/shian-jeng-shrimp-bawan"},
        {"name": "東香台菜海味料理", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/dong-shang-taiwanese-seafood"},
        {"name": "蓮霧腳羊肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lien-wu-chiao-lamb-soup"},
        {"name": "湖東牛肉館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hu-dong-beef"},
        {"name": "舊市羊肉 (岡山)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/joes-gangshan"},
        {"name": "田媽媽 長盈海味屋", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/chang-ying-seafood-house"},
        {"name": "橋仔頭黃家肉燥飯 (橋頭)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/ciao-zai-tou-huang-s-braised-pork-rice-ciaotou"},
        {"name": "廖記米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/liao-chi-migao"},
        {"name": "Lumière", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lumiere-1245897"},
        {"name": "鮨承", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/sushi-noru"},
        {"name": "咩灣裡羊肉店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/baa-wanli-goat"},
        {"name": "肉料理 · 福", "type": "", "desc": "北區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niku-ryouri-fuku"},
    ],
    "高雄": [
        {"name": "小燉食室", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/simmer-house"},
        {"name": "米院子油飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/mi-yuan-tzu-steamed-glutinous-rice"},
        {"name": "春蘭割包", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/chun-lan-gua-bao"},
        {"name": "泰元", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/thai-yuan"},
        {"name": "牛老大涮牛肉 (自強二路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/beef-chief-zihciang-2nd-road"},
        {"name": "菜粽李", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/caizong-li"},
        {"name": "前金肉燥飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/cianjin-brasied-pork-rice"},
        {"name": "昭明海產家庭料理", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/chao-ming"},
        {"name": "永筵小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/yung-yen"},
        {"name": "侯記鴨肉飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hou-chi-duck-rice"},
        {"name": "白玉樓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/pale-jade-pavilion"},
        {"name": "北港蔡三代筒仔米糕 (鹽埕)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/bei-gang-tsai-rice-tube-yancheng"},
        {"name": "良佳豬腳", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/liang-chia-pig-knuckle"},
        {"name": "貳哥食堂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/erge-shih-tang"},
        {"name": "賣塩順", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/mai-yen-shun"},
        {"name": "正宗鴨肉飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/cheng-tsung-duck-rice"},
        {"name": "弘記肉燥飯舖", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hung-chi-rice-shop"},
        {"name": "楊寶寶蒸餃 (朝明路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/yang-bao-bao-nanzih"},
        {"name": "廖記米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/liao-chi-migao"},
        {"name": "橋仔頭黃家肉燥飯 (橋頭)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/ciao-zai-tou-huang-s-braised-pork-rice-ciaotou"},
        {"name": "舊市羊肉 (岡山)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/joes-gangshan"},
        {"name": "湖東牛肉館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hu-dong-beef"},
        {"name": "Lumière", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lumiere-1245897"},
        {"name": "鮨承", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/sushi-noru"},
        {"name": "咩灣裡羊肉店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/baa-wanli-goat"},
        {"name": "肉料理 · 福", "type": "", "desc": "北區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niku-ryouri-fuku"},
    ],
}


def build_bib_gourmand_flex(area: str = "") -> list:
    """米其林必比登推薦"""
    area2 = area[:2] if area else ""
    pool = _BIB_GOURMAND.get(area2, [])
    if not pool:
        # 沒有該城市的必比登 → 顯示全部城市選擇
        cities = list(_BIB_GOURMAND.keys())
        buttons = [
            {"type": "button", "style": "primary", "color": "#B71C1C", "height": "sm",
             "action": {"type": "message", "label": f"🏅 {c}", "text": f"必比登 {c}"}}
            for c in cities
        ]
        return [{"type": "flex", "altText": "米其林必比登推介",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#B71C1C",
                                "contents": [
                                    {"type": "text", "text": "🏅 米其林必比登推介",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    {"type": "text", "text": "每餐 NT$1,000 以內的超值好味道",
                                     "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                              "contents": [
                                  {"type": "text", "text": "選擇城市 👇", "size": "sm", "color": "#555555"},
                              ] + buttons},
                 }}]

    # 排除上次推薦的必比登
    bib_key = f"bib_{area2}"
    last_bib = set(_food_recent.get(bib_key, []))
    fresh_bib = [p for p in pool if p["name"] not in last_bib]
    if len(fresh_bib) < 5:
        fresh_bib = pool
    picks = _random.sample(fresh_bib, min(5, len(fresh_bib)))
    _food_recent[bib_key] = [p["name"] for p in picks]

    color = "#B71C1C"
    items = []
    for i, r in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"🏅 {r['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3, "wrap": True},
                {"type": "text", "text": r["type"], "size": "xxs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": r.get("desc", ""), "size": "xs",
             "color": "#555555", "margin": "xs"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": _maps_url(r["name"], area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍",
                            "text": f"回報 好吃 {r['name']}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌",
                            "text": f"回報 倒閉 {r['name']}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    return [{"type": "flex", "altText": f"必比登推介 — {area2}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏅 必比登推介（{area2}）",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "米其林認證 · 每餐 NT$1,000 以內",
                                 "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"必比登 {area2}"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍽️ 回主選單",
                                                      "text": "今天吃什麼"}},
                     ]},
                 ]},
             }}]


# ── 使用者回饋機制 ──
_FEEDBACK_LOG = []  # 暫存在記憶體，定期匯出


def handle_food_feedback(text: str, user_id: str = "") -> list:
    """處理使用者對餐廳的回饋（好吃/倒閉），並推播通知開發者"""
    import datetime as _dt
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    if "好吃" in text:
        shop = text.replace("回報", "").replace("好吃", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "good", "time": ts})
        if ADMIN_USER_ID:
            push_message(ADMIN_USER_ID, [{"type": "text",
                "text": f"👍 使用者回報好吃\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"👍 感謝推薦！已記錄「{shop}」為好吃店家 🎉\n"
                 f"你的回饋會幫助其他使用者找到更好的餐廳！"}]
    elif "倒閉" in text or "歇業" in text:
        shop = text.replace("回報", "").replace("倒閉", "").replace("歇業", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "closed", "time": ts})
        if ADMIN_USER_ID:
            push_message(ADMIN_USER_ID, [{"type": "text",
                "text": f"❌ 使用者回報歇業\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"❌ 感謝回報！已標記「{shop}」可能歇業 📝\n"
                 f"我們會在下次更新時確認並移除，謝謝你！"}]
    return []


# ── 通用回報（bug / 功能異常 / 錯誤）──
def handle_general_report(text: str, user_id: str = "") -> list:
    """處理通用回報，推播通知開發者"""
    import datetime as _dt
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    content = text.replace("回報", "").strip()
    if len(content) < 2:
        return build_feedback_intro()

    # 自動分類
    if any(w in content for w in ["bug", "壞", "錯誤", "失敗", "沒反應", "當掉", "跑不出來", "無法", "不能"]):
        tag = "🐛 Bug"
    elif any(w in content for w in ["慢", "卡", "lag", "等很久", "超時", "timeout"]):
        tag = "🐌 效能"
    else:
        tag = "📋 回報"

    # 推播通知開發者
    if ADMIN_USER_ID:
        push_message(ADMIN_USER_ID, [{"type": "flex", "altText": f"{tag} 使用者回報",
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {"type": "box", "layout": "vertical",
                           "backgroundColor": "#E74C3C", "paddingAll": "16px",
                           "contents": [
                               {"type": "text", "text": f"{tag} 使用者回報",
                                "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                           ]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md",
                         "paddingAll": "20px",
                         "contents": [
                             {"type": "text", "text": content,
                              "wrap": True, "size": "md", "weight": "bold"},
                             {"type": "separator", "margin": "md"},
                             {"type": "box", "layout": "vertical", "margin": "md",
                              "spacing": "sm", "contents": [
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"👤 {user_id[:10]}..."},
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"🕐 {ts}"},
                              ]},
                         ]},
            }}])

    return [{"type": "text", "text":
             f"📋 收到你的回報！\n\n"
             f"「{content}」\n\n"
             f"已通知開發者，會盡快處理 🙏"}]


# ── 使用者功能建議 / 許願回饋 ──
def build_feedback_intro() -> list:
    """顯示回饋/許願引導卡片"""
    return [{"type": "flex", "altText": "💡 許願 & 回報",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#6C5CE7", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "💡 許願池 & 問題回報",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "20px",
                          "contents": [
                              {"type": "text", "text": "想要新功能？遇到問題？都可以告訴我！",
                               "wrap": True, "size": "sm", "color": "#555555"},
                              {"type": "separator", "margin": "md"},
                              {"type": "text", "text": "✨ 許願（想要新功能）", "weight": "bold",
                               "size": "sm", "margin": "md", "color": "#6C5CE7"},
                              {"type": "text", "wrap": True, "size": "xs", "color": "#888888",
                               "text": "建議 希望有記帳功能\n建議 天氣可以顯示紫外線"},
                              {"type": "text", "text": "🐛 回報（功能異常）", "weight": "bold",
                               "size": "sm", "margin": "md", "color": "#E74C3C"},
                              {"type": "text", "wrap": True, "size": "xs", "color": "#888888",
                               "text": "回報 吃什麼沒反應\n回報 天氣顯示錯誤"},
                          ]},
             }}]


def handle_user_suggestion(text: str, user_id: str, display_name: str = "") -> list:
    """處理使用者功能建議，推播通知給開發者"""
    import datetime as _dt
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    # 提取建議內容
    content = text
    for kw in ["建議", "許願", "功能建議", "我想要", "希望有", "回饋"]:
        content = content.replace(kw, "").strip()

    if len(content) < 2:
        return build_feedback_intro()

    # 回覆使用者
    reply = [{"type": "text", "text":
              f"💡 收到你的建議！\n\n"
              f"「{content}」\n\n"
              f"已送達開發者，感謝你讓生活優轉變得更好 🙏"}]

    # 推播通知給開發者
    if ADMIN_USER_ID:
        name_str = f"（{display_name}）" if display_name else ""
        push_message(ADMIN_USER_ID, [{"type": "flex", "altText": "💡 新功能建議",
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {"type": "box", "layout": "vertical",
                           "backgroundColor": "#6C5CE7", "paddingAll": "16px",
                           "contents": [
                               {"type": "text", "text": "💡 新功能建議",
                                "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                           ]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md",
                         "paddingAll": "20px",
                         "contents": [
                             {"type": "text", "text": content,
                              "wrap": True, "size": "md", "weight": "bold"},
                             {"type": "separator", "margin": "md"},
                             {"type": "box", "layout": "vertical", "margin": "md",
                              "spacing": "sm", "contents": [
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"👤 {user_id[:10]}...{name_str}"},
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"🕐 {ts}"},
                              ]},
                         ]},
            }}])

    return reply


# ── 餐廳資料庫（觀光署開放資料）──
_RESTAURANT_CACHE = {}
try:
    _rest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "restaurant_cache.json")
    if os.path.isfile(_rest_path):
        with open(_rest_path, encoding="utf-8") as _rf:
            _rest_data = json.load(_rf)
            _RESTAURANT_CACHE = _rest_data.get("restaurants", {})
except Exception:
    _RESTAURANT_CACHE = {}


def _maps_url(keyword: str, area: str = "", **_kw) -> str:
    """產生 Google Maps 搜尋連結"""
    if area:
        q = urllib.parse.quote(f"{area} {keyword}")
    else:
        q = urllib.parse.quote(f"{keyword} 附近")
    return f"https://www.google.com/maps/search/{q}/"


def _tw_meal_period() -> tuple:
    """回傳 (時段代碼, 中文標籤)，依台灣時間（UTC+8）"""
    import datetime
    h = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).hour
    if 5 <= h < 10:
        return "M", "早餐推薦"
    elif 10 <= h < 14:
        return "D", "午餐推薦"
    elif 14 <= h < 17:
        return "D", "下午點心推薦"
    elif 17 <= h < 22:
        return "N", "晚餐推薦"
    else:
        return "N", "消夜推薦"


def _filter_food_by_time(pool: list, period: str) -> list:
    """依時段過濾食物；若剩不足3筆則 fallback 全部
    M=早餐(5-10): 只選全天+早餐限定
    D=午餐/下午(10-17): 選全天+午餐以後
    N=晚餐/消夜(17-5): 選全天+午餐以後+晚上限定（午餐品項晚上也能吃）
    """
    if period == "M":
        ok = [p for p in pool if p.get("m", "") in ("", "M")]
    elif period == "D":
        # 午餐：優先全天+午餐，不足3筆就也納入晚餐品項（火鍋/薑母鴨白天也能吃）
        ok = [p for p in pool if p.get("m", "") in ("", "D")]
        if len(ok) < 3:
            ok = [p for p in pool if p.get("m", "") in ("", "D", "N")]
    else:  # N (晚上/消夜) — 午餐品項晚上也開
        ok = [p for p in pool if p.get("m", "") in ("", "D", "N")]
    return ok if len(ok) >= 1 else pool


# 記住最近推薦過的品項，避免連續重複
_food_recent = {}  # {style: [上次推薦的 name 列表]}


def build_food_flex(style: str, area: str = "") -> list:
    """隨機挑 3 道推薦，依時段過濾，避免與上次重複"""
    pool = _FOOD_DB.get(style, _FOOD_DB["便當"])
    period, meal_label = _tw_meal_period()
    filtered = _filter_food_by_time(pool, period)

    # 排除上次推薦過的品項
    last = set(_food_recent.get(style, []))
    fresh = [p for p in filtered if p["name"] not in last]
    # 如果排除後不足 3 個，就放寬（全部都能選）
    if len(fresh) < 3:
        fresh = filtered
    picks = _random.sample(fresh, min(3, len(fresh)))
    # 記住這次推薦的，下次排除
    _food_recent[style] = [p["name"] for p in picks]
    area_label = f"（{area}附近）" if area else ""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32"}
    color = colors.get(style, "#FF8C42")
    icons = {"便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗"}
    icon = icons.get(style, "🍽️")

    items = []
    for i, p in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {p['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3},
                {"type": "text", "text": p["price"], "size": "xs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": p["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📍 Google Maps 搜附近", "uri": _maps_url(p["key"], area, open_now=True)}},
        ]
        if i < len(picks)-1:
            items.append({"type": "separator", "margin": "sm"})

    _style_list = list(_FOOD_DB.keys())
    _si = _style_list.index(style) if style in _style_list else 0
    next_style = _style_list[(_si + 1) % len(_style_list)]
    # 一鍵分享文字
    _share_names = "、".join([p["name"] for p in picks])
    _share_text = (f"🍽️ 今天吃{style}！\n推薦：{_share_names}\n\n"
                   f"用「生活優轉」3秒決定吃什麼 👆")
    _share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
    return [{"type": "flex", "altText": f"今天吃什麼 — {icon}{style}版",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "image",
                                 "url": "https://3c-advisor.vercel.app/liff/images/ramen.jpg",
                                 "flex": 0, "size": "72px",
                                 "aspectRatio": "1:1", "aspectMode": "fit"},
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": color,
                                 "margin": "md", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🍽️ {meal_label}{area_label}",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": f"{icon} {style}版推薦",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"吃什麼 {style} {area}"}},
                         {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": f"換{next_style}版",
                                                      "text": f"吃什麼 {next_style} {area}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🌤️ 今日天氣",
                                     "text": "天氣"}},
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🗓️ 近期活動",
                                     "text": "周末去哪"}},
                     ]},
                     {"type": "button", "style": "link", "height": "sm",
                      "action": {"type": "uri", "label": "📤 分享推薦給朋友",
                                 "uri": _share_url}},
                 ]},
             }}]


def build_food_restaurant_flex(area: str, food_type: str = "") -> list:
    """從觀光署餐廳資料推薦在地餐廳"""
    area2 = area[:2] if area else ""
    pool = _RESTAURANT_CACHE.get(area, _RESTAURANT_CACHE.get(area2, []))
    if not pool:
        # 沒有餐廳資料 → fallback 到品項推薦
        return build_food_flex("享樂", area)

    # 依類型篩選
    if food_type:
        typed = [r for r in pool if food_type in r.get("type", "")]
        if len(typed) >= 3:
            pool = typed

    # 排除上次推薦的餐廳
    rest_key = f"rest_{area}_{food_type}"
    last_rest = set(_food_recent.get(rest_key, []))
    fresh_rest = [p for p in pool if p["name"] not in last_rest]
    if len(fresh_rest) < 5:
        fresh_rest = pool
    picks = _random.sample(fresh_rest, min(5, len(fresh_rest)))
    _food_recent[rest_key] = [p["name"] for p in picks]

    period, meal_label = _tw_meal_period()
    area_label = f"（{area}）" if area else ""
    color = "#6D4C41"

    # 類型 emoji
    type_icons = {
        "中式": "🍚", "日式": "🍣", "西式": "🍝", "素食": "🥬",
        "海鮮": "🦐", "小吃": "🧆", "火鍋": "🍲", "地方特產": "⭐", "其他": "🍴",
    }

    items = []
    for i, r in enumerate(picks):
        rtype = r.get("type", "其他")
        icon = type_icons.get(rtype, "🍴")
        desc_raw = r.get("desc", "")
        desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
        addr = r.get("addr", "")
        town = r.get("town", "")
        sub_info = f"{icon}{rtype}"
        if town:
            sub_info += f" · {town}"

        rname = r['name']
        items += [
            {"type": "text", "text": f"• {rname}", "weight": "bold",
             "size": "sm", "color": color, "wrap": True, "maxLines": 2},
            {"type": "text", "text": sub_info, "size": "xxs",
             "color": "#888888", "margin": "xs"},
            {"type": "text", "text": desc, "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs",
             "maxLines": 2} if desc else {"type": "filler"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": _maps_url(rname, area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍",
                            "text": f"回報 好吃 {rname}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌",
                            "text": f"回報 倒閉 {rname}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    # 可用的類型按鈕
    available_types = list({r.get("type", "") for r in _RESTAURANT_CACHE.get(area, _RESTAURANT_CACHE.get(area2, []))})
    type_buttons = []
    for t in ["小吃", "中式", "日式", "海鮮", "火鍋"][:3]:
        if t in available_types:
            type_buttons.append(
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": f"{type_icons.get(t,'🍴')} {t}",
                            "text": f"餐廳 {t} {area}"}}
            )

    footer_contents = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "color": color, "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                         "text": f"餐廳 {food_type} {area}"}},
            {"type": "button", "style": "secondary", "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🍽️ 品項推薦",
                                         "text": f"吃什麼 享樂 {area}"}},
        ]},
    ]
    if type_buttons:
        footer_contents.append(
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": type_buttons}
        )

    return [{"type": "flex", "altText": f"在地餐廳推薦{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏪 {meal_label}{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"在地餐廳推薦" + (f" · {food_type}" if food_type else ""),
                                 "color": "#FFFFFFCC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": footer_contents},
             }}]


def build_live_food_events(area: str) -> list:
    """從 Accupass 快取拉吃喝玩樂即時活動（給「本週美食活動」用）"""
    area2 = area[:2] if area else ""
    city_cache = _ACCUPASS_CACHE.get(area, _ACCUPASS_CACHE.get(area2, {}))
    events = city_cache.get("吃喝玩樂", [])
    if not events:
        return []

    picks = events[:4]  # 最多顯示 4 筆
    color = "#D84315"
    items = []
    for i, e in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {e.get('name','')}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 4, "wrap": True},
                {"type": "text", "text": "🆕", "size": "xs", "color": "#888888", "flex": 0},
            ]},
            {"type": "text", "text": e.get("desc", ""), "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📅 查看活動詳情",
                        "uri": e.get("url", "https://www.accupass.com")}},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    area_label = f"（{area}）" if area else ""
    return [{"type": "flex", "altText": f"本週美食活動{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🎉 本週美食活動{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "Accupass 即時更新 · 吃喝玩樂精選",
                                 "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": "🍽️ 回到今天吃什麼", "text": "今天吃什麼"}},
                 ]},
             }}]


def build_food_menu() -> list:
    """今天吃什麼 — 主選單（依時段動態調整按鈕順序）"""
    period, meal_label = _tw_meal_period()

    _all_btns = {
        "便當":    ("便當",    "吃什麼 便當"),
        "麵食":    ("麵食",    "吃什麼 麵食"),
        "小吃":    ("小吃",    "吃什麼 小吃"),
        "火鍋":    ("火鍋",    "吃什麼 火鍋"),
        "日韓":    ("日韓",    "吃什麼 日韓"),
        "早午餐":  ("早午餐",  "吃什麼 早午餐"),
        "飲料甜點":("飲料甜點","吃什麼 飲料甜點"),
        "輕食":    ("輕食",    "吃什麼 輕食"),
    }
    _period_order = {
        "M": ["早午餐", "飲料甜點", "輕食", "便當", "麵食", "小吃", "日韓", "火鍋"],
        "D": ["便當",   "麵食",    "小吃", "日韓", "輕食", "早午餐", "飲料甜點", "火鍋"],
        "N": ["火鍋",   "日韓",    "麵食", "便當", "小吃", "飲料甜點", "輕食", "早午餐"],
    }
    order = _period_order.get(period, _period_order["D"])

    ACCENT = "#FF6B35"

    def _btn(key):
        label, text = _all_btns[key]
        return {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                "height": "sm", "action": {"type": "message", "label": label, "text": text}}

    row1 = [_btn(k) for k in order[0:3]]
    row2 = [_btn(k) for k in order[3:6]]
    row3 = [_btn(k) for k in order[6:8]]

    header_hints = {
        "M": "☀️ 早餐 / 早午餐時間",
        "D": "🌞 午餐時間，快速決定！",
        "N": "🌙 晚餐時間，好好犒賞自己",
    }
    hint = header_hints.get(period, "幫你快速決定，外食族救星！")

    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "image",
                                 "url": "https://3c-advisor.vercel.app/liff/images/ramen.jpg",
                                 "flex": 0, "size": "72px",
                                 "aspectRatio": "1:1", "aspectMode": "fit"},
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": ACCENT,
                                 "margin": "md", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🍽️ {meal_label}",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": hint,
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "選一個類型，3秒決定 👇",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold"},
                     {"type": "text", "text": "也可以直接說「台南 火鍋」「台北 拉麵」",
                      "size": "xs", "color": "#8892B0", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row1},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row2},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row3},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "必比登", "text": "必比登"}},
                         {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "在地餐廳", "text": "在地餐廳"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "美食活動", "text": "本週美食活動"}},
                 ]},
             }}]


# ─── 硬體升級諮詢 ─────────────────────────────────────

def build_upgrade_menu() -> list:
    """硬體升級主選單"""
    return [{"type": "flex", "altText": "🔧 電腦硬體升級諮詢", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#263238",
            "paddingBottom": "16px",
            "contents": [
                {"type": "text", "text": "🔧 電腦硬體升級諮詢",
                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                {"type": "text", "text": "哪個零件最值得升級？我來幫你判斷",
                 "color": "#90A4AE", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "選擇你想了解的升級項目：",
                 "size": "sm", "color": "#546E7A", "margin": "sm"},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#37474F", "flex": 1,
                      "action": {"type": "message", "label": "💾 加 RAM", "text": "升級 RAM"}},
                     {"type": "button", "style": "primary", "color": "#455A64", "flex": 1,
                      "action": {"type": "message", "label": "💿 換 SSD", "text": "升級 SSD"}},
                 ]},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#546E7A", "flex": 1,
                      "action": {"type": "message", "label": "🎮 升顯卡 GPU", "text": "升級 GPU"}},
                     {"type": "button", "style": "secondary", "flex": 1,
                      "action": {"type": "message", "label": "🧠 換 CPU", "text": "升級 CPU"}},
                 ]},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "📊 整機效能分析", "text": "電腦效能分析"}},
            ]
        }
    }}]


def build_upgrade_ram() -> list:
    """RAM 升級指南"""
    return [{"type": "flex", "altText": "💾 RAM 升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1565C0",
            "contents": [
                {"type": "text", "text": "💾 RAM 升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "什麼時候值得加 RAM？",
                 "color": "#BBDEFB", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "✅ 適合升級 RAM 的情況",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 多開視窗/分頁時電腦明顯變慢\n"
                     "• 工作管理員顯示 RAM 使用率 > 80%\n"
                     "• 同時用 Chrome + Office + Zoom 很卡\n"
                     "• 影片剪輯/設計軟體跑不動\n"
                     "• 遊戲時有明顯 Lag 或讀取卡頓"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "❌ 加 RAM 幫助不大的情況",
                 "weight": "bold", "size": "sm", "color": "#C62828"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• CPU 使用率長期 > 90%（瓶頸在 CPU）\n"
                     "• RAM 使用率正常但電腦還是很慢\n"
                     "  → 瓶頸可能是 HDD，換 SSD 比較有用\n"
                     "• 遊戲幀數低（瓶頸通常在 GPU）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📊 RAM 容量建議",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "8GB  → 勉強夠，日常瀏覽 OK\n"
                     "16GB → 主流標配，絕大多數使用者夠用 ✅\n"
                     "32GB → 剪片/設計/工程師推薦\n"
                     "64GB+ → 專業工作站等級"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 升級前請確認",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 主機板支援的 RAM 類型（DDR4 / DDR5）\n"
                     "② 主機板最大支援容量（查規格書）\n"
                     "③ 筆電確認插槽數量（部分焊死不可升級）\n"
                     "④ 雙通道效能 > 單條大容量（盡量成對插）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 CP 值最高選擇",
                 "weight": "bold", "size": "sm", "color": "#4527A0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "DDR4 16GB（8GB × 2）：約 NT$500-800\n"
                     "DDR5 16GB（8GB × 2）：約 NT$1,200-1,800\n"
                     "品牌推薦：Kingston / Crucial / G.Skill\n\n"
                     "⚠️ 筆電升級建議找原廠或有保固的店家安裝"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#1565C0", "height": "sm",
                 "action": {"type": "message", "label": "💿 換 SSD 更快嗎？", "text": "升級 SSD"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "📊 整機效能分析", "text": "電腦效能分析"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_ssd() -> list:
    """SSD 升級指南"""
    return [{"type": "flex", "altText": "💿 SSD 升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1B5E20",
            "contents": [
                {"type": "text", "text": "💿 SSD 升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "最有感的升級！開機從 2 分鐘變 10 秒",
                 "color": "#C8E6C9", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🔥 HDD → SSD 效果最明顯",
                 "weight": "bold", "size": "sm", "color": "#1B5E20"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 開機速度：120 秒 → 10 秒\n"
                     "• 軟體載入：5-10 秒 → 1-2 秒\n"
                     "• 檔案複製：快 5-10 倍\n"
                     "• 整體「感覺」快非常多\n\n"
                     "👉 舊電腦還在用 HDD，換 SSD 比買新電腦划算！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📊 SSD 種類比較",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "SATA SSD（舊介面）\n"
                     "  速度 500 MB/s，便宜，適合替換舊 HDD\n\n"
                     "M.2 NVMe（新介面）✅ 推薦\n"
                     "  速度 3,000-7,000 MB/s，是 SATA 的 6-14 倍\n"
                     "  價格不貴，主流選擇\n\n"
                     "⚠️ 先確認主機板/筆電支援哪種介面！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 2026 年 CP 值推薦",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "500GB NVMe：約 NT$800-1,200（入門夠用）\n"
                     "1TB NVMe：約 NT$1,200-1,800 ✅ 最推薦\n"
                     "2TB NVMe：約 NT$2,000-3,000（創作者）\n\n"
                     "品牌推薦：Samsung 990 / WD SN770 / Crucial P3\n"
                     "避開：不知名小廠（壽命不穩定）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📋 升級步驟",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 確認電腦支援的介面（SATA 或 M.2）\n"
                     "② 購買對應 SSD\n"
                     "③ 用「Macrium Reflect」免費軟體克隆硬碟\n"
                     "④ 換上 SSD，舊 HDD 可當外接硬碟用\n"
                     "⑤ 開機，直接享受 10 倍速！"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#1B5E20", "height": "sm",
                 "action": {"type": "message", "label": "💾 RAM 要加嗎？", "text": "升級 RAM"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_gpu() -> list:
    """GPU 顯卡升級指南"""
    return [{"type": "flex", "altText": "🎮 GPU 顯卡升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#4A148C",
            "contents": [
                {"type": "text", "text": "🎮 GPU 顯卡升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "遊戲/剪片/AI 運算的核心",
                 "color": "#CE93D8", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "✅ 適合升級 GPU 的情況",
                 "weight": "bold", "size": "sm", "color": "#4A148C"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 遊戲幀數不足 60fps（特效開低還是卡）\n"
                     "• 想玩 4K / 高畫質遊戲\n"
                     "• 影片剪輯/3D 渲染速度太慢\n"
                     "• 跑 AI / Stable Diffusion 本機模型\n"
                     "• 顯卡老舊（超過 5 年）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "⚠️ 升級前要確認",
                 "weight": "bold", "size": "sm", "color": "#C62828"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 電源供應器（PSU）瓦數夠嗎？\n"
                     "   RTX 4070 建議 650W 以上\n"
                     "   RTX 4080/4090 建議 850W 以上\n"
                     "② 機殼能放下顯卡（長度/高度）？\n"
                     "③ CPU 不要太舊（否則 CPU 卡脖子）\n"
                     "④ 筆電：顯卡通常無法升級！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 2026 年 GPU 推薦",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "入門（1080p 遊戲）：\n"
                     "  RTX 4060 / RX 7600 — 約 NT$6,000-8,000\n\n"
                     "主流（1440p 遊戲 / 剪片）✅ 推薦：\n"
                     "  RTX 4070 Super — 約 NT$14,000-16,000\n\n"
                     "高階（4K / AI 運算）：\n"
                     "  RTX 4080 Super — 約 NT$28,000-33,000\n\n"
                     "二手市場：上一代 RTX 3080 性價比高"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 N 卡 vs A 卡怎麼選？",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "NVIDIA（RTX）：遊戲相容性好、DLSS 技術、\n"
                     "  AI/CUDA 支援佳 → 大多數人首選\n\n"
                     "AMD（RX）：同價位效能好，但 AI/串流軟體\n"
                     "  相容性稍差 → 純遊戲用戶可考慮"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#4A148C", "height": "sm",
                 "action": {"type": "message", "label": "📊 整機效能分析", "text": "電腦效能分析"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_performance_check() -> list:
    """整機效能分析 — 找出瓶頸"""
    return [{"type": "flex", "altText": "📊 電腦效能分析", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#37474F",
            "contents": [
                {"type": "text", "text": "📊 找出電腦真正的瓶頸",
                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                {"type": "text", "text": "打開工作管理員，1 分鐘診斷法",
                 "color": "#90A4AE", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🖥️ 步驟：按 Ctrl+Shift+Esc",
                 "weight": "bold", "size": "sm", "color": "#37474F"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": "開啟工作管理員 → 點「效能」頁籤 → 在電腦最卡的時候查看各項使用率"},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "🔍 診斷結果解讀",
                 "weight": "bold", "size": "sm", "color": "#37474F"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "CPU 使用率 > 90%\n"
                     "→ 瓶頸在處理器，考慮換 CPU 或整機\n\n"
                     "RAM 使用率 > 80%（或「可用」< 1GB）\n"
                     "→ 瓶頸在記憶體，加 RAM 立即見效 ✅\n\n"
                     "磁碟使用率長期 100%\n"
                     "→ 瓶頸在 HDD，換 SSD 效果最明顯 ✅\n\n"
                     "GPU 使用率 > 95%（遊戲時）\n"
                     "→ 瓶頸在顯卡，升 GPU 才有用 ✅\n\n"
                     "全部都很低但還是很卡？\n"
                     "→ 可能是病毒、啟動程式太多、或系統問題"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 免費優化先試試",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 工作管理員 → 啟動 → 停用不必要的程式\n"
                     "② 清除暫存（Win+R → 輸入 %temp% → 全刪）\n"
                     "③ 更新驅動程式（尤其是顯卡驅動）\n"
                     "④ 重灌系統（最乾淨但最耗時）\n\n"
                     "以上試過還是慢，再考慮硬體升級！"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#1565C0", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "💾 加 RAM", "text": "升級 RAM"}},
                     {"type": "button", "style": "primary", "color": "#1B5E20", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "💿 換 SSD", "text": "升級 SSD"}},
                 ]},
                {"type": "button", "style": "primary", "color": "#4A148C", "height": "sm",
                 "action": {"type": "message", "label": "🎮 升顯卡", "text": "升級 GPU"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_message(text: str) -> list:
    """硬體升級諮詢主路由"""
    text_s = text.upper()
    if any(w in text for w in ["RAM", "ram", "記憶體", "加記憶體", "加RAM", "內存"]):
        return build_upgrade_ram()
    if any(w in text for w in ["SSD", "ssd", "硬碟", "固態", "換硬碟", "HDD"]):
        return build_upgrade_ssd()
    if any(w in text for w in ["GPU", "gpu", "顯卡", "顯示卡", "獨顯", "RTX", "GTX", "RX"]):
        return build_upgrade_gpu()
    if any(w in text for w in ["效能分析", "瓶頸", "為什麼慢", "電腦很慢", "電腦效能"]):
        return build_upgrade_performance_check()
    return build_upgrade_menu()


def build_food_region_picker(style: str) -> list:
    """今天吃什麼 — 選擇地區（第一步）"""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32",
              "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    icons = {"便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗",
             "餐廳": "🏪"}
    icon = icons.get(style, "🍽️")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    regions = list(_AREA_REGIONS.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"{trigger} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"你在哪個地區？{icon}{style}推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🍽️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的{icon} {style}美食",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_food_area_picker(style: str, region: str = "") -> list:
    """今天吃什麼 — 選擇城市（第二步）"""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32",
              "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"{trigger} {a}"}}
                for a in row
            ]
        })
    buttons.append(
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "message", "label": "← 重選地區",
                    "text": trigger}}
    )
    return [{"type": "flex", "altText": f"{region}有哪些城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🍽️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_food_message(text: str) -> list:
    """今天吃什麼 — 主路由"""
    text_s = text.strip()

    # ── 解析區域（支援全台 22 縣市）──
    area = ""
    all_cities_pat = "|".join(_ALL_CITIES)
    area_match = re.search(rf'({all_cities_pat})\S{{0,6}}', text_s)
    if area_match:
        area = area_match.group(0)
    area_city = area[:2] if area else ""  # 取前兩字作為城市名

    # ── 解析地區（北部/中部/南部/東部離島）──
    region = ""
    for r in _AREA_REGIONS:
        if r in text_s:
            region = r
            break

    # ── 必比登推介 ──
    if "必比登" in text_s or "米其林" in text_s:
        return build_bib_gourmand_flex(area)

    # ── 在地餐廳路由 ──
    is_restaurant = "餐廳" in text_s or "在地餐廳" in text_s
    if is_restaurant:
        # 解析餐廳類型
        food_type = ""
        for ft in ["小吃", "中式", "日式", "西式", "海鮮", "火鍋", "素食", "地方特產"]:
            if ft in text_s:
                food_type = ft
                break
        if area_city:
            return build_food_restaurant_flex(area_city, food_type)
        if region:
            return build_food_area_picker("餐廳", region)
        return build_food_region_picker("餐廳")

    # ── 解析食物類型 ──
    style = ""
    for cat, kws in _STYLE_KEYWORDS.items():
        if any(w in text_s for w in kws):
            style = cat
            break
    if not style:
        style = "便當"  # 預設

    # ── 本週美食活動（Accupass 即時）──
    if "本週美食" in text_s or "美食活動" in text_s:
        if not area_city and region:
            # 有地區沒城市 → 顯示該地區城市選擇
            areas = _AREA_REGIONS.get(region, [])
            buttons = []
            for i in range(0, len(areas), 3):
                row = areas[i:i+3]
                buttons.append({"type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                         "action": {"type": "message", "label": a, "text": f"本週美食活動 {a}"}}
                        for a in row
                    ]})
            return [{"type": "flex", "altText": f"本週美食活動 — {region}",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": f"🎉 {region} — 選城市",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        if not area_city:
            # 沒指定地區也沒城市 → 先問地區
            buttons = [
                {"type": "button", "style": "primary", "color": "#D84315", "height": "sm",
                 "action": {"type": "message", "label": f"📍 {r}",
                            "text": f"本週美食活動 地區 {r}"}}
                for r in _AREA_REGIONS.keys()
            ]
            return [{"type": "flex", "altText": "本週美食活動 — 選地區",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": "🎉 本週美食活動",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                        {"type": "text", "text": "選擇地區查看近期美食活動",
                                         "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        live_area = area_city
        result = build_live_food_events(live_area)
        if result:
            return result
        # 沒有美食活動 → 告知使用者，提供替代選項
        return [{"type": "flex", "altText": f"{live_area}目前沒有美食活動",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                "contents": [
                                    {"type": "text", "text": f"🎉 {live_area} 美食活動",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": f"目前 {live_area} 沒有近期美食活動 😢",
                          "size": "sm", "color": "#555555", "wrap": True},
                         {"type": "text", "text": "試試其他方式找好吃的 👇",
                          "size": "xs", "color": "#888888", "margin": "sm"},
                     ]},
                     "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                             {"type": "button", "style": "primary", "color": "#6D4C41", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "在地餐廳",
                                                          "text": f"餐廳 {live_area}"}},
                             {"type": "button", "style": "primary", "color": "#C62828", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "享樂版推薦",
                                                          "text": f"吃什麼 享樂 {live_area}"}},
                         ]},
                         {"type": "button", "style": "secondary", "height": "sm",
                          "action": {"type": "message", "label": "回主選單", "text": "今天吃什麼"}},
                     ]},
                 }}]

    # ── 純呼叫主選單 ──
    if text_s in ["今天吃什麼", "晚餐吃什麼", "午餐吃什麼", "吃什麼", "晚餐推薦", "午餐推薦"]:
        return build_food_menu()

    # ── 有風格 + 有城市 → 直接推薦 ──
    if area:
        return build_food_flex(style, area)

    # ── 有風格 + 有地區 → 選城市 ──
    if region:
        return build_food_area_picker(style, region)

    # ── 有風格但沒城市 → 先問地區 ──
    has_style_kw = style != "便當" or any(w in text_s for w in ["便當"])
    is_internal = text_s.startswith("吃什麼 ")
    if has_style_kw and not is_internal:
        return build_food_region_picker(style)

    return build_food_flex(style, area)


# ─── 近期活動推薦 ──────────────────────────────────────

def _load_accupass_cache() -> dict:
    """載入 Accupass 爬蟲快取（accupass_cache.json）"""
    import time as _time
    try:
        # 從 api/ 上一層找 accupass_cache.json
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_path = os.path.join(base, "accupass_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", {})
    except Exception:
        return {}

_ACCUPASS_CACHE = _load_accupass_cache()


_ACTIVITY_DB = {
    "戶外踏青": [
        # 台北
        {"name": "陽明山國家公園", "desc": "火山地形、花海、登山步道，四季皆宜", "area": "台北"},
        {"name": "象山步道", "desc": "101 正面視角、夕陽夜景，市區就能爬山", "area": "台北"},
        {"name": "貓空纜車", "desc": "搭纜車俯瞰台北盆地，終點喝茶超愜意", "area": "台北"},
        {"name": "北投溫泉親水公園", "desc": "免費泡腳、溪流戲水，家庭週末好去處", "area": "台北"},
        # 新北
        {"name": "九份老街", "desc": "山城夜景、紅燈籠、芋圓必吃", "area": "新北"},
        {"name": "北海岸野柳地質公園", "desc": "女王頭、奇岩怪石，地球奇景就在台灣", "area": "新北"},
        {"name": "平溪天燈老街", "desc": "放天燈許願、瀑布健行，超浪漫", "area": "新北"},
        {"name": "福隆海水浴場", "desc": "沙雕節、衝浪、烤肉，北部最棒沙灘", "area": "新北"},
        # 台中
        {"name": "大雪山森林遊樂區", "desc": "賞鳥天堂、帝雉、黑長尾雉出沒", "area": "台中"},
        {"name": "福壽山農場", "desc": "蘋果園、高山蔬菜，秋冬楓紅超美", "area": "台中"},
        {"name": "武陵農場", "desc": "春天賞櫻第一名，溪流釣魚也很棒", "area": "台中"},
        {"name": "高美濕地", "desc": "夕陽倒影、風車海景，台中最美景點", "area": "台中"},
        # 台南
        {"name": "七股鹽山", "desc": "鹽田生態、台灣鹽博物館，老少皆宜", "area": "台南"},
        {"name": "曾文水庫", "desc": "南台灣最大水庫，環湖步道、湖光山色", "area": "台南"},
        {"name": "烏山頭水庫風景區", "desc": "八田與一紀念園區、環湖自行車道", "area": "台南"},
        {"name": "虎頭埤風景區", "desc": "划船、環湖步道，台南人的後花園", "area": "台南"},
        {"name": "走馬瀨農場", "desc": "露營、草皮、飛行傘，南部最大農場", "area": "台南"},
        {"name": "關子嶺溫泉", "desc": "泥漿溫泉全台唯一，泡完皮膚超好", "area": "台南"},
        # 高雄
        {"name": "壽山自然公園", "desc": "獼猴、海景步道、市區旁輕鬆踏青", "area": "高雄"},
        {"name": "茂林國家風景區", "desc": "紫蝶幽谷、峽谷瀑布，南台灣秘境", "area": "高雄"},
        {"name": "桃源區梅山", "desc": "春天梅花盛開，高山部落景致迷人", "area": "高雄"},
        {"name": "旗山老街", "desc": "香蕉之鄉、巴洛克建築、香蕉冰必吃", "area": "高雄"},
        # 其他縣市
        {"name": "太平山國家森林遊樂區", "desc": "雲海、檜木林、原始森林，超療癒", "area": "宜蘭"},
        {"name": "合歡山", "desc": "高山草原、冬天賞雪，壯觀視野", "area": "南投"},
        {"name": "日月潭環湖", "desc": "腳踏車環湖、船遊水社，湖光山色", "area": "南投"},
        {"name": "花蓮太魯閣", "desc": "峽谷地形、步道健行，台灣最壯觀景點", "area": "花蓮"},
        {"name": "墾丁國家公園", "desc": "海灘、珊瑚礁、熱帶風情，全年可玩", "area": "屏東"},
        {"name": "阿里山森林鐵路", "desc": "雲海、神木、日出，台灣高山代表", "area": "嘉義"},
        {"name": "奮起湖", "desc": "老街、森林鐵路便當，小鎮氛圍超好", "area": "嘉義"},
        {"name": "司馬庫斯部落", "desc": "巨木群、神木步道，遠離塵囂的秘境", "area": "新竹"},
        {"name": "清境農場", "desc": "高山牧場、歐式風情、雲霧繚繞", "area": "南投"},
    ],
    "文青咖啡": [
        # 台北
        {"name": "赤峰街商圈", "desc": "台北文青聖地，老屋改造咖啡廳密集", "area": "台北"},
        {"name": "富錦街", "desc": "台北最美林蔭道，歐式咖啡廳 + 選品店", "area": "台北"},
        {"name": "永康街商圈", "desc": "台北最有味道的老街，咖啡廳 + 書店", "area": "台北"},
        {"name": "松山文創園區", "desc": "老煙草工廠、設計展覽、咖啡廳", "area": "台北"},
        {"name": "華山1914文創園區", "desc": "酒廠改造、展演空間、假日市集超熱鬧", "area": "台北"},
        {"name": "中山站咖啡廳一條街", "desc": "從中山站到雙連，全台咖啡密度最高", "area": "台北"},
        # 台中
        {"name": "審計新村", "desc": "台中文創聚落，週末市集 + 質感小店", "area": "台中"},
        {"name": "台中第四信用合作社", "desc": "老銀行改造的質感咖啡廳，必拍打卡點", "area": "台中"},
        {"name": "范特喜微創文化", "desc": "貨櫃屋文創市集，小店密集超好逛", "area": "台中"},
        {"name": "忠信市場", "desc": "老市場改造藝文空間，展覽 + 咖啡", "area": "台中"},
        {"name": "草悟道", "desc": "台中最美大道，咖啡廳 + 書店連成一線", "area": "台中"},
        # 台南
        {"name": "神農街", "desc": "台南百年老街、文創小店、咖啡廳林立", "area": "台南"},
        {"name": "藍晒圖文創園區", "desc": "台南文創地標，特色商店 + 裝置藝術", "area": "台南"},
        {"name": "台南林百貨", "desc": "日治時代百貨，頂樓神社 + 文創選品", "area": "台南"},
        {"name": "正興街", "desc": "巷弄小店密集，老宅咖啡 + 創意甜點", "area": "台南"},
        {"name": "海安路藝術街", "desc": "街頭壁畫藝術、酒吧咖啡廳，文青必訪", "area": "台南"},
        {"name": "孔廟文化園區周邊", "desc": "府城老街巷弄，老宅咖啡 + 文史空間", "area": "台南"},
        {"name": "水交社文化園區", "desc": "眷村改造、黑膠咖啡、文化展覽", "area": "台南"},
        # 高雄
        {"name": "駁二藝術特區", "desc": "高雄港邊倉庫改造，藝術展覽 + 咖啡", "area": "高雄"},
        {"name": "前金老街咖啡廳群", "desc": "高雄文青新聚落，老屋改造咖啡超密集", "area": "高雄"},
        {"name": "新濱碼頭老街", "desc": "港口旁百年街區，老屋咖啡 + 文史散步", "area": "高雄"},
        {"name": "鹽埕區老街", "desc": "高雄最老商圈，懷舊風格小店 + 咖啡廳", "area": "高雄"},
        # 其他
        {"name": "勝利星村", "desc": "屏東眷村改造，慢活咖啡 + 特色小店", "area": "屏東"},
        {"name": "三峽老街", "desc": "清朝古厝、牛角麵包、悠閒午後", "area": "新北"},
        {"name": "鹿港老街", "desc": "鳳眼糕、蚵仔煎、台灣傳統工藝小鎮", "area": "彰化"},
        {"name": "大溪老街", "desc": "日式建築、豆干名產、桃園文青好去處", "area": "桃園"},
    ],
    "親子同樂": [
        # 台北
        {"name": "臺灣科學教育館", "desc": "互動展覽、科學實驗，小孩最愛", "area": "台北"},
        {"name": "兒童新樂園", "desc": "遊樂設施、摩天輪、週末親子首選", "area": "台北"},
        {"name": "故宮博物院", "desc": "翠玉白菜、肉形石，帶孩子認識台灣歷史", "area": "台北"},
        {"name": "台北市立天文科學教育館", "desc": "天象儀、太陽望遠鏡，假日免費開放", "area": "台北"},
        {"name": "台北市立動物園", "desc": "貓熊、無尾熊、企鵝館，半天玩不完", "area": "台北"},
        # 台中
        {"name": "麗寶樂園", "desc": "遊樂園 + 水樂園，暑假必去", "area": "台中"},
        {"name": "國立自然科學博物館", "desc": "恐龍、太空、生命科學館，必去", "area": "台中"},
        {"name": "台中兒童藝術館", "desc": "0-12歲互動展覽，雨天親子首選", "area": "台中"},
        # 台南
        {"name": "台南市立動物園", "desc": "免費入場、動物種類多，台南親子必去", "area": "台南"},
        {"name": "南科考古館", "desc": "8000年前遺址、古代生活互動體驗", "area": "台南"},
        {"name": "奇美博物館", "desc": "歐式建築、藝術 + 自然史展覽，台南必去", "area": "台南"},
        {"name": "台南市兒童交通安全公園", "desc": "兒童模擬開車、騎車，寓教於樂免費入場", "area": "台南"},
        {"name": "台灣歷史博物館", "desc": "台灣史互動展覽，適合國小以上小孩", "area": "台南"},
        # 高雄
        {"name": "義大遊樂世界", "desc": "高雄最大樂園，刺激設施超豐富", "area": "高雄"},
        {"name": "科工館（國立科學工藝博物館）", "desc": "科技互動展，假日親子活動多", "area": "高雄"},
        {"name": "夢時代購物中心（摩天輪）", "desc": "室內逛街 + 頂樓摩天輪，雨天也能玩", "area": "高雄"},
        # 其他
        {"name": "海生館（國立海洋生物博物館）", "desc": "全台最大水族館，企鵝 + 鯊魚超壯觀", "area": "屏東"},
        {"name": "新竹市立動物園", "desc": "全台最老動物園，小而美，免費入場", "area": "新竹"},
        {"name": "小人國主題樂園", "desc": "縮小版台灣景點模型，孩子玩一整天", "area": "桃園"},
        {"name": "礁溪溫泉公園", "desc": "免費泡腳池、戶外溫泉廣場，親子輕鬆遊", "area": "宜蘭"},
    ],
    "運動健身": [
        # 台北
        {"name": "大安森林公園", "desc": "台北市中心綠洲，跑步 + 戶外瑜伽", "area": "台北"},
        {"name": "大佳河濱公園", "desc": "腳踏車道、跑步步道、河岸風光", "area": "台北"},
        {"name": "關渡自然公園", "desc": "賞鳥 + 自行車，兼顧運動與自然生態", "area": "台北"},
        {"name": "象山步道", "desc": "爬完可以看101夜景，市區最佳運動路線", "area": "台北"},
        # 台中
        {"name": "大坑登山步道", "desc": "台中都市裡的健行天堂，1-10號難度各異", "area": "台中"},
        {"name": "東豐自行車綠廊", "desc": "舊鐵道改造，景色優美，適合全家", "area": "台中"},
        {"name": "后豐鐵馬道", "desc": "鐵橋 + 自行車道，接連東豐，風景漂亮", "area": "台中"},
        # 台南
        {"name": "台南都會公園", "desc": "慢跑步道、單車道、生態池，南部最大公園", "area": "台南"},
        {"name": "安平運動公園", "desc": "環境清幽、器材完善，早晨運動首選", "area": "台南"},
        {"name": "成功大學榕園（開放時段）", "desc": "百年榕樹慢跑步道，文青感十足", "area": "台南"},
        {"name": "鹽水八角樓自行車道", "desc": "古蹟騎乘路線，欣賞在地農村風光", "area": "台南"},
        # 高雄
        {"name": "愛河自行車道", "desc": "高雄愛河沿岸，夜晚也很美", "area": "高雄"},
        {"name": "左營蓮池潭", "desc": "環潭慢跑、龍虎塔打卡，假日熱鬧", "area": "高雄"},
        {"name": "旗津海岸公園", "desc": "沙灘慢跑、風車、海景，高雄週末好去處", "area": "高雄"},
        {"name": "澄清湖", "desc": "環湖自行車道 + 散步，高雄最大淡水湖", "area": "高雄"},
        # 其他
        {"name": "羅東運動公園", "desc": "草皮廣大、慢跑步道、湖畔風景優美", "area": "宜蘭"},
        {"name": "集集綠色隧道", "desc": "樟樹林蔭大道，騎車穿越超愜意", "area": "南投"},
        {"name": "新店碧潭", "desc": "泛舟 + 吊橋散步，台北近郊輕運動", "area": "新北"},
        {"name": "虎頭山公園", "desc": "桃園輕鬆爬山、視野好，假日常見跑者", "area": "桃園"},
    ],
    "吃喝玩樂": [
        # 台北
        {"name": "士林夜市", "desc": "台灣最大夜市，必吃大餅包小餅、士林大香腸", "area": "台北"},
        {"name": "饒河街觀光夜市", "desc": "台北知名夜市，胡椒餅不能錯過", "area": "台北"},
        {"name": "寧夏夜市", "desc": "蚵仔煎、古早味豬血糕、台北最在地夜市", "area": "台北"},
        {"name": "通化夜市", "desc": "天津蔥抓餅發源地，台北南區必逛", "area": "台北"},
        # 台中
        {"name": "逢甲夜市", "desc": "台中最熱鬧夜市，創意小吃層出不窮", "area": "台中"},
        {"name": "忠孝夜市", "desc": "台中在地人去的夜市，平價好吃不觀光", "area": "台中"},
        {"name": "一中商圈", "desc": "學生聚集地、手搖飲 + 小吃密集", "area": "台中"},
        # 台南
        {"name": "花園夜市", "desc": "台南最大夜市，週四六日才有，必訪", "area": "台南"},
        {"name": "林森夜市", "desc": "台南在地人才知道的夜市，不觀光不踩雷", "area": "台南"},
        {"name": "武聖夜市", "desc": "週二四日開，推薦蚵仔麵線和鹽酥雞", "area": "台南"},
        {"name": "大東夜市", "desc": "週一三五開，台南最多元的夜市", "area": "台南"},
        {"name": "安平老街", "desc": "蚵仔酥、蝦餅、劍獅伴手禮一條買齊", "area": "台南"},
        {"name": "赤崁樓周邊小吃", "desc": "擔仔麵、棺材板、杏仁豆腐，府城精華", "area": "台南"},
        # 高雄
        {"name": "六合夜市", "desc": "高雄觀光夜市，海鮮 + 在地小吃", "area": "高雄"},
        {"name": "瑞豐夜市", "desc": "高雄在地人愛去的夜市，週末才開", "area": "高雄"},
        {"name": "鳳山商圈夜市", "desc": "鳳山在地小吃激戰區，隱藏版美食多", "area": "高雄"},
        {"name": "三鳳中街", "desc": "南北雜貨批發街，年節前必來掃貨", "area": "高雄"},
        # 其他
        {"name": "廟口夜市", "desc": "基隆海鮮小吃集中地，天婦羅、鼎邊銼必吃", "area": "基隆"},
        {"name": "羅東夜市", "desc": "宜蘭特色小吃，三星蔥餅、卜肉超好吃", "area": "宜蘭"},
        {"name": "新竹城隍廟商圈", "desc": "貢丸湯、米粉炒，新竹小吃一次掃完", "area": "新竹"},
        {"name": "嘉義文化路夜市", "desc": "雞肉飯、火雞肉飯，嘉義人的驕傲", "area": "嘉義"},
    ],
    "市集展覽": [
        # 台北
        {"name": "華山文創市集", "desc": "設計師手作、藝術品、文創選物，假日必逛", "area": "台北"},
        {"name": "松菸誠品市集", "desc": "選品質感高、獨立品牌集中，台北文青首選", "area": "台北"},
        {"name": "台北當代藝術館", "desc": "當代藝術展覽，老建築新靈魂", "area": "台北"},
        {"name": "信義公民會館假日市集", "desc": "農夫市集 + 手作小物，親子友善", "area": "台北"},
        # 台中
        {"name": "審計新村週末市集", "desc": "文創小物、手作甜點、台中最有氣質市集", "area": "台中"},
        {"name": "國立台灣美術館", "desc": "免費入場，常設展 + 特展輪替，台中必去", "area": "台中"},
        {"name": "台中市集（草悟廣場）", "desc": "戶外市集、街頭表演，週末活力滿點", "area": "台中"},
        {"name": "台中文創園區（舊酒廠）", "desc": "台中文化部文創園區，不定期市集與展覽", "area": "台中"},
        {"name": "興大有機農夫市集", "desc": "每週六在中興大學，有機蔬果 + 手作食品", "area": "台中"},
        {"name": "豐原廟東創意市集", "desc": "老廟前的創意小攤，在地特色小物與小吃", "area": "台中"},
        {"name": "台中市纖維工藝博物館", "desc": "纖維與布藝主題展覽，特展常態輪替", "area": "台中"},
        {"name": "勤美術館週末展覽", "desc": "草悟道旁的戶外藝術裝置 + 期間特展", "area": "台中"},
        # 台南
        {"name": "藍晒圖文創園區市集", "desc": "週末小市集、手作體驗、台南文青聖地", "area": "台南"},
        {"name": "台南文化中心特展", "desc": "各類主題展覽，適合全家親子同遊", "area": "台南"},
        {"name": "神農街週末創意市集", "desc": "府城老街手作市集，在地藝術家聚集", "area": "台南"},
        {"name": "奇美博物館特展", "desc": "藝術 + 自然史，台南最高規格展覽空間", "area": "台南"},
        {"name": "台南美術館", "desc": "南美館1館+2館，台南藝術新地標", "area": "台南"},
        # 高雄
        {"name": "駁二藝術特區特展", "desc": "港邊倉庫展覽空間，藝術裝置輪替不重複", "area": "高雄"},
        {"name": "高雄市立美術館", "desc": "免費入場，戶外雕塑公園 + 室內特展", "area": "高雄"},
        {"name": "衛武營藝術文化中心", "desc": "國家級表演廳，也有免費戶外展演", "area": "高雄"},
        {"name": "三鳳中街文創市集", "desc": "傳統與文創融合，高雄獨特市集體驗", "area": "高雄"},
        # 其他
        {"name": "宜蘭傳統藝術中心", "desc": "傳統工藝、老街、假日表演，親子必去", "area": "宜蘭"},
        {"name": "嘉義鐵道藝術村", "desc": "舊倉庫改造，藝術展覽 + 創意市集", "area": "嘉義"},
    ],
    "表演音樂": [
        # 台北
        {"name": "台北小巨蛋", "desc": "大型演唱會主場地，各大歌手常駐", "area": "台北"},
        {"name": "國家音樂廳", "desc": "古典樂、交響樂、歌劇，殿堂級表演", "area": "台北"},
        {"name": "Legacy Taipei", "desc": "中型演唱會、獨立樂團首選場地", "area": "台北"},
        {"name": "河岸留言", "desc": "台北獨立音樂聖地，每週末都有現場演出", "area": "台北"},
        {"name": "The Wall", "desc": "搖滾、indie 音樂，台灣地下音樂重鎮", "area": "台北"},
        # 台中
        {"name": "台中國家歌劇院", "desc": "世界級建築、高規格表演，台中驕傲", "area": "台中"},
        {"name": "Legacy Taichung", "desc": "台中版 Legacy，中型演唱會場地", "area": "台中"},
        {"name": "中山堂（台中）", "desc": "平價演出、在地樂團，接地氣的表演場所", "area": "台中"},
        # 台南
        {"name": "台南文化中心演藝廳", "desc": "台南最大表演廳，各類演出都有", "area": "台南"},
        {"name": "衛屋茶事（文化沙龍）", "desc": "小型音樂會、說書、台南慢生活體驗", "area": "台南"},
        {"name": "甲仙阿里山音樂節", "desc": "戶外音樂祭，南台灣年度盛事", "area": "台南"},
        {"name": "台南人劇團", "desc": "台灣最活躍劇團之一，實驗劇場演出", "area": "台南"},
        # 高雄
        {"name": "衛武營國家藝術文化中心", "desc": "南台灣最大表演場館，音樂劇、芭蕾、演唱會", "area": "高雄"},
        {"name": "駁二大義倉庫", "desc": "戶外演唱會、市集音樂節，港邊最佳氛圍", "area": "高雄"},
        {"name": "春天吶喊（墾丁）", "desc": "台灣最大搖滾音樂祭，每年春假必去", "area": "屏東"},
        # 其他
        {"name": "海洋音樂祭（貢寮）", "desc": "夏天在海邊聽搖滾，全台最熱血音樂節", "area": "新北"},
        {"name": "簡單生活節", "desc": "台北年度生活風格音樂祭，文青必去", "area": "台北"},
    ],
}


def _parse_event_date(date_str: str):
    """解析活動日期字串，回傳 date 物件；失敗回傳 None"""
    import datetime as _dt
    if not date_str:
        return None
    # 支援範圍格式：取結束日期（例如 "04/10-04/13" 取 "04/13"）
    range_m = re.search(r'(\d{1,2})[/\-.](\d{1,2})\s*[~～\-–]\s*(\d{1,2})[/\-.](\d{1,2})', date_str)
    if range_m:
        try:
            end_date = _dt.date(
                _dt.date.today().year,
                int(range_m.group(3)), int(range_m.group(4))
            )
            return end_date
        except ValueError:
            pass
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%m/%d", "%m.%d"):
        try:
            cleaned = re.split(r'[\s(（~～]', date_str)[0].strip()
            d = _dt.datetime.strptime(cleaned, fmt)
            if fmt in ("%m/%d", "%m.%d"):
                d = d.replace(year=_dt.date.today().year)
            return d.date()
        except ValueError:
            continue
    return None


def _is_event_past(date_str: str) -> bool:
    """判斷活動是否已過期（結束日在 3 天前以上）
    - 3 天緩衝：保留本週末還在進行的活動
    - 無日期 → 保留（可能是長期展覽）
    - 超過 60 天前開始且無明確結束日 → 視為過期
    """
    import datetime as _dt
    today = _dt.date.today()
    d = _parse_event_date(date_str)
    if d is None:
        return False  # 無法解析 → 保留
    # 超過 3 天前（含）視為過期
    return d < (today - _dt.timedelta(days=3))


def _parse_event_weekday(date_str: str) -> str:
    """嘗試從活動日期字串解析星期幾，回傳 '五'/'六'/'日' 或空字串"""
    import datetime as _dt
    if not date_str:
        return ""
    d = _parse_event_date(date_str)
    if d:
        return {4: "五", 5: "六", 6: "日"}.get(d.weekday(), "")
    # 嘗試從括號裡直接抓 (六) (日) 等
    m = re.search(r'[（(]([\u4e00-\u9fff])[)）]', date_str)
    if m and m.group(1) in ("五", "六", "日"):
        return m.group(1)
    return ""


def _get_coming_weekend_label() -> str:
    """回傳最近週末的日期標示，例如 '4/11(五)–4/13(日)'"""
    import datetime as _dt
    today = _dt.date.today()
    wd = today.weekday()  # 0=Mon
    days_until_fri = (4 - wd) % 7
    if days_until_fri == 0 and wd == 4:
        days_until_fri = 0
    elif wd in (5, 6):
        days_until_fri = 0  # 已經是週末
    fri = today + _dt.timedelta(days=days_until_fri)
    if wd == 5:
        fri = today - _dt.timedelta(days=1)
    elif wd == 6:
        fri = today - _dt.timedelta(days=2)
    sun = fri + _dt.timedelta(days=2)
    return f"{fri.month}/{fri.day}(五)–{sun.month}/{sun.day}(日)"


def build_activity_flex(category: str, area: str = "") -> list:
    """列出所有活動推薦（即時＋推薦景點），用 carousel 多頁呈現"""
    area2 = area[:2] if area else ""

    # ── 1. 從 Accupass 快取取得即時活動 ──
    import datetime as _dt
    live_events = []
    skipped_past = 0
    if _ACCUPASS_CACHE and area2:
        city_cache = _ACCUPASS_CACHE.get(area, _ACCUPASS_CACHE.get(area2, {}))
        live_raw = city_cache.get(category, [])
        for e in live_raw:
            date_str = e.get("date", "")
            # ── 過濾已過期活動（結束日在 3 天前以上）──
            if _is_event_past(date_str):
                skipped_past += 1
                continue
            day_label  = _parse_event_weekday(date_str)
            date_short = date_str.split(" ")[0] if date_str else ""
            event_date = _parse_event_date(date_str)  # 用於排序
            live_events.append({
                "name":       e.get("name", ""),
                "desc":       e.get("desc", ""),
                "area":       area,
                "url":        e.get("url", ""),
                "is_live":    True,
                "day":        day_label,
                "date_short": date_short,
                "_date":      event_date,   # 內部排序用，不顯示
            })
    if skipped_past:
        print(f"[activity] 過濾掉 {skipped_past} 筆已過期活動")

    # ── 2. 從靜態資料庫取得推薦景點 ──
    static_pool = _ACTIVITY_DB.get(category, [])
    if area2:
        static_filtered = [a for a in static_pool if area2 in a.get("area", "")]
        if not static_filtered:
            static_filtered = static_pool
    else:
        static_filtered = static_pool

    live_names = {e["name"] for e in live_events}
    static_dedup = [e for e in static_filtered if e["name"] not in live_names]

    colors = {
        "戶外踏青": "#2E7D32", "文青咖啡": "#4527A0", "親子同樂": "#E65100",
        "運動健身": "#1565C0", "吃喝玩樂": "#C62828",
        "市集展覽": "#6A1B9A", "表演音樂": "#AD1457",
    }
    color = colors.get(category, "#FF8C42")
    area_label = f"（{area}）" if area else ""
    cats = list(_ACTIVITY_DB.keys())
    next_cat = cats[(cats.index(category) + 1) % len(cats)]
    weekend_label = _get_coming_weekend_label()

    # ── 3. 即時活動依日期由近到遠排序（無日期排最後）──
    _far_future = _dt.date(2099, 12, 31)
    live_events.sort(key=lambda x: x.get("_date") or _far_future)

    # ── 4. 建立 bubble 內容項目的 helper ──
    def _make_items(acts: list) -> list:
        items = []
        for i, act in enumerate(acts):
            is_live = act.get("is_live", False)
            date_info = act.get("date_short", "")
            day_info = act.get("day", "")
            if is_live and date_info:
                tag = f"🆕 {date_info}"
            elif is_live and day_info:
                tag = f"🆕 週{day_info}"
            elif is_live:
                tag = "🔄 進行中"   # 無明確日期 → 長期展覽/持續活動
            else:
                tag = "📌 推薦"
            detail_btn = (
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📅 活動頁面",
                            "uri": act.get("url") or "https://www.accupass.com"}}
                if is_live else
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📍 地圖",
                            "uri": _maps_url(act["name"], act.get("area", ""))}}
            )
            # 分享文字：這個活動 + bot 邀請（壓短避免超過 LINE URI 1000 字元限制）
            _act_name = act["name"][:20]
            _act_date = act.get("date_short") or (f"週{act.get('day','')}" if act.get("day") else "")
            _date_str = f" {_act_date}" if _act_date else ""
            _invite = f"\n👉 搜「生活優轉」也來查" if not LINE_BOT_ID else f"\nhttps://line.me/ti/p/{LINE_BOT_ID}"
            _share_raw = f"📍 揪你去！\n🎪 {_act_name}{_date_str}{_invite}"
            _share_url_act = "https://line.me/R/share?text=" + urllib.parse.quote(_share_raw)
            share_btn = {"type": "button", "style": "link", "height": "sm", "flex": 1,
                         "action": {"type": "uri", "label": "📤 揪朋友去", "uri": _share_url_act}}

            # 截短描述，避免某頁撐太高導致其他頁留白
            desc_raw = act.get("desc", "")
            desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
            items += [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": f"• {act['name']}", "weight": "bold",
                     "size": "sm", "color": color, "flex": 4, "wrap": True,
                     "maxLines": 2},
                    {"type": "text", "text": tag, "size": "xxs",
                     "color": "#888888", "flex": 2, "align": "end"},
                ]},
                {"type": "text", "text": desc, "size": "xs",
                 "color": "#555555", "wrap": True, "margin": "xs",
                 "maxLines": 2},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [detail_btn, share_btn]},
            ]
            if i < len(acts) - 1:
                items.append({"type": "separator", "margin": "sm"})
        return items

    def _make_bubble(title_line2: str, acts: list, is_first: bool = False) -> dict:
        bubble = {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                *([ {"type": "text", "text": f"{category} — {weekend_label}",
                                     "color": "#8892B0", "size": "xs", "margin": "xs"} ] if is_first else []),
                                {"type": "text", "text": title_line2,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                     "contents": _make_items(acts)},
        }
        return bubble

    # ── 5. 合併即時＋靜態，一起分頁 ──
    bubbles = []
    MAX_PER_BUBBLE = 8

    # 即時活動：每分類每城市上限 10 筆，每 8 筆一頁
    live_capped = live_events[:10]
    if live_capped:
        for chunk_start in range(0, len(live_capped), MAX_PER_BUBBLE):
            chunk = live_capped[chunk_start:chunk_start + MAX_PER_BUBBLE]
            label = "🆕 近期活動"
            if len(live_capped) > MAX_PER_BUBBLE:
                page = chunk_start // MAX_PER_BUBBLE + 1
                label += f"（{page}）"
            bubbles.append(_make_bubble(label, chunk, is_first=(len(bubbles) == 0)))

    # 靜態推薦景點：只取前 5 個
    if static_dedup:
        top_static = static_dedup[:5]
        bubbles.append(_make_bubble("📌 推薦景點", top_static, is_first=(len(bubbles) == 0)))

    # 最後一個 bubble 加上 footer 導航按鈕
    if bubbles:
        # 分享文字（壓短避免超過 LINE URI 1000 字元限制）
        _share_acts = (live_events[:2] or static_dedup[:2])
        _share_names = "、".join([e['name'][:12] for e in _share_acts])
        _invite = f"\nhttps://line.me/ti/p/{LINE_BOT_ID}" if LINE_BOT_ID else "\n👉 搜「生活優轉」"
        _share_text = f"🗓️ {area_label}好去處！\n{_share_names}{_invite}"
        _act_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
        bubbles[-1]["footer"] = {
            "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "primary", "color": color, "flex": 1,
                     "height": "sm", "action": {"type": "message",
                                                 "label": f"👉 {next_cat}",
                                                 "text": f"周末 {next_cat} {area}"}},
                    {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                     "height": "sm", "action": {"type": "message",
                                                 "label": "← 回選單",
                                                 "text": "周末去哪"}},
                ]},
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "message", "label": "🌤️ 今日天氣",
                                "text": f"{area[:2] if area else '台北'}天氣"}},
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "uri", "label": "📤 分享活動",
                                "uri": _act_share_url}},
                ]},
            ]}

    # 如果完全沒有活動
    if not bubbles:
        bubbles = [{
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": f"目前 {area} 沒有找到 {category} 相關活動",
                 "size": "sm", "color": "#555555", "wrap": True},
            ]},
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                 "action": {"type": "message", "label": "← 回選單", "text": "周末去哪"}},
            ]},
        }]

    if len(bubbles) == 1:
        return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
                 "contents": bubbles[0]}]
    return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_activity_menu() -> list:
    """近期活動 — 主選單"""
    ACCENT = "#5C6BC0"
    return [{"type": "flex", "altText": "近期活動",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "image",
                                 "url": "https://3c-advisor.vercel.app/liff/images/calendar.jpg",
                                 "flex": 0, "size": "72px",
                                 "aspectRatio": "1:1", "aspectMode": "fit"},
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": ACCENT,
                                 "margin": "md", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "🗓️ 近期活動？",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "幫你找好玩的地方！",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "選一個你想玩的類型 👇",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold"},
                     {"type": "text", "text": "也可以說「台南 戶外踏青」「台北 文青咖啡」",
                      "size": "xs", "color": "#8892B0", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🌿 戶外踏青", "text": "周末 戶外踏青"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "☕ 文青咖啡", "text": "周末 文青咖啡"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "👶 親子同樂", "text": "周末 親子同樂"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動健身", "text": "周末 運動健身"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍜 吃喝玩樂", "text": "周末 吃喝玩樂"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🎨 市集展覽", "text": "周末 市集展覽"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "🎵 表演音樂", "text": "周末 表演音樂"}},
                 ]},
             }}]


# 全台 22 縣市分區
_AREA_REGIONS = {
    "北部": ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部": ["台中", "彰化", "南投", "雲林"],
    "南部": ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}
_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]


def build_activity_region_picker(category: str) -> list:
    """近期活動 — 第一步：選擇區域"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    regions = list(_AREA_REGIONS.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"活動 {category} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"近期{category}在哪個地區？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🗓️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_activity_area_picker(category: str, region: str = "") -> list:
    """近期活動 — 第二步：選擇城市"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"周末 {category} {a}"}}
                for a in row
            ]
        })
    # 加一個「← 重選地區」按鈕
    buttons.append({
        "type": "button", "style": "link", "height": "sm",
        "action": {"type": "message", "label": "← 重選地區",
                   "text": f"周末 {category}"}
    })
    return [{"type": "flex", "altText": f"近期{category}在哪個城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🗓️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_activity_message(text: str) -> list:
    """近期活動 — 主路由"""
    text_s = text.strip()

    # 解析類別
    category = None
    for cat in _ACTIVITY_DB.keys():
        if cat in text_s:
            category = cat
            break
    if not category:
        if any(w in text_s for w in ["爬山", "踏青", "健行", "大自然"]):
            category = "戶外踏青"
        elif any(w in text_s for w in ["咖啡", "文青", "藝文"]):
            category = "文青咖啡"
        elif any(w in text_s for w in ["小孩", "親子", "家庭", "帶小孩"]):
            category = "親子同樂"
        elif any(w in text_s for w in ["運動", "跑步", "騎車", "健身"]):
            category = "運動健身"
        elif any(w in text_s for w in ["夜市", "美食", "吃", "逛街"]):
            category = "吃喝玩樂"
        elif any(w in text_s for w in ["市集", "展覽", "展", "博物館", "美術館"]):
            category = "市集展覽"
        elif any(w in text_s for w in ["演唱會", "音樂", "表演", "演出", "音樂節", "livehouse"]):
            category = "表演音樂"

    # 解析區域（支援全台 22 縣市）
    area = ""
    all_cities_pattern = "|".join(_ALL_CITIES)
    area_match = re.search(rf'({all_cities_pattern})', text_s)
    if area_match:
        area = area_match.group(0)

    # 解析地區（北部/中部/南部/東部離島）
    region = ""
    for r in _AREA_REGIONS:
        if r in text_s:
            region = r
            break

    if not category:
        return build_activity_menu()
    # 有類別 + 有城市 → 直接顯示活動
    if area:
        return build_activity_flex(category, area)
    # 有類別 + 有地區 → 顯示該地區城市選擇
    if region:
        return build_activity_area_picker(category, region)
    # 有類別但沒地區 → 先問在哪個地區
    return build_activity_region_picker(category)


# ─── 天氣＋穿搭建議 ──────────────────────────────────────

# 中央氣象署 API Key（Vercel 環境變數 CWA_API_KEY）
_CWA_KEY = os.environ.get("CWA_API_KEY", "")

_CWA_CITY_MAP = {
    "台北": "臺北市", "台中": "臺中市", "台南": "臺南市", "高雄": "高雄市",
    "新北": "新北市", "桃園": "桃園市", "基隆": "基隆市",
    "新竹": "新竹縣", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "嘉義": "嘉義縣",
    "屏東": "屏東縣", "宜蘭": "宜蘭縣", "花蓮": "花蓮縣",
    "台東": "臺東縣", "澎湖": "澎湖縣", "金門": "金門縣", "連江": "連江縣",
}
# 天氣城市用全台 22 縣市（跟 _ALL_CITIES 一致）
_WEATHER_CITIES = _ALL_CITIES

# 環境部空氣品質 API Key（Vercel 環境變數 MOE_API_KEY）
_MOE_KEY = os.environ.get("MOE_API_KEY", "")

# 城市 → 代表測站（取各縣市最具代表性的測站）
_AQI_STATION = {
    "台北": "中正", "台中": "西屯", "台南": "台南", "高雄": "前金",
    "新北": "板橋", "桃園": "桃園", "新竹": "新竹", "苗栗": "苗栗",
    "彰化": "彰化", "嘉義": "嘉義", "屏東": "屏東", "宜蘭": "宜蘭",
    "花蓮": "花蓮", "台東": "台東", "基隆": "基隆", "澎湖": "馬公",
    "南投": "南投", "雲林": "斗六", "金門": "金門", "連江": "馬祖",
}


def _fetch_cwa_weather(city: str) -> dict:
    """呼叫中央氣象署 F-C0032-001 取得36小時天氣預報"""
    if not _CWA_KEY:
        return {"ok": False, "error": "no_key"}
    cwb_name = _CWA_CITY_MAP.get(city, city + "市")
    url = (
        "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        f"?Authorization={_CWA_KEY}"
        f"&locationName={urllib.parse.quote(cwb_name)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("success") != "true":
            return {"ok": False, "error": "api_error"}
        locs = data["records"]["location"]
        if not locs:
            return {"ok": False, "error": "no_data"}
        elems = {e["elementName"]: e["time"] for e in locs[0]["weatherElement"]}

        def _get(key, idx, default="—"):
            try:
                return elems[key][idx]["parameter"]["parameterName"]
            except Exception:
                return default

        return {
            "ok": True, "city": city,
            # 今日白天
            "wx": _get("Wx", 0), "pop": int(_get("PoP", 0, "0")),
            "min_t": int(_get("MinT", 0, "20")), "max_t": int(_get("MaxT", 0, "25")),
            # 今晚
            "wx_night": _get("Wx", 1), "pop_night": int(_get("PoP", 1, "0")),
            # 明天
            "wx_tom": _get("Wx", 2), "pop_tom": int(_get("PoP", 2, "0")),
            "min_tom": int(_get("MinT", 2, "20")), "max_tom": int(_get("MaxT", 2, "25")),
        }
    except Exception as e:
        print(f"[weather] {e}")
        return {"ok": False, "error": str(e)}


def _wx_icon(wx: str) -> str:
    if "晴" in wx and "雲" not in wx:  return "☀️"
    if "晴" in wx:                     return "🌤️"
    if "雷" in wx:                     return "⛈️"
    if "雨" in wx:                     return "🌧️"
    if "陰" in wx:                     return "☁️"
    if "多雲" in wx:                   return "⛅"
    if "雪" in wx:                     return "❄️"
    return "🌤️"


def _outfit_advice(max_t: int, min_t: int, pop: int) -> tuple:
    """回傳 (穿搭建議, 補充說明)"""
    if max_t >= 32:
        c, n = "輕薄短袖＋透氣材質", "防曬乳必備，帽子加分，小心中暑"
    elif max_t >= 28:
        c, n = "短袖為主，薄外套備著", "室內冷氣強，包包放一件薄外套"
    elif max_t >= 24:
        c, n = "薄長袖或短袖＋輕便外套", "早晚涼，外套放包包最方便"
    elif max_t >= 20:
        c, n = "輕便外套或薄夾克", "早晚溫差大，多一層最安全"
    elif max_t >= 16:
        c, n = "毛衣＋外套", "圍巾帶著，隨時可以拿出來用"
    elif max_t >= 12:
        c, n = "厚外套＋衛衣", "手套、圍巾都考慮帶上"
    else:
        c, n = "羽絨衣＋多層次穿搭", "室內室外差很多，穿脫方便最重要"

    umbrella = ""
    if pop >= 70:   umbrella = "☂️ 雨傘必帶！降雨機率很高"
    elif pop >= 40: umbrella = "🌂 建議帶折疊傘備用"
    elif pop >= 20: umbrella = "☁️ 零星降雨可能，輕便傘備著"
    return c, n, umbrella


def _fetch_aqi(city: str) -> dict:
    """從環境部 aqx_p_432 取得即時 AQI（需 MOE_API_KEY）"""
    if not _MOE_KEY:
        return {"ok": False}
    station = _AQI_STATION.get(city, city)
    url = (
        "https://data.moenv.gov.tw/api/v2/aqx_p_432"
        f"?api_key={_MOE_KEY}&limit=3&sort=ImportDate+desc"
        f"&filters=SiteName,EQ,{urllib.parse.quote(station)}"
        "&format=JSON&fields=SiteName,AQI,Status,PM2.5,Pollutant"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        recs = data.get("records", [])
        if not recs:
            return {"ok": False}
        rec = recs[0]
        aqi = int(rec.get("AQI") or 0)
        status = rec.get("Status", "")
        pm25 = rec.get("PM2.5", "")
        pollutant = rec.get("Pollutant", "")
        # AQI 顏色與 emoji
        if aqi <= 50:    color, emoji = "#2E7D32", "🟢"
        elif aqi <= 100: color, emoji = "#F9A825", "🟡"
        elif aqi <= 150: color, emoji = "#E65100", "🟠"
        elif aqi <= 200: color, emoji = "#C62828", "🔴"
        else:            color, emoji = "#6A1B9A", "🟣"
        label = f"{emoji} AQI {aqi}　{status}"
        if pm25:       label += f"　PM2.5: {pm25}"
        if pollutant:  label += f"　主因: {pollutant}"
        return {"ok": True, "aqi": aqi, "label": label, "color": color}
    except Exception as e:
        print(f"[AQI] {e}")
        return {"ok": False}


def _estimate_uvi(wx: str, max_t: int) -> dict:
    """根據天氣狀況和氣溫估算紫外線等級（不依賴外部 API，永遠有結果）"""
    import datetime as _dt
    h = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).hour

    # 夜間/清晨/傍晚 UV 很低
    if h < 7 or h > 17:
        return {"ok": True, "label": "☀️ 紫外線：低（日落後）", "emoji": "🟢"}

    # 基礎 UV 依季節和氣溫估算（台灣緯度，夏天高冬天低）
    if max_t >= 33:
        base = 10  # 盛夏大晴天
    elif max_t >= 30:
        base = 8
    elif max_t >= 27:
        base = 6
    elif max_t >= 23:
        base = 4
    else:
        base = 3

    # 依天氣修正
    if "雨" in wx:
        base = max(1, base - 4)
    elif "陰" in wx:
        base = max(2, base - 3)
    elif "雲" in wx:
        base = max(3, base - 1)

    # 正午最強，早晚較弱
    if 10 <= h <= 14:
        uvi = base
    elif 9 <= h <= 15:
        uvi = max(2, base - 1)
    elif 7 <= h <= 17:
        uvi = max(1, base - 2)
    else:
        uvi = max(1, base - 3)

    if uvi <= 2:     level = "低量"
    elif uvi <= 5:   level = "中量"
    elif uvi <= 7:   level = "高量"
    elif uvi <= 10:  level = "過量"
    else:            level = "危險"

    advice = ""
    if uvi >= 6:
        advice = "建議擦防曬、戴帽子"
    elif uvi >= 3:
        advice = "外出建議擦防曬"

    label = f"☀️ 紫外線 {level}（UV {uvi}）"
    if advice:
        label += f"　{advice}"
    return {"ok": True, "label": label}


def build_weather_flex(city: str) -> list:
    """天氣＋穿搭建議卡片"""
    w = _fetch_cwa_weather(city)
    if not w.get("ok"):
        if w.get("error") == "no_key":
            return [{"type": "text", "text":
                "⚠️ 天氣功能需要設定 CWA API Key\n"
                "請到 Vercel → Settings → Environment Variables\n"
                "加入 CWA_API_KEY\n"
                "申請（免費）：https://opendata.cwa.gov.tw/user/api"}]
        return [{"type": "text", "text": f"😢 目前無法取得 {city} 的天氣資料，請稍後再試"}]

    clothes, note, umbrella = _outfit_advice(w["max_t"], w["min_t"], w["pop"])
    icon = _wx_icon(w["wx"])
    icon_n = _wx_icon(w["wx_night"])
    icon_t = _wx_icon(w["wx_tom"])
    aqi = _fetch_aqi(city)

    if "雨" in w["wx"]:         hdr = "#1565C0"
    elif w["max_t"] >= 30:     hdr = "#E65100"
    elif w["max_t"] >= 24:     hdr = "#F57C00"
    else:                      hdr = "#37474F"

    body = [
        # 今日概況：天氣＋溫度
        {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{icon} {w['wx']}", "size": "lg", "weight": "bold",
             "color": hdr, "flex": 3, "wrap": True},
            {"type": "text", "text": f"{w['min_t']}–{w['max_t']}°C",
             "size": "lg", "weight": "bold", "color": hdr, "flex": 2, "align": "end"},
        ]},
        # 降雨＋今晚
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": f"💧 降雨 {w['pop']}%", "size": "sm", "color": "#555555", "flex": 1},
            {"type": "text", "text": f"今晚 {icon_n} 雨{w['pop_night']}%",
             "size": "sm", "color": "#555555", "flex": 1, "align": "end"},
        ]},
    ]
    # AQI 行
    if aqi.get("ok"):
        body.append({"type": "text", "text": aqi["label"], "size": "sm",
                     "color": aqi["color"], "wrap": True, "margin": "xs"})
    body.append({"type": "separator", "margin": "md"})
    # 穿搭建議
    body += [
        {"type": "text", "text": "👗 今日穿搭建議", "size": "md", "weight": "bold",
         "color": "#333333", "margin": "md"},
        {"type": "text", "text": clothes, "size": "sm", "color": "#444444",
         "wrap": True, "margin": "xs"},
        {"type": "text", "text": f"💡 {note}", "size": "sm", "color": "#777777",
         "wrap": True, "margin": "xs"},
    ]
    if umbrella:
        body.append({"type": "text", "text": umbrella, "size": "sm",
                     "color": "#1565C0", "weight": "bold", "margin": "sm"})

    body += [
        {"type": "separator", "margin": "md"},
        # 明天預覽
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": "明日", "size": "sm", "color": "#999999", "flex": 1},
            {"type": "text", "text": f"{icon_t} {w['wx_tom']}", "size": "sm",
             "color": "#555555", "flex": 2},
            {"type": "text", "text": f"{w['min_tom']}–{w['max_tom']}°C  雨{w['pop_tom']}%",
             "size": "sm", "color": "#555555", "flex": 3, "align": "end"},
        ]},
    ]

    others = [c for c in _WEATHER_CITIES if c != city][:4]
    city_row = [{"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                 "action": {"type": "message", "label": c, "text": f"{c}天氣"}}
                for c in others]

    food_label = "雨天吃什麼" if "雨" in w["wx"] else "今天吃什麼"
    food_text  = "吃什麼 享樂" if "雨" in w["wx"] else "今天吃什麼"

    # 天氣分享文字（給家人/朋友提醒）
    _umbrella_hint = f"\n{umbrella}" if umbrella else ""
    _weather_share = (
        f"🌤️ {city}今天天氣\n"
        f"{icon} {w['wx']}　{w['min_t']}–{w['max_t']}°C\n"
        f"💧 降雨 {w['pop']}%{_umbrella_hint}\n\n"
        f"👗 穿搭建議：{clothes}\n"
        f"💡 {note}"
        f"{_bot_invite_text()}"
    )
    _weather_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_weather_share)

    return [{"type": "flex", "altText": f"{city}天氣 {w['min_t']}–{w['max_t']}°C {w['wx']}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": "#26A69A", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🌤️ {city}今日天氣",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "中央氣象署即時預報＋穿搭建議",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "xs",
                          "contents": body},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "contents": [
                                     {"type": "button", "style": "primary", "color": "#26A69A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message", "label": "重新整理",
                                                 "text": f"{city}天氣"}},
                                     {"type": "button", "style": "primary", "color": "#1A1F3A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message",
                                                 "label": food_label, "text": food_text}},
                                 ]},
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "margin": "xs", "contents": city_row},
                                {"type": "button", "style": "link", "height": "sm",
                                 "action": {"type": "uri",
                                            "label": "📤 傳給家人朋友提醒穿搭",
                                            "uri": _weather_share_url}},
                            ]},
             }}]


def build_weather_region_picker() -> list:
    """天氣 — 選擇地區（第一步）"""
    buttons = [
        {"type": "button", "style": "primary", "color": "#37474F", "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}", "text": f"天氣 地區 {r}"}}
        for r in _AREA_REGIONS.keys()
    ]
    return [{"type": "flex", "altText": "請選擇地區查天氣",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": "🌤️ 天氣＋穿搭建議",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "選擇地區，馬上告訴你今天穿什麼",
                                 "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_weather_city_picker(region: str = "") -> list:
    """天氣 — 選擇城市（第二步）"""
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    rows = []
    for i in range(0, len(areas), 3):
        chunk = areas[i:i+3]
        cells = [
            {"type": "box", "layout": "vertical", "flex": 1,
             "backgroundColor": "#EEF2F7", "cornerRadius": "10px",
             "paddingAll": "md",
             "action": {"type": "message", "label": c, "text": f"{c}天氣"},
             "contents": [
                 {"type": "text", "text": c, "align": "center",
                  "size": "md", "color": "#1A2D50", "weight": "bold"}
             ]}
            for c in chunk
        ]
        rows.append({"type": "box", "layout": "horizontal",
                     "spacing": "sm", "contents": cells})
    rows.append({"type": "button", "style": "link", "height": "sm",
                 "action": {"type": "message", "label": "← 重選地區", "text": "天氣"}})
    return [{"type": "flex", "altText": f"{region}天氣 — 選城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": f"🌤️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": rows},
             }}]


# ─── 早安摘要 ────────────────────────────────────────

_MORNING_ACTIONS = [
    "🍳 早餐加一顆蛋或豆漿，撐到中午不暴食",
    "💧 今天目標喝水 2000cc 以上",
    "🏃 每工作 50 分鐘起來動一動脖子肩膀",
    "😴 睡前 30 分鐘放下手機，入睡品質提升",
    "🥗 用餐先吃蔬菜，血糖穩定不容易餓",
    "🌞 早上曬 15 分鐘太陽，補維生素 D",
    "🧘 壓力大時做深呼吸：吸 4 秒、憋 7 秒、呼 8 秒",
    "💪 起床先做 2 分鐘伸展，趕走僵硬感",
    "🚶 午餐後走 10 分鐘，血糖控制好 30%",
    "🧠 早上第一小時不看社群，心情會更好",
    "🥜 今天吃一把堅果（約 10 顆），護心又護腦",
    "🚪 早上開窗 10 分鐘，換新鮮空氣",
    "🍵 手搖飲選無糖或少糖，一週省 2000 卡",
    "👁️ 螢幕 20 分鐘就看遠處 20 秒，眼睛謝謝你",
    "🧴 出門記得擦防曬，預防比修復更有效",
    "🍊 吃一顆橘子或奇異果，補充維生素 C",
    "🎵 通勤聽音樂或 podcast，比滑手機減壓",
    "🔋 安排 10 分鐘真正休息，離開螢幕放空",
    "🛏️ 今天固定時間起床，調好生理時鐘",
    "🥤 起床第一件事喝杯溫水，啟動腸胃",
    "📵 吃飯時把手機翻面，專心享受食物",
    "🧊 下午嘴饞選水果代替零食，更健康",
    "🌿 找一個綠色植物看 30 秒，舒緩眼睛疲勞",
    "🎯 今天設一個小目標，完成後獎勵自己",
]


def _get_morning_actions() -> list:
    """根據今天日期選 4 條行動建議（每天不同）"""
    import datetime as _dt
    doy = _dt.date.today().timetuple().tm_yday
    n = len(_MORNING_ACTIONS)
    indices = [(doy * 4 + i) % n for i in range(4)]
    # 避免重複
    seen, result = set(), []
    for idx in indices:
        while idx in seen:
            idx = (idx + 1) % n
        seen.add(idx)
        result.append(_MORNING_ACTIONS[idx])
    return result


# ── 今日小驚喜：週期性優惠 ──
# 格式：(icon, title, body)
# 每個星期幾可放多條，當天隨機選一條
_WEEKLY_DEALS = {
    0: [  # 星期一
        ("☕", "星巴克好友分享日", "指定飲品第二杯半價，揪同事一起喝！"),
        ("🍔", "麥當勞振奮星期一", "大麥克套餐限時優惠，開啟新的一週"),
        ("🛒", "全聯週一生鮮日", "指定蔬果肉品有折扣，下班順路買"),
        ("🧋", "50 嵐週一飲品日", "大杯飲料優惠，Monday Blue 靠它救"),
        ("📺", "Netflix 新片週一上架", "週一通常有新劇、新片上架，追劇開始"),
    ],
    1: [  # 星期二
        ("🧋", "CoCo 週二飲品日", "指定飲品第二杯優惠，下午茶時間到！"),
        ("🍕", "必勝客週二大披薩日", "大披薩外帶特價，晚餐不用煩惱"),
        ("📦", "momo 週二品牌日", "逛逛有沒有需要的東西在特價"),
        ("🍩", "Krispy Kreme 買一送一", "不定期週二推買一送一，粉絲專頁注意"),
        ("🎵", "Spotify 新歌週二更新", "每週新發歌單上架，找首新歌通勤聽"),
    ],
    2: [  # 星期三
        ("🍦", "全家霜淇淋日", "霜淇淋第二件半價，下午來一支消暑"),
        ("☕", "路易莎週三咖啡日", "拿鐵系列有優惠，提神好時機"),
        ("🎬", "威秀影城半價日", "部分場次電影半價，下班看場電影"),
        ("🍣", "壽司郎週三活動日", "不定期推 10 元壽司，社群瘋傳"),
        ("🛒", "Costco 週三特價輪播", "會員 APP 看本週特價，該補貨就衝"),
    ],
    3: [  # 星期四
        ("🍗", "肯德基瘋狂星期四", "V 我 50！指定套餐超值優惠"),
        ("☕", "星巴克數位體驗日", "APP 會員獨享優惠，打開看看有什麼"),
        ("🛍️", "蝦皮週四免運", "滿額免運門檻降低，該補貨的趁今天"),
        ("🍦", "迷客夏週四買一送一", "不定期週四活動，粉專公告"),
        ("🎮", "PS Store 週四更新", "新遊戲特賣、每週精選打折"),
    ],
    4: [  # 星期五
        ("🍺", "TGIF！週五小確幸", "辛苦一週了，下班買杯飲料犒賞自己"),
        ("🎉", "Uber Eats 週五優惠", "外送滿額折扣，在家舒服吃晚餐"),
        ("🎮", "Steam 週末特賣", "看看有沒有想玩的遊戲在打折"),
        ("🍕", "Domino's 週五 Happy Hour", "披薩買大送小，週五聚餐首選"),
        ("📽️", "Apple TV+ 週五新劇", "每週五新劇集更新，訂閱族別錯過"),
    ],
    5: [  # 星期六
        ("🌿", "假日農夫市集", "各地有農夫市集，新鮮蔬果等你逛"),
        ("☕", "cama café 假日優惠", "假日外帶咖啡有折扣，出門帶一杯"),
        ("🎪", "週末市集情報", "搜尋你附近的週末市集，吃喝逛一波"),
        ("🎨", "誠品假日藝文活動", "書店常有作家簽書、小型展覽"),
        ("🏞️", "國家公園免費週六", "部分園區週六免門票，帶家人走走"),
    ],
    6: [  # 星期日
        ("🍳", "週日早午餐提案", "找家好吃的早午餐店，慢慢享受假日"),
        ("📚", "誠品週日閱讀", "逛逛書店，也許會遇到一本好書"),
        ("🛒", "家樂福週日生鮮特價", "一週食材採購日，趁特價補齊"),
        ("🧺", "IKEA 週日家庭日", "一家大小逛逛，順便吃肉丸午餐"),
        ("🎬", "HBO GO 週日新片", "週日晚間新上架電影，佛系追劇"),
    ],
}

# 特殊日期優惠（月/日 → deals）
_SPECIAL_DEALS = {
    (1, 1):   ("🎊", "新年快樂", "各大通路新年特賣中，逛逛有沒有好康！"),
    (1, 20):  ("🏮", "春節採買潮", "年貨大街、Costco、家樂福年貨特賣全面開跑"),
    (2, 14):  ("💝", "情人節快樂", "各大餐廳、甜點店推出情人節限定，約個人吃飯吧"),
    (3, 8):   ("👩", "婦女節快樂", "不少品牌有女性專屬優惠，犒賞自己"),
    (3, 14):  ("🍫", "白色情人節", "回禮日！甜點烘焙材料特價中"),
    (3, 15):  ("🛋️", "IKEA 會員週", "會員獨享價、熱銷商品特價，逛街順便吃肉丸"),
    (4, 1):   ("😜", "愚人節", "小心被整！不過各品牌常推愚人節限定商品"),
    (4, 4):   ("🧒", "兒童節", "遊樂園、親子餐廳有兒童節優惠"),
    (4, 22):  ("🌍", "世界地球日", "不少品牌推環保主題優惠，自備杯折價再多"),
    (5, 1):   ("💪", "勞動節快樂", "辛苦了！不少店家勞動節有特別優惠"),
    (5, 12):  ("💐", "母親節檔期", "百貨母親節檔期、餐廳套餐預訂高峰"),
    (6, 18):  ("🛒", "618 年中慶", "momo、蝦皮、PChome 年中大促銷，趁機撿便宜"),
    (7, 1):   ("🏖️", "暑假開始", "旅遊平台暑期早鳥優惠最後機會"),
    (8, 8):   ("👨", "父親節", "餐廳套餐、3C 禮盒、威士忌買氣旺"),
    (9, 1):   ("🎓", "開學季", "文具、3C 開學優惠中，學生族群看過來"),
    (9, 15):  ("🥮", "中秋烤肉潮", "金蘭醬油、Costco 烤肉組、月餅禮盒開搶"),
    (10, 10): ("🇹🇼", "國慶日快樂", "百貨週年慶陸續開跑，準備搶好康"),
    (10, 25): ("🛍️", "MUJI 週年慶", "無印良品全面 5~9 折，床包寢具最熱賣"),
    (10, 31): ("🎃", "萬聖節", "超商、餐廳萬聖節限定商品登場"),
    (11, 1):  ("🛍️", "雙11預熱", "各大電商雙11活動開始暖身，先加購物車"),
    (11, 11): ("🛍️", "雙11來了！", "蝦皮/momo/PChome 年度最大折扣日，衝！"),
    (11, 28): ("🖤", "黑色星期五", "Costco 黑五特賣、Apple 官網優惠、國際品牌大降價"),
    (12, 12): ("🛒", "雙12最後一波", "年末最後一波電商大促，錯過等明年"),
    (12, 24): ("🎄", "聖誕快樂", "聖誕大餐/交換禮物/市集，享受節日氣氛"),
    (12, 25): ("🎅", "Merry Christmas", "各大百貨聖誕特賣，甜點店限定款別錯過"),
    (12, 31): ("🎆", "跨年夜", "跨年活動、演唱會、煙火資訊，準備迎接新年！"),
}


def _load_surprise_cache() -> dict:
    """載入爬蟲驚喜快取（surprise_cache.json）"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "surprise_cache.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_SURPRISE_CACHE = _load_surprise_cache()

# 保底驚喜池（只在以上都沒資料時用）
_SURPRISES_FALLBACK = [
    ("🎯", "今日挑戰", "中午不滑手機，專心吃飯 15 分鐘，你做得到！"),
    ("📸", "拍照挑戰", "拍一張今天讓你覺得美的東西，記錄小確幸"),
    ("🎲", "午餐冒險", "今天午餐試一家沒吃過的店，也許會有驚喜"),
    ("🎧", "聽首新歌", "打開 Spotify 或 KKBOX 推薦，讓今天有新 BGM"),
    ("✍️", "三件好事", "睡前寫下今天 3 件值得感謝的事，幸福感 UP"),
    ("🍰", "犒賞自己", "完成今天的事之後，買個小甜點獎勵自己"),
]


def _get_morning_surprise(city: str, wx_result: dict) -> tuple:
    """回傳 (icon, title, body)。特殊日期最優先，其餘每天輪播不同類型"""
    import datetime as _dt
    today = _dt.date.today()
    doy = today.timetuple().tm_yday
    weekday = today.weekday()  # 0=Monday

    # ── 特殊日期（節日/電商大促）永遠最優先 ──
    special = _SPECIAL_DEALS.get((today.month, today.day))
    if special:
        return special

    # ── 收集所有可用的驚喜來源 ──
    candidates = []  # (type_name, surprise_tuple)

    # 週期性優惠
    weekly = _WEEKLY_DEALS.get(weekday, [])
    if weekly:
        pick = weekly[doy % len(weekly)]
        candidates.append(("deal", pick))

    # 爬蟲：新歌
    songs = _SURPRISE_CACHE.get("songs", []) if _SURPRISE_CACHE else []
    if songs:
        song = songs[doy % len(songs)]
        candidates.append(("song", ("🎵", "今日推薦新歌",
            f"《{song.get('name','')}》— {song.get('artist','')}")))

    # 爬蟲：PTT 優惠
    deals = _SURPRISE_CACHE.get("deals", []) if _SURPRISE_CACHE else []
    if deals:
        deal = deals[doy % len(deals)]
        candidates.append(("ptt", ("🔥", "今日網友好康",
            deal.get("title", ""))))

    # Accupass 當地活動
    if _ACCUPASS_CACHE:
        city_data = _ACCUPASS_CACHE.get(city, {})
        city_events = []
        for cat, events in city_data.items():
            if isinstance(events, list):
                city_events.extend(events)
        if city_events:
            ev = city_events[doy % len(city_events)]
            candidates.append(("event", ("🎉", f"{city}近期活動",
                f"{ev.get('name', '精彩活動')}，有空去看看～")))

    # ── 用 day_of_year 輪播不同類型 ──
    if candidates:
        pick = candidates[doy % len(candidates)]
        return pick[1]

    # ── 保底 ──
    return _SURPRISES_FALLBACK[doy % len(_SURPRISES_FALLBACK)]


def _fetch_quick_oil() -> dict:
    """輕量抓中油本週 92/95/98 油價"""
    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://www.cpc.com.tw/GetOilPriceJson.aspx?type=TodayOilPriceString",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4, context=_ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
        return {
            "92": data.get("sPrice1", "?"),
            "95": data.get("sPrice2", "?"),
            "98": data.get("sPrice3", "?"),
        }
    except Exception:
        return {}


def _fetch_quick_rates() -> dict:
    """只抓 USD / JPY 即期賣出匯率（台灣銀行 CSV）"""
    import csv as _csv
    try:
        req = urllib.request.Request(
            "https://rate.bot.com.tw/xrt/flcsv/0/day",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read().decode("utf-8-sig")
        result = {}
        for row in _csv.reader(raw.strip().split("\n")):
            if len(row) < 14 or row[0] == "幣別":
                continue
            code = row[0].strip()
            if code not in ("USD", "JPY"):
                continue
            try:
                result[code] = {
                    "spot_buy":  float(row[3])  if row[3].strip()  else 0,
                    "spot_sell": float(row[13]) if row[13].strip() else 0,
                }
            except (ValueError, IndexError):
                pass
        return result
    except Exception as e:
        print(f"[quick_rates] {e}")
        return {}


def _get_user_city(user_id: str) -> str:
    """從 Redis 取得用戶上次使用的城市"""
    if not user_id:
        return ""
    cached = _redis_get(f"user_city:{user_id}")
    if cached and isinstance(cached, str):
        return cached
    return ""


def _set_user_city(user_id: str, city: str):
    """將用戶城市偏好存入 Redis（90 天）"""
    if user_id and city:
        _redis_set(f"user_city:{user_id}", city, ttl=86400 * 90)


def _build_morning_city_picker() -> list:
    """第一次說早安時，讓用戶選城市"""
    # 常用 6 大城市快速選擇 + 更多選項
    quick_cities = ["台北", "新北", "桃園", "台中", "台南", "高雄"]
    buttons = [
        {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
         "action": {"type": "message", "label": c, "text": f"早安 {c}"}}
        for c in quick_cities
    ]
    # 其他城市用兩排小按鈕
    other_cities = [c for c in _ALL_CITIES if c not in quick_cities]
    other_rows = []
    for i in range(0, len(other_cities), 4):
        chunk = other_cities[i:i+4]
        other_rows.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": c, "text": f"早安 {c}"}}
                for c in chunk
            ] + [{"type": "filler"}] * (4 - len(chunk))
        })
    return [{
        "type": "flex",
        "altText": "早安！請選擇你的所在城市",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "☀️ 早安！", "color": "#FFFFFF",
                     "size": "xl", "weight": "bold"},
                    {"type": "text", "text": "選擇你的城市，之後每天自動顯示當地資訊",
                     "color": "#8892B0", "size": "xs", "wrap": True, "margin": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "14px",
                "contents": [
                    {"type": "button", "style": "primary", "height": "sm",
                     "color": "#2E7D32",
                     "action": {"type": "uri", "label": "📍 自動定位（出差/旅遊適用）",
                                "uri": "https://liff.line.me/2009774625-KwBrQAbV?action=morning"}},
                    {"type": "separator", "margin": "sm"},
                    {"type": "text", "text": "🏙️ 或手動選擇城市", "size": "sm",
                     "weight": "bold", "color": "#37474F", "margin": "sm"},
                    *buttons,
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "📍 其他縣市", "size": "xs",
                     "color": "#90A4AE", "margin": "md"},
                    *other_rows,
                ]
            }
        }
    }]


def build_morning_summary(text: str, user_id: str = "") -> list:
    """早安摘要：天氣 + 匯率 + 每日健康 tip"""
    import threading as _thr
    import datetime as _dt

    # 城市偵測：文字指定 > Redis 記憶 > 問用戶
    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        city = city_m.group(1)
        _set_user_city(user_id, city)
    else:
        saved = _get_user_city(user_id)
        if saved:
            city = saved
        else:
            return _build_morning_city_picker()

    # 並行抓：天氣 + 匯率 + 油價（加速早安反應時間）
    wx_result = {}
    rates = {}
    oil = {}
    def _wx():
        nonlocal wx_result
        wx_result = _fetch_cwa_weather(city)
    def _rt():
        nonlocal rates
        rates = _fetch_quick_rates()
    def _oil():
        nonlocal oil
        oil = _fetch_quick_oil()
    _t1 = _thr.Thread(target=_wx); _t2 = _thr.Thread(target=_rt); _t3 = _thr.Thread(target=_oil)
    _t1.start(); _t2.start(); _t3.start()
    _t1.join(timeout=6); _t2.join(timeout=5); _t3.join(timeout=5)

    # 今日小驚喜
    surprise_icon, surprise_title, surprise_body = _get_morning_surprise(city, wx_result)

    _WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
    today = _dt.date.today()
    today_str = f"{today.month}月{today.day}日（星期{_WEEKDAYS[today.weekday()]}）"

    # ── 天氣 + 穿搭 ──
    if wx_result.get("ok"):
        wx = wx_result
        wx_icon = _wx_icon(wx["wx"])
        pop = wx["pop"]
        diff = wx["max_t"] - wx["min_t"]
        # 天氣描述
        wx_main = f"{wx_icon} {wx['wx']}　{wx['min_t']}–{wx['max_t']}°C"
        # 溫差/降雨提示
        if pop >= 70:
            wx_hint = "☂️ 降雨機率高，記得帶傘！"
        elif pop >= 40:
            wx_hint = "🌂 可能有雨，建議帶傘備用"
        elif diff >= 10:
            wx_hint = "早晚溫差大，注意保暖"
        elif wx["max_t"] >= 32:
            wx_hint = "中午很熱，注意防曬補水"
        else:
            wx_hint = "氣溫舒適，適合外出走走"
        # 穿搭行動建議
        outfit, _, umbrella = _outfit_advice(wx["max_t"], wx["min_t"], pop)
        action_parts = [outfit]
        if pop >= 40:
            action_parts.append("帶傘")
        if wx["max_t"] >= 28:
            action_parts.append("防曬必備")
        wx_action = f"👔 行動建議：{'＋'.join(action_parts)}"
    else:
        wx_main = "☁️ 天氣資料暫時無法取得"
        wx_hint = f"可以說「{city}天氣」查詳細"
        wx_action = "👔 建議穿著舒適出門"

    # ── 今日實用資訊：匯率 + 油價（附便宜/貴提示）──
    info_items = []
    usd = rates.get("USD", {}) if rates else {}
    jpy = rates.get("JPY", {}) if rates else {}

    # 匯率判讀（近 3 年區間參考）
    def _usd_tip(rate):
        if rate <= 29.5: return ("🎉", "偏便宜！適合換美金/去美國", "#2E7D32")
        if rate <= 31.0: return ("⚖️", "價位普通", "#555555")
        if rate <= 32.0: return ("⚠️", "略偏高，再等等", "#E65100")
        return ("💸", "近期高點，換匯不划算", "#C62828")

    def _jpy_tip(rate):
        if rate <= 0.215: return ("🎉", "日幣超便宜！衝日本", "#2E7D32")
        if rate <= 0.225: return ("😊", "不錯的換匯點", "#2E7D32")
        if rate <= 0.240: return ("⚖️", "價位普通", "#555555")
        return ("💸", "日幣偏貴，再觀望", "#C62828")

    def _oil_tip(p92):
        try:
            p = float(p92)
        except (ValueError, TypeError):
            return None
        if p <= 28.5: return ("🎉", "油價便宜，該加滿了！", "#2E7D32")
        if p <= 30.5: return ("⚖️", "價位普通", "#555555")
        if p <= 32.0: return ("⚠️", "略偏高，非必要緩一緩", "#E65100")
        return ("💸", "油價高點，省油駕駛", "#C62828")

    # USD 匯率
    if usd.get("spot_sell"):
        icon, tip, color = _usd_tip(usd["spot_sell"])
        info_items.append({"type": "text",
            "text": f"💵 美金 {usd['spot_sell']:.2f}　{icon} {tip}",
            "size": "xs", "color": color, "wrap": True})
    # JPY 匯率
    if jpy.get("spot_sell"):
        icon, tip, color = _jpy_tip(jpy["spot_sell"])
        info_items.append({"type": "text",
            "text": f"💴 日幣 {jpy['spot_sell']:.4f}　{icon} {tip}",
            "size": "xs", "color": color, "wrap": True})
    # 油價
    if oil.get("92") and oil.get("92") != "?":
        oil_tip_result = _oil_tip(oil["92"])
        oil_suffix = ""
        oil_color = "#37474F"
        if oil_tip_result:
            icon, tip, oil_color = oil_tip_result
            oil_suffix = f"　{icon} {tip}"
        info_items.append({"type": "text",
            "text": f"⛽ 92/{oil['92']}　95/{oil['95']}　98/{oil['98']}{oil_suffix}",
            "size": "xs", "color": oil_color, "wrap": True})

    if not info_items:
        info_items = [{"type": "text",
            "text": "即時資訊暫時抓不到，請稍後再試 🙏",
            "size": "xs", "color": "#888888"}]

    # ── 分享文字（傳給朋友/另一半/同事）──
    _bot_invite = f"https://line.me/R/ti/p/{LINE_BOT_ID}" if LINE_BOT_ID else "https://line.me/R/"
    _share_text = (
        f"☀️ 早安！{city} {today_str}\n\n"
        f"🌤 {wx_main}\n{wx_hint}\n\n"
        f"{surprise_icon} 今日小驚喜：{surprise_title}\n{surprise_body}\n\n"
        f"👉 加「生活優轉」每天收到今日小驚喜：\n{_bot_invite}"
    )
    _share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)

    return [{
        "type": "flex",
        "altText": f"☀️ 早安！{city} {today_str}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": f"☀️ 早安！{city}",
                     "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                    {"type": "text", "text": today_str,
                     "color": "#8892B0", "size": "sm", "margin": "xs"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "md", "paddingAll": "14px",
                "contents": [
                    # ── 天氣穿搭區塊 ──
                    {
                        "type": "box", "layout": "vertical",
                        "backgroundColor": "#EBF5FB",
                        "cornerRadius": "10px", "paddingAll": "12px", "spacing": "sm",
                        "contents": [
                            {"type": "text", "text": "🌤 今日天氣與穿搭",
                             "size": "xs", "color": "#1565C0", "weight": "bold"},
                            {"type": "text", "text": wx_main,
                             "size": "md", "color": "#1A1F3A", "weight": "bold"},
                            {"type": "text", "text": wx_hint,
                             "size": "xs", "color": "#546E7A", "wrap": True},
                            {"type": "text", "text": wx_action,
                             "size": "xs", "color": "#37474F", "wrap": True},
                        ]
                    },
                    # ── 今日實用資訊（匯率＋油價）──
                    {
                        "type": "box", "layout": "vertical",
                        "backgroundColor": "#E8F5E9",
                        "cornerRadius": "10px", "paddingAll": "12px", "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": "💡 今日實用資訊",
                             "size": "xs", "color": "#2E7D32", "weight": "bold"},
                            *info_items,
                        ]
                    },
                    # ── 今日小驚喜 ──
                    {
                        "type": "box", "layout": "vertical",
                        "backgroundColor": "#FFF8E1",
                        "cornerRadius": "10px", "paddingAll": "12px", "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": f"{surprise_icon} 今日小驚喜",
                             "size": "xs", "color": "#E65100", "weight": "bold"},
                            {"type": "text", "text": surprise_title,
                             "size": "sm", "color": "#BF360C", "weight": "bold"},
                            {"type": "text", "text": surprise_body,
                             "size": "xs", "color": "#37474F", "wrap": True},
                            {"type": "separator", "margin": "sm", "color": "#FFCC80"},
                            {"type": "text", "text": "📱 更多即時好康",
                             "size": "xxs", "color": "#E65100", "weight": "bold",
                             "margin": "sm"},
                            {"type": "box", "layout": "vertical", "spacing": "xs",
                             "contents": [
                                 {"type": "text",
                                  "text": "• 好康情報誌（Threads）→ 限時餐飲優惠",
                                  "size": "xxs", "color": "#1976D2", "wrap": True,
                                  "action": {"type": "uri", "label": "好康情報誌",
                                             "uri": "https://www.threads.com/@info.talk_tw"}},
                                 {"type": "text",
                                  "text": "• V 妞的旅行 → KKday 折扣碼＋信用卡",
                                  "size": "xxs", "color": "#1976D2", "wrap": True,
                                  "action": {"type": "uri", "label": "V妞的旅行",
                                             "uri": "https://vniki.com/"}},
                                 {"type": "text",
                                  "text": "• 莉芙小姐愛旅遊 → Klook 折扣碼",
                                  "size": "xxs", "color": "#1976D2", "wrap": True,
                                  "action": {"type": "uri", "label": "莉芙小姐",
                                             "uri": "https://nicklee.tw/"}},
                             ]},
                        ]
                    },
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "spacing": "xs", "paddingAll": "10px",
                "contents": [
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [
                         {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                          "action": {"type": "message", "label": "吃什麼",
                                     "text": "今天吃什麼"}},
                         {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                          "action": {"type": "message", "label": "查活動",
                                     "text": "近期活動"}},
                         {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                          "action": {"type": "message", "label": "健康",
                                     "text": "健康小幫手"}},
                     ]},
                    {"type": "button", "style": "primary", "color": "#E65100",
                     "height": "sm",
                     "action": {"type": "uri", "label": "📤 分享給朋友/另一半/同事",
                                "uri": _share_url}},
                    {"type": "button", "style": "secondary", "height": "sm",
                     "color": "#ECEFF1",
                     "action": {"type": "uri", "label": f"📍 換城市（現在：{city}）",
                                "uri": "https://liff.line.me/2009774625-KwBrQAbV?action=morning"}},
                ]
            }
        }
    }]


def build_weather_message(text: str, user_id: str = "") -> list:
    """天氣模組主路由"""
    # 解析城市（全台 22 縣市）
    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        _set_user_city(user_id, city_m.group(1))
        return build_weather_flex(city_m.group(1))

    # 解析地區
    for r in _AREA_REGIONS:
        if r in text:
            return build_weather_city_picker(r)

    return build_weather_region_picker()


# ─── 對話路由 ─────────────────────────────────────

def build_welcome_message() -> list:
    """歡迎訊息 + 快速選單（精美磚塊版）"""

    def _tile(icon, name, line1, line2, color, light_bg, action_text):
        """功能磚塊 helper — 可點擊的彩色卡片"""
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": light_bg,
            "cornerRadius": "12px",
            "paddingAll": "8px",
            "spacing": "xs",
            "action": {"type": "message", "label": name, "text": action_text},
            "contents": [
                {"type": "text", "text": icon, "size": "xxl", "align": "center"},
                {"type": "text", "text": name, "size": "xs", "weight": "bold",
                 "color": color, "align": "center", "margin": "xs"},
                {"type": "text", "text": line1, "size": "xxs",
                 "color": "#888888", "align": "center"},
                {"type": "text", "text": line2, "size": "xxs",
                 "color": "#888888", "align": "center"},
            ]
        }

    return [{
        "type": "flex",
        "altText": "✨ 嗨！我是你的生活優轉",
        "contents": {
            "type": "bubble",
            "size": "mega",
            # ── Header：品牌深色漸層風 ──────────────────────────
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A",
                "paddingTop": "20px", "paddingBottom": "14px",
                "paddingStart": "16px", "paddingEnd": "16px",
                "contents": [
                    # 品牌名稱列
                    {
                        "type": "box", "layout": "horizontal", "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "✨", "size": "xxl",
                             "flex": 0, "gravity": "center"},
                            {
                                "type": "box", "layout": "vertical", "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "生活優轉",
                                     "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                    {"type": "text", "text": "讓每天的選擇更簡單 🎯",
                                     "color": "#8892B0", "size": "xs", "margin": "xs"},
                                ]
                            }
                        ]
                    },
                    # 功能快標籤
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "md",
                        "contents": [
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#FF6B3530", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "🍽️ 吃什麼",
                                           "size": "xxs", "color": "#FF9A7A",
                                           "align": "center"}]},
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#5C6BC030", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "🗓️ 週末活動",
                                           "size": "xxs", "color": "#9FA8DA",
                                           "align": "center"}]},
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#43A04730", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "💪 健康管理",
                                           "size": "xxs", "color": "#A5D6A7",
                                           "align": "center"}]},
                        ]
                    }
                ]
            },
            # ── Body：2×3 功能磚塊 ──────────────────────────────
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": "👇 點選功能，馬上開始",
                     "size": "xs", "color": "#777777", "margin": "xs"},
                    # Row 1
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "sm",
                        "contents": [
                            _tile("📱", "3C推薦",  "手機/筆電", "選購建議",
                                  "#E64A00", "#FFF3EE", "推薦手機"),
                            _tile("🍽️", "吃什麼",  "3秒決定", "今天吃啥",
                                  "#BF360C", "#FFF0E6", "今天吃什麼"),
                            _tile("🗓️", "近期活動", "周末",   "去哪玩",
                                  "#3949AB", "#ECEDFF", "近期活動"),
                        ]
                    },
                    # Row 2
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "sm",
                        "contents": [
                            _tile("💪", "健康",    "BMI/睡眠", "壓力紓解",
                                  "#2E7D32", "#E8F5E9", "健康小幫手"),
                            _tile("💰", "金錢",    "薪資/信用卡", "保險規劃",
                                  "#00695C", "#E0F2F1", "金錢小幫手"),
                            _tile("🔧", "硬體升級", "RAM/SSD", "效能提升",
                                  "#37474F", "#ECEFF1", "電腦升級"),
                        ]
                    },
                    # 早安 / 今日熱話題提示
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#FFFBEA",
                        "cornerRadius": "8px",
                        "paddingAll": "8px",
                        "margin": "md",
                        "action": {"type": "message", "label": "早安", "text": "早安"},
                        "contents": [
                            {"type": "text", "text": "☀️",
                             "size": "sm", "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 打「早安」→ 天氣＋今日小驚喜，每天一個好梗跟朋友聊",
                             "size": "xxs", "color": "#B45309", "flex": 1,
                             "gravity": "center", "wrap": True},
                        ]
                    },
                    {"type": "separator", "margin": "md"},
                    # 底部小工具列
                    {
                        "type": "box", "layout": "horizontal",
                        "margin": "sm", "paddingTop": "4px",
                        "contents": [
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "早安", "text": "早安"},
                             "contents": [
                                 {"type": "text", "text": "☀️", "align": "center", "size": "md"},
                                 {"type": "text", "text": "早安", "size": "xxs",
                                  "color": "#B45309", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "天氣", "text": "天氣"},
                             "contents": [
                                 {"type": "text", "text": "🌤️", "align": "center", "size": "md"},
                                 {"type": "text", "text": "天氣", "size": "xxs",
                                  "color": "#0288D1", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "防詐", "text": "防詐騙"},
                             "contents": [
                                 {"type": "text", "text": "🔍", "align": "center", "size": "md"},
                                 {"type": "text", "text": "防詐", "size": "xxs",
                                  "color": "#C62828", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "法律", "text": "法律常識"},
                             "contents": [
                                 {"type": "text", "text": "⚖️", "align": "center", "size": "md"},
                                 {"type": "text", "text": "法律", "size": "xxs",
                                  "color": "#4527A0", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "回報", "text": "回報"},
                             "contents": [
                                 {"type": "text", "text": "💡", "align": "center", "size": "md"},
                                 {"type": "text", "text": "回報", "size": "xxs",
                                  "color": "#6C5CE7", "align": "center"},
                             ]},
                        ]
                    }
                ]
            }
        }
    }]


# ─── 導引式問卷（狀態用 | 編碼）────────────────────
# 格式：裝置|使用者|用途|預算
# 例如：手機|長輩|拍照|20000
# 每一步從按鈕中累積，直到 4 個欄位齊全才顯示推薦

DEVICE_USE_OPTIONS = {
    "手機": [
        ("📞 日常用（LINE、拍照、上網）", "日常"),
        ("📷 拍照攝影為主", "拍照"),
        ("🎮 玩手遊", "遊戲"),
        ("🎬 看影片追劇", "追劇"),
    ],
    "筆電": [
        ("📝 上課作業報告", "學習"),
        ("💼 工作文書（Word/Excel）", "工作"),
        ("🎬 影片剪輯設計", "創作"),
        ("🎮 玩遊戲", "遊戲"),
    ],
    "平板": [
        ("🎬 看影片追劇", "追劇"),
        ("📚 閱讀電子書", "閱讀"),
        ("✏️ 手寫筆記", "工作"),
        ("🎮 玩遊戲", "遊戲"),
    ],
    "桌機": [
        ("💼 辦公文書（Word/Excel）", "工作"),
        ("🎮 玩電腦遊戲", "遊戲"),
        ("🎬 影片剪輯/設計", "創作"),
        ("🏠 家用多功能", "日常"),
    ],
}

BUDGET_OPTIONS = {
    "手機": [
        ("💰 1 萬以內", "10000"),
        ("👍 1～2 萬", "20000"),
        ("⭐ 2～4 萬", "40000"),
        ("🏆 不限預算", "999999"),
    ],
    "筆電": [
        ("💰 2 萬以內", "20000"),
        ("👍 2～3 萬", "30000"),
        ("⭐ 3～5 萬", "50000"),
        ("🏆 不限預算", "999999"),
    ],
    "平板": [
        ("💰 1 萬以內", "10000"),
        ("👍 1～2 萬", "20000"),
        ("⭐ 2～3 萬", "30000"),
        ("🏆 不限預算", "999999"),
    ],
    "桌機": [
        ("💰 2 萬以內", "20000"),
        ("👍 2～4 萬", "40000"),
        ("⭐ 4～8 萬", "80000"),
        ("🏆 不限預算", "999999"),
    ],
}

STEP_COLORS = {"手機": "#FF8C42", "筆電": "#5B9BD5", "平板": "#4CAF50", "桌機": "#8D6E63"}


def build_wizard_who(device_name: str) -> list:
    """問卷 Step 1：要給誰用？"""
    color = STEP_COLORS.get(device_name, "#FF8C42")
    who_options = [
        ("👤 我自己", "自己"),
        ("👴 爸媽或長輩", "長輩"),
        ("🎒 學生", "學生"),
        ("👶 給小孩", "小孩"),
    ]
    btns = [
        {"type": "button", "style": "secondary",
         "action": {"type": "message", "label": label,
                    "text": f"{device_name}|{val}"}}
        for label, val in who_options
    ]
    return [{
        "type": "flex", "altText": f"步驟 1／3　誰要用這台{device_name}？",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": color,
                "contents": [
                    {"type": "text", "text": f"📋 {device_name}推薦　步驟 1／3",
                     "color": "#FFFFFF", "size": "sm"},
                    {"type": "text", "text": "誰要用這台？",
                     "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                ]
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": btns},
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{"type": "button", "style": "secondary",
                               "action": {"type": "message", "label": "← 重新開始", "text": "你好"}}]
            }
        }
    }]


def build_wizard_use(device_name: str, who: str) -> list:
    """問卷 Step 2：主要做什麼？"""
    color = STEP_COLORS.get(device_name, "#FF8C42")
    options = DEVICE_USE_OPTIONS.get(device_name, [])
    btns = [
        {"type": "button", "style": "secondary",
         "action": {"type": "message", "label": label,
                    "text": f"{device_name}|{who}|{val}"}}
        for label, val in options
    ]
    who_label = {"自己": "你", "長輩": "長輩", "學生": "學生", "小孩": "小孩"}.get(who, who)
    return [{
        "type": "flex", "altText": f"步驟 2／3　主要做什麼？",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": color,
                "contents": [
                    {"type": "text", "text": f"📋 {device_name}推薦　步驟 2／3",
                     "color": "#FFFFFF", "size": "sm"},
                    {"type": "text", "text": f"{who_label}主要用來做什麼？",
                     "color": "#FFFFFF", "size": "xl", "weight": "bold", "wrap": True},
                ]
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": btns},
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{"type": "button", "style": "secondary",
                               "action": {"type": "message", "label": "← 上一步",
                                          "text": f"推薦{device_name}"}}]
            }
        }
    }]


def build_wizard_budget(device_name: str, who: str, use: str) -> list:
    """問卷 Step 3：預算多少？"""
    color = STEP_COLORS.get(device_name, "#FF8C42")
    options = BUDGET_OPTIONS.get(device_name, BUDGET_OPTIONS["手機"])
    btns = [
        {"type": "button", "style": "secondary",
         "action": {"type": "message", "label": label,
                    "text": f"{device_name}|{who}|{use}|{val}"}}
        for label, val in options
    ]
    use_label = {"日常": "日常使用", "拍照": "拍照攝影", "遊戲": "玩遊戲",
                 "追劇": "追劇看片", "學習": "學習作業", "工作": "工作文書",
                 "創作": "影片剪輯", "閱讀": "閱讀電子書"}.get(use, use)
    return [{
        "type": "flex", "altText": "步驟 3／3　預算大概多少？",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": color,
                "contents": [
                    {"type": "text", "text": f"📋 {device_name}推薦　步驟 3／3",
                     "color": "#FFFFFF", "size": "sm"},
                    {"type": "text", "text": "預算大概多少？",
                     "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                    {"type": "text", "text": f"用途：{use_label}",
                     "color": "#FFFFFFCC", "size": "xs"},
                ]
            },
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": btns},
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{"type": "button", "style": "secondary",
                               "action": {"type": "message", "label": "← 上一步",
                                          "text": f"{device_name}|{who}"}}]
            }
        }
    }]


def parse_wizard_state(text: str) -> dict | None:
    """解析 | 編碼的問卷狀態"""
    if "|" not in text:
        return None
    parts = text.split("|")
    device_map = {"手機": "phone", "筆電": "laptop", "平板": "tablet", "桌機": "desktop"}
    device_key = device_map.get(parts[0])
    if not device_key:
        return None
    state = {"device": device_key, "device_name": parts[0]}
    if len(parts) >= 2:
        state["who"] = parts[1]
    if len(parts) >= 3:
        state["use"] = parts[2]
    if len(parts) >= 4:
        try:
            state["budget"] = int(parts[3])
        except Exception:
            state["budget"] = 0
    return state


def build_scenario_menu() -> list:
    """情境推薦：快速選情境，直接跳到預算步驟"""
    return [{
        "type": "flex", "altText": "情境推薦",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#5B9BD5",
                "contents": [
                    {"type": "text", "text": "🎯 情境推薦", "color": "#FFFFFF",
                     "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "選你的狀況，省略填表步驟", "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "點一個最接近你的狀況：",
                     "size": "sm", "color": "#8D6E63"},
                    {"type": "button", "style": "secondary", "margin": "sm",
                     "action": {"type": "message", "label": "👴 長輩換手機（只用 LINE）",
                                "text": "手機|長輩|日常"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "📸 想買拍照好的手機",
                                "text": "手機|自己|拍照"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🎮 手機打遊戲用",
                                "text": "手機|自己|遊戲"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🎒 學生買筆電",
                                "text": "筆電|學生|學習"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💼 工作文書用筆電",
                                "text": "筆電|自己|工作"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🛋️ 在家追劇用平板",
                                "text": "平板|自己|追劇"}},
                    {"type": "separator", "margin": "md"},
                    {"type": "text",
                     "text": "沒有符合的？直接跟我說：\n「我媽要換手機，只用 LINE 和拍照」",
                     "size": "xs", "color": "#8D6E63", "wrap": True, "margin": "md"},
                ]
            }
        }
    }]


def build_spec_explainer(text: str) -> list:
    """看懂規格：白話解釋常見 3C 規格"""
    # 偵測問的是哪個規格
    text_lower = text.lower()

    explanations = []

    if any(w in text_lower for w in ["cpu", "處理器", "晶片", "i5", "i7", "i9", "m1", "m2", "m3", "m4",
                                      "ryzen", "snapdragon", "天璣", "聯發科"]):
        explanations.append({
            "title": "🧠 處理器（CPU）是什麼？",
            "body": "就像大腦，負責所有運算。\n\n"
                    "📱 手機：\n"
                    "• Snapdragon 8 Elite / 天璣 9400 → 最頂級，玩什麼都順\n"
                    "• Snapdragon 7s / 天璣 8300 → 中階，日常夠用\n\n"
                    "💻 筆電：\n"
                    "• Intel i9 / AMD Ryzen 9 → 頂規，影片剪輯/3D設計用\n"
                    "• Intel i7 / Ryzen 7 → 高效能，玩遊戲/多工沒問題\n"
                    "• Intel i5 / Ryzen 5 → 主流款，上網文書綽綽有餘\n"
                    "• Apple M系列 → 省電又快，MacBook 專屬"
        })

    if any(w in text_lower for w in ["ram", "記憶體", "gb", "運行"]):
        explanations.append({
            "title": "💾 記憶體（RAM）是什麼？",
            "body": "就像桌子的大小，桌子越大，同時可以放越多東西。\n\n"
                    "📱 手機：\n"
                    "• 8GB → 日常夠用，LINE/拍照/追劇沒問題\n"
                    "• 12GB → 玩遊戲不卡頓\n"
                    "• 16GB 以上 → 重度遊戲/多開 App\n\n"
                    "💻 筆電：\n"
                    "• 8GB → 文書上網夠用\n"
                    "• 16GB → 推薦，未來幾年不會卡\n"
                    "• 32GB 以上 → 設計師/工程師需要"
        })

    if any(w in text_lower for w in ["儲存", "硬碟", "ssd", "rom", "256", "512", "1tb"]):
        explanations.append({
            "title": "📦 儲存空間是什麼？",
            "body": "就像衣櫃，放你的照片、App、影片。\n\n"
                    "📱 手機：\n"
                    "• 128GB → 如果有雲端備份，堪用\n"
                    "• 256GB → 推薦，不用一直刪照片\n"
                    "• 512GB 以上 → 愛拍影片或不用雲端的人\n\n"
                    "💻 筆電：\n"
                    "• 512GB SSD → 基本款，一般使用夠用\n"
                    "• 1TB SSD → 有大量檔案或不想外接硬碟"
        })

    if any(w in text_lower for w in ["螢幕", "解析度", "oled", "amoled", "lcd", "hz", "刷新率", "nits"]):
        explanations.append({
            "title": "🖥️ 螢幕規格是什麼？",
            "body": "• OLED / AMOLED → 顏色鮮豔、黑色很純，拍照後看起來漂亮，耗電相對多\n"
                    "• LCD / IPS → 顏色自然，戶外陽光下看得清楚，耗電少\n\n"
                    "• 60Hz → 一般滑動，夠用\n"
                    "• 90Hz / 120Hz → 滑起來更順滑，眼睛比較不累\n\n"
                    "• nits（亮度）→ 越高戶外越看得清楚，500 nits 以上建議"
        })

    if any(w in text_lower for w in ["電池", "mah", "續航", "充電"]):
        explanations.append({
            "title": "🔋 電池容量是什麼？",
            "body": "• mAh 越大 → 一般來說撐越久，但也跟處理器效率有關\n\n"
                    "📱 手機：\n"
                    "• 4000mAh 以下 → 輕薄機種，大概撐一天\n"
                    "• 5000mAh → 主流，大多數人一天半到兩天\n"
                    "• 6000mAh 以上 → 重度使用者，撐兩天以上\n\n"
                    "• 快充 W 數越高 → 充電越快（例如 67W 約 40 分鐘充到 80%）"
        })

    if not explanations:
        # 沒有偵測到特定規格 → 顯示所有可問的規格
        return [{
            "type": "flex",
            "altText": "看懂規格",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#4CAF50",
                    "contents": [
                        {"type": "text", "text": "🔍 看懂規格", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                        {"type": "text", "text": "點一個你想了解的", "color": "#FFFFFFCC", "size": "sm"},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "🧠 處理器（CPU）是什麼？", "text": "處理器是什麼"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "💾 記憶體（RAM）是什麼？", "text": "記憶體是什麼"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "📦 儲存空間怎麼選？", "text": "儲存空間是什麼"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "🖥️ 螢幕規格看哪裡？", "text": "螢幕規格是什麼"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "🔋 電池容量怎麼看？", "text": "電池容量是什麼"}},
                    ]
                }
            }
        }]

    # 有偵測到規格 → 回傳白話說明
    messages = []
    for exp in explanations:
        messages.append({
            "type": "flex",
            "altText": exp["title"],
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#4CAF50",
                    "contents": [
                        {"type": "text", "text": exp["title"], "color": "#FFFFFF", "size": "md",
                         "weight": "bold", "wrap": True},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": exp["body"], "size": "sm", "color": "#3E2723",
                         "wrap": True},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "🔍 看其他規格說明", "text": "看懂規格"}},
                        {"type": "button", "style": "primary", "color": "#FF8C42", "margin": "sm",
                         "action": {"type": "message", "label": "📱 幫我推薦手機", "text": "推薦手機"}},
                    ]
                }
            }
        })
    return messages


# ════════════════════════════════════════════════
# 防詐辨識模組
# ════════════════════════════════════════════════

FRAUD_PATTERNS = [
    # ── 金錢操作 ──────────────────────────────────────────
    (["轉帳", "匯款", "解除分期", "ATM", "存款", "帳戶異常", "保證金", "手續費",
      "儲值", "點數卡", "禮物卡", "代墊", "墊付", "先付", "退款操作"], 2, "要求金錢操作"),

    # ── 投資詐騙 ──────────────────────────────────────────
    (["穩賺", "高報酬", "翻倍", "保本", "穩定獲利", "零風險", "日賺", "月入",
      "獲利截圖", "跟我操作", "內部消息", "飆股", "私募", "下單就賺"], 2, "高獲利誘惑"),

    # ── 中獎話術 ──────────────────────────────────────────
    (["你中獎", "恭喜獲得", "抽中", "得獎", "領獎", "幸運獲選",
      "恭喜您", "您已入選", "免費獲得", "獨家贈品"], 2, "中獎話術"),

    # ── 索取個資 ──────────────────────────────────────────
    (["身分證", "帳號密碼", "驗證碼", "個人資料", "銀行卡",
      "健保卡", "護照號碼", "戶籍謄本", "存摺封面", "網路銀行密碼"], 2, "索取個資"),

    # ── 假冒政府機關 ──────────────────────────────────────
    (["警察", "檢察官", "法院", "調查局", "金管會", "健保署", "國稅局", "刑事局",
      "內政部", "移民署", "海關", "地檢署", "廉政署", "洗錢防制"], 2, "假冒政府機關"),

    # ── 假冒身份 ──────────────────────────────────────────
    (["假冒", "冒充", "台灣電力", "台灣大哥大客服", "銀行客服",
      "LINE客服", "Meta客服", "蝦皮客服", "momo客服", "官方帳號",
      "平台客服", "賣家客服", "假帳號"], 2, "假冒身份"),

    # ── 製造緊迫感 ────────────────────────────────────────
    (["今天截止", "立即處理", "馬上", "限時", "24小時", "緊急通知",
      "帳號將被停用", "今日最後", "逾期將", "即將凍結", "請立即"], 1, "製造緊迫感"),

    # ── 引導點擊加群 ──────────────────────────────────────
    (["點擊連結", "掃描QR", "下載APP", "點此", "加好友", "加入群組",
      "加LINE", "加我好友", "私訊我", "加入頻道", "進群"], 1, "引導點擊或加群"),

    # ── 工作詐騙 ──────────────────────────────────────────
    (["在家工作", "輕鬆賺", "高薪兼職", "每天賺", "不用出門", "代購",
      "刷單", "養號", "按讚賺錢", "任務賺錢", "接單賺錢", "兼差"], 1, "工作詐騙誘餌"),

    # ── 投資話術 ──────────────────────────────────────────
    (["老師帶你", "跟著操作", "跟單", "投資群組", "帶單",
      "名師推薦", "大師預測", "AI選股", "量化交易", "跟單平台"], 1, "投資詐騙話術"),

    # ── 要求保密 ──────────────────────────────────────────
    (["不要告訴", "保密", "別讓家人知道", "私下處理", "不要聲張",
      "不要跟別人說", "這是秘密", "只有你知道"], 2, "要求保密"),

    # ── 境外金融 ──────────────────────────────────────────
    (["海外", "境外", "虛擬貨幣", "加密貨幣", "USDT", "比特幣",
      "以太幣", "幣安", "交易所", "冷錢包", "NFT投資"], 1, "境外金融操作"),

    # ── 情感詐騙（新增）──────────────────────────────────
    (["認識一下", "交個朋友", "緣分", "我很孤單", "異國戀",
      "外國人", "在台灣工作", "軍人", "工程師在海外", "我喜歡你"], 1, "情感詐騙話術"),

    # ── 假網拍詐騙（新增）────────────────────────────────
    (["私下交易", "面交", "不走平台", "直接匯款給我", "帳號被停權",
      "系統問題", "請直接轉帳", "跳過平台"], 2, "假網拍私下交易"),

    # ── AI換臉／深偽（新增）──────────────────────────────
    (["視訊驗證", "開鏡頭", "裸照", "私密影片", "截圖勒索",
      "散布影片", "付錢才不發出去"], 3, "勒索詐騙"),
]

def analyze_fraud(text: str) -> dict:
    """分析文字詐騙風險"""
    score = 0
    patterns_found = []
    for keywords, pts, label in FRAUD_PATTERNS:
        if any(kw in text for kw in keywords):
            score += pts
            patterns_found.append(label)
    if score >= 4:
        risk = "high"
    elif score >= 2:
        risk = "medium"
    else:
        risk = "low"
    return {"score": score, "risk": risk, "patterns": patterns_found}


def build_fraud_intro() -> list:
    """防詐辨識：引導用戶貼上可疑內容"""
    return [{
        "type": "flex", "altText": "防詐辨識",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#C0392B",
                "contents": [
                    {"type": "text", "text": "🔍 防詐辨識", "color": "#FFFFFF",
                     "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "幫你分析可疑訊息是否為詐騙",
                     "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text",
                     "text": "📋 使用方式",
                     "size": "sm", "weight": "bold", "color": "#3E2723"},
                    {"type": "text",
                     "text": "把可疑的訊息、LINE 對話、簡訊內容\n複製後直接貼給我，我來幫你分析！",
                     "size": "sm", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "⚡ 常見詐騙類型", "size": "sm",
                     "weight": "bold", "color": "#3E2723", "margin": "md"},
                    {"type": "text",
                     "text": "• 假冒政府/銀行/電信客服\n• 投資高報酬誘惑\n• 假交友引導投資\n• 中獎詐騙\n• 工作詐騙（在家高薪）\n• 解除分期付款",
                     "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text",
                     "text": "⚠️ 記住：不管對方說什麼，先打 165 問！",
                     "size": "xs", "color": "#C0392B", "wrap": True, "weight": "bold"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#C0392B",
                     "action": {"type": "message", "label": "🚨 最新詐騙手法 TOP 8",
                                "text": "最新詐騙手法"}},
                    {"type": "button", "style": "primary", "color": "#E74C3C",
                     "action": {"type": "uri", "label": "📞 撥打 165 反詐專線",
                                "uri": "tel:165"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🔄 回主選單", "text": "你好"}},
                ]
            }
        }
    }]


# ── 2025-2026 最新詐騙手法（定期更新）──
_FRAUD_TRENDS = [
    {"rank": 1, "name": "假投資詐騙", "emoji": "📈",
     "desc": "假冒名人（黃仁勳、謝金河）邀加 LINE 群「飆股向前衝」，推薦虛擬貨幣/AI 基金，先小額獲利再騙大筆",
     "sign": "保證獲利、老師帶單、LINE 群組"},
    {"rank": 2, "name": "網路購物詐騙", "emoji": "🛒",
     "desc": "假冒蝦皮/momo 客服說要「解除分期付款」，引導到 ATM 操作或提供帳號密碼",
     "sign": "低於市價、限時限量、客服來電要求操作 ATM"},
    {"rank": 3, "name": "AI 深偽詐騙", "emoji": "🤖",
     "desc": "用 AI 換臉/變聲假冒親友視訊通話，騙你匯款救急。2026 年暴增趨勢",
     "sign": "緊急借錢、視訊畫質異常、不願多聊"},
    {"rank": 4, "name": "愛情交友詐騙", "emoji": "💕",
     "desc": "交友 App 認識→培養感情→推薦投資平台。「養套殺」模式，跨平台操縱",
     "sign": "異國軍人/商人、很快示愛、引導到其他平台投資"},
    {"rank": 5, "name": "假冒公務機關", "emoji": "🏛️",
     "desc": "自稱警察/檢察官/健保局，說你涉案或個資外洩，要求轉帳到「安全帳戶」",
     "sign": "政府絕不會要求轉帳、+號開頭的電話"},
    {"rank": 6, "name": "求職打工詐騙", "emoji": "💼",
     "desc": "「在家輕鬆月入10萬」、代購代付、虛擬帳戶洗錢，你可能變成車手共犯",
     "sign": "高薪低門檻、要求提供帳戶、先墊款"},
    {"rank": 7, "name": "簡訊釣魚詐騙", "emoji": "📱",
     "desc": "假冒 ETC/郵局/稅務局發簡訊，附短網址要你「補繳費用」，騙取信用卡資料",
     "sign": "短網址、限時繳費、政府不會用簡訊催繳"},
    {"rank": 8, "name": "遊戲點數詐騙", "emoji": "🎮",
     "desc": "假冒遊戲客服或玩家，低價賣帳號/道具，付款後消失。或要求買點數卡抵債",
     "sign": "私下交易、要求購買點數卡、遊戲外溝通"},
]


def build_fraud_trends() -> list:
    """最新詐騙手法排行"""
    items = []
    for f in _FRAUD_TRENDS:
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{f['emoji']} #{f['rank']} {f['name']}",
                 "weight": "bold", "size": "sm", "color": "#C0392B", "flex": 4, "wrap": True},
            ]},
            {"type": "text", "text": f["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs", "maxLines": 3},
            {"type": "text", "text": f"⚠️ 特徵：{f['sign']}", "size": "xxs",
             "color": "#888888", "wrap": True, "margin": "xs"},
            {"type": "separator", "margin": "sm"},
        ]
    # Remove last separator
    if items and items[-1].get("type") == "separator":
        items.pop()

    return [{"type": "flex", "altText": "2025-2026 最新詐騙手法",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#C0392B",
                            "contents": [
                                {"type": "text", "text": "🚨 最新詐騙手法 TOP 8",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "2025-2026 警政署 165 彙整",
                                 "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "button", "style": "primary", "color": "#C0392B", "height": "sm",
                      "action": {"type": "uri", "label": "📞 撥打 165 反詐專線", "uri": "tel:165"}},
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": "🔍 我有可疑訊息要分析", "text": "防詐辨識"}},
                 ]},
             }}]


def build_fraud_result(text: str) -> list:
    """回傳詐騙風險分析結果"""
    result = analyze_fraud(text)
    risk = result["risk"]
    patterns = result["patterns"]

    if risk == "high":
        header_color = "#C0392B"
        risk_emoji = "🚨"
        risk_title = "高度疑似詐騙！"
        risk_desc = "這則訊息含有多項詐騙特徵，請勿轉帳、提供個資或點擊任何連結！"
        action_text = "立即封鎖對方，並撥打 165 反詐騙專線舉報"
        btn_label = "🚨 立即撥打 165"
    elif risk == "medium":
        header_color = "#E67E22"
        risk_emoji = "⚠️"
        risk_title = "發現可疑特徵"
        risk_desc = "這則訊息有部分可疑跡象，請先向家人或親友確認，勿急著回應。"
        action_text = "不要急著採取行動，先冷靜向身邊的人確認"
        btn_label = "📞 撥打 165 諮詢"
    else:
        header_color = "#27AE60"
        risk_emoji = "✅"
        risk_title = "未發現明顯詐騙特徵"
        risk_desc = "目前未偵測到明顯詐騙跡象，但仍請保持警覺。"
        action_text = "如仍有疑慮，隨時可撥打 165 詢問"
        btn_label = "📞 撥打 165 確認"

    pattern_text = "、".join(patterns) if patterns else "無明顯特徵"
    short_text = text[:40] + "…" if len(text) > 40 else text

    return [{
        "type": "flex", "altText": f"{risk_emoji} 詐騙風險分析",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": header_color,
                "contents": [
                    {"type": "text", "text": f"{risk_emoji} {risk_title}",
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": f"分析內容：「{short_text}」",
                     "color": "#FFFFFFCC", "size": "xs", "wrap": True},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text", "text": risk_desc,
                     "size": "sm", "color": "#3E2723", "wrap": True, "weight": "bold"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "🔎 偵測到的特徵",
                     "size": "xs", "weight": "bold", "color": "#8D6E63", "margin": "md"},
                    {"type": "text", "text": pattern_text,
                     "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"💡 建議：{action_text}",
                     "size": "xs", "color": "#5D4037", "wrap": True, "margin": "md"},
                    {"type": "text",
                     "text": "⚠️ 本工具僅供參考，無法取代專業判斷。有疑慮請撥 165。",
                     "size": "xs", "color": "#BBBBBB", "wrap": True, "margin": "md"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#C0392B",
                     "action": {"type": "uri", "label": btn_label, "uri": "tel:165"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🔍 再分析一則",
                                "text": "防詐辨識"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "uri", "label": "⚖️ 法律求助資訊",
                                "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                ]
            }
        }
    }]


# ════════════════════════════════════════════════
# 法律常識模組
# ════════════════════════════════════════════════

def build_legal_guide_intro() -> list:
    """法律常識入口"""
    return [{
        "type": "flex", "altText": "法律常識小幫手",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1C2B4A",
                "contents": [
                    {"type": "text", "text": "⚖️ 法律常識小幫手", "color": "#FFFFFF",
                     "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "白話解釋你的法律權益",
                     "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "常見問題，點一個開始：",
                     "size": "sm", "color": "#8D6E63"},
                    {"type": "button", "style": "secondary", "margin": "sm",
                     "action": {"type": "message", "label": "🏠 租屋糾紛怎麼辦？",
                                "text": "法律 租屋糾紛"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💼 被公司欠薪/違法解僱",
                                "text": "法律 勞資糾紛"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🛍️ 買到假貨/商品有問題",
                                "text": "法律 消費者保護"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🚗 發生車禍怎麼處理",
                                "text": "法律 交通事故"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💰 被詐騙了可以怎麼做",
                                "text": "法律 詐騙求助"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "👨‍👩‍👧 離婚/家暴/監護權",
                                "text": "法律 家事"}},
                    {"type": "separator", "margin": "md"},
                    {"type": "button", "style": "primary", "color": "#1C2B4A",
                     "margin": "md",
                     "action": {"type": "uri", "label": "🌐 開啟完整法律常識網站",
                                "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                ]
            }
        }
    }]


LEGAL_QA = {
    "租屋糾紛": {
        "title": "🏠 租屋糾紛",
        "content": (
            "【房東不退押金】\n"
            "• 搬出前拍照存證（每個房間、每件家具）\n"
            "• 租約結束後 → 房東須於 30 天內退押金\n"
            "• 拒不退還 → 發存證信函，再提小額訴訟\n\n"
            "【房東突然漲租/趕人】\n"
            "• 租約期間內，房東不得任意漲租或趕人\n"
            "• 違反租約 → 可要求損害賠償\n\n"
            "【緊急求助】\n"
            "• 內政部租屋糾紛申訴：1999\n"
            "• 法律扶助基金會：412-8518"
        )
    },
    "勞資糾紛": {
        "title": "💼 勞資糾紛",
        "content": (
            "【被欠薪】\n"
            "• 保留薪資單、轉帳紀錄、通訊對話\n"
            "• 向勞工局申訴（免費，雇主壓力大）\n"
            "• 勞工局電話：1955\n\n"
            "【違法解僱】\n"
            "• 解僱須有法定事由，否則為違法\n"
            "• 可要求復職或資遣費補償\n"
            "• 年資每滿一年給 1 個月平均工資\n\n"
            "【加班費沒給】\n"
            "• 平日加班：前 2 小時 × 1.34 倍，之後 × 1.67 倍\n"
            "• 可申請勞動局調解"
        )
    },
    "消費者保護": {
        "title": "🛍️ 消費者保護",
        "content": (
            "【買到假貨/瑕疵品】\n"
            "• 網購：7 天內無條件退貨（猶豫期）\n"
            "• 實體購買：可依消保法要求修補、換貨或退款\n"
            "• 保留發票、對話紀錄、照片\n\n"
            "【商家不退款】\n"
            "• 先向消保官申訴：1950\n"
            "• 或向消費者保護委員會申訴\n\n"
            "【信用卡爭議】\n"
            "• 向發卡銀行申請「帳單爭議」\n"
            "• 銀行須在 30 天內回覆處理結果"
        )
    },
    "交通事故": {
        "title": "🚗 交通事故",
        "content": (
            "【現場處理】\n"
            "• 先確認人員安全，有傷亡立即撥 110/119\n"
            "• 拍照：車輛位置、損傷、現場環境\n"
            "• 交換資料：姓名、車牌、保險公司\n"
            "• 不要急著移車（除非造成交通危險）\n\n"
            "【理賠】\n"
            "• 強制險（傷亡）→ 對方保險公司\n"
            "• 第三責任險（財損）→ 視過失比例\n"
            "• 傷亡可申請強制險：醫療費最高 20 萬\n\n"
            "【對方逃逸】\n"
            "• 記車牌，立即報警，可申請犯罪被害補償"
        )
    },
    "詐騙求助": {
        "title": "💰 被詐騙了怎麼辦",
        "content": (
            "【已經轉帳了】\n"
            "1. 立即撥打 165，請求凍結帳戶\n"
            "2. 打給你的銀行，請求止付/攔截\n"
            "3. 到警察局報案（越快越好）\n"
            "4. 保留所有對話紀錄、交易紀錄\n\n"
            "【還沒轉帳，但對方一直催】\n"
            "• 立即封鎖對方\n"
            "• 撥打 165 確認是否詐騙\n\n"
            "【重要求助電話】\n"
            "• 165 反詐騙：24 小時\n"
            "• 警政署反詐騙官網：可線上舉報\n"
            "• 法律扶助基金會：412-8518"
        )
    },
    "家事": {
        "title": "👨‍👩‍👧 家事法律",
        "content": (
            "【離婚】\n"
            "• 協議離婚：兩人合意 + 2 位證人簽名\n"
            "• 訴訟離婚：須有法定事由（外遇、惡意遺棄等）\n\n"
            "【監護權】\n"
            "• 離婚後可協議或由法院判決\n"
            "• 法院以「子女最佳利益」為原則\n"
            "• 非監護方有探視權\n\n"
            "【家暴】\n"
            "• 撥打 113 家暴保護專線（24 小時）\n"
            "• 可申請保護令（禁止對方接近）\n"
            "• 到地方法院聲請，費用全免"
        )
    },
}


def build_legal_answer(topic: str) -> list:
    """回傳特定法律主題的說明"""
    qa = LEGAL_QA.get(topic)
    if not qa:
        return build_legal_guide_intro()
    return [
        {
            "type": "flex", "altText": qa["title"],
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#1C2B4A",
                    "contents": [
                        {"type": "text", "text": qa["title"], "color": "#FFFFFF",
                         "size": "lg", "weight": "bold"},
                        {"type": "text", "text": "以下為一般性說明，非正式法律意見",
                         "color": "#FFFFFFCC", "size": "xs"},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": qa["content"], "size": "sm",
                         "color": "#3E2723", "wrap": True},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#1C2B4A",
                         "action": {"type": "uri", "label": "🌐 查看完整說明",
                                    "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "⚖️ 看其他法律主題",
                                    "text": "法律常識"}},
                    ]
                }
            }
        }
    ]


def build_tools_menu() -> list:
    """生活工具箱選單（進階工具：3C選購、防詐、法律）"""
    ACCENT = "#546E7A"

    def _tool_row(icon, title, desc, trigger, color):
        return {
            "type": "box", "layout": "horizontal", "spacing": "md",
            "paddingAll": "md",
            "backgroundColor": "#F8F9FB",
            "cornerRadius": "10px",
            "action": {"type": "message", "label": title, "text": trigger},
            "contents": [
                # 左：色條
                {"type": "box", "layout": "vertical", "width": "4px",
                 "backgroundColor": color, "cornerRadius": "4px", "contents": []},
                # 中：文字
                {"type": "box", "layout": "vertical", "flex": 1, "spacing": "xs",
                 "contents": [
                     {"type": "text", "text": f"{icon} {title}",
                      "size": "md", "weight": "bold", "color": "#1A1F3A"},
                     {"type": "text", "text": desc, "size": "xs",
                      "color": "#8892B0", "wrap": True},
                 ]},
                # 右：箭頭
                {"type": "text", "text": "›", "size": "xl",
                 "color": color, "align": "end", "gravity": "center"},
            ]
        }

    tools = [
        _tool_row("📱", "3C 選購小幫手", "推薦最適合你的手機、筆電、平板",
                  "推薦手機", "#FF8C42"),
        _tool_row("🛡️", "防詐騙辨識",   "辨識可疑訊息、連結、電話號碼",
                  "防詐辨識", "#C0392B"),
        _tool_row("⚖️", "法律小常識",   "租屋、勞資、消費糾紛怎麼辦",
                  "法律常識", "#3949AB"),
        _tool_row("🔧", "硬體升級諮詢", "舊電腦要怎麼升級？問我就對了",
                  "硬體升級", "#546E7A"),
    ]
    # 在工具列之間加間距
    body_contents = []
    for i, t in enumerate(tools):
        if i > 0:
            body_contents.append({"type": "box", "layout": "vertical",
                                  "height": "8px", "contents": []})
        body_contents.append(t)

    return [{
        "type": "flex", "altText": "生活工具箱",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "horizontal",
                "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                "contents": [
                    {"type": "image",
                     "url": "https://3c-advisor.vercel.app/liff/images/wrench.jpg",
                     "flex": 0, "size": "72px",
                     "aspectRatio": "1:1", "aspectMode": "fit"},
                    {"type": "box", "layout": "vertical", "width": "4px",
                     "cornerRadius": "4px", "backgroundColor": ACCENT,
                     "margin": "md", "contents": []},
                    {"type": "box", "layout": "vertical", "flex": 1,
                     "paddingStart": "12px", "contents": [
                         {"type": "text", "text": "🗃️ 生活工具箱",
                          "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                         {"type": "text", "text": "點選需要的工具，馬上幫你",
                          "color": "#8892B0", "size": "xs", "margin": "xs"},
                     ]},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#FFFFFF",
                "paddingAll": "md", "contents": body_contents
            },
        }
    }]


def build_purchase_guide_message() -> list:
    """購買指南 Flex 訊息"""
    return [{
        "type": "flex",
        "altText": "3C 購買指南",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#5B9BD5",
                "contents": [
                    {"type": "text", "text": "📖 購買指南", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "買 3C 前一定要知道的事", "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text", "text": "✅ 購買前確認清單", "size": "sm", "weight": "bold", "color": "#3E2723"},
                    {"type": "text", "text": "1. 確認是「台灣公司貨」還是「平行輸入」\n   → 公司貨保固 1 年，平行輸入需自行送修", "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "text", "text": "2. 比較至少 3 個平台的價格\n   → PChome、蝦皮、momo 價差可達 10%", "size": "xs", "color": "#5D4037", "wrap": True, "margin": "sm"},
                    {"type": "text", "text": "3. 注意贈品是否有需要（通常不值錢）", "size": "xs", "color": "#5D4037", "wrap": True, "margin": "sm"},
                    {"type": "text", "text": "4. 查看近 30 天歷史價格，避免買在高點", "size": "xs", "color": "#5D4037", "wrap": True, "margin": "sm"},
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "⚠️ 常見銷售話術 別被騙", "size": "sm", "weight": "bold", "color": "#E53935", "margin": "md"},
                    {"type": "text", "text": "❌「今天最後一天優惠」→ 通常明天還有\n❌「只剩最後一台」→ 庫存管理話術\n❌「加購配件才有保固」→ 不合法，保固不需額外付費", "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "💡 買回來第一件事", "size": "sm", "weight": "bold", "color": "#2E7D32", "margin": "md"},
                    {"type": "text", "text": "1. 開機檢查外觀是否有刮痕\n2. 測試所有按鍵、連接埠\n3. 拍照存證（出問題時有憑有據）\n4. 登記原廠保固", "size": "xs", "color": "#5D4037", "wrap": True},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#5B9BD5",
                     "action": {"type": "message", "label": "📱 幫我推薦手機", "text": "推薦手機"}},
                    {"type": "button", "style": "secondary", "margin": "sm",
                     "action": {"type": "message", "label": "🔄 回主選單", "text": "你好"}},
                ]
            }
        }
    }]


def build_compare_price_message(text: str) -> list:
    """比價查詢 — 引導用戶說出商品名稱，或直接給 BigGo 連結"""
    import urllib.parse
    # 如果包含具體商品名稱（去掉「幫我比價」後還有內容）
    keyword = text.replace("幫我比價", "").replace("比價", "").strip()
    if len(keyword) >= 2:
        q = urllib.parse.quote(keyword)
        biggo_url = f"https://biggo.com.tw/s/{q}"
        feebee_url = f"https://feebee.com.tw/search/?q={q}"
        return [{
            "type": "flex",
            "altText": f"比價：{keyword}",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#4CAF50",
                    "contents": [
                        {"type": "text", "text": "💰 比價結果", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                        {"type": "text", "text": keyword, "color": "#FFFFFFCC", "size": "sm", "wrap": True},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "點下方按鈕，查看各平台最低價 👇", "size": "sm", "color": "#3E2723", "wrap": True},
                        {"type": "text", "text": "涵蓋 PChome、蝦皮、momo、Yahoo 等", "size": "xs", "color": "#8D6E63"},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#4CAF50",
                         "action": {"type": "uri", "label": "💰 BigGo 跨平台比價", "uri": biggo_url}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "uri", "label": "🔍 飛比價格", "uri": feebee_url}},
                    ]
                }
            }
        }]
    else:
        # 沒有商品名稱 → 引導輸入
        return [{"type": "text", "text": "請告訴我要比價的商品名稱 😊\n\n例如：\n「幫我比價 iPhone 16」\n「幫我比價 MacBook Air M3」"}]


def _detect_feature(text: str) -> tuple:
    """從用戶文字快速分類功能（用於 log，不影響路由邏輯）回傳 (feature, sub_action)"""
    t = text.lower().strip()
    if any(w in t for w in ["吃什麼", "吃甚麼", "吃啥", "晚餐", "午餐", "早餐", "餐廳", "必比登", "米其林"]) or \
       any(w in t for w in _ALL_FOOD_KEYWORDS):
        # 嘗試抓食物類型
        for style, kws in _STYLE_KEYWORDS.items():
            if any(w in t for w in kws):
                return ("food", style)
        return ("food", None)
    if any(w in t for w in ["天氣", "穿什麼", "穿搭", "氣溫", "幾度", "下雨", "帶傘"]):
        for city in ["台北", "台中", "台南", "高雄", "新北", "桃園", "新竹", "嘉義", "基隆", "宜蘭", "花蓮", "台東"]:
            if city in text:
                return ("weather", city)
        return ("weather", None)
    if any(w in t for w in ["周末", "週末", "近期活動", "活動", "出去玩", "踏青", "市集", "展覽"]):
        return ("activity", None)
    if any(w in t for w in ["bmi", "身高", "體重", "減肥", "睡眠", "失眠", "熱量", "喝水"]):
        return ("health", None)
    if any(w in t for w in ["存錢", "理財", "薪水", "信用卡", "保險", "匯率", "油價"]):
        return ("money", None)
    if any(w in t for w in ["找車位", "停車", "車位"]):
        return ("parking", None)
    if any(w in t for w in ["防詐", "詐騙"]):
        return ("fraud", None)
    if any(w in t for w in ["法律"]):
        return ("legal", None)
    if any(w in t for w in ["手機", "筆電", "平板", "桌機", "推薦", "iphone", "samsung"]):
        device = detect_device(text)
        return ("3c", device or None)
    if any(w in t for w in ["工具箱", "更多功能"]):
        return ("tools", None)
    return ("other", None)


_CURRENT_USER_ID = ""   # 每次呼叫 handle_text_message 前會更新

def handle_text_message(text: str, user_id: str = "") -> list:
    """主路由：分析文字，決定回覆什麼"""
    global _CURRENT_USER_ID
    _CURRENT_USER_ID = user_id
    text = text.strip()
    text_lower = text.lower()

    # ── 最優先：按鈕觸發的固定格式指令 ──────────────────────
    if text.startswith("信用卡推薦:"):
        return build_credit_card_result(text.split(":", 1)[1].strip())

    # ── 0-a. 這款適合我嗎（產品卡片按鈕，必須最優先攔截）──────
    if text.startswith("這款適合我嗎"):
        product_name = text.replace("這款適合我嗎", "").strip()
        return build_suitability_message(product_name)


    # ── 0.05 管理員廣播（僅開發者可用）──────
    if text.startswith("廣播 ") and user_id and user_id == ADMIN_USER_ID:
        _bc_content = text[3:].strip()
        if _bc_content:
            _broadcast_message(_bc_content)
            return [{"type": "text", "text": f"📢 已廣播給所有使用者：\n{_bc_content}"}]

    # ── 0.1 使用者回報（餐廳好吃/倒閉 + 通用回報）──────
    if text.startswith("回報 "):
        # 餐廳回報（好吃/倒閉）
        if "好吃" in text or "倒閉" in text or "歇業" in text:
            result = handle_food_feedback(text, user_id)
            if result:
                return result
        # 通用回報（bug、功能異常、錯誤等）
        return handle_general_report(text, user_id)

    # ── 0. 問卷狀態解析（優先處理，避免被其他規則攔截）──────
    state = parse_wizard_state(text)
    if state:
        device_name = state["device_name"]
        if "budget" in state:
            # 所有資訊齊全 → 顯示個人化推薦
            who = state.get("who", "自己")
            use = state.get("use", "日常")
            budget = state["budget"]
            # 將問卷用途對應到 filter_products 的 uses 清單
            use_map = {
                "拍照": ["拍照"], "遊戲": ["遊戲"], "追劇": ["追劇"],
                "工作": ["工作"], "學習": ["學生"], "創作": ["創作"],
                "日常": ["日常"], "閱讀": ["閱讀"],
            }
            uses = use_map.get(use, [])
            if who == "長輩":
                uses.append("長輩")
            elif who == "學生":
                uses.append("學生")
            msgs = build_recommendation_message(state["device"], budget, uses)
            # 在推薦結果前加一行個人化說明
            who_label = {"自己": "你", "長輩": "長輩", "學生": "學生", "小孩": "小孩"}.get(who, who)
            use_label = {"日常": "日常使用", "拍照": "拍照攝影", "遊戲": "玩遊戲",
                         "追劇": "追劇看片", "學習": "學校作業", "工作": "工作文書",
                         "創作": "影片剪輯", "閱讀": "閱讀電子書"}.get(use, use)
            budget_text = "不限預算" if budget >= 999999 else f"NT${budget:,} 以內"
            intro = {"type": "text",
                     "text": f"根據你的需求幫你找到最適合的 {device_name} 👇\n\n"
                             f"👤 使用者：{who_label}\n"
                             f"🎯 主要用途：{use_label}\n"
                             f"💰 預算：{budget_text}"}
            return [intro] + msgs
        elif "use" in state:
            # 有裝置 + 使用者 + 用途 → 問預算
            return build_wizard_budget(device_name, state["who"], state["use"])
        elif "who" in state:
            # 有裝置 + 使用者 → 問用途
            return build_wizard_use(device_name, state["who"])
        else:
            # 只有裝置 → 問使用者（理論上不會到這裡）
            return build_wizard_who(device_name)

    # ── 1.3 早安摘要（在打招呼前優先攔截）──────────────
    _morning_kw = ["早安", "早上好", "早啊", "早哦", "morning", "good morning", "早起了", "早安安"]
    if any(w in text_lower for w in _morning_kw):
        log_usage(user_id, "morning_summary")
        return build_morning_summary(text, user_id=user_id)

    # ── 1. 打招呼 / 幫助 ────────────────────────────
    greetings = ["你好", "嗨", "hi", "hello", "哈囉", "安安", "開始", "幫助", "help", "選單", "功能"]
    if any(text_lower == g or text_lower.startswith(g) for g in greetings):
        return build_welcome_message()

    # ── 2. 情境推薦 ──────────────────────────────────
    if any(w in text for w in ["情境推薦", "不知道", "幫我選", "給誰用", "哪種適合"]):
        return build_scenario_menu()

    # ── 3. 看懂規格 ──────────────────────────────────
    if any(w in text for w in ["看懂規格", "規格", "處理器", "記憶體", "儲存", "螢幕", "電池",
                                "cpu", "ram", "ssd", "oled", "hz", "mah", "什麼意思", "看不懂"]):
        return build_spec_explainer(text)

    # ── 4. 購買指南 ──────────────────────────────────
    if any(w in text for w in ["購買指南", "購買須知", "買之前", "注意事項", "怎麼買"]):
        return build_purchase_guide_message()

    # ── 4.5 消費決策（最優先，避免被食物/3C handler 搶走）──
    _spend_kws = ["划算嗎", "划算", "值得買嗎", "值得買", "要買嗎", "該買嗎", "值得嗎",
                  "貴嗎", "太貴嗎", "消費決策", "信用卡還是現金", "刷卡還是現金",
                  "刷卡或現金", "要不要買", "可以買嗎", "買得起嗎"]
    _spend_items = ["手機", "筆電", "平板", "電視", "冷氣", "冰箱", "洗衣機",
                    "耳機", "相機", "沙發", "包包", "課程", "保險",
                    "iphone", "ipad", "macbook"]
    _has_amount = bool(re.search(r"\d{3,}", text))
    if (any(w in text_lower for w in _spend_kws) or
            (any(w in text_lower for w in _spend_items) and _has_amount)):
        return build_spending_decision(text)

    # ── 4.5 比價查詢 ─────────────────────────────────
    if any(w in text for w in ["比價", "最便宜", "哪裡買便宜", "價格比較", "biggo", "飛比"]):
        return build_compare_price_message(text)

    # ── 4.5 天氣＋穿搭建議 ──────────────────────────────
    if any(w in text for w in ["天氣", "穿什麼", "穿搭", "氣溫", "幾度", "下雨嗎",
                                "要帶傘", "帶傘", "氣象", "預報", "今天冷", "今天熱"]):
        return build_weather_message(text, user_id=user_id)

    # ── 4.6 今天吃什麼（比健康小幫手更早，避免「吃什麼 健康」被誤判）──
    # ── 4.61 聚餐推薦（比一般吃什麼更早攔截）──────────
    if any(w in text for w in ["聚餐", "約飯", "朋友聚", "家庭聚", "公司聚", "同學聚",
                                "包廂", "圍爐", "尾牙", "春酒", "生日餐廳",
                                "辦桌", "大桌", "多人聚餐", "找餐廳"]):
        return build_group_dining_message(text)

    if any(w in text for w in ["吃什麼", "吃甚麼", "吃啥", "晚餐", "午餐", "早餐",
                                "吃飯", "外食", "今天吃", "推薦餐廳", "餐廳推薦",
                                "吃什麼好", "要吃什麼", "本週美食", "美食活動",
                                "在地餐廳", "餐廳", "必比登", "米其林"]) or \
       any(w in text for w in _ALL_FOOD_KEYWORDS):
        return build_food_message(text)

    # ── 4.7 健康小幫手（移除裸字「健康」，避免誤觸）──────
    if any(w in text for w in ["健康小幫手", "BMI", "bmi", "身高", "體重", "減肥", "瘦身",
                                "失眠", "睡不著", "睡眠", "睡不好", "壓力大", "焦慮",
                                "減重", "肥胖", "運動建議", "睡眠改善", "壓力紓解",
                                "幫我算BMI", "熱量", "卡路里", "幾卡", "食物熱量",
                                "運動消耗", "運動熱量", "喝水量", "喝水"]):
        return build_health_message(text)

    # ── 4.8 花太多了（在金錢小幫手前）─────────────────
    if any(w in text for w in ["花太多", "超支", "這週花", "本週花", "花太兇",
                                "錢不夠了", "省錢建議", "省錢小技巧", "怎麼省錢"]):
        return _spend_overspent()

    # ── 4.8 金錢小幫手 ───────────────────────────────
    if any(w in text for w in ["金錢小幫手", "存錢", "理財", "月薪", "薪水", "薪資", "預算規劃",
                                "信用卡", "循環利息", "保險", "醫療險", "儲蓄",
                                "怎麼存", "信用卡使用", "保險建議", "金錢",
                                "匯率", "換匯", "外幣", "美金", "日圓", "日幣",
                                "歐元", "英鎊", "韓元", "韓幣", "人民幣", "泰銖",
                                "信用卡比較", "信用卡推薦", "哪張卡", "回饋",
                                "油價", "加油", "汽油", "柴油"]):
        return build_money_message(text)

    # ── 4.9 近期活動 ────────────────────────────────
    if any(w in text for w in ["近期活動", "周末", "週末", "假日", "出去玩", "去哪玩",
                                "活動推薦", "景點推薦", "玩什麼", "去哪裡",
                                "踏青", "咖啡廳", "親子", "週末活動",
                                "美術館", "博物館", "市集", "展覽活動", "藝文",
                                "文化中心", "藝術特區", "文創", "文創園區",
                                "藝術館", "展演", "音樂祭", "藝文活動",
                                "表演音樂", "戶外踏青", "文青咖啡", "親子同樂",
                                "運動健身", "吃喝玩樂", "市集展覽"]) or \
       (text.startswith("活動") and len(text) > 2):
        return build_activity_message(text)

    # ── 4.10 硬體升級諮詢 ───────────────────────────
    if any(w in text for w in ["硬體升級", "電腦升級", "升級建議", "升級 RAM", "升級 SSD",
                                "升級 GPU", "升級RAM", "升級SSD", "升級GPU",
                                "加RAM", "加 RAM", "加記憶體", "換SSD", "換 SSD", "換硬碟",
                                "顯卡升級", "要升級嗎", "電腦效能分析", "電腦瓶頸",
                                "RAM夠嗎", "RAM 夠嗎", "記憶體夠嗎", "電腦太慢"]):
        return build_upgrade_message(text)

    # ── 5. 防詐辨識 ──────────────────────────────────
    if any(w in text for w in ["防詐", "詐騙", "可疑", "165", "是詐騙嗎", "防詐辨識",
                                "最新詐騙", "詐騙手法"]):
        # 最新詐騙手法
        if "最新" in text or "手法" in text or "排行" in text:
            return build_fraud_trends()
        # 如果只說關鍵字 → 顯示說明；若帶有內容 → 直接分析
        stripped = text
        for kw in ["防詐辨識", "幫我看", "這是詐騙嗎", "防詐", "詐騙"]:
            stripped = stripped.replace(kw, "").strip()
        if len(stripped) >= 10:
            return build_fraud_result(stripped)
        return build_fraud_intro()

    # ── 6. 法律常識 ──────────────────────────────────
    if any(w in text for w in ["法律", "法律常識", "法律問題", "權益"]):
        # 偵測特定主題
        for topic in LEGAL_QA.keys():
            if topic in text:
                return build_legal_answer(topic)
        return build_legal_guide_intro()

    # ── 7. 生活自保頁籤按鈕 ──────────────────────────
    if any(w in text for w in ["消費保護", "消費者保護", "消費糾紛", "退貨", "消保"]):
        return build_legal_answer("消費者保護")

    if any(w in text for w in ["職場求助", "勞資", "職場", "被資遣", "加班費", "欠薪"]):
        return build_legal_answer("勞資糾紛")

    if any(w in text for w in ["緊急求助", "緊急", "急救", "求助"]):
        return [{
            "type": "flex", "altText": "緊急求助管道",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#C0392B",
                    "contents": [
                        {"type": "text", "text": "🆘 緊急求助管道", "color": "#FFFFFF",
                         "size": "lg", "weight": "bold"}
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical", "spacing": "md",
                    "contents": [
                        {"type": "text", "text": "📞 165 反詐騙專線（24小時）", "size": "sm", "weight": "bold", "color": "#C0392B"},
                        {"type": "text", "text": "📞 110 警察報案", "size": "sm", "weight": "bold"},
                        {"type": "text", "text": "📞 113 家暴/跟蹤騷擾保護（24小時）", "size": "sm"},
                        {"type": "text", "text": "📞 1955 勞工申訴專線", "size": "sm"},
                        {"type": "text", "text": "📞 412-8518 法律扶助基金會", "size": "sm"},
                        {"type": "text", "text": "📞 1950 消費者服務", "size": "sm"},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#C0392B",
                         "action": {"type": "message", "label": "🔍 防詐辨識", "text": "防詐辨識"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "⚖️ 法律常識", "text": "法律常識"}},
                    ]
                }
            }
        }]

    # ── 功能建議 / 許願池 / 問題回報 ──────────────────────
    if text in ("回報", "許願", "許願池", "功能建議", "功能回報", "意見回報"):
        return build_feedback_intro()

    if any(w in text for w in ["我想要功能", "希望有功能"]) or \
       (text.startswith("建議") and len(text) >= 4):
        # 取得使用者名稱（若有）
        _fb_name = ""
        try:
            _fb_profile_req = urllib.request.Request(
                f"https://api.line.me/v2/bot/profile/{user_id}",
                headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
            )
            _fb_profile = json.loads(urllib.request.urlopen(_fb_profile_req, timeout=5).read())
            _fb_name = _fb_profile.get("displayName", "")
        except Exception:
            pass
        return handle_user_suggestion(text, user_id, _fb_name)

    if any(w in text for w in ["更多功能", "其他工具", "還有什麼", "其他功能", "工具箱", "所有工具", "生活工具"]):
        return build_tools_menu()

    # ── 找車位 ──────────────────────────────────────────
    if any(w in text for w in ["找車位", "車位", "停車", "停車場", "哪裡停車", "附近停車"]):
        liff_url = "https://liff.line.me/2009774625-KwBrQAbV?action=parking"
        return [{"type": "flex", "altText": "🅿️ 找附近停車位",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "body": {
                         "type": "box", "layout": "vertical",
                         "backgroundColor": "#0D1B35",
                         "paddingAll": "24px", "spacing": "lg",
                         "contents": [
                             {"type": "text", "text": "🅿️ 找附近停車場",
                              "color": "#FFFFFF", "size": "xxl", "weight": "bold",
                              "align": "center"},
                             {"type": "text",
                              "text": "顯示即時剩餘車位，幫你省去繞圈時間",
                              "color": "#7A9CC0", "size": "sm", "wrap": True,
                              "align": "center"},
                             {"type": "separator", "margin": "lg", "color": "#ffffff20"},
                             {"type": "box", "layout": "vertical", "margin": "lg",
                              "spacing": "sm", "contents": [
                                 {"type": "box", "layout": "horizontal", "spacing": "sm",
                                  "contents": [
                                     {"type": "text", "text": "①", "color": "#26A69A",
                                      "size": "sm", "flex": 0},
                                     {"type": "text", "wrap": True, "size": "sm",
                                      "color": "#CCD6F6",
                                      "text": "點下方按鈕開啟定位"},
                                 ]},
                                 {"type": "box", "layout": "horizontal", "spacing": "sm",
                                  "contents": [
                                     {"type": "text", "text": "②", "color": "#26A69A",
                                      "size": "sm", "flex": 0},
                                     {"type": "text", "wrap": True, "size": "sm",
                                      "color": "#CCD6F6",
                                      "text": "允許位置存取"},
                                 ]},
                                 {"type": "box", "layout": "horizontal", "spacing": "sm",
                                  "contents": [
                                     {"type": "text", "text": "③", "color": "#26A69A",
                                      "size": "sm", "flex": 0},
                                     {"type": "text", "wrap": True, "size": "sm",
                                      "color": "#CCD6F6",
                                      "text": "Bot 自動顯示附近停車場與空位數"},
                                 ]},
                             ]},
                             {"type": "button", "style": "primary", "color": "#26A69A",
                              "margin": "xl",
                              "action": {"type": "uri",
                                         "label": "📍 一鍵找附近停車場",
                                         "uri": liff_url}},
                         ]
                     }
                 }}]

    # ── 8. 頁籤切換訊息（點到已啟用頁籤 → 顯示對應選單）──────
    if text.startswith("tab:"):
        if "生活" in text:
            return build_tools_menu()   # 已在生活自保頁 → 顯示工具箱
        return build_welcome_message()  # 已在3C推薦頁 → 顯示歡迎選單

    # ── (舊路由保留) 其他工具 ────────────────────────
    if any(w in text for w in ["其他工具", "還有什麼", "工具箱"]):
        return build_tools_menu()

    # ── 8. 長文自動防詐分析（用戶直接貼可疑內容）───────
    if len(text) >= 30:
        result = analyze_fraud(text)
        if result["risk"] in ("high", "medium"):
            return build_fraud_result(text)

    # ── 6. 偵測裝置 → 啟動問卷 ──────────────────────
    device = detect_device(text)
    if device:
        device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板", "desktop": "桌機"}.get(device, "")
        budget = parse_budget(text)
        uses = detect_use(text)
        # 有足夠資訊（自然語言直接說出來）→ 直接推薦
        if budget or uses:
            return build_recommendation_message(device, budget, uses)
        # 只說了裝置類型 → 啟動問卷 Step 1
        return build_wizard_who(device_name)

    # ── 7. 只說了預算 → 問裝置類型 ──────────────────
    budget = parse_budget(text)
    if budget:
        return [{
            "type": "flex", "altText": "你想買什麼？",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "text", "text": "你想買哪種裝置？",
                         "size": "md", "weight": "bold", "color": "#3E2723"},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#FF8C42",
                         "action": {"type": "message", "label": "📱 手機",
                                    "text": f"手機|自己|日常|{budget}"}},
                        {"type": "button", "style": "primary", "color": "#E07838",
                         "action": {"type": "message", "label": "💻 筆電",
                                    "text": f"筆電|自己|工作|{budget}"}},
                        {"type": "button", "style": "primary", "color": "#C96830",
                         "action": {"type": "message", "label": "📟 平板",
                                    "text": f"平板|自己|追劇|{budget}"}},
                    ]
                }
            }
        }]

    # ── 8. 完全看不懂 → 友善引導 ────────────────────
    return [{
        "type": "text",
        "text": "嗨！我是生活優轉 👋\n\n"
                "我可以幫你：\n"
                "🍜 今天吃什麼\n"
                "🎨 近期活動 / 天氣穿搭\n"
                "🅿️ 找車位（即時空位）\n"
                "📱 3C 推薦 / 信用卡比較\n"
                "💪 健康小幫手 / 金錢小幫手\n"
                "🛡️ 防詐騙 / 法律常識\n\n"
                "可以點下方選單，或直接跟我說你想做什麼 😊"
    }]


# ─── 找車位（TDX 停車 API）────────────────────────────

TDX_CLIENT_ID     = os.environ.get("TDX_CLIENT_ID", "")
TDX_CLIENT_SECRET = os.environ.get("TDX_CLIENT_SECRET", "")

# ── Upstash Redis（持久快取，跨 Vercel instance 共用）────
UPSTASH_REDIS_URL   = os.environ.get("UPSTASH_REDIS_URL",   "https://current-kitten-87278.upstash.io")
UPSTASH_REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_TOKEN", "gQAAAAAAAVTuAAIncDI0Nzc0ZDFjYTEyY2Q0NTczYTcxYjQ1MjNkNjQzZDVkYXAyODcyNzg")

def _redis_get(key: str):
    """從 Upstash Redis 取值；失敗或未設定回傳 None"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        import urllib.parse as _up
        req = urllib.request.Request(
            f"{UPSTASH_REDIS_URL}/get/{_up.quote(key, safe='')}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            result = json.loads(r.read()).get("result")
            return json.loads(result) if result else None
    except Exception as e:
        print(f"[Redis] GET {key} 失敗: {e}")
        return None

def _redis_set(key: str, value, ttl: int = 300):
    """存值到 Upstash Redis（JSON），ttl 秒後過期"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    try:
        payload = json.dumps(["SET", key, json.dumps(value, ensure_ascii=False), "EX", ttl]).encode()
        req = urllib.request.Request(
            UPSTASH_REDIS_URL,
            data=payload,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                     "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            pass
    except Exception as e:
        print(f"[Redis] SET {key} 失敗: {e}")
_tdx_token_cache  = {"token": "", "expires": 0.0}


def _get_tdx_token() -> str:
    """取得 TDX API Token（記憶體快取 50 分鐘 + Redis 快取 55 分鐘）"""
    import time
    now = time.time()
    # 1. 記憶體快取（同實例最快）
    if _tdx_token_cache["token"] and now < _tdx_token_cache["expires"]:
        return _tdx_token_cache["token"]
    if not TDX_CLIENT_ID or not TDX_CLIENT_SECRET:
        return ""
    # 2. Redis 跨實例快取（省去 OAuth 呼叫 ~1-2s）
    cached = _redis_get("tdx_token")
    if cached and isinstance(cached, str) and len(cached) > 20:
        print("[TDX] token Redis命中")
        _tdx_token_cache["token"]   = cached
        _tdx_token_cache["expires"] = now + 3000
        return cached
    try:
        payload = urllib.parse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     TDX_CLIENT_ID,
            "client_secret": TDX_CLIENT_SECRET,
        }).encode()
        req = urllib.request.Request(
            "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.loads(r.read())
        token = res.get("access_token", "")
        expires_in = int(res.get("expires_in", 3600))
        safe_ttl = max(expires_in - 60, 300)        # 提前 60 秒刷新，最少 5 分鐘
        _tdx_token_cache["token"]   = token
        _tdx_token_cache["expires"] = now + safe_ttl
        _redis_set("tdx_token", token, ttl=safe_ttl)
        print("[TDX] token 重新取得並存 Redis")
        return token
    except Exception as e:
        print(f"[TDX] token 失敗: {e}")
        return ""


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """兩點距離（公尺），Haversine 公式"""
    import math
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


def _tdx_get(path: str, token: str, timeout: int = 20) -> list:
    """呼叫 TDX API，回傳 list（支援 City 路徑的巢狀 JSON）"""
    url = "https://tdx.transportdata.tw/api/basic/v1/" + path
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            # TDX City 端點回傳 {"CarParks": [...]} 或 {"ParkingAvailabilities": [...]}
            for key in ("CarParks", "ParkingAvailabilities", "ParkingLots", "RoadSections"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # 最後嘗試第一個 list 值
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
    except Exception as e:
        print(f"[TDX] GET {path[:80]} 失敗: {e}")
        return []


# 台灣各縣市座標框（lat_min, lat_max, lon_min, lon_max, tdx_city）
# 越小的框排越前面，讓 min(area) 選最精確的城市
# TDX 實測可用城市名稱（2026-04 驗證）：
#   直轄市/省轄市不加 County：Taipei, Keelung, Hsinchu, Chiayi, Taichung, Tainan, Kaohsiung, Taoyuan
#   縣需要加 County：HsinchuCounty, MiaoliCounty, ChanghuaCounty, NantouCounty,
#                    YunlinCounty, ChiayiCounty, PingtungCounty, HualienCounty, TaitungCounty, PenghuCounty
#   NewTaipei：API 存在但目前無資料（count=0）
_TW_CITY_BOXES = [
    (25.044, 25.210, 121.460, 121.666, "Taipei"),           # 台北市 (113筆)
    (25.091, 25.199, 121.677, 121.803, "Keelung"),          # 基隆市 (39筆)
    (24.779, 24.852, 120.921, 121.018, "Hsinchu"),          # 新竹市 (24筆)
    (24.679, 24.832, 120.893, 121.082, "HsinchuCounty"),    # 新竹縣 (39筆)
    (24.683, 24.870, 120.620, 120.982, "MiaoliCounty"),     # 苗栗縣 (96筆)
    (24.820, 25.076, 121.139, 121.474, "Taoyuan"),          # 桃園市
    (23.958, 24.389, 120.530, 121.100, "Taichung"),         # 台中市
    (23.750, 24.150, 120.309, 120.745, "ChanghuaCounty"),   # 彰化縣 (176筆)
    (23.308, 23.870, 120.440, 121.070, "NantouCounty"),     # 南投縣 (23筆)
    (23.501, 23.830, 120.090, 120.722, "YunlinCounty"),     # 雲林縣 (4筆)
    (23.443, 23.521, 120.409, 120.520, "Chiayi"),           # 嘉義市 (30筆)
    (23.100, 23.580, 120.180, 120.795, "ChiayiCounty"),     # 嘉義縣 (51筆)
    (22.820, 23.450, 120.020, 120.763, "Tainan"),           # 台南市
    (22.447, 23.140, 120.160, 120.780, "Kaohsiung"),        # 高雄市 (262筆)
    (21.901, 22.809, 120.393, 120.904, "PingtungCounty"),   # 屏東縣 (20筆)
    (23.000, 24.500, 121.280, 121.720, "HualienCounty"),    # 花蓮縣 (81筆)
    (22.200, 23.500, 120.851, 121.554, "TaitungCounty"),    # 台東縣 (4筆)
    (23.200, 23.800, 119.300, 119.750, "PenghuCounty"),     # 澎湖縣
    (24.300, 25.050, 121.500, 122.000, "YilanCounty"),       # 宜蘭縣
    (24.045, 25.176, 121.120, 122.075, "NewTaipei"),        # 新北市（TDX 暫無資料）
]


# 各縣市行政中心座標（用於城市框重疊時的決勝）
_TW_CITY_CENTERS = {
    "Taipei":         (25.047, 121.517),
    "Keelung":        (25.129, 121.740),
    "NewTaipei":      (25.012, 121.465),
    "Taoyuan":        (24.993, 121.301),
    "Hsinchu":        (24.804, 120.971),
    "HsinchuCounty":  (24.839, 121.017),
    "MiaoliCounty":   (24.560, 120.820),
    "Taichung":       (24.147, 120.674),
    "ChanghuaCounty": (24.052, 120.516),
    "NantouCounty":   (23.960, 120.972),
    "YunlinCounty":   (23.707, 120.431),
    "Chiayi":         (23.480, 120.449),
    "ChiayiCounty":   (23.459, 120.432),
    "Tainan":         (22.999, 120.211),
    "Kaohsiung":      (22.627, 120.301),
    "PingtungCounty": (22.674, 120.490),
    "YilanCounty":    (24.700, 121.738),
    "HualienCounty":  (23.991, 121.611),
    "TaitungCounty":  (22.757, 121.144),
    "PenghuCounty":   (23.571, 119.579),
}

def _coords_to_tdx_city(lat: float, lon: float) -> str:
    """座標 → TDX City 路徑名稱
    多個框重疊時，用「最近城市行政中心」決勝，而非最小面積框
    （台灣縣市框大量重疊，最小面積法會把台南誤判成高雄等）
    """
    candidates = []
    for lat_min, lat_max, lon_min, lon_max, city in _TW_CITY_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            candidates.append(city)

    if not candidates:
        return "Taipei"
    if len(candidates) == 1:
        return candidates[0]

    # 多個候選：找行政中心距離最近的城市
    best, best_d = candidates[0], float("inf")
    for city in candidates:
        cx, cy = _TW_CITY_CENTERS.get(city, (25.047, 121.517))
        d = (lat - cx) ** 2 + (lon - cy) ** 2
        if d < best_d:
            best_d = d
            best = city
    return best


# 城市停車資料快取（避免同一次請求重複拉 API）
_tdx_lots_cache:   dict = {}   # city -> (timestamp, [lots])
_tdx_avail_cache:  dict = {}   # city -> (timestamp, {pid: avail})
_TDX_CACHE_TTL = 90            # 快取 90 秒（即時性夠用）

# 停車結果快取（座標格子，約 2km×2km，共用結果避免重複計算）
_parking_result_cache: dict = {}   # "lat2_lon2" -> (timestamp, messages)
_PARKING_RESULT_TTL = 180          # 3 分鐘

def _peek_parking_cache(lat: float, lon: float):
    """快速查停車結果快取（不觸發任何 API）
    命中回傳 messages list；未命中回傳 None"""
    import time as _t
    ck  = _parking_cache_key(lat, lon)
    now = _t.time()
    r   = _redis_get(f"parking_{ck}")
    if r is not None:
        return r
    if ck in _parking_result_cache:
        ts, msgs = _parking_result_cache[ck]
        if now - ts < _PARKING_RESULT_TTL:
            return msgs
    return None

def _parking_cache_key(lat: float, lon: float) -> str:
    """四捨五入到 0.02 度（約 2km）作為快取 key"""
    return f"{round(lat / 0.02) * 0.02:.3f}_{round(lon / 0.02) * 0.02:.3f}"


def _get_tdx_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """TDX 路外停車場（城市路徑）+ 即時車位，type='lot'；城市資料快取 90 秒
    兩個 API 並行呼叫，避免超過 Vercel 10s 限制"""
    import time as _time, threading
    token = _get_tdx_token()
    if not token:
        return []

    city = _coords_to_tdx_city(lat, lon)
    now  = _time.time()
    print(f"[TDX] 查詢城市: {city}，座標: ({lat}, {lon})")

    # ── Redis 持久快取（跨 instance）優先，再 in-memory，最後才打 TDX ──
    lots     = _redis_get(f"tdx_lots_{city}")
    avail_map = _redis_get(f"tdx_avail_{city}")

    if lots is not None:
        print(f"[TDX] lots Redis命中 ({len(lots)} 筆)")
    elif city in _tdx_lots_cache and now - _tdx_lots_cache[city][0] < _TDX_CACHE_TTL:
        lots = _tdx_lots_cache[city][1]
        print(f"[TDX] lots 記憶體命中 ({len(lots)} 筆)")

    if avail_map is not None:
        print(f"[TDX] avail Redis命中 ({len(avail_map)} 筆)")
    elif city in _tdx_avail_cache and now - _tdx_avail_cache[city][0] < 60:
        avail_map = _tdx_avail_cache[city][1]
        print(f"[TDX] avail 記憶體命中")

    lots_buf:  list = []
    avail_buf: list = []

    def _fetch_lots():
        try:
            data = _tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=4)
            lots_buf.extend(data)
        except Exception as e:
            print(f"[TDX] lots 失敗: {e}")

    def _fetch_avail():
        try:
            data = _tdx_get(f"Parking/OffStreet/ParkingAvailability/City/{city}?$format=JSON", token, timeout=4)
            avail_buf.extend(data)
        except Exception as e:
            print(f"[TDX] avail 失敗: {e}")

    threads = []
    if lots is None:
        t1 = threading.Thread(target=_fetch_lots, daemon=True)
        threads.append(t1); t1.start()
    if avail_map is None:
        t2 = threading.Thread(target=_fetch_avail, daemon=True)
        threads.append(t2); t2.start()

    for t in threads:
        t.join(timeout=4)

    if lots is None:
        lots = lots_buf
        _tdx_lots_cache[city] = (now, lots)
        if lots:  # 只有非空才存 Redis，避免暫時失敗把空結果快取 24h
            _redis_set(f"tdx_lots_{city}", lots, ttl=86400)
    if avail_map is None:
        avail_map = {a.get("CarParkID", ""): a for a in avail_buf}
        _tdx_avail_cache[city] = (now, avail_map)
        if avail_map:  # 空結果不快取
            _redis_set(f"tdx_avail_{city}", avail_map, ttl=180)

    print(f"[TDX] CarParks: {len(lots)}, Availabilities: {len(avail_map)}")

    result = []
    for lot in lots:
        pos   = lot.get("CarParkPosition") or lot.get("ParkingPosition") or {}
        p_lat = pos.get("PositionLat") or lot.get("PositionLat")
        p_lon = pos.get("PositionLon") or lot.get("PositionLon")
        if not p_lat or not p_lon:
            continue
        dist = _haversine(lat, lon, float(p_lat), float(p_lon))
        if dist > radius:
            continue

        pid = lot.get("CarParkID", "")
        av  = avail_map.get(pid, {})

        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        name      = _zh(lot.get("CarParkName") or lot.get("ParkingName") or {}) or "停車場"
        addr      = _zh(lot.get("Address") or {})
        fare      = str(_zh(lot.get("FareDescription") or lot.get("PricingNote") or {}))[:30]
        total     = int(av.get("TotalSpaces") or lot.get("TotalCapacity") or 0)
        available = int(av.get("AvailableSpaces", -1))

        result.append({
            "name": name, "addr": addr, "fare": fare,
            "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
            "total": total, "available": available, "type": "lot",
        })

    result.sort(key=lambda x: x["dist"])
    return result


def _twd97tm2_to_wgs84(x: float, y: float):
    """TWD97 TM2 Zone 121 投影座標（公尺）→ WGS84 lat/lon
    台灣範圍內誤差 < 20m，停車場定位夠用"""
    import math
    lat = y / 110540.0
    lat_rad = math.radians(lat)
    lon = 121.0 + (x - 250000.0) / (111320.0 * math.cos(lat_rad))
    return lat, lon


_NTPC_LOT_STATIC: dict = {}  # ID -> {name, addr, fare, total, lat, lon}

def _get_ntpc_lot_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新北市路外公有停車場（靜態資料 + 即時車位合併）
    靜態 dataset: B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68（含 TWD97 座標）
    即時 dataset: e09b35a5-a738-48cc-b0f5-570b67ad9c78（每 3 分鐘更新）
    """
    global _NTPC_LOT_STATIC

    # ── 1. 靜態資料（記憶體 > Redis 24h > API）──
    static_data = _NTPC_LOT_STATIC or _redis_get("ntpc_lot_static") or {}
    if not static_data:
        try:
            req = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68/json?size=500",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                lots_raw = json.loads(r.read())
            for lot in lots_raw:
                lid = lot.get("ID", "")
                try:
                    tw_x = float(lot.get("TW97X", 0) or 0)
                    tw_y = float(lot.get("TW97Y", 0) or 0)
                    if not lid or tw_x < 100000:
                        continue
                    p_lat, p_lon = _twd97tm2_to_wgs84(tw_x, tw_y)
                    static_data[lid] = {
                        "name": lot.get("NAME", "停車場"),
                        "addr": lot.get("ADDRESS", ""),
                        "fare": str(lot.get("PAYEX", ""))[:30],
                        "total": int(lot.get("TOTALCAR", 0) or 0),
                        "lat": p_lat, "lon": p_lon,
                    }
                except Exception:
                    pass
            _NTPC_LOT_STATIC = static_data
            if static_data:  # 空結果不快取
                _redis_set("ntpc_lot_static", static_data, ttl=86400)
            print(f"[NTPC lot] 靜態資料 {len(static_data)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 靜態資料失敗: {e}")
            return []
    else:
        _NTPC_LOT_STATIC = static_data  # 同步記憶體
        print(f"[NTPC lot] 靜態快取命中 {len(static_data)} 筆")

    # ── 2. 即時車位（Redis 3min > API）──
    avail_map: dict = _redis_get("ntpc_lot_avail") or {}
    if not avail_map:
        try:
            req2 = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "e09b35a5-a738-48cc-b0f5-570b67ad9c78/json",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req2, timeout=5) as r:
                avail_list = json.loads(r.read())
            for av in avail_list:
                lid = av.get("ID", "")
                if lid:
                    try:
                        v = int(av.get("AVAILABLECAR", -1))
                        avail_map[lid] = max(v, -1)  # -9 表示未提供，統一設 -1
                    except (ValueError, TypeError):
                        avail_map[lid] = -1
            if avail_map:  # 空結果不快取
                _redis_set("ntpc_lot_avail", avail_map, ttl=180)
            print(f"[NTPC lot] 即時車位 {len(avail_map)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 即時車位失敗: {e}")

    # ── 3. 過濾半徑內的停車場 ──
    result = []
    for lid, info in static_data.items():
        d = _haversine(lat, lon, info["lat"], info["lon"])
        if d > radius:
            continue
        available = avail_map.get(lid, -1)
        result.append({
            "name":      info["name"],
            "addr":      info["addr"],
            "fare":      info["fare"],
            "lat":       info["lat"], "lon": info["lon"],
            "dist":      d,
            "total":     info["total"],
            "available": available,
            "type":      "lot",
        })
    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC lot] 半徑 {radius}m 內 {len(result)} 個停車場")
    return result


def _get_ntpc_street_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新北市路邊停車格即時狀態（NTPC open data）
    API 不支援空間過濾，採 5 頁並行下載後本地過濾，按路名分組回傳
    dataset: 54A507C4-C038-41B5-BF60-BBECB9D052C6
    cellstatus: Y=空位, N=有車
    """
    import math, threading

    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(lat)))
    lat_min, lat_max = lat - lat_delta, lat + lat_delta
    lon_min, lon_max = lon - lon_delta, lon + lon_delta

    DATASET_ID = "54A507C4-C038-41B5-BF60-BBECB9D052C6"
    PAGE_SIZE  = 1000
    MAX_PAGES  = 5
    pages_data = [[] for _ in range(MAX_PAGES)]

    def fetch_page(i):
        url = (f"https://data.ntpc.gov.tw/api/datasets/{DATASET_ID}/json"
               f"?size={PAGE_SIZE}&page={i}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                pages_data[i] = json.loads(r.read()) or []
        except Exception as e:
            print(f"[NTPC] 第{i}頁失敗: {e}")

    threads = [threading.Thread(target=fetch_page, args=(i,)) for i in range(MAX_PAGES)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=4)

    # 按路名分組
    from collections import defaultdict
    road_map: dict = defaultdict(lambda: {"spots": [], "lat": 0.0, "lon": 0.0, "fare": ""})

    for page_records in pages_data:
        for rec in page_records:
            try:
                p_lat = float(rec.get("latitude", 0))
                p_lon = float(rec.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if not (lat_min <= p_lat <= lat_max and lon_min <= p_lon <= lon_max):
                continue
            dist = _haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue

            road = rec.get("roadname") or "路邊停車格"
            status = rec.get("cellstatus", "")
            entry = road_map[road]
            entry["spots"].append({"status": status, "dist": dist, "lat": p_lat, "lon": p_lon})
            if not entry["lat"] or dist < _haversine(lat, lon, entry["lat"], entry["lon"]):
                entry["lat"] = p_lat
                entry["lon"] = p_lon
            if not entry["fare"] and rec.get("paycash"):
                entry["fare"] = rec["paycash"]

    if not road_map:
        print("[NTPC] 範圍內無路邊格資料（可能在這5頁內）")
        return []

    result = []
    for road, info in road_map.items():
        spots   = info["spots"]
        total   = len(spots)
        avail   = sum(1 for s in spots if s["status"] == "Y")
        nearest = min(spots, key=lambda s: s["dist"])
        result.append({
            "name":      road,
            "addr":      road,
            "fare":      info["fare"],
            "lat":       nearest["lat"],
            "lon":       nearest["lon"],
            "dist":      nearest["dist"],
            "total":     total,
            "available": avail,
            "type":      "street",
        })

    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC] 找到 {len(result)} 條路段，共 {sum(r['total'] for r in result)} 格")
    return result


def _get_tainan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """台南市公有停車場即時車位（parkweb.tainan.gov.tw）"""
    try:
        url = "https://parkweb.tainan.gov.tw/api/parking.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read()
            data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            # 可能包在 data key 內
            for k, v in data.items():
                if isinstance(v, list):
                    data = v
                    break
        result = []
        for lot in (data if isinstance(data, list) else []):
            lnglat = lot.get("lnglat", "")
            if not lnglat:
                continue
            try:
                # 格式: "lat,lng"（中文逗號或英文逗號）
                parts = lnglat.replace("，", ",").split(",")
                p_lat, p_lon = float(parts[0].strip()), float(parts[1].strip())
            except Exception:
                continue
            dist = _haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue
            name      = lot.get("name", "停車場")
            addr      = lot.get("address", "")
            fare      = str(lot.get("chargeFee") or lot.get("chargeTime") or "")[:30]
            total     = int(lot.get("car_total") or 0)
            available = int(lot.get("car") if lot.get("car") is not None else -1)
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": p_lat, "lon": p_lon, "dist": dist,
                "total": total, "available": available,
                "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Tainan] 找到 {len(result)} 個停車場（半徑 {radius}m）")
        return result
    except Exception as e:
        print(f"[Tainan] API 失敗: {e}")
        return []


def _get_yilan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """宜蘭縣停車場即時空位（opendataap2.e-land.gov.tw + TDX 座標）
    e-land API 有即時剩餘數但無座標；TDX YilanCounty 有座標但無即時空位。
    策略：TDX 取座標/名稱，e-land 補即時空位（按停車場名稱 fuzzy match）
    """
    try:
        # ── 1. TDX 取宜蘭縣停車場（有座標）──
        token = _get_tdx_token()
        tdx_lots = _redis_get("tdx_lots_YilanCounty")
        if tdx_lots is None:
            try:
                tdx_lots = _tdx_get("Parking/OffStreet/CarPark/City/YilanCounty?$format=JSON", token, timeout=5)
                if tdx_lots:  # 空結果不快取，避免 24h 鎖死
                    _redis_set("tdx_lots_YilanCounty", tdx_lots, ttl=86400)
            except Exception as e:
                print(f"[Yilan] TDX lots 失敗: {e}")
                tdx_lots = []

        # ── 2. e-land 即時空位（有剩餘數但無座標）──
        eland_map: dict = {}  # 名稱 → 剩餘數
        try:
            cached_avail = _redis_get("yilan_avail")
            if cached_avail:
                eland_map = cached_avail
            else:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                url = ("https://opendataap2.e-land.gov.tw/./resource/files/"
                       "2023-02-12/62f4d78b604ba16b8cc1e856dd28d2c3.json")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    raw_data = json.loads(r.read())
                for item in (raw_data if isinstance(raw_data, list) else []):
                    name = item.get("名稱", "")
                    try:
                        avail = int(item.get("小車位剩餘數") or -1)
                    except Exception:
                        avail = -1
                    try:
                        total = int(item.get("小車位總數") or 0)
                    except Exception:
                        total = 0
                    if name:
                        eland_map[name] = {"available": avail, "total": total}
                if eland_map:  # 空結果不快取
                    _redis_set("yilan_avail", eland_map, ttl=180)
                print(f"[Yilan] e-land 即時空位 {len(eland_map)} 筆")
        except Exception as e:
            print(f"[Yilan] e-land avail 失敗: {e}")

        # ── 3. 合併：TDX 座標 + e-land 空位 ──
        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        result = []
        for lot in (tdx_lots or []):
            pos   = lot.get("CarParkPosition") or {}
            p_lat = pos.get("PositionLat")
            p_lon = pos.get("PositionLon")
            if not p_lat or not p_lon:
                continue
            dist = _haversine(lat, lon, float(p_lat), float(p_lon))
            if dist > radius:
                continue
            name = _zh(lot.get("CarParkName") or {}) or "停車場"
            addr = _zh(lot.get("Address") or {})
            fare = str(_zh(lot.get("FareDescription") or {}))[:30]
            # fuzzy match：找 e-land 裡名稱包含 TDX 名稱的項目
            av_data = eland_map.get(name, {})
            if not av_data:
                for ename, edata in eland_map.items():
                    if name[:4] in ename or ename[:4] in name:
                        av_data = edata
                        break
            available = av_data.get("available", -1)
            total     = av_data.get("total", int(lot.get("TotalCapacity") or 0))
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
                "total": total, "available": available, "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Yilan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Yilan] 失敗: {e}")
        return []


def _get_hsinchu_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新竹市路外停車場即時車位（hispark.hccg.gov.tw，即時更新）
    欄位：PARKINGNAME, ADDRESS, WEEKDAYS(費率), FREEQUANTITY(剩餘), TOTALQUANTITY(總),
          LONGITUDE, LATITUDE, UPDATETIME
    """
    try:
        cached = _redis_get("hsinchu_lots")
        if cached:
            data = cached
        else:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            req = urllib.request.Request(
                "https://hispark.hccg.gov.tw/OpenData/GetParkInfo",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                raw = r.read()
            data = json.loads(raw)
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        data = v
                        break
            if data:  # 空結果不快取
                _redis_set("hsinchu_lots", data, ttl=180)
            print(f"[Hsinchu] API 取得 {len(data)} 筆")

        result = []
        for lot in (data if isinstance(data, list) else []):
            try:
                p_lat = float(lot.get("LATITUDE") or 0)
                p_lon = float(lot.get("LONGITUDE") or 0)
                if not p_lat or not p_lon:
                    continue
                dist = _haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("FREEQUANTITY") or -1)
                total     = int(lot.get("TOTALQUANTITY") or 0)
                fare      = str(lot.get("WEEKDAYS") or "")
                # 費率欄位可能很長，只取第一行
                fare = fare.split("\n")[0].split("\r")[0][:30]
                result.append({
                    "name":      lot.get("PARKINGNAME", "停車場"),
                    "addr":      lot.get("ADDRESS", ""),
                    "fare":      fare,
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Hsinchu] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Hsinchu] API 失敗: {e}")
        return []


def _get_taoyuan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """桃園市路外停車場即時車位（桃園開放資料，每分鐘更新）
    API: opendata.tycg.gov.tw  wgsX=緯度, wgsY=經度（命名相反，請注意）
    """
    try:
        # Redis 2分鐘快取（此API每分鐘更新，2分鐘夠用）
        cached = _redis_get("taoyuan_lots")
        if cached:
            data = cached
        else:
            import re as _re
            req = urllib.request.Request(
                "https://opendata.tycg.gov.tw/api/dataset/"
                "f4cc0b12-86ac-40f9-8745-885bddc18f79/resource/"
                "0381e141-f7ee-450e-99da-2240208d1773/download",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                raw = r.read().decode("utf-8", "ignore")
            # 防止 Extra data（有時回傳非標準 JSON）
            start, end = raw.find("["), raw.rfind("]")
            data = json.loads(raw[start:end+1]) if start >= 0 else []
            if data:  # 空結果不快取
                _redis_set("taoyuan_lots", data, ttl=120)
            print(f"[Taoyuan] API 取得 {len(data)} 筆")

        result = []
        for lot in data:
            try:
                # API 命名相反：wgsX=緯度, wgsY=經度
                p_lat = float(lot.get("wgsX", 0) or 0)
                p_lon = float(lot.get("wgsY", 0) or 0)
                if not p_lat or not p_lon:
                    continue
                dist = _haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("surplusSpace", -1) or -1)
                total     = int(lot.get("totalSpace", 0)    or 0)
                result.append({
                    "name":      lot.get("parkName", "停車場"),
                    "addr":      lot.get("address", ""),
                    "fare":      str(lot.get("payGuide", ""))[:30],
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Taoyuan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Taoyuan] API 失敗: {e}")
        return []


def _get_nearby_parking(lat: float, lon: float, radius: int = 1500) -> dict:
    """多來源停車資料整合，回傳 {'street': [...], 'lot': [...], 'city': str}"""
    import threading

    city = _coords_to_tdx_city(lat, lon)
    street_result: list = []
    lot_result:    list = []

    def _run_parallel(fn1, fn2, timeout=5):
        """並行執行兩個函式，各自 timeout 秒，超時只記 log 不崩潰"""
        t1 = threading.Thread(target=fn1, daemon=True)
        t2 = threading.Thread(target=fn2, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=timeout); t2.join(timeout=timeout)
        if t1.is_alive(): print(f"[parking] thread1 超時仍在執行")
        if t2.is_alive(): print(f"[parking] thread2 超時仍在執行")

    if city == "YilanCounty":
        lot_result = _get_yilan_parking(lat, lon, radius)
    elif city == "NewTaipei":
        def fetch_street(): street_result.extend(_get_ntpc_street_parking(lat, lon, radius))
        def fetch_lot():
            try:
                lot_result.extend(_get_ntpc_lot_parking(lat, lon, radius))
            except Exception as e:
                print(f"[NTPC lot] thread 異常: {e}")
        _run_parallel(fetch_street, fetch_lot)
    elif city == "Taoyuan":
        def fetch_tycg(): lot_result.extend(_get_taoyuan_parking(lat, lon, radius))
        def fetch_tdx_ty():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_tycg, fetch_tdx_ty)
    elif city == "Hsinchu":
        def fetch_hsinchu(): lot_result.extend(_get_hsinchu_parking(lat, lon, radius))
        def fetch_tdx_hc():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_hsinchu, fetch_tdx_hc)
    elif city == "Tainan":
        def fetch_tainan(): lot_result.extend(_get_tainan_parking(lat, lon, radius))
        def fetch_tdx():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_tainan, fetch_tdx)
    else:
        lot_result = _get_tdx_parking(lat, lon, radius)

    return {
        "street": street_result[:8] if isinstance(street_result, list) else [],
        "lot":    lot_result[:6]    if isinstance(lot_result,    list) else [],
        "city":   city or "Unknown",
    }


def build_parking_flex(lat: float, lon: float) -> list:
    """位置訊息 → 附近停車 Flex Carousel
    路邊格（路名分組）優先，再接停車場，最後加生活推薦卡
    結果快取 3 分鐘（同 2km 格子內共用）
    """
    import time as _time
    if not TDX_CLIENT_ID:
        return [{"type": "flex", "altText": "找車位",
                 "contents": {
                     "type": "bubble",
                     "header": {"type": "box", "layout": "vertical",
                                "backgroundColor": "#C62828", "contents": [
                                    {"type": "text", "text": "🅿️ 找車位",
                                     "color": "#FFFFFF", "weight": "bold"}]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text",
                          "text": "找車位功能尚未設定 TDX API\n請管理員設定 TDX_CLIENT_ID / TDX_CLIENT_SECRET",
                          "wrap": True, "size": "sm", "color": "#555555"}]},
                 }}]

    # ── 結果快取（座標格子 2km，TTL 3 分鐘）
    ck  = _parking_cache_key(lat, lon)
    now = _time.time()
    # Redis 持久快取優先
    redis_result = _redis_get(f"parking_{ck}")
    if redis_result is not None:
        print(f"[parking] Redis結果快取命中 {ck}")
        return redis_result
    # in-memory 次之
    if ck in _parking_result_cache:
        ts, cached_msgs = _parking_result_cache[ck]
        if now - ts < _PARKING_RESULT_TTL:
            print(f"[parking] 記憶體快取命中 key={ck}")
            return cached_msgs

    # 查一次 2km，快取後快速過濾
    radius_used = 2000
    data = _get_nearby_parking(lat, lon, radius=2000)
    city   = data["city"]
    street = data["street"]
    lots   = data["lot"]
    all_parks = street + lots

    if not all_parks:
        # 官方資料無結果 → 雙卡片：公立 fallback + 私人停車場
        gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
        city_park_url = f"https://www.cityparking.com.tw/"
        times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
        ipark_url     = f"https://www.iparking.com.tw/"
        liff_url      = "https://liff.line.me/2009774625-KwBrQAbV?action=parking"

        bubble_public = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🗺️", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "附近停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "Google Maps 整合查詢",
                                 "color": "#8892B0", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#26A69A", "height": "sm",
                          "action": {"type": "uri", "label": "🗺️ 查所有停車場（含私人）", "uri": gmap_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ iParking 即時空位", "uri": ipark_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "📍 換個位置重新查", "uri": liff_url}},
                         {"type": "text",
                          "text": "💡 此區公立開放資料暫無，已切換至地圖搜尋",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        bubble_private = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#37474F", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "私人停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "城市車旅 × Times",
                                 "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                          "action": {"type": "uri", "label": "🏙️ 城市車旅 找車位",
                                     "uri": city_park_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                     "uri": times_url}},
                         {"type": "text",
                          "text": "💡 私人車場通常不提供即時空位，建議先電話確認",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        return [{"type": "flex", "altText": "🅿️ 幫你找附近停車場",
                 "contents": {"type": "carousel",
                              "contents": [bubble_public, bubble_private]}}]

    radius_label = {1500: "1.5公里", 3000: "3公里", 5000: "5公里"}.get(radius_used, f"{radius_used}m")
    source_note = (
        "資料來源：新北市開放資料 + TDX｜實際以現場為準" if city == "NewTaipei" else
        "資料來源：新竹市 HisPark 即時資料｜實際以現場為準" if city == "Hsinchu" else
        "資料來源：台南市停車資訊 + TDX｜實際以現場為準" if city == "Tainan" else
        "資料來源：宜蘭縣開放資料 + TDX｜實際以現場為準" if city == "YilanCounty" else
        f"資料來源：交通部 TDX（{radius_label}內）｜實際以現場為準"
    )

    def _make_bubble(p: dict) -> dict:
        is_street  = p["type"] == "street"
        av, total  = p["available"], p["total"]
        hdr_color  = "#1B5E20" if is_street else "#1565C0"
        type_label = "🛣️ 路邊停車" if is_street else "🅿️ 停車場"

        if av < 0:
            av_text, av_color = "查無資料", "#888888"
        elif av == 0:
            av_text, av_color = "已滿 🔴", "#C62828"
        elif is_street:
            pct = av / total if total else 1
            av_text = f"{av}/{total} 格"
            av_color = "#E65100" if pct < 0.3 else "#2E7D32"
            av_text += " 🟡" if pct < 0.3 else " 🟢"
        else:
            pct = av / total if total > 0 else 1
            av_text = f"{av} 位"
            av_color = "#E65100" if pct < 0.2 else "#2E7D32"
            av_text += " 🟡" if pct < 0.2 else " 🟢"

        dist_text = f"{p['dist']} m" if p["dist"] < 1000 else f"{p['dist']/1000:.1f} km"
        maps_url  = f"https://www.google.com/maps/dir/?api=1&destination={p['lat']},{p['lon']}"

        rows = [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "空位", "size": "xs",
                 "color": "#888888", "flex": 2, "gravity": "center"},
                {"type": "text", "text": av_text, "size": "lg",
                 "weight": "bold", "color": av_color, "flex": 3, "align": "end"},
            ]},
            {"type": "separator", "margin": "sm"},
            {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                {"type": "text", "text": "📍 距離", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": dist_text, "size": "xs", "flex": 3, "align": "end"},
            ]},
        ]
        if p.get("fare"):
            rows.append({"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "💰 費率", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": p["fare"][:25], "size": "xs",
                 "flex": 3, "align": "end", "wrap": True, "maxLines": 1},
            ]})
        rows.append({"type": "text", "text": source_note,
                     "size": "xxs", "color": "#AAAAAA", "margin": "sm", "wrap": True})

        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": hdr_color, "paddingAll": "md",
                "contents": [
                    {"type": "text", "text": type_label,
                     "color": "#FFFFFFBB", "size": "xxs"},
                    {"type": "text", "text": p["name"], "color": "#FFFFFF",
                     "size": "sm", "weight": "bold", "wrap": True, "maxLines": 2},
                ]
            },
            "body": {"type": "box", "layout": "vertical",
                     "spacing": "xs", "paddingAll": "md", "contents": rows},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "sm",
                       "contents": [
                           {"type": "button", "style": "primary", "color": hdr_color,
                            "height": "sm",
                            "action": {"type": "uri", "label": "🗺️ 導航前往", "uri": maps_url}},
                       ]}
        }

    bubbles = [_make_bubble(p) for p in all_parks]

    # ── 統計摘要文字
    street_avail = sum(p["available"] for p in street if p["available"] >= 0)
    lot_avail    = sum(p["available"] for p in lots   if p["available"] >= 0)
    summary = []
    if street: summary.append(f"路邊 {street_avail} 格可停")
    if lots:   summary.append(f"停車場 {lot_avail} 位可停")
    summary_text = "、".join(summary) if summary else "附近停車資訊如上"

    # ── 私人停車場補充卡（城市車旅/Times/iParking）
    # 公立 API 只涵蓋政府管理的停車場，私人業者（CITY PARKING、Times、台灣聯通等）
    # 不提供 Open Data，永遠需要補充這張卡讓使用者自行查詢
    _city_park_url = "https://www.cityparking.com.tw/"
    _times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
    _ipark_url     = "https://www.iparking.com.tw/"
    _gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
    bubble_private = {
        "type": "bubble", "size": "kilo",
        "header": {"type": "box", "layout": "horizontal",
                   "backgroundColor": "#37474F", "paddingAll": "14px",
                   "contents": [
                       {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                       {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                        "contents": [
                            {"type": "text", "text": "私人停車場",
                             "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                            {"type": "text", "text": "城市車旅 × Times × Google Maps",
                             "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                        ]},
                   ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                      "action": {"type": "uri", "label": "🏙️ 城市車旅 CITY PARKING",
                                 "uri": _city_park_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                 "uri": _times_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🗺️ Google Maps 查所有停車場",
                                 "uri": _gmap_url}},
                     {"type": "text",
                      "text": "💡 私人車場空位需至各平台確認，建議先電話洽詢",
                      "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                 ]},
    }
    bubbles.append(bubble_private)

    # ── 最後一張：融入主選單風格的生活助理推薦卡
    def _tile(icon, label, action_text, bg, fg):
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": bg, "cornerRadius": "12px",
            "paddingAll": "10px", "spacing": "xs",
            "action": {"type": "message", "label": label, "text": action_text},
            "contents": [
                {"type": "text", "text": icon, "size": "xl", "align": "center"},
                {"type": "text", "text": label, "size": "xxs", "weight": "bold",
                 "color": fg, "align": "center", "margin": "xs", "wrap": True},
            ]
        }

    bubbles.append({
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1A1F3A",
            "paddingTop": "16px", "paddingBottom": "12px",
            "paddingStart": "16px", "paddingEnd": "16px",
            "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     {"type": "text", "text": "✨", "size": "xl",
                      "flex": 0, "gravity": "center"},
                     {"type": "box", "layout": "vertical", "flex": 1,
                      "contents": [
                          {"type": "text", "text": "已幫你找到車位 🅿️",
                           "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                          {"type": "text", "text": summary_text,
                           "color": "#8892B0", "size": "xxs", "margin": "xs",
                           "wrap": True},
                      ]}
                 ]},
                {"type": "text",
                 "text": "順便幫你安排接下來的行程 👇",
                 "color": "#8892B0", "size": "xxs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical",
            "paddingAll": "12px", "spacing": "sm",
            "contents": [
                # 第一排磚塊：吃什麼 + 週末活動
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     _tile("🍜", "附近吃什麼", "今天吃什麼",
                           "#FF6B3520", "#FF9A7A"),
                     _tile("🎨", "週末活動", "周末活動",
                           "#6A1B9A20", "#CE93D8"),
                 ]},
                # 第二排磚塊：健康提醒 + Google Maps
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     _tile("💪", "健康小幫手", "健康小幫手",
                           "#43A04720", "#A5D6A7"),
                     {"type": "box", "layout": "vertical", "flex": 1,
                      "backgroundColor": "#1565C020", "cornerRadius": "12px",
                      "paddingAll": "10px", "spacing": "xs",
                      "action": {"type": "uri", "label": "Google Maps",
                                 "uri": f"https://www.google.com/maps/search/%E9%99%84%E8%BF%91/@{lat},{lon},16z"},
                      "contents": [
                          {"type": "text", "text": "🗺️", "size": "xl", "align": "center"},
                          {"type": "text", "text": "搜尋附近", "size": "xxs",
                           "weight": "bold", "color": "#90CAF9",
                           "align": "center", "margin": "xs"},
                      ]},
                 ]},
                # 小提醒
                {"type": "text",
                 "text": "💡 開車超過 2 小時記得休息，注意安全！",
                 "size": "xxs", "color": "#8892B0", "margin": "sm", "wrap": True},
            ]
        }
    })

    alt = f"已找到 {len(street)} 條路邊路段、{len(lots)} 個停車場"
    result_msgs = [{"type": "flex", "altText": alt,
                    "contents": {"type": "carousel", "contents": bubbles}}]

    # 存入快取
    _parking_result_cache[ck] = (now, result_msgs)
    _redis_set(f"parking_{ck}", result_msgs, ttl=180)  # 3 分鐘
    return result_msgs


def _build_stats_html() -> str:
    """查詢 Supabase 使用統計，回傳 HTML 儀表板"""
    rows_feature, rows_city, rows_daily, total_users = [], [], [], 0
    rows_fail_feat = []
    total_fails = 0
    error_msg = ""
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            }
            def _sb(query: str) -> list:
                req = urllib.request.Request(
                    f"{SUPABASE_URL}/rest/v1/linebot_usage_logs?{query}",
                    headers=headers
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    return json.loads(r.read())

            # 各功能使用次數（只取成功）
            all_rows = _sb("select=feature,city,uid_hash,created_at,is_success&limit=5000&order=id.desc")

            from collections import Counter
            import datetime as _dt

            succ_rows = [r for r in all_rows if r.get("is_success", True)]
            fail_rows = [r for r in all_rows if not r.get("is_success", True)]
            total_fails = len(fail_rows)

            feat_cnt  = Counter(r["feature"] for r in succ_rows)
            city_cnt  = Counter(r["city"] for r in succ_rows if r.get("city"))
            total_users = len({r["uid_hash"] for r in all_rows})

            rows_feature = sorted(feat_cnt.items(), key=lambda x: -x[1])
            rows_city    = sorted(city_cnt.items(), key=lambda x: -x[1])[:10]

            # 失敗功能排行
            fail_feat_cnt = Counter(r["feature"] for r in fail_rows)
            rows_fail_feat = sorted(fail_feat_cnt.items(), key=lambda x: -x[1])[:8]

            # 最近 14 天每日次數
            day_cnt: dict = {}
            for r in all_rows:
                ts = r.get("created_at", "")
                if ts:
                    day = ts[:10]
                    day_cnt[day] = day_cnt.get(day, 0) + 1
            today = _dt.date.today()
            rows_daily = []
            for i in range(13, -1, -1):
                d = str(today - _dt.timedelta(days=i))
                rows_daily.append((d, day_cnt.get(d, 0)))
        else:
            error_msg = "Supabase 環境變數未設定"
    except Exception as e:
        error_msg = str(e)

    # ── 功能名稱中文化 ──
    feat_labels = {
        "parking":     "🅿️ 找車位",
        "food":        "🍜 今天吃什麼",
        "activity":    "🎨 近期活動",
        "weather":     "🌤️ 天氣穿搭",
        "health":      "💪 健康小幫手",
        "money":       "💰 金錢小幫手",
        "3c":          "📱 3C 推薦",
        "credit_card": "💳 信用卡",
        "fraud":       "🛡️ 防詐騙",
        "legal":       "⚖️ 法律常識",
        "tools":       "🧰 工具箱",
        "follow":      "➕ 加好友",
        "other":       "💬 自由輸入",
    }

    total_uses = sum(v for _, v in rows_feature)
    fail_rate_pct = round(total_fails * 100 / max(1, total_uses + total_fails), 1)
    fail_color = "#ef5350" if fail_rate_pct > 5 else ("#ffb300" if fail_rate_pct > 1 else "#66bb6a")

    feat_rows_html = "".join(
        f'<tr><td>{feat_labels.get(k, k)}</td><td>{v}</td>'
        f'<td><div class="bar" style="width:{min(100,v*100//max(1,rows_feature[0][1]))}%"></div></td></tr>'
        for k, v in rows_feature
    )
    city_rows_html = "".join(
        f'<tr><td>{k}</td><td>{v}</td>'
        f'<td><div class="bar" style="width:{min(100,v*100//max(1,rows_city[0][1]))}%"></div></td></tr>'
        for k, v in rows_city
    )
    fail_feat_html = "".join(
        f'<tr><td>{feat_labels.get(k, k)}</td><td>{v}</td>'
        f'<td><div class="bar-red" style="width:{min(100,v*100//max(1,rows_fail_feat[0][1]))}%"></div></td></tr>'
        for k, v in rows_fail_feat
    ) if rows_fail_feat else "<tr><td colspan='3' style='color:#66bb6a;text-align:center'>✅ 無失敗記錄</td></tr>"
    daily_labels = json.dumps([d[5:] for d, _ in rows_daily])  # MM-DD
    daily_data   = json.dumps([c for _, c in rows_daily])

    error_html = f'<div class="error">⚠️ {error_msg}</div>' if error_msg else ""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>生活優轉 · 使用統計</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;padding:20px}}
  h1{{color:#fff;font-size:1.4rem;margin-bottom:4px}}
  .sub{{color:#888;font-size:.85rem;margin-bottom:24px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}}
  .card{{background:#1a1f2e;border-radius:12px;padding:18px;text-align:center}}
  .card .num{{font-size:2rem;font-weight:700;color:#64b5f6}}
  .card .lbl{{font-size:.75rem;color:#888;margin-top:4px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
  @media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
  .panel{{background:#1a1f2e;border-radius:12px;padding:16px}}
  .panel h2{{font-size:.95rem;color:#90caf9;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  td{{padding:6px 4px;border-bottom:1px solid #2a2f3e}}
  td:nth-child(2){{text-align:right;color:#64b5f6;font-weight:600;white-space:nowrap;padding-right:8px}}
  td:nth-child(3){{width:40%}}
  .bar{{height:8px;background:linear-gradient(90deg,#1976d2,#64b5f6);border-radius:4px;min-width:2px}}
  .bar-red{{height:8px;background:linear-gradient(90deg,#c62828,#ef9a9a);border-radius:4px;min-width:2px}}
  .chart-wrap{{background:#1a1f2e;border-radius:12px;padding:16px;margin-bottom:24px}}
  .chart-wrap h2{{font-size:.95rem;color:#90caf9;margin-bottom:12px}}
  .error{{background:#b71c1c;color:#fff;padding:12px;border-radius:8px;margin-bottom:16px}}
  .footer{{color:#555;font-size:.75rem;text-align:center;margin-top:16px}}
</style>
</head>
<body>
<h1>🚀 生活優轉 · 使用統計</h1>
<p class="sub">資料來源：Supabase · 最近 5000 筆</p>
{error_html}
<div class="cards">
  <div class="card"><div class="num">{total_uses}</div><div class="lbl">成功次數</div></div>
  <div class="card"><div class="num">{total_users}</div><div class="lbl">不重複用戶</div></div>
  <div class="card"><div class="num">{rows_daily[-1][1] if rows_daily else 0}</div><div class="lbl">今日使用</div></div>
  <div class="card"><div class="num" style="color:{fail_color}">{total_fails}</div><div class="lbl">失敗次數（{fail_rate_pct}%）</div></div>
</div>
<div class="chart-wrap">
  <h2>📅 近 14 天每日使用次數</h2>
  <canvas id="dailyChart" height="80"></canvas>
</div>
<div class="grid">
  <div class="panel">
    <h2>🏆 功能排行（成功）</h2>
    <table>{feat_rows_html}</table>
  </div>
  <div class="panel">
    <h2>📍 城市分佈</h2>
    <table>{city_rows_html}</table>
  </div>
</div>
<div class="grid">
  <div class="panel">
    <h2>🚨 失敗功能排行</h2>
    <table>{fail_feat_html}</table>
  </div>
  <div class="panel">
    <h2>💡 健康指標</h2>
    <table>
      <tr><td>失敗率</td><td style="color:{fail_color}">{fail_rate_pct}%</td><td><div class="bar-red" style="width:{min(100,int(fail_rate_pct*10))}%"></div></td></tr>
      <tr><td>成功次數</td><td>{total_uses}</td><td></td></tr>
      <tr><td>失敗次數</td><td>{total_fails}</td><td></td></tr>
      <tr><td>不重複用戶</td><td>{total_users}</td><td></td></tr>
      <tr><td>今日使用</td><td>{rows_daily[-1][1] if rows_daily else 0}</td><td></td></tr>
    </table>
  </div>
</div>
<p class="footer">生活優轉 LifeUturn · 自動更新 · 失敗率 &gt; 5% 表示有功能異常</p>
<script>
new Chart(document.getElementById('dailyChart'),{{
  type:'bar',
  data:{{
    labels:{daily_labels},
    datasets:[{{
      label:'使用次數',
      data:{daily_data},
      backgroundColor:'rgba(100,181,246,0.7)',
      borderColor:'#64b5f6',
      borderWidth:1,
      borderRadius:4,
    }}]
  }},
  options:{{
    responsive:true,
    plugins:{{legend:{{display:false}}}},
    scales:{{
      x:{{ticks:{{color:'#888'}},grid:{{color:'#2a2f3e'}}}},
      y:{{ticks:{{color:'#888'}},grid:{{color:'#2a2f3e'}},beginAtZero:true}}
    }}
  }}
}});
</script>
</body>
</html>"""


# ─── Vercel Handler ───────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """健康檢查 + 快取預熱"""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)

        if parsed.path in ("/api/warm_cache", "/api/webhook"):
            # 預熱主要城市的 TDX 停車資料
            _WARM_CITIES = ["Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung"]
            # 代表座標（市中心附近）
            _CITY_COORDS = {
                "Taipei":     (25.047, 121.517),
                "NewTaipei":  (25.012, 121.466),
                "Taoyuan":    (24.993, 121.301),
                "Taichung":   (24.147, 120.674),
                "Tainan":     (22.999, 120.227),
                "Kaohsiung":  (22.627, 120.301),
            }
            import threading as _th
            token = _get_tdx_token()
            results = {}

            def _warm(city):
                try:
                    # 只有 lots 需要預熱（24h TTL）；avail 讓使用者觸發即可
                    if _redis_get(f"tdx_lots_{city}") is None:
                        lots = _tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=8)
                        if lots:  # 空結果不快取，避免 24h 鎖死
                            _redis_set(f"tdx_lots_{city}", lots, ttl=86400)
                        results[city] = f"fetched {len(lots)} lots"
                    else:
                        results[city] = "cache hit"
                except Exception as e:
                    results[city] = f"error: {e}"

            threads = [_th.Thread(target=_warm, args=(c,), daemon=True) for c in _WARM_CITIES]
            for t in threads: t.start()
            for t in threads: t.join(timeout=9)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "warmed", "cities": results}).encode())
        elif parsed.path == "/api/push_test":
            # 直接測試 push_message，顯示 LINE API 真實回應
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            uid = qs.get("uid", [""])[0]
            msg = qs.get("msg", ["push測試 ✅"])[0]
            if not uid:
                self.send_response(400); self.end_headers()
                self.wfile.write(b'{"error":"uid required"}'); return
            result = {"uid": uid, "token_set": bool(CHANNEL_ACCESS_TOKEN),
                      "token_prefix": CHANNEL_ACCESS_TOKEN[:20] + "..." if CHANNEL_ACCESS_TOKEN else "EMPTY"}
            try:
                push_data = json.dumps({
                    "to": uid, "messages": [{"type": "text", "text": msg}]
                }).encode("utf-8")
                push_req = urllib.request.Request(
                    "https://api.line.me/v2/bot/message/push",
                    data=push_data,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
                )
                resp = urllib.request.urlopen(push_req, timeout=10)
                result["status"] = f"SUCCESS {resp.status}"
                result["body"] = resp.read().decode("utf-8", "ignore")
            except Exception as pe:
                result["status"] = f"FAILED: {pe}"
                if hasattr(pe, 'read'):
                    result["error_body"] = pe.read().decode("utf-8", "ignore")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

        elif parsed.path == "/api/parking_debug":
            # 直接測試 build_parking_flex，支援 push=uid 參數
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            lat = float(qs.get("lat", ["25.047"])[0])
            lon = float(qs.get("lon", ["121.517"])[0])
            push_uid = qs.get("push", [""])[0]
            push_result = None
            try:
                msgs = build_parking_flex(lat, lon)
                import re as _re
                all_uris = _re.findall(r'"uri"\s*:\s*"([^"]+)"',
                                       json.dumps(msgs, ensure_ascii=False))
                result = {"ok": True, "count": len(msgs),
                          "uris": all_uris,
                          "bad_uris": [u for u in all_uris if any(ord(c)>=128 for c in u)]}
                if push_uid:
                    push_data = json.dumps({
                        "to": push_uid,
                        "messages": msgs[:5]
                    }, ensure_ascii=False).encode("utf-8")
                    push_req = urllib.request.Request(
                        "https://api.line.me/v2/bot/message/push",
                        data=push_data,
                        headers={"Content-Type": "application/json",
                                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
                    )
                    try:
                        presp = urllib.request.urlopen(push_req, timeout=10)
                        push_result = f"SUCCESS {presp.status}: {presp.read().decode('utf-8','ignore')}"
                    except Exception as pe:
                        push_result = f"FAILED: {pe}"
                        if hasattr(pe, 'read'):
                            push_result += f" | {pe.read().decode('utf-8','ignore')}"
                    result["push_result"] = push_result
            except Exception as de:
                import traceback
                result = {"ok": False, "error": str(de), "trace": traceback.format_exc()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/tdx_test":
            # TDX 完整診斷：token + API + 座標比對
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            lat = float(qs.get("lat", ["25.047"])[0])
            lon = float(qs.get("lon", ["121.517"])[0])
            diag = {}
            diag["input"] = {"lat": lat, "lon": lon}
            diag["tdx_client_id_set"] = bool(TDX_CLIENT_ID)
            diag["tdx_client_id_prefix"] = TDX_CLIENT_ID[:8] if TDX_CLIENT_ID else ""
            city = _coords_to_tdx_city(lat, lon)
            diag["city"] = city
            token = _get_tdx_token()
            diag["token_ok"] = bool(token)
            diag["token_prefix"] = token[:12] if token else ""
            if token:
                lots = _tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=8)
                avail = _tdx_get(f"Parking/OffStreet/ParkingAvailability/City/{city}?$format=JSON", token, timeout=8)
                diag["tdx_lots_total"] = len(lots)
                diag["tdx_avail_total"] = len(avail)
                # 半徑 2km 內有幾個
                nearby = [l for l in lots if l.get("CarParkPosition") or l.get("ParkingPosition")]
                within = []
                for l in nearby:
                    pos = l.get("CarParkPosition") or l.get("ParkingPosition") or {}
                    p_lat = pos.get("PositionLat") or l.get("PositionLat")
                    p_lon = pos.get("PositionLon") or l.get("PositionLon")
                    if p_lat and p_lon:
                        d = _haversine(lat, lon, float(p_lat), float(p_lon))
                        if d <= 2000:
                            within.append({"name": str(l.get("CarParkName",""))[:30], "dist": d})
                diag["within_2km"] = sorted(within, key=lambda x: x["dist"])[:10]
                if lots:
                    first = lots[0]
                    pos0 = first.get("CarParkPosition") or first.get("ParkingPosition") or {}
                    diag["sample_lot"] = {
                        "name": str(first.get("CarParkName",""))[:30],
                        "pos": pos0,
                        "keys": list(first.keys())[:15]
                    }
            else:
                diag["error"] = "TDX token 取得失敗"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(diag, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/diag":
            # 全面診斷：LINE API + webhook URL + env
            diag = {
                "env": {
                    "SECRET_set": bool(CHANNEL_SECRET),
                    "SECRET_len": len(CHANNEL_SECRET),
                    "TOKEN_set": bool(CHANNEL_ACCESS_TOKEN),
                    "TOKEN_len": len(CHANNEL_ACCESS_TOKEN),
                    "TOKEN_prefix": CHANNEL_ACCESS_TOKEN[:30] + "..." if CHANNEL_ACCESS_TOKEN else "EMPTY",
                },
            }
            # 1. Check bot info
            try:
                req_bot = urllib.request.Request(
                    "https://api.line.me/v2/bot/info",
                    headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"})
                resp_bot = urllib.request.urlopen(req_bot, timeout=10)
                diag["bot_info"] = json.loads(resp_bot.read().decode("utf-8"))
            except Exception as e:
                err_body = ""
                if hasattr(e, 'read'): err_body = e.read().decode("utf-8","ignore")
                diag["bot_info_error"] = f"{e} | {err_body}"
            # 2. Check webhook endpoint
            try:
                req_wh = urllib.request.Request(
                    "https://api.line.me/v2/bot/channel/webhook/endpoint",
                    headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"})
                resp_wh = urllib.request.urlopen(req_wh, timeout=10)
                diag["webhook"] = json.loads(resp_wh.read().decode("utf-8"))
            except Exception as e:
                err_body = ""
                if hasattr(e, 'read'): err_body = e.read().decode("utf-8","ignore")
                diag["webhook_error"] = f"{e} | {err_body}"
            # 3. Test webhook from LINE's side
            try:
                test_data = json.dumps({"endpoint": "https://3c-advisor.vercel.app/api/webhook"}).encode("utf-8")
                req_test = urllib.request.Request(
                    "https://api.line.me/v2/bot/channel/webhook/test",
                    data=test_data,
                    headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                             "Content-Type": "application/json"})
                resp_test = urllib.request.urlopen(req_test, timeout=15)
                diag["webhook_test"] = json.loads(resp_test.read().decode("utf-8"))
            except Exception as e:
                err_body = ""
                if hasattr(e, 'read'): err_body = e.read().decode("utf-8","ignore")
                diag["webhook_test_error"] = f"{e} | {err_body}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(diag, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/morning_test":
            # 測試早安摘要（debug 用）
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            push_uid = qs.get("push", [""])[0]
            city = qs.get("city", [""])[0] or ""
            test_text = f"早安 {city}".strip() if city else "早安"
            diag = {
                "env": {
                    "SECRET_set": bool(CHANNEL_SECRET),
                    "SECRET_len": len(CHANNEL_SECRET) if CHANNEL_SECRET else 0,
                    "TOKEN_set": bool(CHANNEL_ACCESS_TOKEN),
                    "TOKEN_prefix": CHANNEL_ACCESS_TOKEN[:20] + "..." if CHANNEL_ACCESS_TOKEN else "EMPTY",
                    "CWA_KEY_set": bool(os.environ.get("CWA_API_KEY", "")),
                },
            }
            try:
                msgs = build_morning_summary(test_text)
                msg_json = json.dumps(msgs, ensure_ascii=False)
                diag["build"] = {"ok": True, "count": len(msgs),
                          "altText": msgs[0].get("altText", "") if msgs else "",
                          "type": msgs[0].get("type", "") if msgs else "",
                          "json_size": len(msg_json)}
                if push_uid and msgs:
                    try:
                        push_data = json.dumps({
                            "to": push_uid, "messages": msgs[:5]
                        }, ensure_ascii=False).encode("utf-8")
                        push_req = urllib.request.Request(
                            "https://api.line.me/v2/bot/message/push",
                            data=push_data,
                            headers={"Content-Type": "application/json",
                                     "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
                        )
                        presp = urllib.request.urlopen(push_req, timeout=10)
                        diag["push"] = f"SUCCESS {presp.status}: {presp.read().decode('utf-8','ignore')}"
                    except Exception as pe:
                        err_body = ""
                        if hasattr(pe, 'read'):
                            err_body = pe.read().decode('utf-8','ignore')
                        diag["push"] = f"FAILED: {pe} | {err_body}"
            except Exception as e:
                import traceback
                diag["build"] = {"ok": False, "error": str(e), "trace": traceback.format_exc()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(diag, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/stats":
            # ── 使用統計儀表板 ──────────────────────────────
            html = _build_stats_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "bot": "生活優轉 LifeUturn"}).encode())

    def do_POST(self):
        """接收 LINE Webhook"""
        from urllib.parse import urlparse as _up

        # ── 內部停車 Worker（自己的 10 秒額度）────────────────
        if _up(self.path).path == "/api/parking_worker":
            secret = self.headers.get("X-Parking-Secret", "")
            if secret != "linebot_parking_2026":
                self.send_response(403); self.end_headers(); return
            content_length = int(self.headers.get("Content-Length", 0))
            body_w = json.loads(self.rfile.read(content_length))
            uid_w  = body_w.get("user_id", "")
            lat_w  = float(body_w.get("lat", 0))
            lon_w  = float(body_w.get("lon", 0))
            # 立刻回 202 讓上游繼續，然後做停車搜尋 + push
            self.send_response(202)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"accepted"}')
            try:
                msgs = build_parking_flex(lat_w, lon_w)
                push_message(uid_w, msgs)
            except Exception as _we:
                import traceback; traceback.print_exc()
                push_message(uid_w, [{"type": "text", "text": "找車位時發生錯誤，請稍後再試 🙏"}])
            return

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

                user_id = event.get("source", {}).get("userId", "unknown")

                # 加好友或解除封鎖 → 發送歡迎訊息
                if event.get("type") == "follow":
                    reply_token = event.get("replyToken", "")
                    reply_message(reply_token, build_welcome_message())
                    log_usage(user_id, "follow")
                    continue

                # 位置訊息 → 找車位
                # ① 立刻 reply → webhook 快速結束（< 2 秒）
                # ② fire-and-forget → parking_worker 自己有 10 秒額度
                if event.get("type") == "message" and event.get("message", {}).get("type") == "location":
                    reply_token = event.get("replyToken", "")
                    lat = float(event["message"].get("latitude", 0))
                    lon = float(event["message"].get("longitude", 0))
                    city_hint = event["message"].get("address", "")[:6]
                    print(f"[webhook] location: {lat},{lon}")
                    # 快速路徑：快取命中 → 直接 reply 卡片（不需 push）
                    cached = _peek_parking_cache(lat, lon)
                    if cached:
                        reply_message(reply_token, cached)
                        log_usage(user_id, "parking", sub_action="傳位置_cached", city=city_hint)
                    else:
                        reply_message(reply_token, [{"type": "text",
                            "text": "📍 定位成功！\n🔍 正在搜尋附近車位..."}])
                        try:
                            messages = build_parking_flex(lat, lon)
                            push_message(user_id, messages)
                            log_usage(user_id, "parking", sub_action="傳位置", city=city_hint)
                        except Exception as pe:
                            import traceback; traceback.print_exc()
                            push_message(user_id, [{"type": "text", "text": "找車位時發生錯誤，請稍後再試 🙏"}])
                            log_usage(user_id, "parking", sub_action="傳位置", is_success=False)
                    continue

                # 文字訊息
                if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
                    reply_token = event.get("replyToken", "")
                    user_text = event["message"]["text"]
                    print(f"[webhook] user said: {user_text}")

                    # LIFF 早安自動定位隱藏指令（格式：__morning_city__:台北）
                    if user_text.startswith("__morning_city__:"):
                        try:
                            city = user_text.split(":", 1)[1].strip()
                            all_cities_pat = "|".join(_ALL_CITIES)
                            import re as _re
                            city_m = _re.search(rf"({all_cities_pat})", city)
                            if city_m:
                                city = city_m.group(1)
                                _set_user_city(user_id, city)
                                msgs = build_morning_summary(city, user_id=user_id)
                                reply_message(reply_token, msgs)
                                log_usage(user_id, "morning_summary", sub_action="liff_locate")
                            else:
                                reply_message(reply_token, _build_morning_city_picker())
                        except Exception as me:
                            print(f"[webhook] morning_city error: {me}")
                            reply_message(reply_token, _build_morning_city_picker())
                        continue

                    # LIFF 自動定位隱藏指令（格式：__parking__:lat,lon）
                    if user_text.startswith("__parking__:"):
                        try:
                            coords = user_text.split(":")[1].split(",")
                            lat, lon = float(coords[0]), float(coords[1])
                            print(f"[webhook] LIFF parking: {lat},{lon}")
                            # 快速路徑：快取命中 → 直接 reply 卡片
                            cached = _peek_parking_cache(lat, lon)
                            if cached:
                                reply_message(reply_token, cached)
                                log_usage(user_id, "parking", sub_action="liff_cached")
                            else:
                                reply_message(reply_token, [{"type": "text",
                                    "text": "📍 定位成功！\n🔍 正在搜尋附近車位..."}])
                                messages = build_parking_flex(lat, lon)
                                push_message(user_id, messages)
                                log_usage(user_id, "parking", sub_action="liff_auto")
                        except Exception as pe:
                            import traceback; traceback.print_exc()
                            push_message(user_id, [{"type": "text", "text": "定位失敗，請稍後再試 🙏"}])
                        continue
                    # 判斷功能類別（用於 log，不影響路由）
                    _feature, _sub = _detect_feature(user_text)
                    try:
                        messages = handle_text_message(user_text, user_id=user_id)
                        reply_message(reply_token, messages)
                        log_usage(user_id, _feature, sub_action=_sub)
                    except Exception as he:
                        import traceback
                        print(f"[handler] ERROR in handle_text_message: {he}")
                        traceback.print_exc()
                        messages = [{"type": "text", "text": "系統發生錯誤，請稍後再試 🙏"}]
                        reply_message(reply_token, messages)
                        log_usage(user_id, _feature, sub_action=_sub, is_success=False)

        except Exception as e:
            print(f"[webhook] ERROR: {e}")
            import traceback
            traceback.print_exc()
