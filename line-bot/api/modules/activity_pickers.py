"""Activity menu and city picker builders."""

from __future__ import annotations


_AREA_REGIONS = {
    "北部": ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部": ["台中", "彰化", "南投", "雲林"],
    "南部": ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}


_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]


def build_activity_menu(city: str = "") -> list:
    """近期活動 — 主選單"""
    ACCENT = "#5C6BC0"
    suf = f" {city}" if city else ""
    city_hint = f"📍 {city} — 選一個你想玩的類型 👇" if city else "選一個你想玩的類型 👇"
    return [{"type": "flex", "altText": "近期活動",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "🗓️ 近期活動？",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "幫你找好玩的地方！",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": city_hint,
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "也可以說「台南 戶外踏青」「台北 文青咖啡」",
                      "size": "xs", "color": "#8892B0", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🌿 戶外踏青", "text": f"周末 戶外踏青{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "☕ 文青咖啡", "text": f"周末 文青咖啡{suf}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "👶 親子同樂", "text": f"周末 親子同樂{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動健身", "text": f"周末 運動健身{suf}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍜 吃喝玩樂", "text": f"周末 吃喝玩樂{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🎨 市集展覽", "text": f"周末 市集展覽{suf}"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "🎵 表演音樂", "text": f"周末 表演音樂{suf}"}},
                 ]},
             }}]


def build_activity_region_picker(category: str) -> list:
    """近期活動 — 第一步：選擇區域"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    regions = list(_AREA_REGIONS.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"活動 {category} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"近期{category}在哪個地區？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🗓️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_activity_area_picker(category: str, region: str = "") -> list:
    """近期活動 — 第二步：選擇城市"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"周末 {category} {a}"}}
                for a in row
            ]
        })
    # 加一個「← 重選地區」按鈕
    buttons.append({
        "type": "button", "style": "link", "height": "sm",
        "action": {"type": "message", "label": "← 重選地區",
                   "text": f"周末 {category}"}
    })
    return [{"type": "flex", "altText": f"近期{category}在哪個城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🗓️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_activity_city_picker(category: str = "") -> list:
    """近期活動 — 問城市（按北中南東離島分區顯示）"""
    ACCENT = "#5C6BC0"
    cat_suffix = f" {category}" if category else ""

    def _btn(c, primary=False):
        btn = {"type": "button",
               "style": "primary" if primary else "secondary",
               "height": "sm", "flex": 1,
               "action": {"type": "message", "label": c,
                          "text": f"近期活動{cat_suffix} {c}"}}
        if primary:
            btn["color"] = ACCENT
        return btn

    def _rows(cities, primary=False):
        btns = [_btn(c, primary) for c in cities]
        return [{"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": btns[i:i+3]}
                for i in range(0, len(btns), 3)]

    def _section(label, cities, primary=False):
        header = {"type": "text", "text": label, "size": "xs",
                  "color": "#8892B0", "margin": "md"}
        return [header] + _rows(cities, primary)

    region_order = [
        ("🏙️ 北部", ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"], True),
        ("🌾 中部", ["台中", "彰化", "南投", "雲林"], False),
        ("☀️ 南部", ["嘉義", "台南", "高雄", "屏東"], False),
        ("🏔️ 東部 ＋ 離島", ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"], False),
    ]

    body_contents = []
    for label, cities, primary in region_order:
        body_contents.extend(_section(label, cities, primary))

    return [{"type": "flex", "altText": "近期活動 — 你在哪個城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "🗓️ 近期活動",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                {"type": "text", "text": "你在哪個城市？",
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": body_contents},
             }}]
