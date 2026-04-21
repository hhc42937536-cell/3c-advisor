"""Hardware upgrade guidance builders."""

from __future__ import annotations

from modules.tech_upgrade_cards import build_upgrade_gpu
from modules.tech_upgrade_cards import build_upgrade_performance_check
from modules.tech_upgrade_cards import build_upgrade_ram
from modules.tech_upgrade_cards import build_upgrade_ssd


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
