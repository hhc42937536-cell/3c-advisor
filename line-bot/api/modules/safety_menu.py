"""Safety tools menu builder."""

from __future__ import annotations


def build_tools_menu() -> list:
    """生活工具箱選單 — 磚塊格版（4排×3格）。"""

    def _tile(
        icon: str, name: str, hint: str,
        color: str, light_bg: str, trigger: str
    ) -> dict:
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": light_bg,
            "cornerRadius": "12px",
            "paddingAll": "8px",
            "spacing": "xs",
            "action": {"type": "message", "label": name, "text": trigger},
            "contents": [
                {"type": "text", "text": icon, "size": "xxl", "align": "center"},
                {"type": "text", "text": name, "size": "xs", "weight": "bold",
                 "color": color, "align": "center", "margin": "xs"},
                {"type": "text", "text": hint, "size": "xxs",
                 "color": "#888888", "align": "center"},
            ]
        }

    def _row(tiles: list) -> dict:
        return {
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "margin": "sm", "contents": tiles
        }

    return [{
        "type": "flex", "altText": "🗃️ 所有功能",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "🗃️ 所有功能",
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text",
                     "text": "點按鈕，或直接打字告訴我你需要什麼",
                     "color": "#8892B0", "size": "xs", "margin": "xs"},
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "margin": "md", "contents": [
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "天氣", "text": "天氣"},
                          "contents": [{"type": "text", "text": "打「天氣」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "好累", "text": "好累"},
                          "contents": [{"type": "text", "text": "打「好累」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "吃什麼", "text": "今天吃什麼"},
                          "contents": [{"type": "text", "text": "打「吃什麼」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                     ]},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": "👇 點選功能，馬上開始",
                     "size": "xs", "color": "#777777", "margin": "xs"},
                    # Row 1
                    _row([
                        _tile("🍽️", "吃什麼",  "3秒決定",  "#BF360C", "#FFF0E6", "今天吃什麼"),
                        _tile("🌤️", "天氣",    "出門必看",  "#0277BD", "#E1F5FE", "天氣"),
                        _tile("🗓️", "近期活動", "週末去哪",  "#283593", "#ECEDFF", "近期活動"),
                    ]),
                    # Row 2
                    _row([
                        _tile("🍻", "聚餐地點", "選地點",   "#E65100", "#FFF3EE", "聚餐"),
                        _tile("🌿", "情緒支援", "說說看",   "#2E7D32", "#E8F5E9", "好累"),
                        _tile("🛡️", "防詐辨識", "貼訊息",   "#C62828", "#FFEBEE", "防詐辨識"),
                    ]),
                    # Row 3
                    _row([
                        _tile("⚖️", "法律常識", "應對方式", "#4527A0", "#EDE7F6", "法律常識"),
                        _tile("📱", "3C推薦",  "手機選購",  "#E64A00", "#FFF3EE", "推薦手機"),
                        _tile("💰", "比價",    "不花冤枉錢", "#00695C", "#E0F2F1", "比價"),
                    ]),
                    # Row 4
                    _row([
                        _tile("🤔", "消費決策", "值不值",   "#6A1B9A", "#F3E5F5", "消費決策"),
                        _tile("🔧", "硬體升級", "RAM/SSD", "#37474F", "#ECEFF1", "硬體升級"),
                        _tile("☀️", "早安",    "天氣+提醒", "#F57F17", "#FFFBEA", "早安"),
                    ]),
                    {"type": "separator", "margin": "md"},
                    # 底部小工具列
                    {
                        "type": "box", "layout": "horizontal",
                        "margin": "sm", "paddingTop": "4px",
                        "contents": [
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "許願", "text": "許願"},
                             "contents": [
                                 {"type": "text", "text": "💡", "align": "center", "size": "md"},
                                 {"type": "text", "text": "許願", "size": "xxs",
                                  "color": "#6C5CE7", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "回報", "text": "回報"},
                             "contents": [
                                 {"type": "text", "text": "📋", "align": "center", "size": "md"},
                                 {"type": "text", "text": "回報", "size": "xxs",
                                  "color": "#546E7A", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "選單", "text": "選單"},
                             "contents": [
                                 {"type": "text", "text": "🏠", "align": "center", "size": "md"},
                                 {"type": "text", "text": "回首頁", "size": "xxs",
                                  "color": "#555555", "align": "center"},
                             ]},
                        ]
                    }
                ]
            },
        }
    }]
