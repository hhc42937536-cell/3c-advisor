"""使用者回饋、問題回報、功能建議路由"""

from __future__ import annotations

import datetime as _dt

_FEEDBACK_LOG: list = []


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


def handle_food_feedback(
    text: str,
    user_id: str = "",
    *,
    admin_user_id: str = "",
    push_message=None,
) -> list:
    """處理使用者對餐廳的回饋（好吃/倒閉），並推播通知開發者"""
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    if "好吃" in text:
        shop = text.replace("回報", "").replace("好吃", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "good", "time": ts})
        if admin_user_id and push_message:
            push_message(admin_user_id, [{"type": "text",
                "text": f"👍 使用者回報好吃\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"👍 感謝推薦！已記錄「{shop}」為好吃店家 🎉\n"
                 "你的回饋會幫助其他使用者找到更好的餐廳！"}]
    elif "倒閉" in text or "歇業" in text:
        shop = text.replace("回報", "").replace("倒閉", "").replace("歇業", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "closed", "time": ts})
        if admin_user_id and push_message:
            push_message(admin_user_id, [{"type": "text",
                "text": f"❌ 使用者回報歇業\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"❌ 感謝回報！已標記「{shop}」可能歇業 📝\n"
                 "我們會在下次更新時確認並移除，謝謝你！"}]
    return []


def handle_general_report(
    text: str,
    user_id: str = "",
    *,
    admin_user_id: str = "",
    push_message=None,
) -> list:
    """處理通用回報，推播通知開發者"""
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    content = text.replace("回報", "").strip()
    if len(content) < 2:
        return build_feedback_intro()

    if any(w in content for w in ["bug", "壞", "錯誤", "失敗", "沒反應", "當掉", "跑不出來", "無法", "不能"]):
        tag = "🐛 Bug"
    elif any(w in content for w in ["慢", "卡", "lag", "等很久", "超時", "timeout"]):
        tag = "🐌 效能"
    else:
        tag = "📋 回報"

    if admin_user_id and push_message:
        push_message(admin_user_id, [{"type": "flex", "altText": f"{tag} 使用者回報",
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
             f"📋 收到你的回報！\n\n「{content}」\n\n已通知開發者，會盡快處理 🙏"}]


def handle_user_suggestion(
    text: str,
    user_id: str,
    display_name: str = "",
    *,
    admin_user_id: str = "",
    push_message=None,
) -> list:
    """處理使用者功能建議，推播通知給開發者"""
    ts = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    content = text
    for kw in ["建議", "許願", "功能建議", "我想要", "希望有", "回饋"]:
        content = content.replace(kw, "").strip()
    if len(content) < 2:
        return build_feedback_intro()

    reply = [{"type": "text", "text":
              f"💡 收到你的建議！\n\n「{content}」\n\n已送達開發者，感謝你讓生活優轉變得更好 🙏"}]

    if admin_user_id and push_message:
        name_str = f"（{display_name}）" if display_name else ""
        push_message(admin_user_id, [{"type": "flex", "altText": "💡 新功能建議",
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
