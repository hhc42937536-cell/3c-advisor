from modules.money_credit_cards import build_credit_card_advice
from modules.money_credit_cards import build_credit_card_menu
from modules.money_credit_cards import build_credit_card_result
from modules.money_rates import build_exchange_rate
from modules.money_rates import build_oil_price
from modules.money_spending import build_spending_decision
from modules.money_spending_cards import _spend_overspent

import re


def build_budget_plan(salary: int) -> list:
    need = int(salary * 0.5)
    want = int(salary * 0.3)
    save = int(salary * 0.2)
    return [{"type":"flex","altText":f"月薪 {salary:,} 預算規劃","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#E65100","contents":[
            {"type":"text","text":"💰 月薪預算規劃","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":f"月薪 NT${salary:,} — 50/30/20 法則","color":"#FFE0B2","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"md","contents":[
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"🏠 必要支出 50%","weight":"bold","size":"sm","color":"#C62828","flex":3},
                {"type":"text","text":f"NT${need:,}","size":"lg","weight":"bold","color":"#C62828","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"房租、水電、三餐、交通、基本保險","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"🎉 享樂支出 30%","weight":"bold","size":"sm","color":"#E65100","flex":3},
                {"type":"text","text":f"NT${want:,}","size":"lg","weight":"bold","color":"#E65100","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"娛樂、購物、外食、旅遊","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"box","layout":"horizontal","contents":[
                {"type":"text","text":"💎 儲蓄/投資 20%","weight":"bold","size":"sm","color":"#2E7D32","flex":3},
                {"type":"text","text":f"NT${save:,}","size":"lg","weight":"bold","color":"#2E7D32","flex":2,"align":"end"},
            ]},
            {"type":"text","text":"緊急備用金 → 定期定額 ETF → 目標存款","size":"xs","color":"#888888","wrap":True},
            {"type":"separator"},
            {"type":"text","text":"💡 最有效的存錢方法","weight":"bold","size":"sm","color":"#3E2723"},
            {"type":"text","text":f"薪水入帳當天，馬上轉 NT${save:,} 到另一個帳戶，剩下的才用於生活。\n\n🎯 第一目標：存滿 NT${save*6:,}（6個月緊急備用金）","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1565C0","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 保險要買哪些？","text":"保險建議"}},
        ]}
    }}]


def build_insurance_guide() -> list:
    return [{"type":"flex","altText":"保險購買指南","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#4527A0","contents":[
            {"type":"text","text":"🛡️ 保險購買指南","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"哪些必買？哪些不必要？","color":"#D1C4E9","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"✅ 這 4 種最值得買","weight":"bold","size":"sm","color":"#2E7D32"},
            {"type":"text","text":"① 🏥 實支實付醫療險 — 住院手術費用報銷\n② 💪 意外險 — 便宜但保障高\n③ 🎗️ 重大疾病險 — 癌症/心臟病治療費\n④ ☠️ 定期壽險 — 有家人依賴才需要","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"⚠️ 這些先不用急著買","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"• 儲蓄險（報酬率不如 ETF）\n• 投資型保單（費用高、結構複雜）\n• 終身壽險（非常貴、不划算）","size":"xs","color":"#E65100","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"💡 新鮮人保險購買順序","weight":"bold","size":"sm","color":"#4527A0"},
            {"type":"text","text":"① 先存緊急備用金（3-6 個月支出）\n② 買意外險（最便宜，先保基本）\n③ 買實支實付醫療險\n④ 有穩定收入後考慮重大疾病險\n\n💰 預算參考：月薪 10% 以內用於保費","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#4527A0","height":"sm",
             "action":{"type":"message","label":"💰 月薪預算規劃","text":"存錢方法"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
        ]}
    }}]


def build_saving_tips() -> list:
    return [{"type":"flex","altText":"存錢方法大全","contents":{
        "type":"bubble",
        "header":{"type":"box","layout":"vertical","backgroundColor":"#E65100","contents":[
            {"type":"text","text":"💰 存錢方法大全","color":"#FFFFFF","size":"md","weight":"bold"},
            {"type":"text","text":"讓錢自動幫你存","color":"#FFE0B2","size":"xs","margin":"sm"},
        ]},
        "body":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"text","text":"🥇 最有效：先存後花","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"薪水入帳當天，馬上轉 20% 到另一個帳戶（高利活存），剩下才用於生活。\n👉 設定「自動轉帳」，連想都不用想","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"📱 記帳 App 推薦","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"• Moneybook 記帳城市（台灣人最愛）\n• CWMoney（介面簡單好上手）\n• 麻布記帳（可連結銀行自動匯入）\n\n記帳是讓你知道錢去哪了，不是讓你痛苦的","size":"xs","color":"#555555","wrap":True},
            {"type":"separator","margin":"sm"},
            {"type":"text","text":"🎯 3 個存錢目標","weight":"bold","size":"sm","color":"#E65100"},
            {"type":"text","text":"① 緊急備用金：3-6 個月薪水\n② 定期定額 ETF（0050/00878）\n③ 短期目標：旅遊基金、換手機基金","size":"xs","color":"#555555","wrap":True},
        ]},
        "footer":{"type":"box","layout":"vertical","spacing":"sm","contents":[
            {"type":"button","style":"primary","color":"#1565C0","height":"sm",
             "action":{"type":"message","label":"💳 信用卡","text":"信用卡推薦"}},
            {"type":"button","style":"secondary","height":"sm",
             "action":{"type":"message","label":"🛡️ 要買哪些保險？","text":"保險建議"}},
        ]}
    }}]


def build_money_menu() -> list:
    ACCENT = "#F9A825"
    return [{"type": "flex", "altText": "金錢小幫手",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "💰 金錢小幫手",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "你的隨身財務顧問",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": "💡 告訴我你的月薪，幫你規劃預算",
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "直接輸入：「月薪 3 萬怎麼規劃」",
                      "size": "xs", "color": "#8892B0", "margin": "sm", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💰 存錢方法", "text": "存錢方法"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🛡️ 保險", "text": "保險建議"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💳 信用卡", "text": "信用卡推薦"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "💱 匯率", "text": "匯率查詢"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "⛽ 本週油價", "text": "油價"}},
                 ]},
             }}]


def build_money_message(text: str) -> list:
    if any(w in text for w in ["油價", "加油", "汽油", "柴油", "92", "95", "98"]):
        return build_oil_price()
    if any(w in text for w in ["匯率", "換匯", "外幣", "美金", "日圓", "日幣",
                                "歐元", "英鎊", "韓元", "韓幣", "人民幣", "泰銖"]):
        return build_exchange_rate(text)

    salary = 0
    m = re.search(r'月薪\s*(\d+)|薪水\s*(\d+)|薪資\s*(\d+)', text)
    if m:
        salary = int(next(g for g in m.groups() if g))
    else:
        m2 = re.search(r'(\d+)\s*萬', text)
        if m2:
            salary = int(m2.group(1)) * 10000
        else:
            m3 = re.search(r'(\d{4,6})', text.replace(",",""))
            if m3:
                val = int(m3.group(1))
                if 15000 <= val <= 300000:
                    salary = val

    if salary >= 15000 and any(w in text for w in ["月薪","薪水","薪資","規劃","怎麼存","如何存","預算"]):
        return build_budget_plan(salary)
    if any(w in text for w in ["信用卡比較", "信用卡推薦", "哪張卡", "回饋", "信用卡使用"]):
        return build_credit_card_menu()
    if any(w in text for w in ["信用卡","循環利息","最低應繳","刷卡"]):
        return build_credit_card_menu()
    if any(w in text for w in ["保險","醫療險","壽險","意外險","重大疾病"]):
        return build_insurance_guide()
    if any(w in text for w in ["存錢","儲蓄","記帳","理財","怎麼存"]):
        return build_saving_tips()
    return build_money_menu()
