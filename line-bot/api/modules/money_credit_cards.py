"""Credit card reward recommendation builders."""

from __future__ import annotations


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
                 "action": {"type": "uri", "label": "🔍 Google 搜尋申辦",
                            "uri": apply_url}},
            ]},
        })

    return [{"type": "flex", "altText": f"{emoji} {category} 推薦信用卡",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_credit_card_advice() -> list:
    return build_credit_card_menu()
