"""Food menu and area picker Flex builders."""

from __future__ import annotations

from modules.food_utils import _btn3d, _tw_meal_period


def build_food_menu(city: str = "") -> list:
    """今天吃什麼 — 主選單（精簡 4 按鈕版）"""
    period, meal_label = _tw_meal_period()
    suf = f" {city}" if city else ""
    city2 = city[:2] if city else ""
    meal_hints = {
        "M": "輕一點最美味 ☕",
        "D": "飽足感第一 🍱",
        "N": "好好犒賞自己 🎉",
        "L": "消夜就要簡單吃 🌙",
    }
    hint = meal_hints.get(period, "外食族救星！")
    header_sub = f"{city2} · {hint}" if city2 else hint
    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#E65100",
                     "paddingTop": "22px", "paddingBottom": "18px", "paddingAll": "20px",
                     "contents": [
                         {"type": "text", "text": "🍜 今天吃什麼？",
                          "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                         {"type": "text", "text": f"{meal_label} · {header_sub}",
                          "color": "#FFD0B0", "size": "sm", "margin": "sm", "wrap": True},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "16px", "spacing": "md",
                     "contents": [
                         _btn3d("🎲 幫我決定！（隨機推薦）",
                                f"吃什麼 隨機{suf}", "#27AE60", "#1A6E35"),
                         _btn3d("📍 分享位置，推薦附近美食",
                                "📍 我要分享位置找美食", "#1565C0", "#0A3D8A"),
                         _btn3d("🗺️ 目的地美食查詢",
                                "目的地美食", "#00695C", "#003D36"),
                         {"type": "separator", "margin": "md", "color": "#E0E0E0"},
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                              _btn3d("🍽️ 選類型", f"吃什麼 選類型{suf}",
                                     "#BF360C", "#7A1F05", flex=1),
                              _btn3d("🏅 評鑑推薦", f"吃什麼 特殊需求{suf}",
                                     "#6A1B9A", "#3E0B6B", flex=1),
                          ]},
                     ]},
             }}]


def build_food_type_picker(city: str = "") -> list:
    """第二層：選類型（依早/午/晚/消夜四時段調整順序與標題）"""
    period, meal_label = _tw_meal_period()
    suf = f" {city}" if city else ""
    _period_cfg = {
        "M": (["台式早餐", "西式早餐", "早午餐", "粥", "麵包蛋糕", "輕食", "飲料甜點"],
              "☀️ 早餐時間，吃好一點開始今天"),
        "D": (["便當", "麵食", "拉麵", "港式", "義式", "小吃", "日韓", "火鍋", "素食", "輕食"],
              "🌞 午餐時間，飽足感優先"),
        "N": (["火鍋", "便當", "日韓", "燒烤", "拉麵", "義式", "港式", "麵食", "素食"],
              "🌙 晚餐時間，好好犒賞自己"),
        "L": (["夜市小吃", "炸物", "拉麵", "粥", "火鍋", "麵食", "飲料甜點"],
              "🌃 消夜時間，簡單吃就好"),
    }
    order, hint = _period_cfg.get(period, _period_cfg["D"])
    _row_colors = [
        ("#D84315", "#8A2400"),
        ("#6D4C41", "#3E2723"),
        ("#37474F", "#1C3039"),
    ]
    rows = []
    for ri, i in enumerate(range(0, len(order), 3)):
        chunk = order[i:i+3]
        mc, sc = _row_colors[min(ri, len(_row_colors) - 1)]
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [_btn3d(k, f"吃什麼 {k}{suf}", mc, sc, flex=1)
                                   for k in chunk]})
    return [{"type": "flex", "altText": "選類型推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#BF360C",
                     "paddingAll": "16px", "paddingTop": "18px",
                     "contents": [
                         {"type": "text", "text": f"🍽️ {meal_label} — 選類型",
                          "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                         {"type": "text", "text": hint,
                          "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "12px", "spacing": "sm",
                     "contents": rows + [
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "← 回主選單",
                                     "text": f"今天吃什麼{suf}"}},
                     ]},
             }}]


def build_food_special_picker(city: str = "") -> list:
    """第二層：精選評鑑（必比登 / 在地餐廳 / 聚餐 / 美食活動）"""
    suf = f" {city}" if city else ""
    return [{"type": "flex", "altText": "精選評鑑推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#4A148C",
                     "paddingAll": "16px", "paddingTop": "18px",
                     "contents": [
                         {"type": "text", "text": "🏅 精選評鑑推薦",
                          "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                         {"type": "text", "text": "評鑑認可 / 多人聚餐 / 近期美食活動",
                          "color": "#CE93D8", "size": "xs", "margin": "xs"},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "12px", "spacing": "sm",
                     "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                              _btn3d("⭐ 必比登", f"必比登{suf}", "#E65100", "#8A3000", flex=1),
                              _btn3d("🏠 在地餐廳", f"在地餐廳{suf}", "#1565C0", "#0A3D8A", flex=1),
                          ]},
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                              _btn3d("🍻 多人聚餐", "聚餐", "#C62828", "#7B1515", flex=1),
                              _btn3d("🎪 美食活動", "本週美食活動", "#6A1B9A", "#3E0B6B", flex=1),
                          ]},
                         _btn3d("🌏 地方特色小吃", f"地方特色{suf}", "#00695C", "#003D36"),
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "← 回主選單",
                                     "text": f"今天吃什麼{suf}"}},
                     ]},
             }}]


def build_food_entry_region_picker(area_regions: dict) -> list:
    """今天吃什麼 — 分享位置優先，備用地區選擇"""
    keys = list(area_regions.keys())
    region_rows = []
    for i in range(0, len(keys), 3):
        row_btns = [
            {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
             "action": {"type": "message", "label": r, "text": f"今天吃什麼 選城市 {r}"}}
            for r in keys[i:i+3]
        ]
        region_rows.append({"type": "box", "layout": "horizontal",
                             "spacing": "sm", "contents": row_btns})
    _quick_items = [
        {"type": "action", "action": {"type": "location", "label": "📍 分享我的位置"}},
        {"type": "action", "action": {"type": "message", "label": "北部", "text": "今天吃什麼 選城市 北部"}},
        {"type": "action", "action": {"type": "message", "label": "中部", "text": "今天吃什麼 選城市 中部"}},
        {"type": "action", "action": {"type": "message", "label": "南部", "text": "今天吃什麼 選城市 南部"}},
        {"type": "action", "action": {"type": "message", "label": "東部離島", "text": "今天吃什麼 選城市 東部離島"}},
    ]
    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "🍽️ 今天吃什麼？",
                                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                {"type": "text", "text": "分享位置，秒推 1.5km 內美食地圖",
                                 "color": "#FFCCAA", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "14px",
                          "contents": [
                              {"type": "button", "style": "primary", "color": "#E65100",
                               "action": {"type": "message",
                                          "label": "📍 分享位置，立即推薦附近美食",
                                          "text": "📍 我要分享位置找美食"}},
                              {"type": "separator"},
                              {"type": "text", "text": "或選擇地區", "size": "xs",
                               "color": "#AAAAAA", "align": "center"},
                              *region_rows,
                          ]},
             },
             "quickReply": {"items": _quick_items}}]


def build_food_entry_city_picker(region: str, area_regions: dict, all_cities: list) -> list:
    """今天吃什麼（無城市）— 第二步：選城市"""
    areas = area_regions.get(region, all_cities)
    rows = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        rows.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"今天吃什麼 {a}"}}
                for a in row
            ]
        })
    rows.append(
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "message", "label": "← 重選地區", "text": "今天吃什麼"}}
    )
    return [{"type": "flex", "altText": f"{region} — 選擇城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": f"🍽️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": rows},
             }}]


def build_food_region_picker(style: str, area_regions: dict) -> list:
    """今天吃什麼 — 選擇地區（第一步）"""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32",
              "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    icons = {"便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗", "餐廳": "🏪"}
    icon = icons.get(style, "🍽️")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    regions = list(area_regions.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"{trigger} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"你在哪個地區？{icon}{style}推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🍽️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的{icon} {style}美食",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_food_area_picker(style: str, region: str, area_regions: dict, all_cities: list) -> list:
    """今天吃什麼 — 選擇城市（第二步）"""
    colors = {"便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00", "火鍋": "#D32F2F",
              "日韓": "#1565C0", "早午餐": "#FF8F00", "飲料甜點": "#6A1B9A", "輕食": "#2E7D32",
              "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    areas = area_regions.get(region, all_cities)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"{trigger} {a}"}}
                for a in row
            ]
        })
    buttons.append(
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "message", "label": "← 重選地區", "text": trigger}}
    )
    return [{"type": "flex", "altText": f"{region}有哪些城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🍽️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]
