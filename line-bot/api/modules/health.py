from modules.health_nutrition import build_calorie_result
from modules.health_nutrition import build_exercise_result
from modules.health_nutrition import _EXERCISE_DB

import re
from modules.health_basic import build_bmi_flex
from modules.health_basic import build_diet_advice
from modules.health_basic import build_sleep_advice
from modules.health_basic import build_stress_advice
from modules.health_basic import build_water_intake
from modules.health_basic import parse_height_weight
from modules.health_mood import build_mood_support

import urllib.parse

# ── 食物熱量資料庫（台灣常見外食，每份 kcal）──

# ── 運動消耗計算（每分鐘 kcal，以 60kg 為基準）──


def build_health_menu() -> list:
    ACCENT = "#43A047"
    return [{"type": "flex", "altText": "健康小幫手",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "💪 健康小幫手",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "你的隨身健康顧問",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "想了解什麼？直接問或點下方 👇",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "📊 BMI", "text": "幫我算BMI"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔥 食物熱量", "text": "食物熱量查詢"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動消耗", "text": "運動消耗計算"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💧 喝水量", "text": "每日喝水量"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🥗 減重", "text": "減肥方法"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "😴 睡眠", "text": "睡眠改善"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "😰 壓力紓解", "text": "壓力紓解"}},
                 ]},
             }}]


def build_health_message(text: str) -> list:
    if any(w in text for w in ["熱量", "卡路里", "幾卡", "幾大卡"]):
        return build_calorie_result(text)
    if "食物熱量" in text:
        return [{"type": "text", "text": "🔥 輸入食物名稱查熱量\n\n"
                 "例如：\n「珍珠奶茶熱量」\n「排骨便當幾卡」\n「雞排熱量多少」"}]

    if any(w in text for w in ["運動消耗", "運動熱量"]):
        return build_exercise_result(text)
    has_exercise = any(ex in text for ex in _EXERCISE_DB.keys())
    has_time = bool(re.search(r'\d+\s*(?:分|小時|hr)', text, re.I))
    if has_exercise and has_time:
        return build_exercise_result(text)

    if "喝水" in text:
        m = re.search(r'(\d{2,3}(?:\.\d)?)\s*(?:kg|公斤)', text, re.I)
        if m:
            return build_water_intake(float(m.group(1)))
        m2 = re.search(r'體重\s*(\d{2,3})', text)
        if m2:
            return build_water_intake(float(m2.group(1)))
        return [{"type": "text", "text": "💧 請告訴我你的體重\n\n例如：「喝水 65公斤」"}]

    height, weight = parse_height_weight(text)
    if height and weight and 100 <= height <= 220 and 20 <= weight <= 200:
        return build_bmi_flex(height, weight)
    if any(w in text for w in ["bmi", "BMI", "幫我算", "算一下"]):
        return [{"type": "text", "text": "請告訴我你的身高和體重 😊\n\n例如：\n「我身高 170cm，體重 75kg」\n「170公分 65公斤」"}]

    if any(w in text for w in ["失眠", "睡不著", "睡不好", "睡眠", "一直醒"]):
        return build_sleep_advice()
    if any(w in text for w in ["減肥", "瘦身", "減重", "變瘦", "肥胖"]):
        return build_diet_advice()
    if any(w in text for w in ["壓力", "焦慮", "心情不好", "很煩", "紓壓"]):
        return build_stress_advice()
    return build_health_menu()
