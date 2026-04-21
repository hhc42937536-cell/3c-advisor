"""Spending decision helper cards."""

from __future__ import annotations

import re
from modules.money_spending_cards import _spend_card
from modules.money_spending_cards import _spend_overspent
from modules.money_spending_logic import match_spending_item


def build_spending_decision(text: str) -> list:
    if any(w in text for w in ["花太多", "超支", "這週花", "本週花", "花太兇", "錢不夠了"]):
        return _spend_overspent()

    if any(w in text for w in ["信用卡還是現金", "刷卡還是現金", "刷卡或現金",
                                "信用卡刷好嗎", "刷卡好嗎"]):
        nums = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]{2,}", text)]
        return _spend_card(int(max(nums)) if nums else 0)

    nums = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]{2,}", text)]
    amount = max(nums) if nums else 0

    item = text
    for kw in ["這個划算嗎", "這支", "這台", "這款", "这个", "划算嗎", "划算",
               "值得買嗎", "值得買", "要買嗎", "該買嗎", "值得嗎", "要不要買",
               "可以買嗎", "買得起嗎", "好嗎", "貴嗎", "太貴嗎", "消費決策",
               "信用卡刷", "刷", "元", "塊", "元的"]:
        item = item.replace(kw, " ")
    item = re.sub(r"\d[\d,]*", " ", item)
    item = re.sub(r"\s+", " ", item).strip()

    if amount == 0:
        return [{"type": "flex", "altText": "消費決策小幫手",
                 "contents": {"type": "bubble",
                     "styles": {"header": {"backgroundColor": "#1A2D50"}},
                     "header": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": "🤔 消費決策小幫手",
                          "color": "#FFFFFF", "size": "md", "weight": "bold"},
                         {"type": "text", "text": "直接用日常語言問我就好",
                          "color": "#AABBDD", "size": "xs", "margin": "xs"},
                     ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                              "contents": [
                         {"type": "text", "text": "這樣問我就懂：",
                          "size": "sm", "weight": "bold", "color": "#333333"},
                         {"type": "text",
                          "text": "「這支手機 20000 划算嗎？」\n「iPhone 16 買 28900 值得嗎？」\n「要不要買這台筆電 35000？」\n「冷氣 25000 太貴嗎？」",
                          "size": "sm", "color": "#555555", "wrap": True, "margin": "xs"},
                     ]},
                     "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                                "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                             {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                              "action": {"type": "message", "label": "手機 20000",
                                         "text": "這支手機 20000 划算嗎？"}},
                             {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                              "action": {"type": "message", "label": "筆電 35000",
                                         "text": "要不要買這台筆電 35000？"}},
                         ]},
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "💳 刷卡還是現金？",
                                     "text": "信用卡還是現金"}},
                     ]},
                 }}]

    lo, hi, cat_label, rec_cmd = match_spending_item(item)
    display_item = item if item else (cat_label or "這項商品")

    sal_lo, sal_hi = 50000, 60000
    pct_lo = int(amount / sal_hi * 100)
    pct_hi = int(amount / sal_lo * 100)
    hours = amount / 250
    hours_str = f"{hours:.0f} 小時" if hours < 8 else f"{hours/8:.1f} 天"

    if lo is not None:
        if amount < lo * 0.75:
            verdict = "價格偏低，留意品質"
            color = "#E65100"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格比行情低很多，建議確認是否為平行輸入、展示品或二手品，購買前先確認保固條件。"
        elif amount <= hi * 1.1:
            color = "#2E7D32"
            pct = (amount - lo) / (hi - lo) if hi > lo else 0.5
            pos = "入門款" if pct < 0.25 else ("中段" if pct < 0.65 else "中高段")
            verdict = f"價格合理（{pos}）"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格在{cat_label}市場屬於{pos}。建議上 BigGo 確認是近期最低價再下手，不急的話等雙11或週年慶可再省 10%。"
        else:
            verdict = "價格偏高"
            color = "#C62828"
            market = f"市場行情約 NT${lo:,}–{hi:,}"
            tip = f"這個價格高出正常行情。建議等雙11 / 週年慶 / 品牌促銷，或考慮上一代同規格機型，功能差不多但便宜不少。"
    else:
        market = ""
        if amount <= 1000:
            verdict, color, tip = "小額，不用太糾結", "#2E7D32", "只要是你真正需要的，買就對了。"
        elif amount <= 5000:
            verdict, color, tip = "中等消費，建議先比價", "#E65100", "先上蝦皮、momo 比價，同樣的東西通常能省 10–20%。"
        elif amount <= 20000:
            verdict, color, tip = "大額，建議睡一晚再決定", "#C62828", "等 24 小時再買。隔天還是很想要，代表是真正需要。確認有無 0 利率分期。"
        else:
            verdict, color, tip = "重大支出，謹慎評估", "#B71C1C", "確認緊急備用金（建議 3–6 個月生活費）不受影響，再考慮是否購買。"

    if pct_hi <= 15:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，財務壓力小"
        sal_color = "#2E7D32"
    elif pct_hi <= 40:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，在合理範圍"
        sal_color = "#E65100"
    else:
        sal_label = f"占月薪約 {pct_lo}–{pct_hi}%，比例偏高"
        sal_color = "#C62828"

    _impulse_cats = ("衣物", "鞋子", "包包")
    if cat_label in ("手機", "筆電", "平板"):
        advice_40 = "40+ 觀點：工具類消費值得投資，但功能夠用就好，不需要追最新款。前一代機型通常便宜 20–30%，但規格差距很小。"
    elif cat_label in ("大家電", "家具"):
        advice_40 = "40+ 觀點：耐用品值得買好一點，便宜貨折舊快，長期反而更貴。品牌售後服務也很重要。"
    elif cat_label in ("餐飲（每人）", "飲品"):
        advice_40 = "40+ 觀點：偶爾好好吃一頓是生活品質的一部分，不用有罪惡感。但如果是日常習慣，要注意每月餐飲佔總支出的比例。"
    elif cat_label == "課程":
        advice_40 = "40+ 觀點：投資自己的技能是報酬率最高的消費。但要確認課程有完課率（買了沒看等於白花）。"
    elif cat_label == "旅遊":
        monthly_cost = int(amount / 12)
        advice_40 = f"40+ 觀點：旅遊是很值得的體驗消費。若預算緊，可以拆成每月存 NT${monthly_cost:,}，半年後再出發，體驗相同但財務壓力小很多。"
    elif cat_label == "年繳保險":
        monthly = int(amount / 12)
        advice_40 = f"40+ 重點：保險的關鍵不是「划不划算」，而是「保障夠不夠」。這份保險每月等於 NT${monthly:,}。40+ 優先順序：醫療 > 失能 > 壽險。"
    elif cat_label in _impulse_cats:
        advice_40 = f"40+ 提醒：這類消費衝動比例高。建議先放購物車 24 小時，隔天還是很想買再出手。統計上衝動消費 70% 隔天就後悔了。"
    else:
        advice_40 = "40+ 觀點：先確認是「需要」還是「想要」。30 天後還想買，代表是真正的需求。"

    body_items = [
        {"type": "box", "layout": "horizontal",
         "backgroundColor": "#F5F7FA", "cornerRadius": "8px", "paddingAll": "md",
         "contents": [
             {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                 {"type": "text", "text": f"NT${int(amount):,}",
                  "size": "xxl", "weight": "bold", "color": color},
                 {"type": "text", "text": f"≈ 工作 {hours_str}",
                  "size": "xs", "color": "#888888"},
             ]},
             {"type": "box", "layout": "vertical", "flex": 1, "contents": [
                 {"type": "text", "text": sal_label, "size": "xs",
                  "color": sal_color, "wrap": True, "align": "end"},
             ]},
         ]},
        *([{"type": "text", "text": f"市場行情：{market}", "size": "xs",
            "color": "#888888", "margin": "xs"}] if market else []),
        {"type": "separator", "margin": "sm"},
        {"type": "text", "text": verdict, "size": "lg",
         "weight": "bold", "color": color, "margin": "sm"},
        {"type": "text", "text": tip, "size": "sm", "color": "#444444", "wrap": True},
        {"type": "separator", "margin": "sm"},
        {"type": "text", "text": advice_40, "size": "sm",
         "color": "#555555", "wrap": True, "margin": "sm"},
    ]

    footer_rows = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
            {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
             "action": {"type": "message", "label": "再問一個", "text": "這個划算嗎"}},
            {"type": "button", "style": "link", "flex": 1, "height": "sm",
             "action": {"type": "message", "label": "刷卡或現金？", "text": "信用卡還是現金"}},
        ]},
    ]
    if rec_cmd:
        footer_rows.append(
            {"type": "button", "style": "primary", "color": "#1A2D50",
             "height": "sm", "margin": "sm",
             "action": {"type": "message",
                        "label": f"找 CP 值高的{cat_label}",
                        "text": rec_cmd}}
        )

    return [{"type": "flex",
             "altText": f"{display_item} NT${int(amount):,} — {verdict}",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": color}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text",
                      "text": f"🤔 {display_item} 值得買嗎？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "務實評估，幫你做決定",
                      "color": "#FFFFFF", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical",
                          "spacing": "sm", "contents": body_items},
                 "footer": {"type": "box", "layout": "vertical",
                            "spacing": "sm", "contents": footer_rows},
             }}]
