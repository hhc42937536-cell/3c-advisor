"""
3C 推薦、硬體升級諮詢、導引式問卷、規格說明、購買指南模組
=============================================================
從 webhook.py 萃取的獨立模組，保留所有產品推薦邏輯。
"""

import json
import os
import re
import urllib.request
import urllib.parse

# ─── 產品資料來源 ─────────────────────────────────
PRODUCTS_URL = os.environ.get(
    "PRODUCTS_URL",
    "https://hhc42937536-cell.github.io/3c-advisor/products.json",
)

# LINE Bot ID（用於分享邀請連結）
LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")

# ─── 產品資料快取 ─────────────────────────────────
_products_cache: dict = {"data": None, "ts": 0}


def _bot_invite_text() -> str:
    """生成 bot 邀請文字（有 ID 就附連結，沒有就純文字）"""
    if LINE_BOT_ID:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{LINE_BOT_ID}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"


def load_products() -> dict:
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

    def _btn(label: str, use: str, color: str) -> dict:
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
    if any(w in text for w in ["RAM", "ram", "記憶體", "加記憶體", "加RAM", "內存"]):
        return build_upgrade_ram()
    if any(w in text for w in ["SSD", "ssd", "硬碟", "固態", "換硬碟", "HDD"]):
        return build_upgrade_ssd()
    if any(w in text for w in ["GPU", "gpu", "顯卡", "顯示卡", "獨顯", "RTX", "GTX", "RX"]):
        return build_upgrade_gpu()
    if any(w in text for w in ["效能分析", "瓶頸", "為什麼慢", "電腦很慢", "電腦效能"]):
        return build_upgrade_performance_check()
    return build_upgrade_menu()


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
    state: dict = {"device": device_key, "device_name": parts[0]}
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


# ─── 購買指南 & 比價 ──────────────────────────────

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
