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
    import urllib.parse
    price = p.get("price", "")
    brand = p.get("brand", "")
    name = p.get("name", "")[:30]
    tag = p.get("tag", "")
    pros = p.get("pros", "")[:40]
    cons = p.get("cons", "")[:30]
    spec_line = spec_to_plain_line(p)

    # 購買連結（引導去 PChome 搜尋，讓用戶自己比較）
    search_q = urllib.parse.quote(f"{brand} {name}")
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
                    "action": {"type": "uri", "label": "🛒 查詢這款商品", "uri": pchome_url},
                },
                {
                    "type": "button", "style": "secondary",
                    "action": {"type": "message", "label": "❓ 這款適合我嗎？", "text": f"這款適合我嗎 {brand} {name}"},
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
}

STEP_COLORS = {"手機": "#FF8C42", "筆電": "#5B9BD5", "平板": "#4CAF50"}


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
    device_map = {"手機": "phone", "筆電": "laptop", "平板": "tablet"}
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


def build_tools_menu() -> list:
    """其他工具選單 — 未來加工具只要在這裡加按鈕"""
    return [{
        "type": "flex",
        "altText": "工具選單",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#5B9BD5",
                "contents": [
                    {"type": "text", "text": "🛠️ 所有工具", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "選擇你需要的服務", "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    # ── 現有工具 ──────────────────────
                    {"type": "text", "text": "現有工具", "size": "xs", "color": "#8D6E63", "weight": "bold"},
                    {"type": "button", "style": "primary", "color": "#FF8C42",
                     "action": {"type": "message", "label": "📱 3C 推薦小幫手", "text": "你好"}},
                    # ── 未來工具（加在這裡）──────────
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "即將推出", "size": "xs", "color": "#BDBDBD", "weight": "bold", "margin": "md"},
                    {"type": "button", "style": "secondary", "color": "#BDBDBD",
                     "action": {"type": "message", "label": "🎫 搶票助手（開發中）", "text": "搶票助手"}},
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
        biggo_url = f"https://biggo.com.tw/search/{q}"
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
                "工作": ["工作"], "學習": ["學生"], "創作": ["工作"],
                "日常": [], "閱讀": [],
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

    # ── 5. 其他工具 ──────────────────────────────────
    if any(w in text for w in ["其他工具", "還有什麼", "其他功能"]):
        return build_tools_menu()

    # ── 6. 偵測裝置 → 啟動問卷 ──────────────────────
    device = detect_device(text)
    if device:
        device_name = {"phone": "手機", "laptop": "筆電", "tablet": "平板"}.get(device, "")
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
