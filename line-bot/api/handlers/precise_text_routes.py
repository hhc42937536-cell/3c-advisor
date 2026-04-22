"""Precise text-route helpers for webhook text handling."""

from __future__ import annotations

import json
import urllib.request

TXT_CHANGE_CITY = "\u63db\u57ce\u5e02"
TXT_ACTIVITY = "\u6d3b\u52d5"
TXT_SPECIAL_SHOPS = "\u7279\u8272\u540d\u5e97 "
TXT_LOCAL_SPECIAL = "\u5730\u65b9\u7279\u8272"
TXT_SHARE_LOCATION_FOOD = "\u6211\u8981\u5206\u4eab\u4f4d\u7f6e\u627e\u7f8e\u98df"
TXT_SAFETY_LAW = ["\u9632\u8a50\u6cd5\u5f8b", "\u9632\u8a50&\u6cd5\u5f8b", "\u9632\u8a50\u8207\u6cd5\u5f8b"]
TXT_FEEDBACK_MENU = ["\u56de\u5831", "\u8a31\u9858", "\u8a31\u9858\u6c60", "\u529f\u80fd\u5efa\u8b70", "\u529f\u80fd\u56de\u5831", "\u610f\u898b\u56de\u5831"]
TXT_SUGGEST_TRIGGERS = ["\u6211\u60f3\u8981\u529f\u80fd", "\u5e0c\u671b\u6709\u529f\u80fd"]
TXT_SUGGEST_PREFIX = "\u5efa\u8b70"
GROUP_DINING_KWS = [
    "\u805a\u9910", "\u7d04\u98ef", "\u670b\u53cb\u805a", "\u5bb6\u5ead\u805a", "\u516c\u53f8\u805a", "\u540c\u5b78\u805a",
    "\u5305\u5ec2", "\u570d\u7210", "\u5c3e\u7259", "\u6625\u9152", "\u751f\u65e5\u9910\u5ef3", "\u8fa6\u684c", "\u5927\u684c", "\u591a\u4eba\u805a\u9910", "\u627e\u9910\u5ef3",
]


def build_safety_law_entry() -> list:
    return [{
        "type": "flex",
        "altText": "\u9632\u8a50\u9a19\u8207\u6cd5\u5f8b\u5e38\u8b58",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1A1F3A",
                "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "\u9632\u8a50\u9a19 \u8207 \u6cd5\u5f8b\u5e38\u8b58", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "\u9078\u64c7\u4f60\u8981\u7684\u529f\u80fd", "color": "#8892B0", "size": "xs", "margin": "xs"},
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "14px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "button", "style": "primary", "color": "#C0392B", "action": {"type": "message", "label": "\u9632\u8a50\u9a19\u8fa8\u8b58", "text": "\u9632\u8a50\u8fa8\u8b58"}},
                            {"type": "text", "text": "\u8cbc\u4e0a\u53ef\u7591\u8a0a\u606f\u8b93\u6211\u5206\u6790", "color": "#888888", "size": "xs", "align": "center"},
                        ],
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "button", "style": "primary", "color": "#3949AB", "action": {"type": "message", "label": "\u6cd5\u5f8b\u5e38\u8b58", "text": "\u6cd5\u5f8b\u5e38\u8b58"}},
                            {"type": "text", "text": "\u79df\u5c4b \u52de\u8cc7 \u6d88\u8cbb\u7d1b\u722d", "color": "#888888", "size": "xs", "align": "center"},
                        ],
                    },
                ],
            },
        },
    }]


def maybe_route_precise_text(
    text: str,
    user_id: str,
    *,
    all_cities,
    build_weather_region_picker,
    build_activity_message,
    build_group_dining_message,
    build_specialty_shops,
    build_city_specialties,
    build_food_message,
    build_feedback_intro,
    handle_user_suggestion,
    channel_access_token,
):
    if text == TXT_CHANGE_CITY:
        return build_weather_region_picker()

    if text.startswith(TXT_ACTIVITY) and len(text) > len(TXT_ACTIVITY):
        return build_activity_message(text, user_id=user_id)

    if any(w in text for w in GROUP_DINING_KWS):
        return build_group_dining_message(text)

    if text.startswith(TXT_SPECIAL_SHOPS):
        parts = text[len(TXT_SPECIAL_SHOPS):].strip().split(" ", 1)
        if len(parts) == 2:
            return build_specialty_shops(parts[0], parts[1])

    if TXT_LOCAL_SPECIAL in text and any(c in text for c in all_cities):
        city_match = next((c for c in all_cities if c in text), "")
        return build_city_specialties(city_match)

    if TXT_SHARE_LOCATION_FOOD in text or "目的地美食" in text:
        return build_food_message(text, user_id=user_id)

    if text.strip() in TXT_SAFETY_LAW:
        return build_safety_law_entry()

    if text in TXT_FEEDBACK_MENU:
        return build_feedback_intro()

    if any(w in text for w in TXT_SUGGEST_TRIGGERS) or (text.startswith(TXT_SUGGEST_PREFIX) and len(text) >= 4):
        display_name = ""
        try:
            profile_req = urllib.request.Request(
                f"https://api.line.me/v2/bot/profile/{user_id}",
                headers={"Authorization": f"Bearer {channel_access_token}"},
            )
            profile = json.loads(urllib.request.urlopen(profile_req, timeout=5).read())
            display_name = profile.get("displayName", "")
        except Exception:
            pass
        return handle_user_suggestion(text, user_id, display_name)

    return None
