"""Intent dispatcher routes for classified text messages."""

from __future__ import annotations

LATEST = "\u6700\u65b0"
TREND = "\u8da8\u52e2"
RANKING = "\u6392\u884c"
FRAUD_ANALYZE = [
    "\u9632\u8a50\u8fa8\u8b58",
    "\u5e6b\u6211\u5206\u6790",
    "\u9019\u662f\u4e0d\u662f\u8a50\u9a19",
    "\u9632\u8a50",
    "\u8a50\u9a19",
]
CONSUMER_DISPUTE = "\u6d88\u8cbb\u7d1b\u722d"
LABOR_DISPUTE = "\u52de\u8cc7\u7d1b\u722d"
LOCATION_LABEL = "\u5206\u4eab\u4f4d\u7f6e"


def build_emergency_message() -> list:
    return [{
        "type": "flex",
        "altText": "緊急聯絡資訊",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#C0392B",
                "contents": [
                    {"type": "text", "text": "🚨 緊急聯絡資訊", "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "165 防詐騙專線", "size": "sm", "weight": "bold", "color": "#C0392B"},
                    {"type": "text", "text": "110 警察報案", "size": "sm", "weight": "bold"},
                    {"type": "text", "text": "113 保護專線", "size": "sm"},
                    {"type": "text", "text": "1955 勞工諮詢", "size": "sm"},
                    {"type": "text", "text": "1950 消費者諮詢", "size": "sm"},
                ],
            },
        },
    }]


def build_parking_location_prompt() -> list:
    return [{
        "type": "text",
        "text": "📍 請分享您的位置，我來幫您找附近停車場",
        "quickReply": {
            "items": [{
                "type": "action",
                "action": {
                    "type": "location",
                    "label": LOCATION_LABEL,
                },
            }],
        },
    }]


def route_intent_dispatch(
    text: str,
    user_id: str,
    *,
    classify_intent,
    parse_height_weight,
    food_keywords,
    build_weather_message,
    build_food_message,
    build_health_message,
    spend_overspent,
    build_money_message,
    build_activity_message,
    build_upgrade_message,
    build_fraud_trends,
    build_fraud_result,
    build_fraud_intro,
    legal_qa,
    build_legal_answer,
    build_legal_guide_intro,
    build_tools_menu,
):
    intent = classify_intent(text, parse_height_weight, list(food_keywords))

    if intent == "weather":
        return build_weather_message(text, user_id=user_id)
    if intent == "food":
        return build_food_message(text, user_id=user_id)
    if intent == "health":
        return build_health_message(text)
    if intent == "overspent":
        return spend_overspent()
    if intent == "money":
        return build_money_message(text)
    if intent == "activity":
        return build_activity_message(text, user_id=user_id)
    if intent == "tech":
        return build_upgrade_message(text)
    if intent == "safety":
        if any(w in text for w in [LATEST, TREND, RANKING]):
            return build_fraud_trends()
        stripped = text
        for kw in FRAUD_ANALYZE:
            stripped = stripped.replace(kw, "").strip()
        return build_fraud_result(stripped) if len(stripped) >= 10 else build_fraud_intro()
    if intent == "legal":
        for topic in legal_qa.keys():
            if topic in text:
                return build_legal_answer(topic)
        return build_legal_guide_intro()
    if intent == "consumer":
        return build_legal_answer(CONSUMER_DISPUTE)
    if intent == "labor":
        return build_legal_answer(LABOR_DISPUTE)
    if intent == "emergency":
        return build_emergency_message()
    if intent == "parking":
        return build_parking_location_prompt()
    if intent == "tools":
        return build_tools_menu()

    return None
