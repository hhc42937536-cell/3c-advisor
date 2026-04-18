import csv as _csv
import json
import re
import ssl as _ssl
import urllib.parse
import urllib.request

CREDIT_CARDS_DB = {
    "現金回饋": [
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付/網購/外送 6%", "tags":["行動支付","網購","外送"]},
        {"bank":"滙豐", "name":"Live+現金回饋卡", "fee":"首年免，次年NT$2,000", "cashback":"國內4.88%、海外5.88%", "tags":["海外","通用"]},
        {"bank":"玉山", "name":"U Bear信用卡", "fee":"首年免，次年NT$3,000", "cashback":"影音訂閱/網購 10%", "tags":["網購","影音訂閱"]},
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"海外/網購最高7.5%", "tags":["海外","網購"]},
        {"bank":"永豐", "name":"幣倍卡", "fee":"首年免，次年NT$3,000", "cashback":"海外10%、國內5%", "tags":["海外","通用"]},
        {"bank":"永豐", "name":"DAWAY卡", "fee":"首年免，次年NT$3,000", "cashback":"LINE Pay 最高6%", "tags":["行動支付","LINE Pay"]},
        {"bank":"遠東商銀", "name":"快樂信用卡", "fee":"首年免，次年NT$2,000", "cashback":"悠遊加值5%、通用2%", "tags":["交通","大眾運輸"]},
        {"bank":"遠東商銀", "name":"遠東樂家+卡", "fee":"首年免，次年NT$2,000", "cashback":"寵物/親子商店最高10%", "tags":["親子","寵物","生活"]},
        {"bank":"第一銀行", "name":"iLEO卡", "fee":"首年免，次年NT$1,200", "cashback":"海外/行動支付最高13%", "tags":["海外","行動支付"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"行動支付3.8%、加油3.3%", "tags":["行動支付","加油"]},
        {"bank":"玉山", "name":"Pi拍錢包信用卡", "fee":"首年免，次年NT$3,000", "cashback":"Pi幣回饋最高5%、保費有回饋", "tags":["通用","保費"]},
    ],
    "網購外送": [
        {"bank":"中國信託", "name":"foodpanda卡", "fee":"首年免，次年NT$1,800", "cashback":"外送平台最高30%", "tags":["外送","餐飲"]},
        {"bank":"中國信託", "name":"LINE Pay卡", "fee":"條件免年費", "cashback":"指定商店最高16%、韓國30%", "tags":["行動支付","海外"]},
        {"bank":"玉山", "name":"U Bear信用卡", "fee":"首年免，次年NT$3,000", "cashback":"影音/網購10%", "tags":["網購","影音訂閱"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付/網購/外送6%", "tags":["外送","網購"]},
    ],
    "加油交通": [
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"加油最高7.5%", "tags":["加油"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付加油6%", "tags":["加油","行動支付"]},
        {"bank":"遠東商銀", "name":"快樂信用卡", "fee":"首年免，次年NT$2,000", "cashback":"悠遊加值5%", "tags":["大眾運輸","悠遊卡"]},
        {"bank":"遠東商銀", "name":"遠東樂行卡", "fee":"首年免，次年NT$2,000", "cashback":"計程車/Uber 3%、加油折扣", "tags":["計程車","Uber","加油"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"加油3.3%", "tags":["加油"]},
    ],
    "海外旅遊": [
        {"bank":"滙豐", "name":"Live+現金回饋卡", "fee":"首年免，次年NT$2,000", "cashback":"海外5.88%現金回饋", "tags":["海外","旅遊"]},
        {"bank":"永豐", "name":"幣倍卡", "fee":"首年免，次年NT$3,000", "cashback":"海外10%雙幣無手續費", "tags":["海外","旅遊"]},
        {"bank":"第一銀行", "name":"iLEO卡", "fee":"首年免，次年NT$1,200", "cashback":"海外最高13%", "tags":["海外"]},
        {"bank":"玉山", "name":"Unicard", "fee":"首年免，次年NT$3,000", "cashback":"海外7.5%", "tags":["海外","旅遊"]},
        {"bank":"第一銀行", "name":"御璽商旅卡", "fee":"條件免，次年NT$2,000", "cashback":"旅遊15%、海外3%", "tags":["旅遊","商務"]},
    ],
    "餐飲美食": [
        {"bank":"中國信託", "name":"foodpanda卡", "fee":"首年免，次年NT$1,800", "cashback":"外送30%、餐飲5%", "tags":["外送","餐飲"]},
        {"bank":"滙豐", "name":"匯鑽卡", "fee":"首年免，次年NT$2,000", "cashback":"行動支付餐飲6%", "tags":["餐飲","行動支付"]},
        {"bank":"第一銀行", "name":"一卡通聯名卡", "fee":"首年免，次年NT$300", "cashback":"早餐店最高5%、超商3.5%", "tags":["早餐","超商"]},
    ],
    "保費繳稅": [
        {"bank":"永豐", "name":"保倍卡", "fee":"首年免，次年NT$3,000", "cashback":"保費1.2%無上限現金回饋", "tags":["保費"]},
        {"bank":"玉山", "name":"Pi拍錢包信用卡", "fee":"首年免，次年NT$3,000", "cashback":"保費有Pi幣回饋", "tags":["保費"]},
        {"bank":"台新", "name":"Richart卡", "fee":"首年免，次年NT$1,500", "cashback":"保費/繳稅有回饋", "tags":["保費","繳稅"]},
    ],
}

_CC_CATEGORY_EMOJI = {
    "現金回饋": "💰",
    "網購外送": "🛒",
    "加油交通": "⛽",
    "海外旅遊": "✈️",
    "餐飲美食": "🍽️",
    "保費繳稅": "📋",
}

_CURRENCY_NAMES = {
    "USD": "🇺🇸 美元", "JPY": "🇯🇵 日圓", "EUR": "🇪🇺 歐元",
    "GBP": "🇬🇧 英鎊", "AUD": "🇦🇺 澳幣", "CAD": "🇨🇦 加幣",
    "HKD": "🇭🇰 港幣", "SGD": "🇸🇬 新幣", "CHF": "🇨🇭 瑞士法郎",
    "CNY": "🇨🇳 人民幣", "KRW": "🇰🇷 韓元", "THB": "🇹🇭 泰銖",
    "SEK": "🇸🇪 瑞典克朗", "NZD": "🇳🇿 紐幣", "ZAR": "🇿🇦 南非幣",
    "MYR": "🇲🇾 馬幣", "PHP": "🇵🇭 菲律賓比索", "IDR": "🇮🇩 印尼盾",
    "VND": "🇻🇳 越南盾",
}

_CURRENCY_ALIAS = {
    "美元": "USD", "美金": "USD", "usd": "USD",
    "日圓": "JPY", "日幣": "JPY", "日元": "JPY", "jpy": "JPY",
    "歐元": "EUR", "eur": "EUR",
    "英鎊": "GBP", "gbp": "GBP",
    "澳幣": "AUD", "aud": "AUD",
    "港幣": "HKD", "hkd": "HKD",
    "人民幣": "CNY", "cny": "CNY", "rmb": "CNY",
    "韓元": "KRW", "韓幣": "KRW", "krw": "KRW",
    "泰銖": "THB", "thb": "THB",
    "新幣": "SGD", "新加坡幣": "SGD", "sgd": "SGD",
    "加幣": "CAD", "cad": "CAD",
    "紐幣": "NZD", "nzd": "NZD",
    "越南盾": "VND", "vnd": "VND",
    "馬幣": "MYR", "myr": "MYR",
}


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


def build_credit_card_menu() -> list:
    _CC_COLORS = {
        "現金回饋": "#E65100", "網購外送": "#AD1457",
        "加油交通": "#1565C0", "海外旅遊": "#00695C",
        "餐飲美食": "#6A1B9A", "保費繳稅": "#37474F",
    }
    cats = list(_CC_CATEGORY_EMOJI.items())
    rows = []
    for i in range(0, len(cats), 2):
        pair = cats[i:i+2]
        row_items = []
        for cat, emoji in pair:
            color = _CC_COLORS.get(cat, "#1565C0")
            row_items.append({
                "type": "box", "layout": "vertical",
                "flex": 1, "spacing": "xs",
                "backgroundColor": color,
                "cornerRadius": "12px",
                "paddingAll": "14px",
                "action": {"type": "message", "label": f"{emoji} {cat}", "text": f"信用卡推薦:{cat}"},
                "contents": [
                    {"type": "text", "text": emoji, "size": "xxl", "align": "center"},
                    {"type": "text", "text": cat, "color": "#FFFFFF", "size": "sm",
                     "weight": "bold", "align": "center", "margin": "sm"},
                ]
            })
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row_items})

    return [{"type": "flex", "altText": "💳 信用卡推薦比較", "contents": {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#0D47A1", "paddingAll": "16px",
                   "contents": [
            {"type": "text", "text": "💳 信用卡推薦", "color": "#FFFFFF", "size": "lg", "weight": "bold"},
            {"type": "text", "text": "選你最常刷的類別，推最划算的卡", "color": "#90CAF9",
             "size": "xs", "margin": "sm"},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "paddingAll": "14px",
                 "contents": rows},
    }}]


def build_credit_card_result(category: str) -> list:
    category = category.strip()
    cards = CREDIT_CARDS_DB.get(category, [])[:4]
    if not cards:
        return [{"type": "text", "text": f"找不到「{category}」的信用卡資料，請重新選擇類別。"}]
    emoji = _CC_CATEGORY_EMOJI.get(category, "💳")
    bubbles = []
    for card in cards:
        tags_text = "  ".join(f"#{t}" for t in card.get("tags", []))
        apply_url = (f"https://www.google.com/search?q="
                     + urllib.parse.quote(f"{card['bank']} {card['name']} 申辦"))
        bubbles.append({
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "vertical",
                       "backgroundColor": "#1565C0", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": card["bank"],
                            "color": "#90CAF9", "size": "xs"},
                           {"type": "text", "text": card["name"],
                            "color": "#FFFFFF", "size": "md",
                            "weight": "bold", "wrap": True},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                     "paddingAll": "14px", "contents": [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": "💰 回饋", "size": "xs",
                     "color": "#888888", "flex": 2},
                    {"type": "text", "text": card["cashback"], "size": "sm",
                     "weight": "bold", "color": "#0D47A1",
                     "flex": 5, "wrap": True},
                ]},
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": "📅 年費", "size": "xs",
                     "color": "#888888", "flex": 2},
                    {"type": "text", "text": card["fee"], "size": "xs",
                     "color": "#555555", "flex": 5, "wrap": True},
                ]},
                {"type": "text", "text": tags_text, "size": "xxs",
                 "color": "#1565C0", "wrap": True, "margin": "sm"},
            ]},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "10px",
                       "contents": [
                {"type": "button", "style": "primary", "color": "#1565C0",
                 "height": "sm",
                 "action": {"type": "uri", "label": "🔍 搜尋申辦",
                            "uri": apply_url}},
            ]},
        })

    return [{"type": "flex", "altText": f"{emoji} {category} 推薦信用卡",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_credit_card_advice() -> list:
    return build_credit_card_menu()


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


def build_oil_price() -> list:
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://www.cpc.com.tw/GetOilPriceJson.aspx?type=TodayOilPriceString",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return [{"type": "text", "text": "無法取得油價資料，請稍後再試"}]

    date   = data.get("PriceUpdate", "")
    p92    = data.get("sPrice1", "?")
    p95    = data.get("sPrice2", "?")
    p98    = data.get("sPrice3", "?")
    diesel = data.get("sPrice5", "?")
    lpg    = data.get("sPrice6", "?")

    return [{"type": "flex", "altText": f"本週油價 92:{p92} 95:{p95} 98:{p98}",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#FF6F00",
                            "contents": [
                                {"type": "text", "text": "⛽ 本週油價",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"中油牌價 · 更新日期 {date}",
                                 "color": "#FFE0B2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "92 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p92}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "95 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p95}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "98 無鉛", "size": "md", "color": "#555555", "flex": 3},
                         {"type": "text", "text": f"NT${p98}/公升", "size": "md",
                          "weight": "bold", "color": "#E65100", "flex": 3, "align": "end"},
                     ]},
                     {"type": "separator"},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "超級柴油", "size": "sm", "color": "#888888", "flex": 3},
                         {"type": "text", "text": f"NT${diesel}/公升", "size": "sm",
                          "color": "#888888", "flex": 3, "align": "end"},
                     ]},
                     {"type": "box", "layout": "horizontal", "contents": [
                         {"type": "text", "text": "液化石油氣", "size": "sm", "color": "#888888", "flex": 3},
                         {"type": "text", "text": f"NT${lpg}/公斤", "size": "sm",
                          "color": "#888888", "flex": 3, "align": "end"},
                     ]},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "中油每週日 24:00 公告新油價",
                      "size": "xxs", "color": "#888888", "wrap": True},
                 ]},
             }}]


def build_exchange_rate(query: str = "") -> list:
    try:
        req = urllib.request.Request(
            "https://rate.bot.com.tw/xrt/flcsv/0/day",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8-sig")
    except Exception:
        return [{"type": "text", "text": "無法取得匯率資料，請稍後再試"}]

    lines = raw.strip().split("\n")
    reader = _csv.reader(lines)
    rates = {}
    for row in reader:
        if len(row) < 14 or row[0] == "幣別":
            continue
        code = row[0].strip()
        try:
            cash_buy  = float(row[2])  if row[2].strip()  else 0
            cash_sell = float(row[12]) if row[12].strip() else 0
            spot_buy  = float(row[3])  if row[3].strip()  else 0
            spot_sell = float(row[13]) if row[13].strip() else 0
        except (ValueError, IndexError):
            continue
        rates[code] = {
            "cash_buy": cash_buy, "cash_sell": cash_sell,
            "spot_buy": spot_buy, "spot_sell": spot_sell,
        }

    target = ""
    query_lower = query.lower()
    for alias, code in _CURRENCY_ALIAS.items():
        if alias in query_lower:
            target = code
            break
    if not target:
        for code in rates:
            if code.lower() in query_lower:
                target = code
                break

    if target and target in rates:
        r = rates[target]
        name = _CURRENCY_NAMES.get(target, target)
        items = [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": name, "size": "lg", "weight": "bold",
                 "color": "#E65100", "flex": 3},
                {"type": "text", "text": target, "size": "sm",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "separator", "margin": "md"},
            {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                {"type": "text", "text": "", "flex": 2, "size": "xs"},
                {"type": "text", "text": "買入", "flex": 2, "size": "xs", "color": "#888888", "align": "center"},
                {"type": "text", "text": "賣出", "flex": 2, "size": "xs", "color": "#888888", "align": "center"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "💵 現金", "flex": 2, "size": "sm"},
                {"type": "text", "text": f"{r['cash_buy']:.2f}" if r['cash_buy'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#2E7D32"},
                {"type": "text", "text": f"{r['cash_sell']:.2f}" if r['cash_sell'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#C62828"},
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "🏦 即期", "flex": 2, "size": "sm"},
                {"type": "text", "text": f"{r['spot_buy']:.2f}" if r['spot_buy'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#2E7D32"},
                {"type": "text", "text": f"{r['spot_sell']:.2f}" if r['spot_sell'] else "-",
                 "flex": 2, "size": "sm", "align": "center", "color": "#C62828"},
            ]},
        ]
        if r['spot_sell'] > 0:
            amount_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:元|塊|萬)?', query)
            foreign_amt = float(amount_m.group(1)) if amount_m and float(amount_m.group(1)) > 0 else 100
            if "萬" in query and amount_m:
                foreign_amt *= 10000
            twd = round(foreign_amt * r['spot_sell'])
            items += [
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"💱 {target} {foreign_amt:,.0f} ≈ NT${twd:,}（即期賣出）",
                 "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
            ]

        return [{"type": "flex", "altText": f"匯率查詢 {target}",
                 "contents": {
                     "type": "bubble",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                                "contents": [
                                    {"type": "text", "text": "💱 台灣銀行匯率",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                     "footer": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": "買入＝你賣外幣給銀行 / 賣出＝你跟銀行買外幣",
                          "size": "xxs", "color": "#888888", "wrap": True},
                     ]},
                 }}]

    hot = ["USD", "JPY", "EUR", "GBP", "AUD", "CNY", "KRW", "HKD", "SGD", "THB"]
    items = []
    for code in hot:
        if code not in rates:
            continue
        r = rates[code]
        name = _CURRENCY_NAMES.get(code, code)
        sell = r['spot_sell'] or r['cash_sell']
        items.append({"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": name, "size": "xs", "flex": 3},
            {"type": "text", "text": f"{sell:.2f}" if sell else "-",
             "size": "xs", "flex": 2, "align": "end", "color": "#C62828"},
            {"type": "button", "style": "link", "height": "sm", "flex": 1,
             "action": {"type": "message", "label": "詳細", "text": f"匯率 {code}"}},
        ]})

    return [{"type": "flex", "altText": "今日匯率",
             "contents": {
                 "type": "bubble",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "contents": [
                                {"type": "text", "text": "💱 台灣銀行今日匯率",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "即期賣出（你買外幣的價格）",
                                 "color": "#FFE0B2", "size": "xxs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": items},
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


def _spend_card(amount: int = 0) -> list:
    installment = ""
    if amount >= 3000:
        m3  = int(amount / 3)
        m6  = int(amount / 6)
        m12 = int(amount / 12)
        installment = f"\n分期參考（0 利率）：\n• 3 期 ≈ 每月 NT${m3:,}\n• 6 期 ≈ 每月 NT${m6:,}\n• 12 期 ≈ 每月 NT${m12:,}"

    return [{"type": "flex", "altText": "刷卡還是付現？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#1A2D50"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💳 刷卡還是付現？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "這樣判斷最省錢",
                      "color": "#AABBDD", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "✅ 刷卡比較划算",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "• 有 1% 以上現金回饋\n• 有 0 利率分期（金額 > 3000）\n• 當月有滿額禮\n• 保固或購物保障較好",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "✅ 付現比較好",
                      "size": "sm", "weight": "bold", "color": "#C62828"},
                     {"type": "text",
                      "text": "• 夜市、攤販、傳統市場\n• 你容易忘繳卡費（循環利息 15%！）\n• 店家加收刷卡手續費\n• 這個月已超出預算",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     *([{"type": "separator", "margin": "sm"},
                        {"type": "text", "text": installment, "size": "sm",
                         "color": "#555555", "wrap": True}] if installment else []),
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "40+ 提醒：信用卡讓你月底才感受到痛苦。如果「不知道錢去哪了」，先付現 2 個月試試。",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "primary", "color": "#1A2D50",
                      "height": "sm",
                      "action": {"type": "message", "label": "💰 金錢小幫手",
                                 "text": "金錢小幫手"}},
                 ]},
             }}]


def _spend_overspent() -> list:
    return [{"type": "flex", "altText": "這週花太多怎麼辦？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💸 這週花太多了？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "不用焦慮，這樣處理",
                      "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "40+ 最常見的三個超支陷阱",
                      "size": "sm", "weight": "bold", "color": "#333333"},
                     {"type": "text",
                      "text": "1️⃣ 外食＋飲料 — 每天多花 150 元，一個月就多 4500\n"
                              "2️⃣ 網購衝動 — 加購物車就忘記，月底一次扣\n"
                              "3️⃣ 訂閱服務 — 忘記取消的 Netflix/Spotify/健身房",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "今天開始能做的 3 件事",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "✅ 剩下這週改付現金，讓自己感受到「錢在減少」\n"
                              "✅ 把非必要消費延到下週再決定\n"
                              "✅ 今晚花 5 分鐘，把這週最大的 3 筆支出寫下來",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text",
                      "text": "告訴我這週花最多的是什麼，我幫你分析值不值得 😊",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "看省錢小技巧",
                                     "text": "省錢建議"}},
                         {"type": "button", "style": "link", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "💰 金錢小幫手",
                                     "text": "金錢小幫手"}},
                     ]},
                 ]},
             }}]


def build_spending_decision(text: str) -> list:
    if any(w in text for w in ["花太多", "超支", "這週花", "本週花", "花太兇", "錢不夠了"]):
        return _spend_overspent()

    if any(w in text for w in ["信用卡還是現金", "刷卡還是現金", "刷卡或現金",
                                "信用卡刷好嗎", "刷卡好嗎"]):
        nums = [float(m.replace(",", "")) for m in re.findall(r"\d[\d,]{2,}", text)]
        return _spend_card(int(max(nums)) if nums else 0)

    _ITEM_RANGES = [
        (["電視", "tv", "液晶"],                          3000,  60000, "電視",   None),
        (["iphone", "手機", "android", "三星", "samsung","pixel","小米"], 5000, 50000, "手機", "推薦手機"),
        (["筆電", "laptop", "macbook", "電腦", "notebook"],15000, 80000, "筆電",  "推薦筆電"),
        (["ipad", "平板", "tablet"],                       5000,  40000, "平板",   "推薦平板"),
        (["airpods", "耳機"],                              500,   15000, "耳機",   None),
        (["冷氣", "冰箱", "洗衣機", "烘衣機"],            10000, 80000, "大家電", None),
        (["沙發", "床", "書桌", "椅子", "家具"],           3000,  50000, "家具",   None),
        (["包包", "皮包", "名牌包"],                       1000,  30000, "包包",   None),
        (["球鞋", "運動鞋", "鞋"],                          500,  15000, "鞋子",   None),
        (["外套", "衣服", "上衣", "褲"],                    300,   8000, "衣物",   None),
        (["火鍋", "燒肉", "牛排", "壽司", "餐廳", "吃飯", "料理"], 100, 800, "餐飲（每人）", None),
        (["咖啡", "飲料", "下午茶"],                         50,    300, "飲品",   None),
        (["機票", "飯店", "住宿", "旅遊"],                 3000,  50000, "旅遊",   None),
        (["課程", "線上課", "補習"],                        500,  30000, "課程",   None),
        (["保險"],                                         3000,  30000, "年繳保險",None),
    ]

    def _match_item(s):
        sl = s.lower()
        for kws, lo, hi, label, rec_cmd in _ITEM_RANGES:
            if any(k in sl for k in kws):
                return lo, hi, label, rec_cmd
        return None, None, None, None

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

    lo, hi, cat_label, rec_cmd = _match_item(item)
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
