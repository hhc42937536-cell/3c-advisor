"""靜態訊息建構：歡迎選單、購買指南、比價"""

from __future__ import annotations

import urllib.parse

from modules.tech_guides import (
    build_compare_price_message,
    build_purchase_guide_message,
)

__all__ = [
    "build_compare_price_message",
    "build_purchase_guide_message",
    "build_welcome_message",
]


def build_welcome_message() -> list:
    """歡迎訊息 + 快速選單（精美磚塊版）"""

    def _tile(icon, name, line1, line2, color, light_bg, action_text):
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
        "altText": "嗨！我是你的生活優轉，你的日常心靈小夥伴",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#FFFDE7",
                "paddingTop": "20px", "paddingBottom": "14px",
                "paddingStart": "16px", "paddingEnd": "16px",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal", "spacing": "md",
                        "contents": [
                            {"type": "text", "text": "🌟", "size": "xxl",
                             "flex": 0, "gravity": "center"},
                            {
                                "type": "box", "layout": "vertical", "flex": 1,
                                "contents": [
                                    {"type": "text", "text": "生活優轉",
                                     "color": "#E65100", "size": "xl", "weight": "bold"},
                                    {"type": "text",
                                     "text": "想輕鬆、想吃好、想出去玩，都可以找我 🌱",
                                     "color": "#8D6E63", "size": "xs", "margin": "xs"},
                                ]
                            }
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "md",
                        "contents": [
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#FFCCBC", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "🍽️ 吃什麼",
                                           "size": "xxs", "color": "#BF360C",
                                           "align": "center"}]},
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#C5CAE9", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "🗓️ 週末活動",
                                           "size": "xxs", "color": "#283593",
                                           "align": "center"}]},
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#C8E6C9", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "contents": [{"type": "text", "text": "🌱 心情小站",
                                           "size": "xxs", "color": "#1B5E20",
                                           "align": "center"}]},
                            {"type": "box", "layout": "vertical", "flex": 1,
                             "backgroundColor": "#FFF9C4", "cornerRadius": "6px",
                             "paddingAll": "5px",
                             "action": {"type": "message", "label": "今天想輕鬆一下",
                                        "text": "今天想輕鬆一下"},
                             "contents": [{"type": "text", "text": "💛 輕鬆一下",
                                           "size": "xxs", "color": "#F57F17",
                                           "align": "center"}]},
                        ]
                    }
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": "👇 點選功能，馬上開始",
                     "size": "xs", "color": "#777777", "margin": "xs"},
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "sm",
                        "contents": [
                            _tile("🍽️", "吃什麼", "3秒決定", "今天吃啥",
                                  "#BF360C", "#FFF0E6", "今天吃什麼"),
                            _tile("🌤️", "天氣穿搭", "出門必看", "要帶傘嗎",
                                  "#0277BD", "#E1F5FE", "天氣"),
                            _tile("🗓️", "近期活動", "周末", "去哪玩",
                                  "#3949AB", "#ECEDFF", "近期活動"),
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "margin": "sm",
                        "contents": [
                            _tile("🍻", "聚餐地點", "選地點", "幾個人",
                                  "#E65100", "#FFF3EE", "聚餐"),
                            _tile("🌿", "情緒支援", "好累嗎", "說說看",
                                  "#2E7D32", "#E8F5E9", "好累"),
                            _tile("🛡️", "防詐辨識", "可疑訊息", "貼過來",
                                  "#C62828", "#FFEBEE", "防詐辨識"),
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#FFFBEA", "cornerRadius": "8px",
                        "paddingAll": "8px", "margin": "md",
                        "action": {"type": "message", "label": "早安", "text": "早安"},
                        "contents": [
                            {"type": "text", "text": "☀️", "size": "sm",
                             "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 打「早安」→ 天氣＋今日小驚喜，每天一個好梗跟朋友聊",
                             "size": "xxs", "color": "#B45309", "flex": 1,
                             "gravity": "center", "wrap": True},
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#F0F4FF", "cornerRadius": "8px",
                        "paddingAll": "8px", "margin": "sm",
                        "action": {"type": "message", "label": "好累", "text": "好累"},
                        "contents": [
                            {"type": "text", "text": "🌿", "size": "sm",
                             "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 好累、不知道幹嘛、心情不太對，都可以找我說說 🌱",
                             "size": "xxs", "color": "#3949AB", "flex": 1,
                             "gravity": "center", "wrap": True},
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#F5F5F5", "cornerRadius": "8px",
                        "paddingAll": "8px", "margin": "sm",
                        "action": {"type": "message", "label": "其他工具", "text": "其他工具"},
                        "contents": [
                            {"type": "text", "text": "🛠️", "size": "sm",
                             "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 下方選單 →「所有工具」有防詐騙、法律常識、勞工權益等更多功能",
                             "size": "xxs", "color": "#555555", "flex": 1,
                             "gravity": "center", "wrap": True},
                        ]
                    },
                    {"type": "separator", "margin": "md"},
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
