"""
LINE Bot Webhook — 生活優轉 LifeUturn
=================================
Vercel Serverless Function (Python)
處理所有 LINE 訊息，根據內容路由到不同模組。
"""

import sys
import json
import os
import re
import hashlib
import hmac
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

# 確保 Vercel 能找到 modules/ 與 utils/（api/ 目錄加入 sys.path）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── LINE 設定 ─────────────────────────────────────────────
CHANNEL_SECRET        = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN  = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_BOT_ID           = os.environ.get("LINE_BOT_ID", "")
ADMIN_USER_ID         = os.environ.get("ADMIN_USER_ID", "")
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
SUPABASE_URL          = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY          = os.environ.get("SUPABASE_KEY", "")
TDX_CLIENT_ID         = os.environ.get("TDX_CLIENT_ID", "")
TDX_CLIENT_SECRET     = os.environ.get("TDX_CLIENT_SECRET", "")

# ─── utils ─────────────────────────────────────────────────
from utils.line_api    import reply_message, push_message
from utils.line_api    import broadcast_message as _broadcast_message
from utils.line_api    import verify_signature
from utils.supabase    import log_usage
from utils.supabase    import record_eaten as _record_eaten, get_eaten as _get_eaten
from utils.redis       import redis_get as _redis_get, redis_set as _redis_set
from utils.google_places import nearby_places as _nearby_places_google
from utils.google_places import text_search as _text_search_places
from utils.google_places import photo_url as _places_photo_url
from utils.intent      import classify_intent

# ─── modules ───────────────────────────────────────────────
from modules.food     import (
    build_food_message, build_group_dining_message,
    build_specialty_shops, build_city_specialties,
    build_food_restaurant_flex,
    _ALL_CITIES, _STYLE_KEYWORDS, _ALL_FOOD_KEYWORDS,
)
from modules.weather  import (
    build_weather_message, build_weather_region_picker,
    build_morning_summary, _fetch_cwa_weather,
    _fetch_quick_oil, _fetch_quick_rates,
    _set_user_city, _get_user_city, _build_morning_city_picker,
)
from modules.health   import build_health_message, build_mood_support, parse_height_weight
from modules.money    import (
    build_money_message, build_spending_decision, _spend_overspent,
    build_credit_card_result,
)
from modules.activity import build_activity_message
from modules.tech     import (
    build_recommendation_message, build_suitability_message,
    build_upgrade_message, build_spec_explainer, build_scenario_menu,
    build_wizard_who, build_wizard_use, build_wizard_budget,
    parse_wizard_state, detect_device, parse_budget, detect_use,
)
from modules.safety   import (
    analyze_fraud, build_fraud_intro, build_fraud_trends, build_fraud_result,
    build_legal_guide_intro, build_legal_answer, build_tools_menu, LEGAL_QA,
)
from modules.parking  import build_parking_flex, _build_post_parking_food



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
        "altText": "嗨！我是你的生活優轉，你的日常心靈小夥伴",
        "contents": {
            "type": "bubble",
            "size": "mega",
            # ── Header：溫暖明亮風格 ──────────────────────────
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#FFFDE7",
                "paddingTop": "20px", "paddingBottom": "14px",
                "paddingStart": "16px", "paddingEnd": "16px",
                "contents": [
                    # 品牌名稱列
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
                                    {"type": "text", "text": "想輕鬆、想吃好、想出去玩，都可以找我 🌱",
                                     "color": "#8D6E63", "size": "xs", "margin": "xs"},
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
                            _tile("🍽️", "吃什麼",  "3秒決定", "今天吃啥",
                                  "#BF360C", "#FFF0E6", "今天吃什麼"),
                            _tile("🌤️", "天氣穿搭", "出門必看", "要帶傘嗎",
                                  "#0277BD", "#E1F5FE", "天氣"),
                            _tile("🗓️", "近期活動", "周末",   "去哪玩",
                                  "#3949AB", "#ECEDFF", "近期活動"),
                        ]
                    },
                    # Row 2
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
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#F0F4FF",
                        "cornerRadius": "8px",
                        "paddingAll": "8px",
                        "margin": "sm",
                        "action": {"type": "message", "label": "好累", "text": "好累"},
                        "contents": [
                            {"type": "text", "text": "🌿",
                             "size": "sm", "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 好累、不知道幹嘛、心情不太對，都可以找我說說 🌱",
                             "size": "xxs", "color": "#3949AB", "flex": 1,
                             "gravity": "center", "wrap": True},
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal",
                        "backgroundColor": "#F5F5F5",
                        "cornerRadius": "8px",
                        "paddingAll": "8px",
                        "margin": "sm",
                        "action": {"type": "message", "label": "其他工具", "text": "其他工具"},
                        "contents": [
                            {"type": "text", "text": "🛠️",
                             "size": "sm", "flex": 0, "gravity": "center"},
                            {"type": "text",
                             "text": " 下方選單 →「所有工具」有防詐騙、法律常識、勞工權益等更多功能",
                             "size": "xxs", "color": "#555555", "flex": 1,
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

    # ── 1. 打招呼 / 幫助 ────────────────────────────
    greetings = ["你好", "嗨", "hi", "hello", "哈囉", "安安", "開始", "幫助", "help", "選單", "功能"]
    if any(text_lower == g or text_lower.startswith(g) for g in greetings):
        return build_welcome_message()

    # ── 1.5 情緒觸發（比功能路由早，讓日常抱怨被接住）──────────
    _mood_kws = ["心情不好", "心情差", "好煩", "煩死", "煩透了", "超煩",
                 "好累", "累死", "累透了", "超累", "好疲憊", "疲憊",
                 "難過", "不開心", "很鬱悶", "鬱悶", "低落", "很喪",
                 "不想出門", "不想動", "沒動力", "提不起勁",
                 "無聊死", "好無聊", "超無聊", "不知道幹嘛", "沒事幹",
                 "焦慮", "壓力大", "壓力好大", "很有壓力", "喘不過氣",
                 "沒目標", "沒有目標", "人生沒目標", "不知道目標",
                 "什麼都不想做", "甚麼都不想做", "什麼都不想", "甚麼都不想",
                 "活著沒意思", "沒意思", "沒意義", "人生無聊", "迷茫", "迷失",
                 "被罵", "被念", "被嗆", "被兇", "被罵慘", "被罵死",
                 "吵架", "吵起來", "跟他吵", "跟她吵", "又吵", "大吵",
                 "被說", "被批評", "被否定", "被嫌", "被討厭",
                 "被欺負", "被霸凌", "被排擠", "被孤立", "沒有朋友",
                 "考不好", "考差了", "成績差", "成績不好", "考砸了", "被當掉",
                 "被老師罵", "老師罵我", "作業寫不完", "功課好難", "不想上學",
                 "讀書好累", "唸書好累", "考試壓力"]
    if any(w in text for w in _mood_kws):
        log_usage(user_id, "mood_support")
        return build_mood_support(text)

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

    # ── 精確格式先判斷（不進評分，避免破壞特殊流程）──────

    if text in ("換城市",):
        return build_weather_region_picker()

    # 活動＋城市前綴（如「活動台南」）
    if text.startswith("活動") and len(text) > 2:
        return build_activity_message(text, user_id=user_id)

    # 聚餐子功能
    if any(w in text for w in ["聚餐", "約飯", "朋友聚", "家庭聚", "公司聚", "同學聚",
                                "包廂", "圍爐", "尾牙", "春酒", "生日餐廳",
                                "辦桌", "大桌", "多人聚餐", "找餐廳"]):
        return build_group_dining_message(text)

    if text.startswith("特色名店 "):
        parts = text[5:].strip().split(" ", 1)
        if len(parts) == 2:
            return build_specialty_shops(parts[0], parts[1])

    if "地方特色" in text and any(c in text for c in _ALL_CITIES):
        city_match = next((c for c in _ALL_CITIES if c in text), "")
        return build_city_specialties(city_match)

    if "我要分享位置找美食" in text:
        return build_food_message(text, user_id=user_id)

    # 防詐+法律合併入口（Rich Menu 按鈕，精確指令）
    if text.strip() in ["防詐法律", "防詐&法律", "防詐與法律"]:
        return [{
            "type": "flex", "altText": "防詐騙 ＆ 法律常識",
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                    "contents": [
                        {"type": "text", "text": "🛡️⚖️ 防詐騙 ＆ 法律常識",
                         "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                        {"type": "text", "text": "選擇你需要的功能",
                         "color": "#8892B0", "size": "xs", "margin": "xs"},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical",
                    "spacing": "md", "paddingAll": "14px",
                    "contents": [
                        {"type": "box", "layout": "vertical", "spacing": "xs",
                         "contents": [
                             {"type": "button", "style": "primary", "color": "#C0392B",
                              "action": {"type": "message", "label": "🛡️ 防詐騙辨識", "text": "防詐辨識"}},
                             {"type": "text", "text": "貼上可疑訊息讓我分析",
                              "color": "#888888", "size": "xs", "align": "center"},
                         ]},
                        {"type": "box", "layout": "vertical", "spacing": "xs",
                         "contents": [
                             {"type": "button", "style": "primary", "color": "#3949AB",
                              "action": {"type": "message", "label": "⚖️ 法律常識", "text": "法律常識"}},
                             {"type": "text", "text": "租屋／勞資／消費糾紛",
                              "color": "#888888", "size": "xs", "align": "center"},
                         ]},
                    ]
                }
            }
        }]

    # 功能建議 / 許願池（精確指令）
    if text in ("回報", "許願", "許願池", "功能建議", "功能回報", "意見回報"):
        return build_feedback_intro()

    if any(w in text for w in ["我想要功能", "希望有功能"]) or \
       (text.startswith("建議") and len(text) >= 4):
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

    # ══ 評分制意圖分類 ════════════════════════════════════
    # 每個關鍵字帶權重（3/2/1），分數最高者獲勝。
    # 「165 55」→ health+5（身高體重信號），不再被 safety 搶走。
    # 新功能只需在 utils/intent.py 加關鍵字，不用管順序。
    _intent = classify_intent(text, parse_height_weight, list(_ALL_FOOD_KEYWORDS))

    if _intent == "weather":
        return build_weather_message(text, user_id=user_id)
    if _intent == "food":
        return build_food_message(text, user_id=user_id)
    if _intent == "health":
        return build_health_message(text)
    if _intent == "overspent":
        return _spend_overspent()
    if _intent == "money":
        return build_money_message(text)
    if _intent == "activity":
        return build_activity_message(text, user_id=user_id)
    if _intent == "tech":
        return build_upgrade_message(text)
    if _intent == "safety":
        if "最新" in text or "手法" in text or "排行" in text:
            return build_fraud_trends()
        stripped = text
        for kw in ["防詐辨識", "幫我看", "這是詐騙嗎", "防詐", "詐騙"]:
            stripped = stripped.replace(kw, "").strip()
        return build_fraud_result(stripped) if len(stripped) >= 10 else build_fraud_intro()
    if _intent == "legal":
        for topic in LEGAL_QA.keys():
            if topic in text:
                return build_legal_answer(topic)
        return build_legal_guide_intro()
    if _intent == "consumer":
        return build_legal_answer("消費者保護")
    if _intent == "labor":
        return build_legal_answer("勞資糾紛")
    if _intent == "emergency":
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
    if _intent == "parking":
        if user_id:
            _redis_set(f"food_locate:{user_id}", "", ttl=1)  # 清除食物定位 flag，避免互相干擾
        return [{
            "type": "text",
            "text": "🅿️ 點下方「📍 分享位置」，我立刻幫你找附近停車場！",
            "quickReply": {
                "items": [{
                    "type": "action",
                    "action": {
                        "type": "location",
                        "label": "📍 分享我的位置"
                    }
                }]
            }
        }]
    if _intent == "tools":
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



def _city_from_coords(lat: float, lon: float) -> str:
    """用 GPS 座標反查台灣城市（address 欄位空白時的 fallback）"""
    _BOXES = [
        ("台北", 25.00, 25.21, 121.44, 121.67),
        ("新北", 24.75, 25.30, 121.25, 122.05),
        ("基隆", 25.08, 25.22, 121.60, 121.82),
        ("桃園", 24.78, 25.08, 120.93, 121.40),
        ("新竹", 24.67, 24.92, 120.85, 121.25),
        ("苗栗", 24.28, 24.72, 120.60, 121.07),
        ("台中", 23.95, 24.45, 120.45, 121.15),
        ("彰化", 23.82, 24.15, 120.35, 120.78),
        ("南投", 23.50, 24.20, 120.53, 121.35),
        ("雲林", 23.50, 23.87, 120.10, 120.73),
        ("嘉義", 23.20, 23.62, 120.22, 120.70),
        ("台南", 22.78, 23.35, 119.95, 120.52),
        ("高雄", 22.38, 23.00, 120.15, 120.85),
        ("屏東", 21.90, 22.78, 120.35, 120.90),
        ("宜蘭", 24.52, 24.90, 121.47, 122.03),
        ("花蓮", 23.20, 24.55, 121.32, 121.87),
        ("台東", 22.18, 23.30, 120.87, 121.60),
        ("澎湖", 23.20, 23.80, 119.30, 119.75),
        ("金門", 24.36, 24.52, 118.20, 118.48),
        ("連江", 26.12, 26.22, 119.90, 120.05),
    ]
    for city, lat_min, lat_max, lon_min, lon_max in _BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return city
    return ""

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
            import threading as _th
            results = {}

            # 1. 預熱停車場（TDX）
            _WARM_CITIES = ["Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", "Kaohsiung"]
            token = _get_tdx_token()
            def _warm_parking(city):
                try:
                    if _redis_get(f"tdx_lots_{city}") is None:
                        lots = _tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=6)
                        if lots:
                            _redis_set(f"tdx_lots_{city}", lots, ttl=86400)
                        results[f"parking_{city}"] = f"fetched {len(lots)}"
                    else:
                        results[f"parking_{city}"] = "cache_hit"
                except Exception as e:
                    results[f"parking_{city}"] = f"err:{e}"

            # 2. 預熱天氣（6 大城市，15 分鐘 TTL）
            _WEATHER_WARM = ["台北", "新北", "台中", "台南", "高雄", "桃園"]
            def _warm_weather(city):
                try:
                    if not _redis_get(f"cwa_wx:{city}"):
                        _fetch_cwa_weather(city)
                        results[f"wx_{city}"] = "fetched"
                    else:
                        results[f"wx_{city}"] = "cache_hit"
                except Exception as e:
                    results[f"wx_{city}"] = f"err:{e}"

            # 3. 預熱匯率 + 油價（TTL 1h / 6h）
            def _warm_rates():
                try:
                    if not _redis_get("morning_rates"):
                        _fetch_quick_rates()
                        results["rates"] = "fetched"
                    else:
                        results["rates"] = "cache_hit"
                except Exception as e:
                    results["rates"] = f"err:{e}"

            def _warm_oil():
                try:
                    if not _redis_get("morning_oil"):
                        _fetch_quick_oil()
                        results["oil"] = "fetched"
                    else:
                        results["oil"] = "cache_hit"
                except Exception as e:
                    results["oil"] = f"err:{e}"

            threads = (
                [_th.Thread(target=_warm_parking, args=(c,), daemon=True) for c in _WARM_CITIES] +
                [_th.Thread(target=_warm_weather, args=(c,), daemon=True) for c in _WEATHER_WARM] +
                [_th.Thread(target=_warm_rates, daemon=True),
                 _th.Thread(target=_warm_oil,   daemon=True)]
            )
            for t in threads: t.start()
            for t in threads: t.join(timeout=8)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "warmed", "detail": results}).encode())
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

        elif parsed.path == "/api/food_test":
            # 診斷美食推薦：?lat=22.9876&lon=120.2131&city=台南
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            _lat = float(qs.get("lat", ["22.9876"])[0])
            _lon = float(qs.get("lon", ["120.2131"])[0])
            _city = qs.get("city", ["台南"])[0]
            result = {"lat": _lat, "lon": _lon, "city": _city,
                      "GOOGLE_KEY_SET": bool(GOOGLE_PLACES_API_KEY)}
            # 測 Google Places
            try:
                places = _nearby_places_google(_lat, _lon, radius=1500)
                result["places_count"] = len(places)
                result["places_sample"] = [p.get("name") for p in places[:3]]
            except Exception as e:
                result["places_error"] = str(e)
            # 測 build_post_parking_food
            try:
                msgs = _build_post_parking_food(_city, _lat, _lon)
                result["msgs_count"] = len(msgs)
                result["msg_type"] = msgs[0].get("type") if msgs else None
                if msgs and msgs[0].get("contents", {}).get("type") == "carousel":
                    result["bubbles"] = len(msgs[0]["contents"]["contents"])
            except Exception as e:
                import traceback
                result["food_error"] = str(e)
                result["food_traceback"] = traceback.format_exc()[-500:]
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

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
        elif parsed.path == "/api/setup_richmenu":
            # ── 一次性：把 Rich Menu 第一排 LIFF 按鈕改成 message 類型 ──
            log = []
            try:
                headers_line = {"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"}

                # 1. 取現有 rich menu 清單
                req = urllib.request.Request("https://api.line.me/v2/bot/richmenu/list", headers=headers_line)
                with urllib.request.urlopen(req, timeout=10) as r:
                    menus = json.loads(r.read().decode())["richmenus"]
                old_id = menus[0]["richMenuId"] if menus else None
                log.append(f"old_id={old_id}")

                # 2. 建新 Rich Menu（同版型，前三個改 message）
                new_menu = {
                    "size": {"width": 2500, "height": 1686},
                    "selected": True,
                    "name": "生活優轉選單（無LIFF版）",
                    "chatBarText": "✨ 點我開啟功能選單",
                    "areas": [
                        {"bounds": {"x": 0,    "y": 0,    "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "今天吃什麼", "text": "今天吃什麼"}},
                        {"bounds": {"x": 833,  "y": 0,    "width": 834,  "height": 562},
                         "action": {"type": "message", "label": "近期活動",  "text": "近期活動"}},
                        {"bounds": {"x": 1667, "y": 0,    "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "天氣+穿搭", "text": "天氣"}},
                        {"bounds": {"x": 0,    "y": 562,  "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "健康小幫手", "text": "健康小幫手"}},
                        {"bounds": {"x": 833,  "y": 562,  "width": 834,  "height": 562},
                         "action": {"type": "message", "label": "金錢小幫手", "text": "金錢小幫手"}},
                        {"bounds": {"x": 1667, "y": 562,  "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "找車位",    "text": "找車位"}},
                        {"bounds": {"x": 0,    "y": 1124, "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "3C 推薦",   "text": "推薦手機"}},
                        {"bounds": {"x": 833,  "y": 1124, "width": 834,  "height": 562},
                         "action": {"type": "message", "label": "防詐騙",    "text": "防詐辨識"}},
                        {"bounds": {"x": 1667, "y": 1124, "width": 833,  "height": 562},
                         "action": {"type": "message", "label": "法律常識",  "text": "法律常識"}},
                    ]
                }
                body = json.dumps(new_menu, ensure_ascii=False).encode("utf-8")
                req2 = urllib.request.Request(
                    "https://api.line.me/v2/bot/richmenu",
                    data=body,
                    headers={**headers_line, "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req2, timeout=10) as r:
                    new_id = json.loads(r.read().decode())["richMenuId"]
                log.append(f"new_id={new_id}")

                # 3. 複製舊 Rich Menu 的圖片到新的
                if old_id:
                    img_req = urllib.request.Request(
                        f"https://api-data.line.me/v2/bot/richmenu/{old_id}/content",
                        headers=headers_line
                    )
                    with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                        img_data = img_resp.read()
                        content_type = img_resp.headers.get("Content-Type", "image/png")
                    upload_req = urllib.request.Request(
                        f"https://api-data.line.me/v2/bot/richmenu/{new_id}/content",
                        data=img_data,
                        headers={**headers_line, "Content-Type": content_type}
                    )
                    urllib.request.urlopen(upload_req, timeout=15).close()
                    log.append("image_copied=ok")

                # 4. 設為全體預設
                set_req = urllib.request.Request(
                    f"https://api.line.me/v2/bot/user/all/richmenu/{new_id}",
                    data=b"",
                    method="POST",
                    headers=headers_line
                )
                urllib.request.urlopen(set_req, timeout=10).close()
                log.append("set_default=ok")

                # 5. 刪所有舊的（含孤立選單）
                for m in menus:
                    mid = m["richMenuId"]
                    if mid == new_id:
                        continue
                    try:
                        del_req = urllib.request.Request(
                            f"https://api.line.me/v2/bot/richmenu/{mid}",
                            method="DELETE",
                            headers=headers_line
                        )
                        urllib.request.urlopen(del_req, timeout=10).close()
                        log.append(f"deleted={mid}")
                    except Exception as de:
                        log.append(f"delete_failed={mid}:{de}")

                result = {"ok": True, "log": log}
            except Exception as e:
                result = {"ok": False, "error": str(e), "log": log}

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))

        elif parsed.path == "/api/richmenu_info":
            # ── 查目前 Rich Menu 設定（一次性診斷）────────────────
            try:
                req = urllib.request.Request(
                    "https://api.line.me/v2/bot/richmenu/list",
                    headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8"))
            except Exception as e:
                data = {"error": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

        elif parsed.path == "/api/debug_routes":
            # ── Rich menu 路由測試 ─────────────────────────
            import traceback as _tb
            test_cases = ["推薦手機", "今天吃什麼", "周末去哪", "健康小幫手", "金錢小幫手", "其他工具"]
            results = {}
            import sys as _sys
            results["python_version"] = _sys.version
            for t in test_cases:
                try:
                    msgs = handle_text_message(t, user_id="debug_test")
                    results[t] = {"ok": True, "count": len(msgs), "type": msgs[0].get("type") if msgs else None}
                except Exception as e:
                    results[t] = {"ok": False, "error": str(e), "trace": _tb.format_exc()}
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(results, ensure_ascii=False, indent=2).encode("utf-8"))
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

                # Postback → 吃過了記錄
                if event.get("type") == "postback":
                    reply_token = event.get("replyToken", "")
                    pdata = event.get("postback", {}).get("data", "")
                    if pdata.startswith("ate:"):
                        parts = pdata[4:].split(":", 1)
                        rname = parts[0]
                        rcity = parts[1] if len(parts) > 1 else ""
                        _record_eaten(user_id, rname, rcity)
                        reply_message(reply_token, [{"type": "text",
                            "text": f"✅ 記住了！\n下次不再推薦「{rname}」給你 😊"}])
                        log_usage(user_id, "food", sub_action="吃過了", city=rcity)
                    continue

                # 位置訊息 → 食物定位 or 找車位
                if event.get("type") == "message" and event.get("message", {}).get("type") == "location":
                    reply_token = event.get("replyToken", "")
                    lat = float(event["message"].get("latitude", 0))
                    lon = float(event["message"].get("longitude", 0))
                    _addr_raw = event["message"].get("address", "")
                    city_hint = _addr_raw[:6]
                    # 從地址解析城市，address 空白時用座標反查
                    _parking_city = ""
                    for _c in _ALL_CITIES:
                        if _c in _addr_raw:
                            _parking_city = _c[:2]
                            break
                    if not _parking_city:
                        _parking_city = _city_from_coords(lat, lon)
                    if _parking_city:
                        _set_user_city(user_id, _parking_city)

                    # ── 食物定位意圖（來自「吃什麼」Quick Reply）──
                    _food_flag = _redis_get(f"food_locate:{user_id}")
                    print(f"[food_locate] flag={_food_flag!r} city={_parking_city} lat={lat:.4f} lon={lon:.4f}")
                    if _food_flag:
                        _redis_set(f"food_locate:{user_id}", "", ttl=1)  # 清除 flag
                        try:
                            food_cards = _build_post_parking_food(
                                _parking_city or "", lat, lon, user_id=user_id, addr=_addr_raw)
                            if not food_cards and _parking_city:
                                # fallback: 直接顯示城市餐廳卡（"餐廳 台南" 不觸發主選單路由）
                                food_cards = build_food_message(
                                    f"餐廳 {_parking_city}", user_id=user_id)
                            if not food_cards:
                                food_cards = build_food_message("餐廳", user_id=user_id)
                            reply_message(reply_token, food_cards)
                        except Exception as _fe:
                            import traceback; traceback.print_exc()
                            print(f"[food_locate] build failed: {_fe}")
                            _fb_city = _parking_city or ""
                            reply_message(reply_token,
                                build_food_message(f"餐廳 {_fb_city}" if _fb_city else "餐廳",
                                                   user_id=user_id))
                        log_usage(user_id, "food", sub_action="位置定位", city=_parking_city)
                        continue
                    print(f"[webhook] location: {lat},{lon} city={_parking_city} addr={_addr_raw[:20]!r}")

                    def _build_food_inline(_city, _lat, _lon, _uid):
                        try:
                            return _build_post_parking_food(_city, _lat, _lon, user_id=_uid, addr=_addr_raw)
                        except Exception as _fe:
                            import traceback; traceback.print_exc()
                            print(f"[food_inline] FAILED: {_fe}")
                            return []

                    # 停車後問候卡片（附近美食 / 活動 選一）
                    _city2 = _parking_city[:2] if _parking_city else ""
                    _after_parking_card = {"type": "flex", "altText": "需要推薦附近美食或活動嗎？",
                        "contents": {"type": "bubble", "size": "kilo",
                            "body": {"type": "box", "layout": "vertical",
                                "paddingAll": "16px", "spacing": "sm",
                                "contents": [
                                    {"type": "text", "text": "需要順便幫你推薦嗎？ 😊",
                                     "weight": "bold", "size": "sm", "color": "#1A1F3A"},
                                    {"type": "text", "text": "選一個，馬上幫你找",
                                     "size": "xs", "color": "#888888", "margin": "xs"},
                                ]},
                            "footer": {"type": "box", "layout": "vertical",
                                "spacing": "sm", "paddingAll": "12px",
                                "contents": [
                                    {"type": "button", "style": "primary", "color": "#FF6B35",
                                     "height": "sm",
                                     "action": {"type": "message",
                                                "label": "🍜 附近美食推薦",
                                                "text": "📍 我要分享位置找美食"}},
                                    {"type": "button", "style": "secondary", "height": "sm",
                                     "action": {"type": "message",
                                                "label": "🎉 附近活動",
                                                "text": f"近期活動 {_city2}" if _city2 else "近期活動"}},
                                ]}}}

                    # 快速路徑：快取命中
                    cached = _peek_parking_cache(lat, lon)
                    if cached:
                        reply_message(reply_token, cached)
                        push_message(user_id, [_after_parking_card])
                        log_usage(user_id, "parking", sub_action="傳位置_cached", city=city_hint)
                    else:
                        reply_message(reply_token, [{"type": "text",
                            "text": "📍 定位成功！\n🔍 正在搜尋附近車位..."}])
                        try:
                            messages = build_parking_flex(lat, lon, city=_parking_city)
                            push_message(user_id, messages + [_after_parking_card])
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
                            _liff_city = _get_user_city(user_id) or _city_from_coords(lat, lon)
                            _liff_city2 = _liff_city[:2] if _liff_city else ""
                            _liff_after_card = {"type": "flex", "altText": "需要推薦附近美食或活動嗎？",
                                "contents": {"type": "bubble", "size": "kilo",
                                    "body": {"type": "box", "layout": "vertical",
                                        "paddingAll": "16px", "spacing": "sm",
                                        "contents": [
                                            {"type": "text", "text": "需要順便幫你推薦嗎？ 😊",
                                             "weight": "bold", "size": "sm", "color": "#1A1F3A"},
                                            {"type": "text", "text": "選一個，馬上幫你找",
                                             "size": "xs", "color": "#888888", "margin": "xs"},
                                        ]},
                                    "footer": {"type": "box", "layout": "vertical",
                                        "spacing": "sm", "paddingAll": "12px",
                                        "contents": [
                                            {"type": "button", "style": "primary", "color": "#FF6B35",
                                             "height": "sm",
                                             "action": {"type": "message",
                                                        "label": "🍜 附近美食推薦",
                                                        "text": "📍 我要分享位置找美食"}},
                                            {"type": "button", "style": "secondary", "height": "sm",
                                             "action": {"type": "message",
                                                        "label": "🎉 附近活動",
                                                        "text": f"近期活動 {_liff_city2}" if _liff_city2 else "近期活動"}},
                                        ]}}}
                            if cached:
                                reply_message(reply_token, cached)
                                push_message(user_id, [_liff_after_card])
                                log_usage(user_id, "parking", sub_action="liff_cached")
                            else:
                                reply_message(reply_token, [{"type": "text",
                                    "text": "📍 定位成功！\n🔍 正在搜尋附近車位..."}])
                                messages = build_parking_flex(lat, lon, city=_liff_city)
                                push_message(user_id, messages + [_liff_after_card])
                                log_usage(user_id, "parking", sub_action="liff_auto")
                        except Exception as pe:
                            import traceback; traceback.print_exc()
                            push_message(user_id, [{"type": "text", "text": "定位失敗，請稍後再試 🙏"}])
                        continue

                    # ── 早安（直接在 do_POST 處理，不經 handle_text_message）──
                    _morning_kw = ["早安", "早上好", "早啊", "早哦", "morning", "good morning", "早起了", "早安安"]
                    if any(w in user_text.lower() for w in _morning_kw):
                        try:
                            msgs = build_morning_summary(user_text, user_id=user_id)
                            reply_message(reply_token, msgs)
                            log_usage(user_id, "morning_summary")
                        except Exception as _me:
                            import traceback; traceback.print_exc()
                            reply_message(reply_token, [{"type": "text", "text": "早安！系統忙碌中，請稍後再試 🙏"}])
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
