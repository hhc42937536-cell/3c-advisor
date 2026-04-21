"""Parking Flex card builder."""

from __future__ import annotations

import time as _time


def build_parking_flex(
    lat: float,
    lon: float,
    city: str = "",
    *,
    tdx_client_id: str,
    parking_cache_key,
    redis_get,
    redis_set,
    parking_result_cache: dict,
    parking_result_ttl: int,
    get_nearby_parking,
) -> list:
    """位置訊息 → 附近停車 Flex Carousel
    路邊格（路名分組）優先，再接停車場，最後加生活推薦卡
    結果快取 3 分鐘（同 2km 格子內共用）
    """
    if not tdx_client_id:
        return [{"type": "flex", "altText": "找車位",
                 "contents": {
                     "type": "bubble",
                     "header": {"type": "box", "layout": "vertical",
                                "backgroundColor": "#C62828", "contents": [
                                    {"type": "text", "text": "🅿️ 找車位",
                                     "color": "#FFFFFF", "weight": "bold"}]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text",
                          "text": "找車位功能尚未設定 TDX API\n請管理員設定 tdx_client_id / TDX_CLIENT_SECRET",
                          "wrap": True, "size": "sm", "color": "#555555"}]},
                 }}]

    # ── 結果快取（座標格子 2km，TTL 3 分鐘）
    ck  = parking_cache_key(lat, lon)
    now = _time.time()
    # Redis 持久快取優先
    redis_result = redis_get(f"parking_{ck}")
    if redis_result is not None:
        print(f"[parking] Redis結果快取命中 {ck}")
        return redis_result
    # in-memory 次之
    if ck in parking_result_cache:
        ts, cached_msgs = parking_result_cache[ck]
        if now - ts < parking_result_ttl:
            print(f"[parking] 記憶體快取命中 key={ck}")
            return cached_msgs

    # 查一次 2km，快取後快速過濾
    radius_used = 2000
    data = get_nearby_parking(lat, lon, radius=2000)
    city   = data["city"]
    street = data["street"]
    lots   = data["lot"]
    all_parks = street + lots

    if not all_parks:
        # 官方資料無結果 → 雙卡片：公立 fallback + 私人停車場
        gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
        city_park_url = "https://www.cityparking.com.tw/"
        times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
        ipark_url     = "https://www.iparking.com.tw/"
        liff_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"

        bubble_public = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🗺️", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "附近停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "Google Maps 整合查詢",
                                 "color": "#8892B0", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#26A69A", "height": "sm",
                          "action": {"type": "uri", "label": "🗺️ 查所有停車場（含私人）", "uri": gmap_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ iParking 即時空位", "uri": ipark_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "📍 換個位置重新查", "uri": liff_url}},
                         {"type": "text",
                          "text": "💡 此區公立開放資料暫無，已切換至地圖搜尋",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        bubble_private = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#37474F", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "私人停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "城市車旅 × Times",
                                 "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                          "action": {"type": "uri", "label": "🏙️ 城市車旅 找車位",
                                     "uri": city_park_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                     "uri": times_url}},
                         {"type": "text",
                          "text": "💡 私人車場通常不提供即時空位，建議先電話確認",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        return [{"type": "flex", "altText": "🅿️ 幫你找附近停車場",
                 "contents": {"type": "carousel",
                              "contents": [bubble_public, bubble_private]}}]

    radius_label = {1500: "1.5公里", 3000: "3公里", 5000: "5公里"}.get(radius_used, f"{radius_used}m")
    source_note = (
        "資料來源：新北市開放資料 + TDX｜實際以現場為準" if city == "NewTaipei" else
        "資料來源：新竹市 HisPark 即時資料｜實際以現場為準" if city == "Hsinchu" else
        "資料來源：台南市停車資訊 + TDX｜實際以現場為準" if city == "Tainan" else
        "資料來源：宜蘭縣開放資料 + TDX｜實際以現場為準" if city == "YilanCounty" else
        f"資料來源：交通部 TDX（{radius_label}內）｜實際以現場為準"
    )

    def _make_bubble(p: dict) -> dict:
        is_street  = p["type"] == "street"
        av, total  = p["available"], p["total"]
        hdr_color  = "#1B5E20" if is_street else "#1565C0"
        type_label = "🛣️ 路邊停車" if is_street else "🅿️ 停車場"

        if av < 0:
            av_text, av_color = "查無資料", "#888888"
        elif av == 0:
            av_text, av_color = "已滿 🔴", "#C62828"
        elif is_street:
            pct = av / total if total else 1
            av_text = f"{av}/{total} 格"
            av_color = "#E65100" if pct < 0.3 else "#2E7D32"
            av_text += " 🟡" if pct < 0.3 else " 🟢"
        else:
            pct = av / total if total > 0 else 1
            av_text = f"{av} 位"
            av_color = "#E65100" if pct < 0.2 else "#2E7D32"
            av_text += " 🟡" if pct < 0.2 else " 🟢"

        dist_text = f"{p['dist']} m" if p["dist"] < 1000 else f"{p['dist']/1000:.1f} km"
        maps_url  = f"https://www.google.com/maps/dir/?api=1&destination={p['lat']},{p['lon']}"

        rows = [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "空位", "size": "xs",
                 "color": "#888888", "flex": 2, "gravity": "center"},
                {"type": "text", "text": av_text, "size": "lg",
                 "weight": "bold", "color": av_color, "flex": 3, "align": "end"},
            ]},
            {"type": "separator", "margin": "sm"},
            {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                {"type": "text", "text": "📍 距離", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": dist_text, "size": "xs", "flex": 3, "align": "end"},
            ]},
        ]
        if p.get("fare"):
            rows.append({"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "💰 費率", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": p["fare"][:25], "size": "xs",
                 "flex": 3, "align": "end", "wrap": True, "maxLines": 1},
            ]})
        rows.append({"type": "text", "text": source_note,
                     "size": "xxs", "color": "#AAAAAA", "margin": "sm", "wrap": True})

        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": hdr_color, "paddingAll": "md",
                "contents": [
                    {"type": "text", "text": type_label,
                     "color": "#FFFFFFBB", "size": "xxs"},
                    {"type": "text", "text": p["name"], "color": "#FFFFFF",
                     "size": "sm", "weight": "bold", "wrap": True, "maxLines": 2},
                ]
            },
            "body": {"type": "box", "layout": "vertical",
                     "spacing": "xs", "paddingAll": "md", "contents": rows},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "sm",
                       "contents": [
                           {"type": "button", "style": "primary", "color": hdr_color,
                            "height": "sm",
                            "action": {"type": "uri", "label": "🗺️ 導航前往", "uri": maps_url}},
                       ]}
        }

    bubbles = [_make_bubble(p) for p in all_parks]

    # ── 統計摘要文字
    street_avail = sum(p["available"] for p in street if p["available"] >= 0)
    lot_avail    = sum(p["available"] for p in lots   if p["available"] >= 0)
    summary = []
    if street: summary.append(f"路邊 {street_avail} 格可停")
    if lots:   summary.append(f"停車場 {lot_avail} 位可停")

    # ── 私人停車場補充卡（城市車旅/Times/iParking）
    # 公立 API 只涵蓋政府管理的停車場，私人業者（CITY PARKING、Times、台灣聯通等）
    # 不提供 Open Data，永遠需要補充這張卡讓使用者自行查詢
    _city_park_url = "https://www.cityparking.com.tw/"
    _times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
    _ipark_url     = "https://www.iparking.com.tw/"
    _gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
    bubble_private = {
        "type": "bubble", "size": "kilo",
        "header": {"type": "box", "layout": "horizontal",
                   "backgroundColor": "#37474F", "paddingAll": "14px",
                   "contents": [
                       {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                       {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                        "contents": [
                            {"type": "text", "text": "私人停車場",
                             "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                            {"type": "text", "text": "城市車旅 × Times × Google Maps",
                             "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                        ]},
                   ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                      "action": {"type": "uri", "label": "🏙️ 城市車旅 CITY PARKING",
                                 "uri": _city_park_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                 "uri": _times_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🗺️ Google Maps 查所有停車場",
                                 "uri": _gmap_url}},
                     {"type": "text",
                      "text": "💡 私人車場空位需至各平台確認，建議先電話洽詢",
                      "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                 ]},
    }
    bubbles.append(bubble_private)

    # life card 已移除 — 美食卡片改由 inline push 緊接在停車結果後送出

    alt = f"已找到 {len(street)} 條路邊路段、{len(lots)} 個停車場"
    result_msgs = [{"type": "flex", "altText": alt,
                    "contents": {"type": "carousel", "contents": bubbles}}]

    # 存入快取
    parking_result_cache[ck] = (now, result_msgs)
    redis_set(f"parking_{ck}", result_msgs, ttl=180)  # 3 分鐘
    return result_msgs
