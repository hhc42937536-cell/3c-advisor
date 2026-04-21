"""Basic health advice and BMI builders."""

from __future__ import annotations

import re
import urllib.parse


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
             "action": {"type": "message", "label": "🥗 健康減重方法", "text": "減肥方法"}},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "😴 改善睡眠", "text": "睡眠改善"}},
                {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                 "height": "sm", "action": {"type": "message", "label": "🍽️ 健康吃什麼", "text": "吃什麼 輕食"}},
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
