"""Morning summary Flex builder."""

from __future__ import annotations

import datetime as _dt
import re
import threading as _thr
import time as _time
import urllib.parse as _up


def build_morning_summary(
    text: str,
    user_id: str = "",
    *,
    all_cities: list,
    line_bot_id: str,
    morning_actions: list,
    get_user_city,
    set_user_city,
    build_morning_city_picker,
    fetch_cwa_weather,
    fetch_quick_rates,
    fetch_quick_oil,
    wx_icon,
    outfit_advice,
    get_national_deal,
    get_city_local_deal,
) -> list:
    """早安摘要：天氣 + 穿搭 + 匯率 + 油價 + 今日好康"""
    all_cities_pat = "|".join(all_cities)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        city = city_m.group(1)
        set_user_city(user_id, city)
    else:
        saved = get_user_city(user_id)
        if saved:
            city = saved
        else:
            return build_morning_city_picker()

    wx_result: dict = {}
    rates: dict = {}
    oil: dict = {}

    def _wx() -> None:
        nonlocal wx_result
        wx_result = fetch_cwa_weather(city)

    def _rt() -> None:
        nonlocal rates
        rates = fetch_quick_rates()

    def _oil_fn() -> None:
        nonlocal oil
        oil = fetch_quick_oil()

    _t1 = _thr.Thread(target=_wx, daemon=True)
    _t2 = _thr.Thread(target=_rt, daemon=True)
    _t3 = _thr.Thread(target=_oil_fn, daemon=True)
    _t1.start(); _t2.start(); _t3.start()
    _dl = _time.time() + 3
    _t1.join(timeout=max(0, _dl - _time.time()))
    _t2.join(timeout=max(0, _dl - _time.time()))
    _t3.join(timeout=max(0, _dl - _time.time()))

    today = _dt.date.today()
    doy   = today.timetuple().tm_yday
    _WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
    today_str = f"{today.month}月{today.day}日（星期{_WEEKDAYS[today.weekday()]}）"

    if wx_result.get("ok"):
        wx = wx_result
        wx_icon = wx_icon(wx["wx"])
        pop = wx["pop"]
        wx_main = f"{wx_icon} {wx['wx']}　{wx['min_t']}–{wx['max_t']}°C"
        if pop >= 70:
            wx_hint = "☂️ 降雨機率高，記得帶傘！"
        elif pop >= 40:
            wx_hint = "🌂 可能有雨，建議帶傘備用"
        elif wx["max_t"] - wx["min_t"] >= 10:
            wx_hint = "早晚溫差大，注意保暖"
        elif wx["max_t"] >= 32:
            wx_hint = "中午很熱，注意防曬補水"
        else:
            wx_hint = "氣溫舒適，適合外出走走"
        outfit, _, _ = outfit_advice(wx["max_t"], wx["min_t"], pop)
        parts = [outfit]
        if pop >= 40:
            parts.append("帶傘")
        if wx["max_t"] >= 28:
            parts.append("防曬必備")
        wx_outfit = "👔 " + "＋".join(parts)
        wx_night_icon = wx_icon(wx.get("wx_night", ""))
        wx_night = f"今晚 {wx_night_icon} 雨{wx.get('pop_night', 0)}%"
        wx_tom_icon = wx_icon(wx.get("wx_tom", ""))
        wx_tomorrow = f"明天 {wx_tom_icon} {wx.get('min_tom','?')}-{wx.get('max_tom','?')}°C 雨{wx.get('pop_tom',0)}%"
        wx_items = [
            {"type": "text", "text": wx_main,     "size": "md", "weight": "bold", "color": "#1A2D50"},
            {"type": "text", "text": wx_hint,     "size": "xs", "color": "#E65100", "wrap": True},
            {"type": "text", "text": wx_outfit,   "size": "xs", "color": "#37474F", "wrap": True, "margin": "sm"},
            {"type": "text", "text": wx_night,    "size": "xs", "color": "#607D8B", "margin": "xs"},
            {"type": "text", "text": wx_tomorrow, "size": "xs", "color": "#607D8B"},
        ]
    else:
        wx_main = "天氣資料暫時無法取得"
        wx_items = [
            {"type": "text", "text": "☁️ 天氣資料暫時無法取得", "size": "sm", "color": "#888"},
            {"type": "text", "text": f"可說「{city}天氣」查詢",  "size": "xs", "color": "#AAA"},
        ]

    info_items = []
    usd = rates.get("USD", {}) if rates else {}
    jpy = rates.get("JPY", {}) if rates else {}
    if usd.get("spot_sell"):
        r = usd["spot_sell"]
        tip = "🎉便宜" if r <= 29.5 else "⚖️普通" if r <= 31.0 else "⚠️偏高" if r <= 32.0 else "💸高點"
        info_items.append({"type": "text", "text": f"💵 美金 {r:.2f}　{tip}",
                           "size": "xs", "color": "#37474F", "wrap": True})
    if jpy.get("spot_sell"):
        r = jpy["spot_sell"]
        tip = "🎉超便宜" if r <= 0.215 else "😊不錯" if r <= 0.225 else "⚖️普通" if r <= 0.240 else "💸偏貴"
        info_items.append({"type": "text", "text": f"💴 日幣 {r:.4f}　{tip}",
                           "size": "xs", "color": "#37474F", "wrap": True})
    if oil and oil.get("92") and oil["92"] != "?":
        try:
            p = float(oil["92"])
            tip = "🎉便宜加滿" if p <= 28.5 else "⚖️普通" if p <= 30.5 else "⚠️略高" if p <= 32.0 else "💸高點"
            info_items.append({"type": "text",
                               "text": f"⛽ 92/{oil['92']}　95/{oil['95']}　98/{oil['98']}　{tip}",
                               "size": "xs", "color": "#37474F", "wrap": True})
        except Exception:
            pass
    if not info_items:
        info_items = [{"type": "text", "text": "匯率/油價暫時無法取得", "size": "xs", "color": "#AAA"}]

    nat_icon, nat_title, nat_body = get_national_deal(city, user_id)
    loc_icon, loc_title, loc_body = get_city_local_deal(city, user_id)

    tip = morning_actions[doy % len(morning_actions)]

    _bot_invite = f"https://line.me/R/ti/p/{line_bot_id}" if line_bot_id else "https://line.me/R/"
    _share_text = (
        f"☀️ 早安！{city} {today_str}\n\n"
        f"🌤 {wx_main}\n\n"
        f"{nat_icon} {nat_title}：{nat_body}\n\n"
        f"👉 加「生活優轉」每天收到專屬好康：\n{_bot_invite}"
    )
    import urllib.parse as _up
    _share_url = f"https://social-plugins.line.me/lineit/share?url={_up.quote(_share_text)}"

    return [{"type": "flex", "altText": f"☀️ 早安！{city} {today_str}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": f"☀️ 早安！{city}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                {"type": "text", "text": today_str,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "14px", "contents": [
                     {"type": "text", "text": "🌤 今日天氣", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0"},
                     *wx_items,
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "💹 今日匯率＋油價", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "md"},
                     *info_items,
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "🎁 今日小驚喜", "size": "xs",
                      "weight": "bold", "color": "#E65100", "margin": "md"},
                     {"type": "text", "text": f"{nat_icon} {nat_title}", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "sm"},
                     {"type": "text", "text": nat_body, "size": "xs",
                      "color": "#37474F", "wrap": True},
                     {"type": "text", "text": f"{loc_icon} {loc_title}", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "sm"},
                     {"type": "text", "text": loc_body, "size": "xs",
                      "color": "#37474F", "wrap": True},
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "💡 今日健康提醒", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "md"},
                     {"type": "text", "text": tip, "size": "xs",
                      "color": "#37474F", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical",
                            "spacing": "xs", "paddingAll": "10px",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "吃什麼", "text": "今天吃什麼"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "查活動", "text": "近期活動"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "健康", "text": "健康小幫手"}},
                      ]},
                     {"type": "button", "style": "primary", "color": "#E65100", "height": "sm",
                      "action": {"type": "uri", "label": "📤 分享給朋友", "uri": _share_url}},
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": f"📍 換城市（{city}）",
                                 "text": "換城市"}},
                 ]},
             }}]
