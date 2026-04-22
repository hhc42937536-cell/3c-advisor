"""Main router for food recommendation text commands."""

from __future__ import annotations

import random as _random
import re


def build_food_message(
    text: str,
    user_id: str = None,
    *,
    all_cities: list,
    area_regions: dict,
    style_keywords: dict,
    redis_set,
    get_user_city,
    set_user_city,
    tw_meal_period,
    build_bib_gourmand_flex,
    build_food_restaurant_flex,
    build_food_area_picker,
    build_food_region_picker,
    build_food_flex,
    build_live_food_events,
    build_food_special_picker,
    build_city_specialties,
    build_food_type_picker,
    build_food_menu,
    build_food_entry_city_picker,
    build_food_entry_region_picker,
    build_trending_specialty=None,
    build_trending_by_district=None,
) -> list:
    """今天吃什麼 — 主路由"""
    text_s = text.strip()

    # ── 解析區域（支援全台 22 縣市）──
    area = ""
    all_cities_pat = "|".join(all_cities)
    area_match = re.search(rf'({all_cities_pat})\S{{0,6}}', text_s)
    if area_match:
        area = area_match.group(0)
        set_user_city(user_id, area[:2])
    area_city = area[:2] if area else ""

    # ── 若用戶沒指定城市，自動帶入上次使用的城市 ──
    if not area_city and user_id:
        saved = get_user_city(user_id)
        if saved:
            area_city = saved
            area = saved

    # ── 解析地區（北部/中部/南部/東部離島）──
    region = ""
    for r in area_regions:
        if r in text_s:
            region = r
            break

    # ── 目的地美食查詢：顯示地址輸入提示 ──
    if "目的地美食" in text_s and "我要分享位置找美食" not in text_s:
        if user_id:
            redis_set(f"food_destination:{user_id}", "1", ttl=300)
        _dest_cities = ["台北", "台南", "高雄", "台中", "桃園", "新北"]
        return [{
            "type": "text",
            "text": (
                "🗺️ 目的地美食查詢\n\n"
                "請直接輸入地址或城市，例如：\n"
                "・台南市東區\n"
                "・高雄左營區文自路\n"
                "・台北信義區\n\n"
                "或點下方按鈕快速選城市 👇"
            ),
            "quickReply": {
                "items": [
                    {"type": "action", "action": {"type": "location", "label": "📍 分享位置"}},
                    *[
                        {"type": "action", "action": {
                            "type": "message", "label": c, "text": f"目的地美食地址:{c}"
                        }}
                        for c in _dest_cities
                    ],
                ]
            }
        }]

    # ── 必買伴手禮 / 最新流行美食 ──
    if build_trending_specialty and build_trending_by_district:
        _souvenir_kw = ["必買伴手禮", "伴手禮推薦", "伴手禮", "必買"]
        _trending_kw = ["最新流行", "最新美食", "最新必吃", "流行美食", "打卡美食"]
        _is_souvenir = any(kw in text_s for kw in _souvenir_kw)
        _is_trending = any(kw in text_s for kw in _trending_kw)
        if not (_is_souvenir or _is_trending):
            if re.search(r'20\d\d', text_s) and "必買" in text_s:
                _is_souvenir = True
            if re.search(r'20\d\d', text_s) and any(w in text_s for w in ["推薦", "流行", "打卡"]):
                _is_trending = True
        if _is_souvenir or _is_trending:
            _district_pat = re.compile(
                r"(必買伴手禮|伴手禮|最新流行|流行美食|打卡美食)\s*"
                r"(台北|新北|基隆|桃園|新竹|苗栗|台中|彰化|南投|雲林"
                r"|嘉義|台南|高雄|屏東|宜蘭|花蓮|台東|澎湖|金門|連江)?"
                r"([^\s]{2,6}[區市鄉鎮])"
            )
            _dm = _district_pat.search(text_s)
            if _dm:
                _d_mode = "souvenir" if any(kw in _dm.group(1) for kw in ["伴手禮", "必買"]) else "trending"
                _d_city = (_dm.group(2) or area_city or "")[:2]
                _d_dist = _dm.group(3)
                return build_trending_by_district(_d_dist, _d_city, _d_mode)
            if _is_souvenir and area_city:
                return build_trending_specialty(area_city, "souvenir")
            if _is_trending and area_city:
                return build_trending_specialty(area_city, "trending")

    # ── 必比登推介 ──
    if "必比登" in text_s or "米其林" in text_s:
        return build_bib_gourmand_flex(area)

    # ── 在地餐廳路由 ──
    is_restaurant = "餐廳" in text_s or "在地餐廳" in text_s
    if is_restaurant:
        food_type = ""
        for ft in ["小吃", "中式", "日式", "西式", "海鮮", "火鍋", "素食", "地方特產"]:
            if ft in text_s:
                food_type = ft
                break
        if area_city:
            return build_food_restaurant_flex(area_city, food_type)
        if region:
            return build_food_area_picker("餐廳", region)
        return build_food_region_picker("餐廳")

    # ── 隨機推薦（幫我決定 / 隨機 / 隨便）──
    if any(w in text_s for w in ["隨機", "幫我決定", "隨便吃", "不知道吃什麼"]):
        _rand_pool = (
            ["早午餐", "輕食", "飲料甜點"]
            if tw_meal_period()[0] == "M"
            else ["便當", "麵食", "小吃", "火鍋", "日韓", "輕食"]
        )
        return build_food_flex(_random.choice(_rand_pool), area_city)

    # ── 解析食物類型 ──
    style = ""
    for cat, kws in style_keywords.items():
        if any(w in text_s for w in kws):
            style = cat
            break
    if not style:
        style = "便當"

    # ── 本週美食活動（Accupass 即時）──
    if "本週美食" in text_s or "美食活動" in text_s:
        if not area_city and region:
            areas = area_regions.get(region, [])
            buttons = []
            for i in range(0, len(areas), 3):
                row = areas[i:i+3]
                buttons.append({"type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                         "action": {"type": "message", "label": a, "text": f"本週美食活動 {a}"}}
                        for a in row
                    ]})
            return [{"type": "flex", "altText": f"本週美食活動 — {region}",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": f"🎉 {region} — 選城市",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        if not area_city:
            buttons = [
                {"type": "button", "style": "primary", "color": "#D84315", "height": "sm",
                 "action": {"type": "message", "label": f"📍 {r}",
                            "text": f"本週美食活動 地區 {r}"}}
                for r in area_regions.keys()
            ]
            return [{"type": "flex", "altText": "本週美食活動 — 選地區",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": "🎉 本週美食活動",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                        {"type": "text", "text": "選擇地區查看近期美食活動",
                                         "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        live_area = area_city
        result = build_live_food_events(live_area)
        if result:
            return result
        return [{"type": "flex", "altText": f"{live_area}目前沒有美食活動",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                "contents": [
                                    {"type": "text", "text": f"🎉 {live_area} 美食活動",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": f"目前 {live_area} 沒有近期美食活動 😢",
                          "size": "sm", "color": "#555555", "wrap": True},
                         {"type": "text", "text": "試試其他方式找好吃的 👇",
                          "size": "xs", "color": "#888888", "margin": "sm"},
                     ]},
                     "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                             {"type": "button", "style": "primary", "color": "#6D4C41", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "在地餐廳",
                                                          "text": f"餐廳 {live_area}"}},
                             {"type": "button", "style": "primary", "color": "#C62828", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "享樂版推薦",
                                                          "text": f"吃什麼 享樂 {live_area}"}},
                         ]},
                         {"type": "button", "style": "secondary", "height": "sm",
                          "action": {"type": "message", "label": "回主選單", "text": "今天吃什麼"}},
                     ]},
                 }}]

    # ── 分享位置快捷 ──
    if "我要分享位置找美食" in text_s:
        if user_id:
            redis_set(f"food_locate:{user_id}", "1", ttl=180)
        return [{
            "type": "text",
            "text": "好的！請分享你的位置，我馬上幫你找附近美食 📍",
            "quickReply": {
                "items": [
                    {"type": "action", "action": {"type": "location", "label": "📍 分享我的位置"}},
                ]
            }
        }]

    # ── 純呼叫主選單 ──
    _food_bare = ["今天吃什麼", "晚餐吃什麼", "午餐吃什麼", "吃什麼", "晚餐推薦", "午餐推薦"]
    if any(text_s == b or text_s.startswith(b + " ") or text_s.startswith(b + "\n")
           for b in _food_bare):
        _sel_match = re.search(r'選城市\s+(' + '|'.join(area_regions.keys()) + r')', text_s)
        if _sel_match:
            return build_food_entry_city_picker(_sel_match.group(1))
        if "選類型" in text_s:
            return build_food_type_picker(area_city)
        if "特殊需求" in text_s:
            return build_food_special_picker(area_city)
        if "地方特色" in text_s:
            if area_city:
                return build_city_specialties(area_city)
            return build_food_special_picker("")
        explicit_style = style and (style != "便當" or "便當" in text_s)
        if explicit_style and area_city:
            return build_food_flex(style, area_city)
        if area_city:
            return build_food_menu(city=area_city, user_id=user_id or "")
        return build_food_entry_region_picker(user_id or "")

    # ── 有風格 + 有城市 → 直接推薦 ──
    if area:
        return build_food_flex(style, area)

    # ── 有風格 + 有地區 → 選城市 ──
    if region:
        return build_food_area_picker(style, region)

    # ── 有風格但沒城市 → 先問地區 ──
    has_style_kw = style != "便當" or any(w in text_s for w in ["便當"])
    is_internal = text_s.startswith("吃什麼 ")
    if has_style_kw and not is_internal:
        return build_food_region_picker(style)

    return build_food_flex(style, area)
