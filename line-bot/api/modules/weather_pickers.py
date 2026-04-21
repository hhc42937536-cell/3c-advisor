"""Weather location picker Flex builders."""

from __future__ import annotations


def build_weather_region_picker(area_regions: dict) -> list:
    """Weather region picker."""
    buttons = [
        {"type": "button", "style": "primary", "color": "#37474F", "height": "sm",
         "action": {"type": "message", "label": f"📍 {region}", "text": f"天氣 地區 {region}"}}
        for region in area_regions.keys()
    ]
    return [{"type": "flex", "altText": "請選擇地區查天氣",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": "🌤️ 天氣＋穿搭建議",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "選擇地區，馬上告訴你今天穿什麼",
                                 "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_weather_city_picker(region: str, area_regions: dict, all_cities: list) -> list:
    """Weather city picker."""
    areas = area_regions.get(region, all_cities)
    rows = []
    for i in range(0, len(areas), 3):
        chunk = areas[i:i + 3]
        cells = [
            {"type": "box", "layout": "vertical", "flex": 1,
             "backgroundColor": "#EEF2F7", "cornerRadius": "10px",
             "paddingAll": "md",
             "action": {"type": "message", "label": city, "text": f"{city}天氣"},
             "contents": [
                 {"type": "text", "text": city, "align": "center",
                  "size": "md", "color": "#1A2D50", "weight": "bold"}
             ]}
            for city in chunk
        ]
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": cells})
    rows.append({"type": "button", "style": "link", "height": "sm",
                 "action": {"type": "message", "label": "← 重選地區", "text": "天氣"}})
    return [{"type": "flex", "altText": f"{region}天氣 — 選城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": f"🌤️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": rows},
             }}]


def build_morning_city_picker() -> list:
    """Morning summary city picker."""
    accent = "#1A1F3A"

    def _btn(city: str, primary: bool = False) -> dict:
        btn: dict = {"type": "button", "style": "primary" if primary else "secondary",
                     "height": "sm", "flex": 1,
                     "action": {"type": "message", "label": city, "text": f"早安 {city}"}}
        if primary:
            btn["color"] = accent
        return btn

    def _rows(cities: list, primary: bool = False) -> list:
        btns = [_btn(city, primary) for city in cities]
        return [{"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": btns[i:i + 3]}
                for i in range(0, len(btns), 3)]

    def _section(label: str, cities: list, primary: bool = False) -> list:
        return [{"type": "text", "text": label, "size": "xs",
                 "color": "#8892B0", "margin": "md"}] + _rows(cities, primary)

    body: list = []
    body += _section("🏙️ 北部", ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"], True)
    body += _section("🌾 中部", ["台中", "彰化", "南投", "雲林"])
    body += _section("☀️ 南部", ["嘉義", "台南", "高雄", "屏東"])
    body += _section("🏔️ 東部 ＋ 離島", ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"])

    return [{"type": "flex", "altText": "早安！請選擇你的城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": accent, "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "☀️ 早安！",
                                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                {"type": "text", "text": "選擇城市，之後每天自動顯示當地資訊",
                                 "color": "#8892B0", "size": "xs", "wrap": True, "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": body},
             }}]
