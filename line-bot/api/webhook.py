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
    if is_desktop:
        # 桌機：連結到網站配置頁 + 詢問組裝
        website_url = "https://hhc42937536-cell.github.io/3c-advisor/"
        return {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#8D6E63", "height": "sm",
                 "action": {"type": "uri", "label": "🖥️ 查看完整規格建議", "uri": website_url}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "❓ 這配置適合我嗎？",
                            "text": f"這款適合我嗎 桌機 {name}"}},
            ]
        }
    else:
        # 一般產品：四大電商平台
        search_q   = urllib.parse.quote(f"{brand} {name}")
        pchome_url = f"https://ecshweb.pchome.com.tw/search/v3.3/?q={search_q}"
        momo_url   = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={search_q}"
        yahoo_url  = f"https://tw.buy.yahoo.com/search/product?p={search_q}"
        shopee_url = f"https://shopee.tw/search?keyword={search_q}"
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
                    "type": "button", "style": "secondary", "height": "sm",
                    "action": {"type": "message", "label": "❓ 這款適合我嗎？",
                               "text": f"這款適合我嗎 {brand} {name}"},
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
        status, color = "體重過輕 😟", "#1565C0"
        advice = "建議增加蛋白質攝取（蛋、雞胸肉、豆腐），每週做 2-3 次重量訓練增肌。"
    elif bmi < 24:
        status, color = "體重正常 ✅", "#2E7D32"
        advice = "繼續保持！每週 150 分鐘有氧運動 + 均衡飲食，維持現況最重要。"
    elif bmi < 27:
        status, color = "體重過重 ⚠️", "#E65100"
        advice = "建議每天減少 300-500 大卡攝取，多走路爬樓梯。循序漸進比激烈節食有效。"
    elif bmi < 30:
        status, color = "輕度肥胖 🔴", "#C62828"
        advice = "建議諮詢營養師制定飲食計畫，配合有氧運動（走路/游泳/騎車）。"
    else:
        status, color = "中重度肥胖 🚨", "#B71C1C"
        advice = "建議諮詢醫師評估健康風險，可考慮專業減重門診協助。"
    ideal_low = round(18.5 * (height/100)**2, 1)
    ideal_high = round(24 * (height/100)**2, 1)
    return [{"type":"flex","altText":f"BMI 計算結果：{bmi}","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":color,"contents":[
            {"type":"text","text":"🏃 BMI 健康分析","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":f"身高 {int(height)}cm｜體重 {weight}kg","color":"#FFFFFF","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"md","contents":[
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"BMI 指數","size":"sm","color":"#888888","flex":2},
                {"type":"text","text":str(bmi),"size":"xxl","weight":"bold","color":color,"flex":1,"align":"end"},
            ]},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"健康狀態","size":"sm","color":"#888888","flex":2},
                {"type":"text","text":status,"size":"sm","weight":"bold","color":color,"flex":3,"align":"end","wrap":True},
            ]},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"理想體重","size":"sm","color":"#888888","flex":2},
                {"type":"text","text":f"{ideal_low}～{ideal_high} kg","size":"sm","color":"#2E7D32","flex":3,"align":"end"},
            ]},
            {"type":"separator","margin":"md"},
            {"type":"text","text":"💡 建議","weight":"bold","size":"sm","color":"#3E2723"},
            {"type":"text","text":advice,"size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#2E7D32","height":"sm",
             "action":{"type":"message","label":"🥗 健康減重方法","text":"減肥方法"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"😴 改善睡眠","text":"睡眠改善"}},
        ]}
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


def build_health_menu() -> list:
    return [{"type":"flex","altText":"健康小幫手","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#2E7D32","contents":[
            {"type":"text","text":"🏃 健康小幫手","color":"#FFFFFF","size":"lg","weight":"bold"},
            {"type":"text","text":"你的隨身健康顧問","color":"#C8E6C9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":"想了解什麼？直接問我，或點選下方 👇","size":"sm","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#2E7D32","height":"sm",
             "action":{"type":"message","label":"📊 BMI 計算","text":"幫我算BMI"}},
            {"type":"button","style":"primary","color":"#1B5E20","height":"sm",
             "action":{"type":"message","label":"🥗 健康減重方法","text":"減肥方法"}},
            {"type":"button","style":"primary","color":"#1A237E","height":"sm",
             "action":{"type":"message","label":"😴 睡眠改善","text":"睡眠改善"}},
            {"type":"button","style":"primary","color":"#6A1B9A","height":"sm",
             "action":{"type":"message","label":"😰 壓力紓解","text":"壓力紓解"}},
        ]}
    }}]


def build_health_message(text: str) -> list:
    """健康小幫手主路由"""
    height, weight = parse_height_weight(text)
    if height and weight and 100 <= height <= 220 and 20 <= weight <= 200:
        return build_bmi_flex(height, weight)
    if any(w in text for w in ["bmi", "BMI", "幫我算", "算一下"]):
        return [{"type":"text","text":"請告訴我你的身高和體重 😊\n\n例如：\n「我身高 170cm，體重 75kg」\n「170公分 65公斤」"}]
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
             "action":{"type":"message","label":"💳 信用卡怎麼用最划算？","text":"信用卡使用"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 保險要買哪些？","text":"保險建議"}},
        ]}
    }}]


def build_credit_card_advice() -> list:
    return [{"type":"flex","altText":"信用卡使用指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#1565C0","contents":[
            {"type":"text","text":"💳 信用卡使用指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"讓信用卡幫你賺錢，不是賠錢","color":"#BBDEFB","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"✅ 正確使用方式","weight":"bold","size":"sm","color":"#1565C0"},
            {"type":"text","text":"• 每月全額繳清，絕對不繳最低應繳\n• 刷卡賺回饋（現金回饋 1-3%）\n• 固定支出設定自動扣款（水電/訂閱）","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🚨 循環利息有多恐怖？","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"年利率 15-20%！\n\n欠 NT$10,000 只繳最低應繳：\n→ 1 年後你還欠 NT$11,500\n→ 5 年後你欠快 NT$24,000\n\n👉 一旦開始循環，盡快一次還清","size":"xs","color":"#C62828","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"💡 還清循環利息的方法","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"① 申請「信貸代償」（利率只要 3-7%）\n② 問銀行是否有「分期零利率」方案\n③ 暫停刷卡，優先把欠款還清","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#E65100","height":"sm",
             "action":{"type":"message","label":"💰 月薪預算規劃","text":"存錢方法"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 保險要買哪些？","text":"保險建議"}},
        ]}
    }}]


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
             "action":{"type":"message","label":"💳 信用卡怎麼用？","text":"信用卡使用"}},
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
             "action":{"type":"message","label":"💳 信用卡怎麼用最划算？","text":"信用卡使用"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 要買哪些保險？","text":"保險建議"}},
        ]}
    }}]


def build_money_menu() -> list:
    return [{"type":"flex","altText":"金錢小幫手","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#E65100","contents":[
            {"type":"text","text":"💰 金錢小幫手","color":"#FFFFFF","size":"lg","weight":"bold"},
            {"type":"text","text":"你的隨身財務顧問","color":"#FFE0B2","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","contents":[
            {"type":"text","text":"直接告訴我月薪，或點選下方 👇","size":"sm","color":"#555555","wrap":True},
            {"type":"text","text":"例如：「我月薪 35000 怎麼規劃？」","size":"xs","color":"#AAAAAA","margin":"sm"},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#E65100","height":"sm",
             "action":{"type":"message","label":"📊 月薪預算規劃","text":"我月薪35000怎麼規劃"}},
            {"type":"button","style":"primary","color":"#BF360C","height":"sm",
             "action":{"type":"message","label":"💰 存錢方法","text":"存錢方法"}},
            {"type":"button","style":"primary","color":"#1565C0","height":"sm",
             "action":{"type":"message","label":"💳 信用卡怎麼用？","text":"信用卡使用"}},
            {"type":"button","style":"primary","color":"#4527A0","height":"sm",
             "action":{"type":"message","label":"🛡️ 保險買哪些？","text":"保險建議"}},
        ]}
    }}]


def build_money_message(text: str) -> list:
    """金錢小幫手主路由"""
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
    if any(w in text for w in ["信用卡","循環利息","最低應繳","刷卡"]):
        return build_credit_card_advice()
    if any(w in text for w in ["保險","醫療險","壽險","意外險","重大疾病"]):
        return build_insurance_guide()
    if any(w in text for w in ["存錢","儲蓄","記帳","理財","怎麼存"]):
        return build_saving_tips()
    return build_money_menu()


# ─── 今天吃什麼 ──────────────────────────────────────

import random as _random

# 食物推薦庫（健康版 / 享樂版 / 快速版）
_FOOD_DB = {
    "健康": [
        {"name": "雞肉飯 + 燙青菜", "desc": "高蛋白、低脂，台灣小吃最健康選項", "price": "~80元", "key": "雞肉飯"},
        {"name": "越南河粉", "desc": "清湯底、蔬菜多、熱量低，飽足感高", "price": "~120元", "key": "越南河粉"},
        {"name": "日式定食", "desc": "蒸煮為主、蔬菜豐富，可選烤魚或豆腐", "price": "~180元", "key": "日式定食"},
        {"name": "素食自助餐", "desc": "可自由搭配蔬菜豆製品，熱量最容易控制", "price": "~100元", "key": "素食自助餐"},
        {"name": "韓式豆腐鍋", "desc": "低卡高蛋白，辣度可調，暖胃又健康", "price": "~180元", "key": "韓式豆腐鍋"},
        {"name": "壽司輕食", "desc": "份量小、選海鮮口味熱量低，適合減脂", "price": "~150元", "key": "迴轉壽司"},
        {"name": "鮭魚酪梨沙拉", "desc": "好脂肪、高蛋白，健身族最愛", "price": "~200元", "key": "健康輕食沙拉"},
        {"name": "蒸蛋 + 燙蔬菜便當", "desc": "清爽低卡，適合腸胃不好時", "price": "~90元", "key": "健康便當"},
        {"name": "溫泉蛋蕎麥麵", "desc": "低GI主食、清爽無負擔，日本料理健康選", "price": "~150元", "key": "蕎麥麵"},
        {"name": "烤雞腿便當", "desc": "烤的比炸的健康，蛋白質充足好控熱量", "price": "~100元", "key": "烤雞便當"},
        {"name": "海鮮粥", "desc": "低熱量好消化，腸胃疲憊時最棒選擇", "price": "~100元", "key": "海鮮粥"},
        {"name": "地中海沙拉", "desc": "橄欖油+蔬菜+起司，抗氧化效果佳", "price": "~180元", "key": "沙拉輕食"},
        {"name": "雞胸肉蔬菜捲", "desc": "低卡高纖，健身族外食首選", "price": "~130元", "key": "健康捲餅"},
        {"name": "清蒸魚 + 糙米飯", "desc": "Omega-3 豐富，清淡不油膩", "price": "~160元", "key": "清蒸魚"},
        {"name": "豆漿 + 燕麥", "desc": "植物蛋白豐富，簡單卻很養生", "price": "~60元", "key": "豆漿燕麥"},
        {"name": "涼麵（麻醬少量）", "desc": "夏天消暑，醬汁少放更清爽", "price": "~70元", "key": "涼麵"},
        {"name": "魚片湯麵", "desc": "清湯低熱量，魚肉蛋白豐富好吸收", "price": "~120元", "key": "魚片湯麵"},
        {"name": "義式番茄蔬菜湯", "desc": "茄紅素豐富，低卡又暖胃", "price": "~150元", "key": "蔬菜湯"},
    ],
    "享樂": [
        {"name": "麻辣火鍋", "desc": "過癮、暖身、社交神器，吃完很滿足", "price": "~350元", "key": "麻辣火鍋"},
        {"name": "燒肉吃到飽", "desc": "肉量管夠，週末犒賞自己首選", "price": "~599元", "key": "燒肉吃到飽"},
        {"name": "牛肉麵", "desc": "濃郁湯底、大塊牛肉，台灣魂料理", "price": "~160元", "key": "牛肉麵"},
        {"name": "鹽酥雞 + 珍奶", "desc": "台灣夜市靈魂，爽快就是最大理由", "price": "~120元", "key": "鹽酥雞"},
        {"name": "拉麵", "desc": "濃厚豚骨或醬油湯底，讓你忘記煩惱", "price": "~280元", "key": "拉麵"},
        {"name": "炸雞排便當", "desc": "台式便當王者，誰不愛？", "price": "~100元", "key": "雞排便當"},
        {"name": "韓式炸雞", "desc": "外酥內嫩、沾醬選甜辣，停不下來", "price": "~280元", "key": "韓式炸雞"},
        {"name": "壽喜燒", "desc": "甜鹹醬汁配嫩牛肉，超級下飯", "price": "~350元", "key": "壽喜燒"},
        {"name": "海鮮熱炒", "desc": "三杯中卷、炒蛤蜊，配啤酒超爽", "price": "~400元", "key": "海鮮熱炒"},
        {"name": "泰式打拋豬飯", "desc": "香辣下飯，加個荷包蛋更完美", "price": "~130元", "key": "泰式料理"},
        {"name": "台式爌肉飯", "desc": "油亮滷汁、入口即化，最溫暖的台灣味", "price": "~90元", "key": "爌肉飯"},
        {"name": "印度咖哩", "desc": "濃郁香料、暖身開胃，配印度烤餅超棒", "price": "~220元", "key": "印度咖哩"},
        {"name": "乾式熟成牛排", "desc": "偶爾犒賞自己，人生就該這樣過", "price": "~800元", "key": "牛排"},
        {"name": "鴨血臭豆腐", "desc": "台式宵夜經典，就是要重口味", "price": "~80元", "key": "臭豆腐"},
        {"name": "起司焗烤義大利麵", "desc": "濃郁起司拉絲，療癒系食物代表", "price": "~220元", "key": "焗烤義大利麵"},
        {"name": "薑母鴨", "desc": "冬天限定首選，補氣暖身又過癮", "price": "~350元", "key": "薑母鴨"},
        {"name": "鐵板燒", "desc": "現點現做、視覺享受，吃飯也是一種體驗", "price": "~450元", "key": "鐵板燒"},
        {"name": "廣式飲茶", "desc": "蝦餃、燒賣、腸粉，週末家人聚餐最佳", "price": "~300元", "key": "港式飲茶"},
    ],
    "快速": [
        {"name": "超商關東煮 + 飯糰", "desc": "5分鐘解決，便宜又不踩雷", "price": "~60元", "key": "超商熟食"},
        {"name": "滷肉飯 + 貢丸湯", "desc": "台灣人的靈魂食物，快速又飽足", "price": "~70元", "key": "滷肉飯"},
        {"name": "乾麵 + 滷蛋", "desc": "10分鐘內上桌，簡單又飽足", "price": "~70元", "key": "乾麵"},
        {"name": "水餃（店面）", "desc": "煮一鍋快速搞定，可加湯增飽足", "price": "~80元", "key": "水餃"},
        {"name": "潛艇堡或三明治", "desc": "快速、可客製，蛋白蔬菜都有", "price": "~100元", "key": "三明治輕食"},
        {"name": "蛋餅 + 豆漿", "desc": "早餐店隨時都有，簡單溫暖", "price": "~50元", "key": "蛋餅"},
        {"name": "自助餐打便當", "desc": "3分鐘選好打包走，菜色最多樣", "price": "~90元", "key": "自助餐便當"},
        {"name": "肉圓 + 四神湯", "desc": "台灣傳統小吃，2攤搞定一餐", "price": "~70元", "key": "肉圓"},
        {"name": "切仔麵 + 黑白切", "desc": "台式麵攤速食，湯清麵Q", "price": "~80元", "key": "切仔麵"},
        {"name": "刈包（控肉夾餅）", "desc": "台版漢堡，站著吃5分鐘結束", "price": "~60元", "key": "刈包"},
        {"name": "烤地瓜 + 茶葉蛋", "desc": "超商最健康的快速組合", "price": "~40元", "key": "地瓜茶葉蛋"},
        {"name": "麵線羹", "desc": "台灣小吃、滑順好入口，暖胃快速", "price": "~60元", "key": "麵線"},
        {"name": "碗粿 + 魚丸湯", "desc": "台南風格小吃，簡單溫潤", "price": "~65元", "key": "碗粿"},
        {"name": "豬血糕 + 花生粉", "desc": "夜市快速點心，意外的高鐵食物", "price": "~35元", "key": "豬血糕"},
        {"name": "鍋貼 + 蛋花湯", "desc": "煎香鍋貼配湯，10分鐘飽足", "price": "~75元", "key": "鍋貼"},
    ],
}


def _maps_url(keyword: str, area: str = "") -> str:
    """產生 Google Maps 搜尋連結"""
    q = urllib.parse.quote(f"{area} {keyword}".strip())
    return f"https://www.google.com/maps/search/{q}"


def build_food_flex(style: str, area: str = "") -> list:
    """隨機挑 3 道推薦，回傳 Flex 訊息"""
    pool = _FOOD_DB.get(style, _FOOD_DB["享樂"])
    picks = _random.sample(pool, min(3, len(pool)))
    area_label = f"（{area}附近）" if area else ""
    colors = {"健康": "#2E7D32", "享樂": "#C62828", "快速": "#E65100"}
    color = colors.get(style, "#FF8C42")
    icons = {"健康": "🥗", "享樂": "🍖", "快速": "⚡"}
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
             "action": {"type": "uri", "label": f"📍 找附近{p['name']}", "uri": _maps_url(p["key"], area)}},
        ]
        if i < len(picks)-1:
            items.append({"type": "separator", "margin": "sm"})

    next_style = {"健康": "享樂", "享樂": "快速", "快速": "健康"}[style]
    return [{"type": "flex", "altText": f"今天吃什麼 — {icon}{style}版",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🍽️ 今天吃什麼{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"{icon} {style}版推薦",
                                 "color": "#FFFFFF", "size": "xs", "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"吃什麼 {style} {area}"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": f"換{next_style}版",
                                                      "text": f"吃什麼 {next_style} {area}"}},
                     ]},
                 ]},
             }}]


def build_food_menu() -> list:
    """今天吃什麼 — 主選單"""
    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#FF5722",
                            "contents": [
                                {"type": "text", "text": "🍽️ 今天吃什麼？", "color": "#FFFFFF",
                                 "size": "lg", "weight": "bold"},
                                {"type": "text", "text": "幫你快速決定，外食族救星！",
                                 "color": "#FFCCBC", "size": "xs", "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "想吃哪種風格？", "size": "sm",
                      "color": "#555555", "weight": "bold"},
                     {"type": "text", "text": "也可以說「台南東區 健康版」「台北信義 享樂版」",
                      "size": "xs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "button", "style": "primary", "color": "#2E7D32", "height": "sm",
                      "action": {"type": "message", "label": "🥗 健康清爽版", "text": "吃什麼 健康"}},
                     {"type": "button", "style": "primary", "color": "#C62828", "height": "sm",
                      "action": {"type": "message", "label": "🍖 享樂滿足版", "text": "吃什麼 享樂"}},
                     {"type": "button", "style": "primary", "color": "#E65100", "height": "sm",
                      "action": {"type": "message", "label": "⚡ 快速方便版", "text": "吃什麼 快速"}},
                 ]},
             }}]


def build_food_message(text: str) -> list:
    """今天吃什麼 — 主路由"""
    text_s = text.strip()

    # 解析風格和區域（例如「吃什麼 健康 台南東區」）
    style = "享樂"  # 預設
    if any(w in text_s for w in ["健康", "清爽", "低卡", "減脂"]):
        style = "健康"
    elif any(w in text_s for w in ["快速", "方便", "省時", "懶得"]):
        style = "快速"
    elif any(w in text_s for w in ["享樂", "好吃", "過癮", "大吃", "犒賞"]):
        style = "享樂"

    # 解析區域
    area = ""
    area_match = re.search(r'(台南|高雄|台北|台中|新北|桃園|新竹|嘉義|屏東|宜蘭|花蓮|台東)\S{0,6}', text_s)
    if area_match:
        area = area_match.group(0)

    # 純呼叫主選單（沒有風格關鍵字且不是內部按鈕觸發）
    if text_s in ["今天吃什麼", "晚餐吃什麼", "午餐吃什麼", "吃什麼", "晚餐推薦", "午餐推薦"]:
        return build_food_menu()

    return build_food_flex(style, area)


# ─── 周末活動推薦 ──────────────────────────────────────

_ACTIVITY_DB = {
    "戶外踏青": [
        {"name": "陽明山國家公園", "desc": "火山地形、花海、登山步道，四季皆宜", "area": "台北"},
        {"name": "太平山國家森林遊樂區", "desc": "雲海、檜木林、原始森林，超療癒", "area": "宜蘭"},
        {"name": "合歡山", "desc": "高山草原、冬天賞雪，壯觀視野", "area": "南投"},
        {"name": "墾丁國家公園", "desc": "海灘、珊瑚礁、熱帶風情，全年可玩", "area": "屏東"},
        {"name": "奮起湖", "desc": "老街、森林鐵路便當，小鎮氛圍超好", "area": "嘉義"},
        {"name": "七股鹽山", "desc": "鹽田生態、台灣鹽博物館，老少皆宜", "area": "台南"},
        {"name": "壽山自然公園", "desc": "獼猴、海景步道、市區旁輕鬆踏青", "area": "高雄"},
        {"name": "清境農場", "desc": "高山牧場、歐式風情、雲霧繚繞", "area": "南投"},
        {"name": "九份老街", "desc": "山城夜景、紅燈籠、芋圓必吃", "area": "新北"},
        {"name": "花蓮太魯閣", "desc": "峽谷地形、步道健行，台灣最壯觀景點", "area": "花蓮"},
        {"name": "日月潭環湖", "desc": "腳踏車環湖、船遊水社，湖光山色", "area": "南投"},
        {"name": "福壽山農場", "desc": "蘋果園、高山蔬菜，秋冬楓紅超美", "area": "台中"},
        {"name": "北海岸野柳地質公園", "desc": "女王頭、奇岩怪石，地球奇景就在台灣", "area": "新北"},
        {"name": "大雪山森林遊樂區", "desc": "賞鳥天堂、帝雉、黑長尾雉出沒", "area": "台中"},
        {"name": "司馬庫斯部落", "desc": "巨木群、神木步道，遠離塵囂的秘境", "area": "新竹"},
        {"name": "阿里山森林鐵路", "desc": "雲海、神木、日出，台灣高山代表", "area": "嘉義"},
    ],
    "文青咖啡": [
        {"name": "赤峰街商圈", "desc": "台北文青聖地，老屋改造咖啡廳密集", "area": "台北"},
        {"name": "神農街", "desc": "台南百年老街、文創小店、咖啡廳林立", "area": "台南"},
        {"name": "駁二藝術特區", "desc": "高雄港邊倉庫改造，藝術展覽 + 咖啡", "area": "高雄"},
        {"name": "審計新村", "desc": "台中文創聚落，週末市集 + 質感小店", "area": "台中"},
        {"name": "松山文創園區", "desc": "老煙草工廠、設計展覽、咖啡廳", "area": "台北"},
        {"name": "藍晒圖文創園區", "desc": "台南文創地標，特色商店 + 裝置藝術", "area": "台南"},
        {"name": "勝利星村", "desc": "屏東眷村改造，慢活咖啡 + 特色小店", "area": "屏東"},
        {"name": "富錦街", "desc": "台北最美林蔭道，歐式咖啡廳 + 選品店", "area": "台北"},
        {"name": "台中第四信用合作社", "desc": "老銀行改造的質感咖啡廳，必拍打卡點", "area": "台中"},
        {"name": "永康街商圈", "desc": "台北最有味道的老街，咖啡廳 + 書店", "area": "台北"},
        {"name": "台南林百貨", "desc": "日治時代百貨，頂樓神社 + 文創選品", "area": "台南"},
        {"name": "三峽老街", "desc": "清朝古厝、牛角麵包、悠閒午後", "area": "新北"},
        {"name": "鹿港老街", "desc": "鳳眼糕、蚵仔煎、台灣傳統工藝小鎮", "area": "彰化"},
        {"name": "大溪老街", "desc": "日式建築、豆干名產、桃園文青好去處", "area": "桃園"},
    ],
    "親子同樂": [
        {"name": "臺灣科學教育館", "desc": "互動展覽、科學實驗，小孩最愛", "area": "台北"},
        {"name": "兒童新樂園", "desc": "遊樂設施、摩天輪、週末親子首選", "area": "台北"},
        {"name": "麗寶樂園", "desc": "遊樂園 + 水樂園，暑假必去", "area": "台中"},
        {"name": "義大遊樂世界", "desc": "高雄最大樂園，刺激設施超豐富", "area": "高雄"},
        {"name": "國立自然科學博物館", "desc": "恐龍、太空、生命科學館，必去", "area": "台中"},
        {"name": "台南市立動物園", "desc": "免費入場、動物種類多，台南親子必去", "area": "台南"},
        {"name": "海生館（國立海洋生物博物館）", "desc": "全台最大水族館，企鵝 + 鯊魚超壯觀", "area": "屏東"},
        {"name": "新竹市立動物園", "desc": "全台最老動物園，小而美，免費入場", "area": "新竹"},
        {"name": "故宮博物院", "desc": "翠玉白菜、肉形石，帶孩子認識台灣歷史", "area": "台北"},
        {"name": "台北市立天文科學教育館", "desc": "天象儀、太陽望遠鏡，假日免費開放", "area": "台北"},
        {"name": "南科考古館", "desc": "8000年前遺址、古代生活互動體驗", "area": "台南"},
        {"name": "奇美博物館", "desc": "歐式建築、藝術 + 自然史展覽，台南必去", "area": "台南"},
        {"name": "小人國主題樂園", "desc": "縮小版台灣景點模型，孩子玩一整天", "area": "桃園"},
        {"name": "礁溪溫泉公園", "desc": "免費泡腳池、戶外溫泉廣場，親子輕鬆遊", "area": "宜蘭"},
    ],
    "運動健身": [
        {"name": "大佳河濱公園", "desc": "腳踏車道、跑步步道、河岸風光", "area": "台北"},
        {"name": "愛河自行車道", "desc": "高雄愛河沿岸，夜晚也很美", "area": "高雄"},
        {"name": "東豐自行車綠廊", "desc": "舊鐵道改造，景色優美，適合全家", "area": "台中"},
        {"name": "左營蓮池潭", "desc": "環潭慢跑、龍虎塔打卡，假日熱鬧", "area": "高雄"},
        {"name": "大安森林公園", "desc": "台北市中心綠洲，跑步 + 戶外瑜伽", "area": "台北"},
        {"name": "虎頭山公園", "desc": "桃園輕鬆爬山、視野好，假日常見跑者", "area": "桃園"},
        {"name": "關渡自然公園", "desc": "賞鳥 + 自行車，兼顧運動與自然生態", "area": "台北"},
        {"name": "大坑登山步道", "desc": "台中都市裡的健行天堂，1-10號難度各異", "area": "台中"},
        {"name": "旗津海岸公園", "desc": "沙灘慢跑、風車、海景，高雄週末好去處", "area": "高雄"},
        {"name": "羅東運動公園", "desc": "草皮廣大、慢跑步道、湖畔風景優美", "area": "宜蘭"},
        {"name": "南投自行車道（集集綠色隧道）", "desc": "樟樹林蔭大道，騎車穿越超愜意", "area": "南投"},
        {"name": "新店碧潭", "desc": "泛舟 + 吊橋散步，台北近郊輕運動", "area": "新北"},
    ],
    "吃喝玩樂": [
        {"name": "士林夜市", "desc": "台灣最大夜市，必吃大餅包小餅、士林大香腸", "area": "台北"},
        {"name": "花園夜市", "desc": "台南最大夜市，週四六日才有，必訪", "area": "台南"},
        {"name": "六合夜市", "desc": "高雄觀光夜市，海鮮 + 在地小吃", "area": "高雄"},
        {"name": "逢甲夜市", "desc": "台中最熱鬧夜市，創意小吃層出不窮", "area": "台中"},
        {"name": "饒河街觀光夜市", "desc": "台北知名夜市，胡椒餅不能錯過", "area": "台北"},
        {"name": "瑞豐夜市", "desc": "高雄在地人愛去的夜市，週末才開", "area": "高雄"},
        {"name": "廟口夜市", "desc": "基隆海鮮小吃集中地，天婦羅、鼎邊銼必吃", "area": "基隆"},
        {"name": "羅東夜市", "desc": "宜蘭特色小吃，三星蔥餅、卜肉超好吃", "area": "宜蘭"},
        {"name": "大溪豆干老街", "desc": "各種豆干口味試吃掃貨，伴手禮首選", "area": "桃園"},
        {"name": "新竹城隍廟商圈", "desc": "貢丸湯、米粉炒，新竹小吃一次掃完", "area": "新竹"},
        {"name": "嘉義文化路夜市", "desc": "雞肉飯、火雞肉飯，嘉義人的驕傲", "area": "嘉義"},
        {"name": "林森夜市", "desc": "台南在地人才知道的夜市，不觀光不踩雷", "area": "台南"},
    ],
}


def build_activity_flex(category: str, area: str = "") -> list:
    """隨機挑 3 個活動推薦"""
    pool = _ACTIVITY_DB.get(category, [])
    if area:
        filtered = [a for a in pool if area[:2] in a.get("area", "")]
        if not filtered:
            filtered = pool
    else:
        filtered = pool

    picks = _random.sample(filtered, min(3, len(filtered)))
    colors = {
        "戶外踏青": "#2E7D32", "文青咖啡": "#4527A0", "親子同樂": "#E65100",
        "運動健身": "#1565C0", "吃喝玩樂": "#C62828",
    }
    color = colors.get(category, "#FF8C42")
    area_label = f"（{area}）" if area else ""

    items = []
    for i, act in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {act['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3},
                {"type": "text", "text": act.get("area", ""), "size": "xs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": act["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📍 Google Maps 導航",
                        "uri": _maps_url(act["name"], act.get("area", ""))}},
        ]
        if i < len(picks)-1:
            items.append({"type": "separator", "margin": "sm"})

    cats = list(_ACTIVITY_DB.keys())
    next_cat = cats[(cats.index(category) + 1) % len(cats)]
    return [{"type": "flex", "altText": f"周末活動 — {category}",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🗓️ 周末去哪{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": category,
                                 "color": "#FFFFFF", "size": "xs", "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"周末 {category} {area}"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": f"換{next_cat}",
                                                      "text": f"周末 {next_cat} {area}"}},
                     ]},
                 ]},
             }}]


def build_activity_menu() -> list:
    """周末活動 — 主選單"""
    return [{"type": "flex", "altText": "周末去哪？",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#5B9BD5",
                            "contents": [
                                {"type": "text", "text": "🗓️ 周末去哪？", "color": "#FFFFFF",
                                 "size": "lg", "weight": "bold"},
                                {"type": "text", "text": "幫你找好玩的地方！",
                                 "color": "#DDEEFF", "size": "xs", "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "選一個你想玩的類型 👇", "size": "sm", "color": "#555555"},
                     {"type": "text", "text": "也可以說「台南 戶外踏青」「台北 文青咖啡」",
                      "size": "xs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": "#2E7D32", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🌿 戶外踏青", "text": "周末 戶外踏青"}},
                         {"type": "button", "style": "primary", "color": "#4527A0", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "☕ 文青咖啡", "text": "周末 文青咖啡"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": "#E65100", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "👶 親子同樂", "text": "周末 親子同樂"}},
                         {"type": "button", "style": "primary", "color": "#1565C0", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動健身", "text": "周末 運動健身"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#C62828", "height": "sm",
                      "action": {"type": "message", "label": "🍜 吃喝玩樂", "text": "周末 吃喝玩樂"}},
                 ]},
             }}]


def build_activity_area_picker(category: str) -> list:
    """周末活動 — 選擇城市"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00"}
    color = colors.get(category, "#5B9BD5")
    areas = ["台北", "新北", "桃園", "新竹", "台中", "台南", "高雄", "屏東", "宜蘭", "花蓮", "嘉義", "南投"]
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
    return [{"type": "flex", "altText": f"周末{category}在哪個城市？",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🗓️ 你在哪個城市？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」景點",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_activity_message(text: str) -> list:
    """周末活動 — 主路由"""
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
        elif any(w in text_s for w in ["咖啡", "文青", "藝文", "展覽"]):
            category = "文青咖啡"
        elif any(w in text_s for w in ["小孩", "親子", "家庭", "帶小孩"]):
            category = "親子同樂"
        elif any(w in text_s for w in ["運動", "跑步", "騎車", "健身"]):
            category = "運動健身"
        elif any(w in text_s for w in ["夜市", "美食", "吃", "逛街"]):
            category = "吃喝玩樂"

    # 解析區域
    area = ""
    area_match = re.search(r'(台南|高雄|台北|台中|新北|桃園|新竹|嘉義|屏東|宜蘭|花蓮|台東)', text_s)
    if area_match:
        area = area_match.group(0)

    if not category:
        return build_activity_menu()
    # 有類別但沒指定區域 → 先問在哪個城市
    if not area:
        return build_activity_area_picker(category)
    return build_activity_flex(category, area)


# ─── 對話路由 ─────────────────────────────────────

def build_welcome_message() -> list:
    """歡迎訊息 + 快速選單"""
    return [{
        "type": "flex",
        "altText": "嗨！我是你的生活超級助理 ✨",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1C2B4A",
                "paddingAll": "lg",
                "contents": [
                    {"type": "text", "text": "✨ 生活超級助理",
                     "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                    {"type": "text", "text": "你的日常好夥伴，什麼都能問我！",
                     "color": "#FFFFFFBB", "size": "sm", "margin": "xs"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "paddingAll": "lg",
                "contents": [
                    {"type": "text", "text": "👇 我可以幫你做這些事",
                     "size": "sm", "weight": "bold", "color": "#1C2B4A"},
                    {"type": "separator", "margin": "sm"},
                    # 3C
                    {"type": "box", "layout": "horizontal", "margin": "sm", "spacing": "sm",
                     "contents": [
                         {"type": "text", "text": "📱", "size": "sm", "flex": 0},
                         {"type": "text", "text": "3C 推薦", "size": "sm", "weight": "bold",
                          "color": "#FF8C42", "flex": 2},
                         {"type": "text", "text": "手機/筆電/平板選購建議", "size": "xs",
                          "color": "#8D6E63", "flex": 5, "wrap": True},
                     ]},
                    # 吃什麼
                    {"type": "box", "layout": "horizontal", "margin": "xs", "spacing": "sm",
                     "contents": [
                         {"type": "text", "text": "🍽️", "size": "sm", "flex": 0},
                         {"type": "text", "text": "今天吃什麼", "size": "sm", "weight": "bold",
                          "color": "#E65100", "flex": 2},
                         {"type": "text", "text": "健康/享樂/快速餐廳推薦", "size": "xs",
                          "color": "#8D6E63", "flex": 5, "wrap": True},
                     ]},
                    # 周末
                    {"type": "box", "layout": "horizontal", "margin": "xs", "spacing": "sm",
                     "contents": [
                         {"type": "text", "text": "🗓️", "size": "sm", "flex": 0},
                         {"type": "text", "text": "周末去哪", "size": "sm", "weight": "bold",
                          "color": "#5C6BC0", "flex": 2},
                         {"type": "text", "text": "戶外/咖啡/親子/運動活動", "size": "xs",
                          "color": "#8D6E63", "flex": 5, "wrap": True},
                     ]},
                    # 健康
                    {"type": "box", "layout": "horizontal", "margin": "xs", "spacing": "sm",
                     "contents": [
                         {"type": "text", "text": "💪", "size": "sm", "flex": 0},
                         {"type": "text", "text": "健康小幫手", "size": "sm", "weight": "bold",
                          "color": "#43A047", "flex": 2},
                         {"type": "text", "text": "BMI 計算/睡眠/壓力紓解", "size": "xs",
                          "color": "#8D6E63", "flex": 5, "wrap": True},
                     ]},
                    # 金錢
                    {"type": "box", "layout": "horizontal", "margin": "xs", "spacing": "sm",
                     "contents": [
                         {"type": "text", "text": "💰", "size": "sm", "flex": 0},
                         {"type": "text", "text": "金錢小幫手", "size": "sm", "weight": "bold",
                          "color": "#00897B", "flex": 2},
                         {"type": "text", "text": "薪資規劃/信用卡/保險建議", "size": "xs",
                          "color": "#8D6E63", "flex": 5, "wrap": True},
                     ]},
                    {"type": "separator", "margin": "sm"},
                    {"type": "text",
                     "text": "🔍 防詐辨識  ⚖️ 法律常識  也都有！",
                     "size": "xs", "color": "#8D6E63", "margin": "sm"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#FF8C42", "flex": 1,
                          "action": {"type": "message", "label": "📱 3C推薦", "text": "推薦手機"}},
                         {"type": "button", "style": "primary", "color": "#E65100", "flex": 1,
                          "action": {"type": "message", "label": "🍽️ 吃什麼", "text": "今天吃什麼"}},
                         {"type": "button", "style": "primary", "color": "#5C6BC0", "flex": 1,
                          "action": {"type": "message", "label": "🗓️ 周末", "text": "周末去哪"}},
                     ]},
                    {"type": "box", "layout": "horizontal", "spacing": "sm", "margin": "sm",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#43A047", "flex": 1,
                          "action": {"type": "message", "label": "💪 健康", "text": "健康小幫手"}},
                         {"type": "button", "style": "primary", "color": "#00897B", "flex": 1,
                          "action": {"type": "message", "label": "💰 金錢", "text": "金錢小幫手"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "action": {"type": "message", "label": "🛠️ 更多", "text": "其他工具"}},
                     ]},
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
                     "action": {"type": "uri", "label": "📞 撥打 165 反詐專線",
                                "uri": "tel:165"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🔄 回主選單", "text": "你好"}},
                ]
            }
        }
    }]


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
    """所有工具選單"""
    return [{
        "type": "flex", "altText": "所有工具",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#2D2D2D",
                "contents": [
                    {"type": "text", "text": "🛠️ 生活小幫手工具箱",
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "選擇你需要的服務",
                     "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "📱 3C 工具", "size": "xs",
                     "color": "#FF8C42", "weight": "bold"},
                    {"type": "button", "style": "primary", "color": "#FF8C42", "height": "sm",
                     "action": {"type": "message", "label": "📱 3C 推薦小幫手",
                                "text": "推薦手機"}},
                    {"type": "separator", "margin": "sm"},
                    {"type": "text", "text": "🛡️ 安全 & 法律", "size": "xs",
                     "color": "#C0392B", "weight": "bold", "margin": "sm"},
                    {"type": "button", "style": "primary", "color": "#C0392B", "height": "sm",
                     "action": {"type": "message", "label": "🔍 防詐辨識",
                                "text": "防詐辨識"}},
                    {"type": "button", "style": "primary", "color": "#1C2B4A", "height": "sm",
                     "margin": "sm",
                     "action": {"type": "message", "label": "⚖️ 法律常識",
                                "text": "法律常識"}},
                    {"type": "separator", "margin": "sm"},
                    {"type": "text", "text": "💚 生活健康", "size": "xs",
                     "color": "#2E7D32", "weight": "bold", "margin": "sm"},
                    {"type": "button", "style": "primary", "color": "#43A047", "height": "sm",
                     "action": {"type": "message", "label": "💪 健康小幫手",
                                "text": "健康小幫手"}},
                    {"type": "button", "style": "primary", "color": "#00897B", "height": "sm",
                     "margin": "sm",
                     "action": {"type": "message", "label": "💰 金錢小幫手",
                                "text": "金錢小幫手"}},
                    {"type": "separator", "margin": "sm"},
                    {"type": "text", "text": "🍽️ 今日生活", "size": "xs",
                     "color": "#E65100", "weight": "bold", "margin": "sm"},
                    {"type": "button", "style": "primary", "color": "#E65100", "height": "sm",
                     "action": {"type": "message", "label": "🍽️ 今天吃什麼",
                                "text": "今天吃什麼"}},
                    {"type": "button", "style": "primary", "color": "#5C6BC0", "height": "sm",
                     "margin": "sm",
                     "action": {"type": "message", "label": "🗓️ 周末去哪",
                                "text": "周末去哪"}},
                ]
            }
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


def handle_text_message(text: str) -> list:
    """主路由：分析文字，決定回覆什麼"""
    text = text.strip()
    text_lower = text.lower()

    # ── 0-a. 這款適合我嗎（產品卡片按鈕，必須最優先攔截）──────
    if text.startswith("這款適合我嗎"):
        product_name = text.replace("這款適合我嗎", "").strip()
        return build_suitability_message(product_name)

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

    # ── 4.5 比價查詢 ─────────────────────────────────
    if any(w in text for w in ["比價", "最便宜", "哪裡買便宜", "價格比較", "biggo", "飛比"]):
        return build_compare_price_message(text)

    # ── 4.6 健康小幫手 ───────────────────────────────
    if any(w in text for w in ["健康小幫手", "健康", "BMI", "bmi", "身高", "體重", "減肥", "瘦身",
                                "失眠", "睡不著", "睡眠", "睡不好", "壓力大", "焦慮",
                                "減重", "肥胖", "運動建議", "睡眠改善", "壓力紓解",
                                "幫我算BMI"]):
        return build_health_message(text)

    # ── 4.7 金錢小幫手 ───────────────────────────────
    if any(w in text for w in ["金錢小幫手", "存錢", "理財", "月薪", "薪水", "薪資", "預算規劃",
                                "信用卡", "循環利息", "保險", "醫療險", "儲蓄",
                                "記帳", "怎麼存", "信用卡使用", "保險建議", "金錢"]):
        return build_money_message(text)

    # ── 4.8 今天吃什麼 ──────────────────────────────
    if any(w in text for w in ["吃什麼", "吃啥", "晚餐", "午餐", "早餐",
                                "吃飯", "外食", "今天吃", "推薦餐廳", "餐廳推薦",
                                "吃什麼好", "要吃什麼"]):
        return build_food_message(text)

    # ── 4.9 周末活動 ────────────────────────────────
    if any(w in text for w in ["周末", "週末", "假日", "出去玩", "去哪玩",
                                "活動推薦", "景點推薦", "玩什麼", "去哪裡",
                                "踏青", "咖啡廳", "親子", "週末活動"]):
        return build_activity_message(text)

    # ── 5. 防詐辨識 ──────────────────────────────────
    if any(w in text for w in ["防詐", "詐騙", "可疑", "165", "是詐騙嗎", "防詐辨識"]):
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

    if any(w in text for w in ["更多功能", "其他工具", "還有什麼", "其他功能", "工具箱"]):
        return build_tools_menu()

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
        "text": "嗨！我是 3C 推薦小幫手 🛍️\n\n"
                "我可以幫你：\n"
                "📱 推薦最適合的手機/筆電/平板\n"
                "🎯 根據你的生活需求客製化推薦\n"
                "🔍 用白話解釋看不懂的規格\n"
                "📖 告訴你買 3C 要注意什麼\n\n"
                "可以點下方選單，或直接跟我說你的需求 😊"
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
