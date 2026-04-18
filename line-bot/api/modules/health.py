import random
import re
import urllib.parse

# ── 食物熱量資料庫（台灣常見外食，每份 kcal）──
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

# ── 運動消耗計算（每分鐘 kcal，以 60kg 為基準）──
_EXERCISE_DB = {
    "跑步": 10, "慢跑": 8, "快走": 5, "走路": 3.5, "散步": 3,
    "游泳": 9, "騎車": 7, "腳踏車": 7, "自行車": 7,
    "瑜珈": 4, "重訓": 6, "健身": 6, "有氧": 7,
    "籃球": 8, "羽球": 7, "桌球": 5, "網球": 8,
    "跳繩": 11, "拳擊": 10, "爬山": 7, "登山": 7,
    "爬樓梯": 8, "跳舞": 6, "打掃": 3.5, "拖地": 3,
    "棒球": 5, "足球": 8, "排球": 5,
}


def parse_height_weight(text: str):
    """從文字解析身高(cm)和體重(kg)，回傳 (height, weight) 或 (None, None)"""
    m = re.search(r'(\d{2,3})\s*(?:cm|公分)', text, re.I)
    h = float(m.group(1)) if m else None
    m2 = re.search(r'(\d{2,3}(?:\.\d)?)\s*(?:kg|公斤|公)', text, re.I)
    w = float(m2.group(1)) if m2 else None
    if not h:
        m = re.search(r'身高\s*(\d{2,3})', text)
        h = float(m.group(1)) if m else None
    if not w:
        m2 = re.search(r'體重\s*(\d{2,3})', text)
        w = float(m2.group(1)) if m2 else None
    if not h or not w:
        nums = re.findall(r'\d+(?:\.\d)?', text)
        if len(nums) >= 2:
            a, b = float(nums[0]), float(nums[1])
            if 100 <= a <= 220 and 20 <= b <= 200:
                h, w = a, b
    return h, w


def build_bmi_flex(height: float, weight: float) -> list:
    bmi = round(weight / ((height / 100) ** 2), 1)
    if bmi < 18.5:
        status, bmi_color = "體重過輕 😟", "#1565C0"
        advice = "建議增加蛋白質攝取（蛋、雞胸肉、豆腐），每週做 2-3 次重量訓練增肌。"
    elif bmi < 24:
        status, bmi_color = "體重正常 ✅", "#43A047"
        advice = "繼續保持！每週 150 分鐘有氧運動 + 均衡飲食，維持現況最重要。"
    elif bmi < 27:
        status, bmi_color = "體重過重 ⚠️", "#F9A825"
        advice = "建議每天減少 300-500 大卡攝取，多走路爬樓梯。循序漸進比激烈節食有效。"
    elif bmi < 30:
        status, bmi_color = "輕度肥胖 🔴", "#FF6B35"
        advice = "建議諮詢營養師制定飲食計畫，配合有氧運動（走路/游泳/騎車）。"
    else:
        status, bmi_color = "中重度肥胖 🚨", "#C62828"
        advice = "建議諮詢醫師評估健康風險，可考慮專業減重門診協助。"

    ideal_low  = round(18.5 * (height / 100) ** 2, 1)
    ideal_high = round(24   * (height / 100) ** 2, 1)
    ACCENT = "#43A047"

    return [{"type": "flex", "altText": f"BMI 計算結果：{bmi}", "contents": {
        "type": "bubble",
        "header": {"type": "box", "layout": "vertical",
                   "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                   "contents": [
                       {"type": "box", "layout": "vertical", "flex": 1,
                        "paddingStart": "12px", "contents": [
                            {"type": "text", "text": "💪 BMI 健康分析",
                             "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            {"type": "text", "text": f"身高 {int(height)} cm｜體重 {weight} kg",
                             "color": "#8892B0", "size": "xs", "margin": "xs"},
                        ]},
                   ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "md",
                 "backgroundColor": "#FFFFFF",
                 "contents": [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "BMI 指數", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": str(bmi), "size": "xxl", "weight": "bold",
                 "color": bmi_color, "flex": 1, "align": "end"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "健康狀態", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": status, "size": "sm", "weight": "bold",
                 "color": bmi_color, "flex": 3, "align": "end", "wrap": True},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "理想體重", "size": "sm", "color": "#8892B0", "flex": 2},
                {"type": "text", "text": f"{ideal_low}～{ideal_high} kg",
                 "size": "sm", "color": ACCENT, "flex": 3, "align": "end"},
            ]},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": "💡 建議", "weight": "bold", "size": "sm", "color": "#1A1F3A"},
            {"type": "text", "text": advice, "size": "xs", "color": "#555555", "wrap": True},
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                   "backgroundColor": "#FFFFFF",
                   "contents": [
            {"type": "button", "style": "primary", "color": ACCENT, "height": "sm",
             "action": {"type": "message", "label": "🥗 減重", "text": "減肥方法"}},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "😴 睡眠", "text": "睡眠改善"}},
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "🍽️ 吃什麼", "text": "吃什麼 輕食"}},
            ]},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📤 分享 BMI 結果給朋友",
                        "uri": "https://line.me/R/share?text=" + urllib.parse.quote(
                            f"💪 我的 BMI 是 {bmi}（{status}）\n"
                            f"理想體重：{ideal_low}～{ideal_high} kg\n\n"
                            f"用「生活優轉」幫你算算！"
                        )}},
        ]},
    }}]


def build_sleep_advice() -> list:
    return [{"type":"flex","altText":"睡眠改善指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#1A237E","contents":[
            {"type":"text","text":"😴 睡眠改善指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"科學方法讓你一覺好眠","color":"#C5CAE9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"🌙 睡前 1 小時","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 手機調暗或開護眼模式\n• 避免咖啡、茶、可樂\n• 洗溫水澡（37-40°C）幫助放鬆","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🛏️ 臥室環境","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 溫度 18-22°C 最易入睡\n• 完全遮光（眼罩或遮光窗簾）\n• 可用白噪音 App 或風扇聲","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"⏰ 最關鍵的習慣","weight":"bold","size":"sm","color":"#1A237E"},
            {"type":"text","text":"• 固定時間起床（包括週末！）\n• 下午 3 點後避免午睡超過 20 分鐘\n• 睡前焦慮→寫「明天待辦清單」清空腦袋","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🚨 要看醫生的情況","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"超過 3 週還是睡不好、打呼嚴重（可能睡眠呼吸中止症）→ 建議看家醫科或睡眠門診","size":"xs","color":"#C62828","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1A237E","height":"sm",
             "action":{"type":"message","label":"😰 壓力大怎麼辦？","text":"壓力紓解"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🏃 運動建議","text":"減肥方法"}},
        ]}
    }}]


def build_diet_advice() -> list:
    return [{"type":"flex","altText":"健康減重指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#2E7D32","contents":[
            {"type":"text","text":"🥗 健康減重指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"不節食也能瘦，科學方法最有效","color":"#C8E6C9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"📐 核心觀念：熱量赤字","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"每天少吃 300-500 大卡 = 每週減 0.3-0.5 公斤\n太快減反而掉肌肉、容易復胖","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🍽️ 飲食原則","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"✅ 優先吃：蛋白質（雞胸/豆腐/蛋）、蔬菜、全穀\n❌ 少吃：含糖飲料、精緻澱粉、油炸物\n💡 技巧：先吃蔬菜和蛋白質，最後才吃飯","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🏃 運動選擇","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"初學者：每天快走 30 分鐘就夠了！\n進階：有氧（燃脂）+ 重訓（維持肌肉）\n最重要的運動：你能持續做的那種","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"❌ 常見錯誤","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"• 不吃早餐（讓你下午更餓亂吃）\n• 只靠運動不控飲食（效果很慢）\n• 喝代餐（停喝就復胖）","size":"xs","color":"#C62828","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#2E7D32","height":"sm",
             "action":{"type":"message","label":"📊 幫我算 BMI","text":"幫我算BMI"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"😴 睡眠改善","text":"睡眠改善"}},
        ]}
    }}]


def build_mood_support(text: str = "") -> list:
    _crisis_kws = ["不想活", "不想活了", "活不下去", "去死", "想死",
                   "結束生命", "消失就好", "消失算了", "不如死掉"]
    _lost_kws = ["沒目標", "沒有目標", "人生沒目標", "什麼都不想做", "甚麼都不想做",
                 "什麼都不想", "甚麼都不想", "活著沒意思", "沒意思", "沒意義",
                 "人生無聊", "迷茫", "迷失", "不知道目標"]
    _conflict_kws = ["被罵", "被念", "被嗆", "被兇", "被罵慘", "被罵死",
                     "吵架", "吵起來", "跟他吵", "跟她吵", "又吵", "大吵",
                     "被說", "被批評", "被否定", "被嫌", "被討厭"]
    _student_kws = ["被欺負", "被霸凌", "被排擠", "被孤立", "沒有朋友",
                    "考不好", "考差了", "成績差", "成績不好", "考砸了", "被當掉",
                    "被老師罵", "老師罵我", "作業寫不完", "功課好難", "不想上學",
                    "讀書好累", "唸書好累", "考試壓力"]
    is_crisis   = any(w in text for w in _crisis_kws)
    is_lost     = any(w in text for w in _lost_kws)
    is_conflict = any(w in text for w in _conflict_kws)
    is_student  = any(w in text for w in _student_kws)

    if is_crisis:
        return [
            {"type": "text",
             "text": "聽到你說這些，我有點擔心你 🫂\n\n你現在還好嗎？\n\n如果情緒很難受，可以打這支電話，有人會陪你說話 👇\n\n📞 安心專線：1925（24小時免費，不用說名字）"},
        ]

    if is_student:
        openers = [
            "這種事不好受，但你願意說出來就很勇敢 🌱",
            "考不好或被欺負，都不代表你不好，真的 ✨",
            "學生時期這種感受特別重，我知道 🌿",
            "遇到這種事，會想逃很正常，先讓自己喘口氣就好 🍃",
        ]
        header_text = "🌱 你說的，我都聽到了"
        header_sub = "學校的事，不用一個人扛"
        body_ack = "不管是被欺負、考不好，還是不想上學，這些感受都是真的，不用假裝沒事。"
        body_hint = "等你準備好了，如果想做點什麼讓自己好過一點 👇"
        buttons = [
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🍜 吃點好的，先犒賞自己", "text": "今天吃什麼"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🎪 出去走走，換個空氣", "text": "活動推薦"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "☕ 找個地方靜一靜", "text": "今天吃什麼 咖啡廳"}},
        ]
    elif is_conflict:
        openers = [
            "這種事真的很消耗，說出來就好 🌬️",
            "被罵或吵架完，情緒需要時間，不用急著沒事 🌿",
            "發生這種事，會難受很正常 ✨",
            "先讓自己緩一下，不用馬上想對還是錯 🚶",
        ]
        header_text = "🌬️ 情緒還在，沒關係"
        header_sub = "不用急著好起來"
        body_ack = "剛剛發生的事還在心裡，這很正常。先讓自己的情緒有個地方放，不用硬撐。"
        body_hint = "如果想做點什麼換換狀態的話 👇"
        buttons = [
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🍜 吃點讓自己舒服的", "text": "今天吃什麼"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🎪 出去散散心", "text": "活動推薦"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "☕ 找個安靜的地方坐坐", "text": "今天吃什麼 咖啡廳"}},
        ]
    elif is_lost:
        openers = [
            "沒有方向的感覺很煎熬，但這個時期很多人都走過 🌱",
            "不知道目標在哪，不代表你有問題，只是還沒找到 ✨",
            "迷茫的時候不用硬逼自己想清楚，先讓自己好好喘口氣 🍃",
            "人生不是每個時候都要有答案，先照顧好現在就夠了 🌿",
        ]
        header_text = "🌱 不知道方向，也沒關係"
        header_sub = "先照顧好現在的自己就夠了"
        body_ack = "沒有目標的感覺很重，但這不是你的錯，也不是永遠的狀態。先讓自己休息一下。"
        body_hint = "如果想走出去動一動，或只是換個環境 👇"
        buttons = [
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🎪 出去找點新體驗", "text": "活動推薦"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🚶 附近隨便走走", "text": "在地景點"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🍜 先吃頓好的", "text": "今天吃什麼"}},
        ]
    else:
        openers = [
            "今天不太順對嗎，說出來就好 🌿",
            "聽起來很累，先喘口氣 ✨",
            "這種感覺很真實，不用假裝沒事 🍃",
            "有時候就是會這樣，沒關係的 🌱",
        ]
        header_text = "🌿 今天辛苦了"
        header_sub = "不用急著好起來"
        body_ack = "不管是累、煩、還是說不上來的低落，這些感受都值得被好好對待。先讓自己休息一下。"
        body_hint = "如果想做點什麼讓自己好過一點 👇"
        buttons = [
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🍜 吃點讓自己開心的", "text": "今天吃什麼"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "🎪 附近有什麼活動", "text": "活動推薦"}},
            {"type": "button", "style": "secondary", "height": "sm",
             "action": {"type": "message", "label": "☕ 找家咖啡廳坐坐", "text": "今天吃什麼 咖啡廳"}},
        ]

    return [
        {"type": "text", "text": random.choice(openers)},
        {"type": "flex", "altText": header_text,
         "contents": {
             "type": "bubble", "size": "mega",
             "header": {"type": "box", "layout": "vertical",
                        "backgroundColor": "#37474F", "paddingAll": "16px",
                        "contents": [
                            {"type": "text", "text": header_text,
                             "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            {"type": "text", "text": header_sub,
                             "color": "#B0BEC5", "size": "xs", "margin": "xs"},
                        ]},
             "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                      "paddingAll": "16px",
                      "contents": [
                          {"type": "text", "text": body_ack,
                           "size": "sm", "color": "#333333", "wrap": True},
                          {"type": "text", "text": body_hint,
                           "size": "xs", "color": "#888888",
                           "wrap": True, "margin": "md"},
                      ]},
             "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                        "paddingAll": "12px", "contents": buttons},
         }}
    ]


def build_stress_advice() -> list:
    return [{"type":"flex","altText":"壓力紓解指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#6A1B9A","contents":[
            {"type":"text","text":"😰 壓力紓解指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"科學方法讓你找回平靜","color":"#E1BEE7","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"⚡ 立即舒緩（5 分鐘內）","weight":"bold","size":"sm","color":"#6A1B9A"},
            {"type":"text","text":"• 4-7-8 呼吸法：吸氣4秒→憋氣7秒→呼氣8秒，做 3 次\n• 走到戶外吹風 5 分鐘\n• 喝一杯溫開水","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"📅 長期習慣","weight":"bold","size":"sm","color":"#6A1B9A"},
            {"type":"text","text":"• 每天 30 分鐘運動（最強壓力解藥）\n• 睡前寫「3 件今天的好事」\n• 限制看新聞/社群的時間","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🆘 需要專業協助的情況","weight":"bold","size":"sm","color":"#C62828"},
            {"type":"text","text":"持續 2 週以上的憂鬱、焦慮、失眠影響生活 → 建議諮詢身心科或心理師\n\n📞 安心專線：1925（24小時免費）","size":"xs","color":"#C62828","wrap":True},
        ]}
    }}]


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


def build_water_intake(weight: float) -> list:
    ml = round(weight * 30)
    cups = round(ml / 250)
    return [{"type": "flex", "altText": "每日喝水量建議",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#0288D1",
                            "contents": [
                                {"type": "text", "text": "💧 每日喝水量建議",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "text", "text": f"體重 {weight:.0f} kg", "size": "sm", "color": "#888888"},
                     {"type": "text", "text": f"💧 建議每日 {ml:,} ml", "size": "lg",
                      "weight": "bold", "color": "#0288D1"},
                     {"type": "text", "text": f"約 {cups} 杯水（250ml/杯）", "size": "sm", "color": "#555555"},
                     {"type": "separator"},
                     {"type": "text", "text": "⏰ 建議分配：\n"
                      "• 起床：250ml\n• 上午：500ml\n• 午餐前：250ml\n"
                      "• 下午：500ml\n• 晚餐前：250ml\n• 睡前少量",
                      "size": "xs", "color": "#555555", "wrap": True},
                 ]},
             }}]


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
