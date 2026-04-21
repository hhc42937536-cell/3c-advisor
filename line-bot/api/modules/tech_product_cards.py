"""3C product Flex card builders."""

from __future__ import annotations

import os
import urllib.parse

from modules.tech_product_data import spec_to_plain_line


LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")


def _bot_invite_text() -> str:
    """生成 bot 邀請文字（有 ID 就附連結，沒有就純文字）"""
    if LINE_BOT_ID:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{LINE_BOT_ID}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"


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
