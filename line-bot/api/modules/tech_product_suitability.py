"""3C product suitability analysis builders."""

from __future__ import annotations

import re
import urllib.parse

from modules.tech_product_data import detect_device
from modules.tech_product_data import load_products


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
