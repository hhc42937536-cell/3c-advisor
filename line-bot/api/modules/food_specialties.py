"""City specialty food builders."""

from __future__ import annotations

import concurrent.futures
import json
import re
import urllib.parse

# ─── 行政區資料 ──────────────────────────────────────────
_CITY_DISTRICTS: dict[str, list[str]] = {
    "台北": ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
    "新北": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "樹林區", "鶯歌區", "三峽區", "淡水區", "汐止區", "土城區"],
    "台中": ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區"],
    "台南": ["中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區", "歸仁區", "新營區", "鹽水區"],
    "高雄": ["楠梓區", "左營區", "鼓山區", "三民區", "鹽埕區", "前金區", "新興區", "苓雅區", "前鎮區", "小港區", "鳳山區", "林園區"],
    "桃園": ["桃園區", "中壢區", "大溪區", "楊梅區", "蘆竹區", "龜山區", "八德區", "龍潭區", "平鎮區"],
    "基隆": ["仁愛區", "信義區", "中正區", "中山區", "安樂區", "暖暖區", "七堵區"],
    "新竹": ["東區", "北區", "香山區", "竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉"],
    "苗栗": ["苗栗市", "頭份市", "竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", "公館鄉", "三義鄉", "大湖鄉"],
    "彰化": ["彰化市", "員林市", "和美鎮", "鹿港鎮", "溪湖鎮", "田中鎮", "北斗鎮", "二林鎮"],
    "南投": ["南投市", "埔里鎮", "草屯鎮", "竹山鎮", "集集鎮", "名間鄉", "魚池鄉", "國姓鄉", "水里鄉"],
    "雲林": ["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "北港鎮", "土庫鎮", "二崙鄉", "崙背鄉"],
    "嘉義": ["東區", "西區", "太保市", "朴子市", "布袋鎮", "大林鎮", "民雄鄉", "新港鄉"],
    "屏東": ["屏東市", "潮州鎮", "東港鎮", "恆春鎮", "萬丹鄉", "內埔鄉", "里港鄉", "高樹鄉"],
    "宜蘭": ["宜蘭市", "羅東鎮", "蘇澳鎮", "頭城鎮", "礁溪鄉", "壯圍鄉", "員山鄉", "冬山鄉", "五結鄉", "三星鄉"],
    "花蓮": ["花蓮市", "吉安鄉", "壽豐鄉", "鳳林鎮", "光復鄉", "瑞穗鄉", "玉里鎮"],
    "台東": ["台東市", "成功鎮", "關山鎮", "池上鄉", "卑南鄉", "鹿野鄉", "長濱鄉"],
    "澎湖": ["馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"],
    "金門": ["金城鎮", "金湖鎮", "金沙鎮", "金寧鄉", "烈嶼鄉"],
    "連江": ["南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"],
}


def build_city_specialties(
    city: str,
    city_specialties: dict,
    tw_season,
    restaurant_fallback,
    text_search_places=None,
    places_photo_url=None,
    redis_get=None,
    redis_set=None,
) -> list:
    """城市特色小吃：含 Places API 評分、照片、換城市卡、quickReply。"""
    city2 = city[:2] if city else ""
    season = tw_season(city2)
    pool = city_specialties.get(city, city_specialties.get(city2, []))
    if not pool:
        return restaurant_fallback(city)
    items = [p for p in pool if p.get("s", "") in ("", season)]
    if not items:
        items = pool

    def _fetch_place(key: str) -> dict:
        """搜 Places API 取 photo_ref + rating，7 天 Redis 快取。"""
        cache_key = f"specialty_place:{key}"
        if redis_get:
            cached = redis_get(cache_key)
            if cached:
                try:
                    return json.loads(cached) if isinstance(cached, str) else cached
                except Exception:
                    pass
        if not text_search_places:
            return {}
        results = text_search_places(key, max_results=1)
        data: dict = {}
        if results:
            r = results[0]
            data = {
                "photo_ref": r.get("photo_ref", ""),
                "rating": r.get("rating", 0),
                "reviews": r.get("user_ratings_total", 0),
            }
        if redis_set and data:
            redis_set(cache_key, json.dumps(data), ttl=7 * 86400)
        return data

    def _bubble(item: dict, place: dict) -> dict:
        tag = ("🌞 夏季限定" if item.get("s") == "hot"
               else ("🧥 冬季限定" if item.get("s") == "cold" else "🗺️ 在地特色"))
        photo_url = (places_photo_url(place.get("photo_ref", ""))
                     if places_photo_url and place.get("photo_ref") else "")
        rating = place.get("rating", 0)
        reviews = place.get("reviews", 0)

        if rating >= 4.5 and reviews >= 100:
            rating_str = f"★{rating}  ({reviews}則)"
            rating_color = "#E53935"
        elif rating >= 4.0:
            rating_str = f"★{rating}  ({reviews}則)" if reviews else f"★{rating}"
            rating_color = "#F57C00"
        elif rating:
            rating_str = f"★{rating}"
            rating_color = "#888888"
        else:
            rating_str = ""
            rating_color = "#888888"

        body_contents: list = [
            {"type": "text", "text": item["desc"], "size": "sm", "color": "#444444", "wrap": True},
        ]
        if rating_str:
            body_contents.append(
                {"type": "text", "text": rating_str, "size": "xs",
                 "color": rating_color, "margin": "sm"}
            )

        bubble: dict = {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "10px",
                "contents": [
                    {"type": "text", "text": item["name"],
                     "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
                    {"type": "text", "text": tag,
                     "color": "#8892B0", "size": "xxs", "margin": "xs"},
                ]},
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "12px",
                "contents": body_contents,
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#FF6B35", "height": "sm",
                     "action": {"type": "message", "label": "🏆 找名店推薦",
                                "text": f"特色名店 {city2} {item['name']}"}},
                ]},
        }
        if photo_url:
            bubble["hero"] = {
                "type": "image", "url": photo_url,
                "size": "full", "aspectRatio": "20:13", "aspectMode": "cover",
            }
        return bubble

    batch = items[:8]
    # 平行抓取評分（Places API 有 key 才呼叫）
    if text_search_places:
        keys = [it.get("key", it["name"]) for it in batch]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            place_data = list(ex.map(_fetch_place, keys))
    else:
        place_data = [{} for _ in batch]

    bubbles = [_bubble(item, place) for item, place in zip(batch, place_data)]

    # 換城市卡
    specialty_cities = list(city_specialties.keys())
    city_btn_rows: list = []
    row: list = []
    for i, c in enumerate(specialty_cities):
        row.append({
            "type": "button", "style": "secondary", "flex": 1, "height": "sm",
            "action": {"type": "message", "label": c, "text": f"地方特色 {c}"},
        })
        if len(row) == 3 or i == len(specialty_cities) - 1:
            city_btn_rows.append({"type": "box", "layout": "horizontal",
                                   "spacing": "xs", "contents": row})
            row = []
    bubbles.append({
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#37474F", "paddingAll": "10px",
            "contents": [
                {"type": "text", "text": "📍 換個城市看看",
                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                {"type": "text", "text": "點選城市切換特色小吃",
                 "color": "#B0BEC5", "size": "xxs", "margin": "xs"},
            ]},
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "10px",
            "contents": city_btn_rows,
        },
    })

    quick_reply = {
        "items": [
            {"type": "action", "action": {
                "type": "message", "label": "🛍 必買伴手禮",
                "text": f"必買伴手禮 {city2}"}},
            {"type": "action", "action": {
                "type": "message", "label": "🔥 最新流行美食",
                "text": f"最新流行 {city2}"}},
        ]
    }
    return [{"type": "flex", "altText": f"{city2} 特色美食",
             "contents": {"type": "carousel", "contents": bubbles},
             "quickReply": quick_reply}]


def build_specialty_shops(city: str, food_name: str, text_search_places, restaurant_bubble_builder) -> list:
    """第二步：用 Google Places Text Search 搜該城市的食物名店。"""
    city2 = city[:2] if city else ""
    query = f"{city2} {food_name}"
    shops = text_search_places(query, max_results=5)
    if not shops:
        gmap_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/"
        return [{"type": "text",
                 "text": f"搜尋「{query}」名店中...\n目前無法取得即時資料，點下方連結用 Google Maps 搜尋 👇\n{gmap_uri}"}]
    eaten_set: set = set()
    bubbles = []
    for r in shops:
        r["dist"] = None
        b = restaurant_bubble_builder(r, None, None, city2, eaten_set,
                                     subtitle=f"🏆 {city2}{food_name}名店")
        bubbles.append(b)
    return [{"type": "flex", "altText": f"{query} 名店推薦",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_trending_by_district(
    district: str,
    city2: str,
    mode: str,
    text_search_places,
    restaurant_bubble_builder,
    redis_get=None,
    redis_set=None,
) -> list:
    """行政區層級：必買伴手禮 / 最新流行 — Google Places 即時搜尋。"""
    is_souvenir = mode == "souvenir"
    color = "#2E7D32" if is_souvenir else "#E65100"
    mode_label = "必買伴手禮" if is_souvenir else "最新流行美食"
    title = f"🛍 {district} 必買伴手禮" if is_souvenir else f"🔥 {district} 最新流行美食"
    alt = f"{district} {mode_label}"
    swap_label = "🔥 最新流行" if is_souvenir else "🛍 必買伴手禮"
    swap_mode = "最新流行" if is_souvenir else "必買伴手禮"
    intent_prefix = "必買伴手禮" if is_souvenir else "最新流行"

    nav_bubble: dict = {
        "type": "bubble", "size": "kilo",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": color, "paddingAll": "12px",
            "contents": [
                {"type": "text", "text": title, "color": "#FFFFFF", "size": "md", "weight": "bold"},
                {"type": "text", "text": "整合 Google Maps + 部落格精選",
                 "color": "#FFFFFF", "size": "xxs", "margin": "xs"},
            ]},
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "12px",
            "contents": [
                {"type": "button", "style": "primary", "height": "sm",
                 "color": "#E65100" if is_souvenir else "#2E7D32",
                 "action": {"type": "message", "label": swap_label,
                            "text": f"{swap_mode} {city2}"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": f"← {city2} 行政區",
                            "text": f"{intent_prefix} {city2}"}},
            ]},
    }

    bubbles: list[dict] = []

    def _normalize_brand(name: str) -> str:
        for sep in ['|', '｜', '·', '•', '-', '－']:
            name = name.split(sep)[0]
        name = re.sub(r'[（(【\[].*', '', name)
        name = re.sub(
            r'\s+(?:台北|新北|基隆|桃園|新竹|苗栗|台中|彰化|南投|雲林'
            r'|嘉義|台南|高雄|屏東|宜蘭|花蓮|台東|澎湖|金門|連江)\S*', '', name)
        name = re.sub(r'[\u4e00-\u9fff]{1,4}[店館分舖號]$', '', name).strip()
        cjk = re.sub(r'[^\u4e00-\u9fff]', '', name)
        return cjk[:3]

    seen_pids: set[str] = set()
    seen_brands: set[str] = set()

    def _add_new(p: dict) -> None:
        pid = p.get("place_id", "")
        bk = _normalize_brand(p.get("name", ""))
        if (pid and pid in seen_pids) or (bk and bk in seen_brands):
            return
        if pid:
            seen_pids.add(pid)
        if bk:
            seen_brands.add(bk)
        bubbles.append(restaurant_bubble_builder(p, None, None, city2, set(), subtitle=title))

    # Google Places 搜尋（帶 Redis 快取 3 天）
    _souvenir_exclude = {"健康餐", "便當", "滷味", "鹹水雞", "剉冰", "冰品", "火鍋", "拉麵", "壽司"}
    kw = (f"{district} 伴手禮 老店 禮盒 名產館"
          if is_souvenir else f"{district} 人氣 必吃 新開")
    cache_key = f"trending_district:{mode}:{district}"
    places: list = []
    if redis_get:
        cached = redis_get(cache_key)
        if cached:
            try:
                places = json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
    if not places:
        raw = text_search_places(kw, max_results=12)
        if is_souvenir:
            raw = [p for p in raw
                   if not any(ex in p.get("name", "") for ex in _souvenir_exclude)]
        else:
            raw = [p for p in raw if (p.get("user_ratings_total") or 9999) <= 3000]
        filtered = [p for p in raw if (p.get("rating") or 0) >= 3.8]
        places = (filtered or raw)[:8]
        if places and redis_set:
            redis_set(cache_key, json.dumps(places), ttl=3 * 86400)

    for p in places:
        _add_new(p)

    if not bubbles:
        return [{"type": "text",
                 "text": f"目前找不到 {district} 的{mode_label}資料，試試「地方特色 {city2}」"}]

    return [{"type": "flex", "altText": alt,
             "contents": {"type": "carousel",
                          "contents": [nav_bubble] + bubbles[:10]}}]


def build_trending_specialty(
    city: str,
    mode: str,
    text_search_places,
    restaurant_bubble_builder,
    redis_get=None,
    redis_set=None,
) -> list:
    """城市層級必買伴手禮 / 最新流行：顯示市區結果，quickReply 供細分行政區。"""
    city2 = city[:2] if city else ""
    if not city2:
        return []

    is_souvenir = mode == "souvenir"
    intent_prefix = "必買伴手禮" if is_souvenir else "最新流行"
    swap_label = "🔥 最新流行" if is_souvenir else "🛍 必買伴手禮"
    swap_mode = "最新流行" if is_souvenir else "必買伴手禮"

    msgs = build_trending_by_district(
        city2, city2, mode,
        text_search_places, restaurant_bubble_builder,
        redis_get=redis_get, redis_set=redis_set,
    )
    districts = _CITY_DISTRICTS.get(city2, [])[:12]
    if msgs and districts:
        quick_items = [
            {"type": "action", "action": {
                "type": "message", "label": d[:6],
                "text": f"{intent_prefix} {city2}{d}"}}
            for d in districts
        ]
        quick_items.append({"type": "action", "action": {
            "type": "message", "label": swap_label,
            "text": f"{swap_mode} {city2}"}})
        msgs[0]["quickReply"] = {"items": quick_items[:13]}
    return msgs
