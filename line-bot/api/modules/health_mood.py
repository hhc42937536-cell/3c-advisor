"""Mood support message builders."""

from __future__ import annotations

import random


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
