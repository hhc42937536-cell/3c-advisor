"""Weather Flex card builders."""

from __future__ import annotations

import urllib.parse


def build_weather_flex(
    city: str,
    user_id: str = "",
    *,
    fetch_cwa_weather,
    fetch_aqi,
    outfit_advice,
    wx_icon,
    estimate_uvi,
    bot_invite_text,
) -> list:
    """天氣＋穿搭建議卡片"""
    w = fetch_cwa_weather(city)
    if not w.get("ok"):
        if w.get("error") == "no_key":
            return [{"type": "text", "text":
                "⚠️ 天氣功能需要設定 CWA API Key\n"
                "請到 Vercel → Settings → Environment Variables\n"
                "加入 CWA_API_KEY\n"
                "申請（免費）：https://opendata.cwa.gov.tw/user/api"}]
        return [{"type": "text", "text": f"😢 目前無法取得 {city} 的天氣資料，請稍後再試"}]

    clothes, note, umbrella = outfit_advice(w["max_t"], w["min_t"], w["pop"])
    icon = wx_icon(w["wx"])
    icon_n = wx_icon(w["wx_night"])
    icon_t = wx_icon(w["wx_tom"])
    aqi = fetch_aqi(city)

    if "雨" in w["wx"]:        hdr = "#1565C0"
    elif w["max_t"] >= 30:    hdr = "#E65100"
    elif w["max_t"] >= 24:    hdr = "#F57C00"
    else:                     hdr = "#37474F"

    body = [
        {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{icon} {w['wx']}", "size": "lg", "weight": "bold",
             "color": hdr, "flex": 3, "wrap": True},
            {"type": "text", "text": f"{w['min_t']}–{w['max_t']}°C",
             "size": "lg", "weight": "bold", "color": hdr, "flex": 2, "align": "end"},
        ]},
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": f"💧 降雨 {w['pop']}%", "size": "sm", "color": "#555555", "flex": 1},
            {"type": "text", "text": f"今晚 {icon_n} 雨{w['pop_night']}%",
             "size": "sm", "color": "#555555", "flex": 1, "align": "end"},
        ]},
    ]
    if aqi.get("ok"):
        body.append({"type": "text", "text": aqi["label"], "size": "sm",
                     "color": aqi["color"], "wrap": True, "margin": "xs"})
    body.append({"type": "separator", "margin": "md"})
    body += [
        {"type": "text", "text": "👗 今日穿搭建議", "size": "md", "weight": "bold",
         "color": "#333333", "margin": "md"},
        {"type": "text", "text": clothes, "size": "sm", "color": "#444444",
         "wrap": True, "margin": "xs"},
        {"type": "text", "text": f"💡 {note}", "size": "sm", "color": "#777777",
         "wrap": True, "margin": "xs"},
    ]
    if umbrella:
        body.append({"type": "text", "text": umbrella, "size": "sm",
                     "color": "#1565C0", "weight": "bold", "margin": "sm"})

    uvi = estimate_uvi(w["wx"], w["max_t"])
    if uvi.get("ok"):
        body.append({"type": "text", "text": uvi["label"], "size": "sm",
                     "color": "#E65100", "wrap": True, "margin": "xs"})

    body.append({"type": "separator", "margin": "md"})

    _suggest = []
    _tdiff = w["max_t"] - w["min_t"]
    if _tdiff >= 10:
        _suggest.append(f"🌡️ 今日溫差 {_tdiff}°C，外出一定要帶外套")
    elif _tdiff >= 7:
        _suggest.append(f"🌡️ 溫差 {_tdiff}°C，早晚記得加衣")

    if "雨" in w["wx"] or w["pop"] >= 60:
        _suggest.append("🏠 雨天最適合咖啡廳、室內逛街或窩在家")
    elif w["max_t"] >= 33:
        _suggest.append("🏊 高溫天，泳池或室內冷氣活動最涼快")
    elif w["max_t"] >= 27 and ("晴" in w["wx"] or "多雲" in w["wx"]):
        _suggest.append("🚴 好天氣！適合騎車、健行、戶外活動")
    elif w["max_t"] <= 20:
        _suggest.append("☕ 涼爽天，逛夜市、喝熱飲、散步心情好")
    else:
        _suggest.append("🌿 天氣舒適，外出走走心情好")

    if aqi.get("ok"):
        if aqi["aqi"] <= 50:
            _suggest.append("💨 空氣品質良好，適合開窗通風")
        elif aqi["aqi"] > 100:
            _suggest.append("😷 空氣品質不佳，外出建議戴口罩")

    _trend = w["max_tom"] - w["max_t"]
    if _trend >= 3:
        _suggest.append(f"📈 明天升溫 +{_trend}°C，越來越熱囉")
    elif _trend <= -3:
        _suggest.append(f"📉 明天降溫 {abs(_trend)}°C，多備一件衣")
    elif "雨" in w["wx_tom"] and "雨" not in w["wx"]:
        _suggest.append("🌧️ 明天有雨，今天記得把衣服收進來")

    if _suggest:
        body.append({"type": "text", "text": "💡 今日建議",
                     "size": "sm", "weight": "bold", "color": "#37474F", "margin": "sm"})
        for _s in _suggest:
            body.append({"type": "text", "text": _s, "size": "xs",
                         "color": "#555555", "wrap": True, "margin": "xs"})

    body += [
        {"type": "separator", "margin": "md"},
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": "明日", "size": "sm", "color": "#999999", "flex": 1},
            {"type": "text", "text": f"{icon_t} {w['wx_tom']}", "size": "sm",
             "color": "#555555", "flex": 2},
            {"type": "text", "text": f"{w['min_tom']}–{w['max_tom']}°C  雨{w['pop_tom']}%",
             "size": "sm", "color": "#555555", "flex": 3, "align": "end"},
        ]},
    ]

    food_label = "雨天吃什麼" if "雨" in w["wx"] else "今天吃什麼"
    food_text  = "吃什麼 享樂" if "雨" in w["wx"] else "今天吃什麼"

    _umbrella_hint = f"\n{umbrella}" if umbrella else ""
    _weather_share = (
        f"🌤️ {city}今天天氣\n"
        f"{icon} {w['wx']}　{w['min_t']}–{w['max_t']}°C\n"
        f"💧 降雨 {w['pop']}%{_umbrella_hint}\n\n"
        f"👗 穿搭建議：{clothes}\n"
        f"💡 {note}"
        f"{bot_invite_text()}"
    )
    _weather_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_weather_share)

    return [{"type": "flex", "altText": f"{city}天氣 {w['min_t']}–{w['max_t']}°C {w['wx']}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": "#26A69A", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🌤️ {city}今日天氣",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "中央氣象署即時預報＋穿搭建議",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "xs",
                          "contents": body},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "contents": [
                                     {"type": "button", "style": "primary", "color": "#26A69A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message", "label": "重新整理",
                                                 "text": f"{city}天氣"}},
                                     {"type": "button", "style": "primary", "color": "#1A1F3A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message",
                                                 "label": food_label, "text": food_text}},
                                 ]},
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "contents": [
                                     {"type": "button", "style": "secondary", "flex": 1,
                                      "height": "sm",
                                      "action": {"type": "message", "label": "📍 換城市",
                                                 "text": "換城市"}},
                                     {"type": "button", "style": "link", "flex": 1,
                                      "height": "sm",
                                      "action": {"type": "uri",
                                                 "label": "📤 傳給家人朋友",
                                                 "uri": _weather_share_url}},
                                 ]},
                            ]},
             }}]
