"""Oil price and exchange rate builders."""

from __future__ import annotations

import csv as _csv
import json
import re
import ssl as _ssl
import urllib.parse
import urllib.request


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
