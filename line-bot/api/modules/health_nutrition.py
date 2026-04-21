"""Calorie and exercise health builders."""

from __future__ import annotations

import re


_CALORIE_DB = {
    # 飯麵主食
    "白飯": {"cal": 280, "unit": "一碗", "note": "約200g"},
    "滷肉飯": {"cal": 510, "unit": "一碗", "note": "含肥肉燥"},
    "雞肉飯": {"cal": 380, "unit": "一碗", "note": "嘉義式"},
    "牛肉麵": {"cal": 550, "unit": "一碗", "note": "紅燒"},
    "排骨便當": {"cal": 780, "unit": "一個", "note": "炸排骨＋三菜"},
    "雞腿便當": {"cal": 820, "unit": "一個", "note": "炸雞腿＋三菜"},
    "控肉飯": {"cal": 580, "unit": "一碗", "note": "滷五花"},
    "乾麵": {"cal": 380, "unit": "一碗", "note": "加肉燥"},
    "水餃": {"cal": 450, "unit": "10顆", "note": "高麗菜豬肉"},
    "鍋貼": {"cal": 520, "unit": "10顆", "note": "煎的比水餃高"},
    "炒飯": {"cal": 620, "unit": "一盤", "note": "蛋炒飯"},
    "拉麵": {"cal": 650, "unit": "一碗", "note": "豚骨"},
    "鍋燒意麵": {"cal": 480, "unit": "一碗", "note": ""},
    "涼麵": {"cal": 430, "unit": "一盤", "note": "含麻醬"},
    "肉粽": {"cal": 520, "unit": "一顆", "note": "南部粽"},
    "碗粿": {"cal": 320, "unit": "一碗", "note": ""},
    "米粉湯": {"cal": 350, "unit": "一碗", "note": ""},
    # 小吃
    "蚵仔煎": {"cal": 480, "unit": "一份", "note": "含醬料"},
    "臭豆腐": {"cal": 400, "unit": "一份", "note": "炸的"},
    "鹽酥雞": {"cal": 550, "unit": "一份", "note": "約200g"},
    "蔥油餅": {"cal": 350, "unit": "一片", "note": "加蛋"},
    "割包": {"cal": 380, "unit": "一個", "note": ""},
    "肉圓": {"cal": 320, "unit": "一顆", "note": "彰化炸的"},
    "麵線": {"cal": 350, "unit": "一碗", "note": "大腸麵線"},
    "胡椒餅": {"cal": 380, "unit": "一個", "note": ""},
    "蛋餅": {"cal": 280, "unit": "一份", "note": "原味"},
    "飯糰": {"cal": 420, "unit": "一個", "note": "傳統"},
    "蘿蔔糕": {"cal": 220, "unit": "一份", "note": "煎的"},
    "滷味": {"cal": 350, "unit": "一份", "note": "中份"},
    # 飲料
    "珍珠奶茶": {"cal": 650, "unit": "一杯700ml", "note": "全糖"},
    "珍奶": {"cal": 650, "unit": "一杯700ml", "note": "全糖"},
    "奶茶": {"cal": 380, "unit": "一杯700ml", "note": "全糖"},
    "紅茶": {"cal": 200, "unit": "一杯700ml", "note": "半糖"},
    "綠茶": {"cal": 150, "unit": "一杯700ml", "note": "半糖"},
    "美式咖啡": {"cal": 10, "unit": "一杯", "note": "黑咖啡"},
    "拿鐵": {"cal": 180, "unit": "一杯", "note": "全脂鮮奶"},
    "豆漿": {"cal": 120, "unit": "一杯", "note": "無糖"},
    "可樂": {"cal": 140, "unit": "一罐330ml", "note": ""},
    "啤酒": {"cal": 150, "unit": "一罐330ml", "note": ""},
    # 其他
    "薑母鴨": {"cal": 800, "unit": "一人份", "note": "含湯底"},
    "火鍋": {"cal": 700, "unit": "一人份", "note": "不含飲料"},
    "韓式炸雞": {"cal": 600, "unit": "一份", "note": ""},
    "燒肉": {"cal": 750, "unit": "一人份", "note": "吃到飽約1200"},
    "披薩": {"cal": 280, "unit": "一片", "note": ""},
    "漢堡": {"cal": 520, "unit": "一個", "note": "速食店"},
    "薯條": {"cal": 380, "unit": "中份", "note": ""},
    "雞排": {"cal": 630, "unit": "一片", "note": "夜市大雞排"},
}


_EXERCISE_DB = {
    "跑步": 10, "慢跑": 8, "快走": 5, "走路": 3.5, "散步": 3,
    "游泳": 9, "騎車": 7, "腳踏車": 7, "自行車": 7,
    "瑜珈": 4, "重訓": 6, "健身": 6, "有氧": 7,
    "籃球": 8, "羽球": 7, "桌球": 5, "網球": 8,
    "跳繩": 11, "拳擊": 10, "爬山": 7, "登山": 7,
    "爬樓梯": 8, "跳舞": 6, "打掃": 3.5, "拖地": 3,
    "棒球": 5, "足球": 8, "排球": 5,
}


def build_calorie_result(query: str) -> list:
    query_clean = query.replace("熱量", "").replace("卡路里", "").replace("多少", "").strip()
    matches = []
    for name, info in _CALORIE_DB.items():
        if query_clean in name or name in query_clean:
            matches.append((name, info))
    if not matches:
        for name, info in _CALORIE_DB.items():
            if any(c in name for c in query_clean if len(c.strip()) > 0):
                matches.append((name, info))

    if not matches:
        return [{"type": "text", "text": f"找不到「{query_clean}」的熱量資料\n\n"
                 "試試看這些關鍵字：\n"
                 "• 主食：滷肉飯、牛肉麵、排骨便當\n"
                 "• 小吃：蚵仔煎、鹽酥雞、雞排\n"
                 "• 飲料：珍珠奶茶、拿鐵、豆漿\n\n"
                 "或直接問「珍奶熱量多少」"}]

    items = []
    for name, info in matches[:5]:
        cal = info["cal"]
        run_min = round(cal / 8)
        bar_len = min(cal // 50, 12)
        bar = "🟩" * min(bar_len, 5) + "🟨" * min(max(bar_len - 5, 0), 4) + "🟥" * max(bar_len - 9, 0)
        note = f"（{info['note']}）" if info.get("note") else ""
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"🍽️ {name}", "weight": "bold",
                 "size": "md", "color": "#2E7D32", "flex": 3},
                {"type": "text", "text": f"{cal} kcal", "weight": "bold",
                 "size": "md", "color": "#C62828", "flex": 2, "align": "end"},
            ]},
            {"type": "text", "text": f"{info['unit']}{note}", "size": "xs",
             "color": "#888888", "margin": "xs"},
            {"type": "text", "text": bar, "size": "xs", "margin": "xs"},
            {"type": "text", "text": f"需慢跑約 {run_min} 分鐘消耗", "size": "xs",
             "color": "#555555", "margin": "xs"},
        ]
        if len(matches) > 1:
            items.append({"type": "separator", "margin": "md"})

    return [{"type": "flex", "altText": "食物熱量查詢",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#2E7D32",
                            "contents": [
                                {"type": "text", "text": "🔥 食物熱量查詢",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "text", "text": "💡 小提示：微糖 = 全糖的70%熱量、去冰不影響熱量",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]


def build_exercise_result(text: str) -> list:
    exercise = ""
    cal_per_min = 0
    for name, cpm in _EXERCISE_DB.items():
        if name in text:
            exercise = name
            cal_per_min = cpm
            break
    if not exercise:
        return [{"type": "text", "text": "支援的運動類型：\n\n"
                 "• 有氧：跑步、慢跑、快走、游泳、騎車、跳繩\n"
                 "• 球類：籃球、羽球、網球、排球\n"
                 "• 其他：瑜珈、重訓、爬山、跳舞\n\n"
                 "輸入格式：「跑步 30分鐘」或「游泳 1小時」"}]

    minutes = 30
    m = re.search(r'(\d+)\s*分', text)
    if m:
        minutes = int(m.group(1))
    else:
        m2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:小時|hr)', text, re.I)
        if m2:
            minutes = int(float(m2.group(1)) * 60)

    total_cal = round(cal_per_min * minutes)
    if total_cal >= 650:
        food_equiv = "一杯全糖珍奶 🧋"
    elif total_cal >= 500:
        food_equiv = "一個排骨便當 🍱"
    elif total_cal >= 350:
        food_equiv = "一碗滷肉飯 🍚"
    elif total_cal >= 200:
        food_equiv = "一杯拿鐵 ☕"
    else:
        food_equiv = "一份蘿蔔糕 🥞"

    return [{"type": "flex", "altText": f"運動消耗：{exercise} {minutes}分鐘",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#1565C0",
                            "contents": [
                                {"type": "text", "text": "🏃 運動熱量消耗",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": exercise, "size": "lg", "weight": "bold",
                          "color": "#1565C0", "flex": 2},
                         {"type": "text", "text": f"{minutes} 分鐘", "size": "lg",
                          "color": "#333333", "flex": 2, "align": "end"},
                     ]},
                     {"type": "separator"},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "消耗熱量", "size": "sm", "color": "#888888", "flex": 2},
                         {"type": "text", "text": f"🔥 {total_cal} kcal", "size": "md",
                          "weight": "bold", "color": "#C62828", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "約等於吃掉", "size": "sm", "color": "#888888", "flex": 2},
                         {"type": "text", "text": food_equiv, "size": "sm",
                          "color": "#555555", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "每分鐘消耗", "size": "xs", "color": "#AAAAAA", "flex": 2},
                         {"type": "text", "text": f"{cal_per_min} kcal/min（以60kg計）", "size": "xs",
                          "color": "#AAAAAA", "flex": 3, "align": "end"},
                     ]},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💡 體重越重消耗越高，此為 60kg 估算值",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]
