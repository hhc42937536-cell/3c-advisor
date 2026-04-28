"""裝置/預算偵測回退路由（handle_text_message 的最後一關）"""

from __future__ import annotations


def route_device_budget_fallback(
    text: str,
    *,
    detect_device,
    parse_budget,
    detect_use,
    build_recommendation_message,
    build_wizard_who,
) -> list:
    """偵測裝置關鍵字或預算，啟動問卷或直接推薦；完全看不懂則友善引導"""
    device = detect_device(text)
    if device:
        device_name = {"phone": "手機", "laptop": "筆電",
                       "tablet": "平板", "desktop": "桌機"}.get(device, "")
        budget = parse_budget(text)
        uses = detect_use(text)
        if budget or uses:
            return build_recommendation_message(device, budget, uses)
        return build_wizard_who(device_name)

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

    return [{"type": "text",
             "text": "嗨！我是生活優轉 👋\n\n"
                     "我可以幫你：\n"
                     "🍽️ 決定今天吃什麼\n"
                     "🌤️ 查天氣\n"
                     "🗓️ 找週末活動\n"
                     "🛡️ 防詐騙分析\n\n"
                     "輸入「功能」查看所有功能 ✨"}]
