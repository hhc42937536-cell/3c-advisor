"""Activity Flex message builders."""

from __future__ import annotations

import datetime as _dt
import os
import urllib.parse

from modules.activity_data import _ACTIVITY_DB
from modules.activity_utils import _get_accupass_cache
from modules.activity_utils import _get_coming_weekend_label
from modules.activity_utils import _is_event_past
from modules.activity_utils import _maps_url
from modules.activity_utils import _parse_event_date
from modules.activity_utils import _parse_event_weekday


LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")


def build_activity_flex(category: str, area: str = "") -> list:
    """列出所有活動推薦（即時＋推薦景點），用 carousel 多頁呈現"""
    area2 = area[:2] if area else ""

    # ── 1. 從 Accupass 快取取得即時活動 ──
    live_events = []
    skipped_past = 0
    _ac = _get_accupass_cache()
    if _ac and area2:
        city_cache = _ac.get(area, _ac.get(area2, {}))
        live_raw = city_cache.get(category, [])
        for e in live_raw:
            date_str = e.get("date", "")
            # ── 過濾已過期活動（結束日在 3 天前以上）──
            if _is_event_past(date_str):
                skipped_past += 1
                continue
            day_label = _parse_event_weekday(date_str)
            date_short = date_str.split(" ")[0] if date_str else ""
            event_date = _parse_event_date(date_str)  # 用於排序
            live_events.append({
                "name":       e.get("name", ""),
                "desc":       e.get("desc", ""),
                "area":       area,
                "url":        e.get("url", ""),
                "is_live":    True,
                "day":        day_label,
                "date_short": date_short,
                "_date":      event_date,   # 內部排序用，不顯示
            })
    if skipped_past:
        print(f"[activity] 過濾掉 {skipped_past} 筆已過期活動")

    # ── 2. 從靜態資料庫取得推薦景點 ──
    static_pool = _ACTIVITY_DB.get(category, [])
    if area2:
        static_filtered = [a for a in static_pool if area2 in a.get("area", "")]
        if not static_filtered:
            static_filtered = static_pool
    else:
        static_filtered = static_pool

    live_names = {e["name"] for e in live_events}
    static_dedup = [e for e in static_filtered if e["name"] not in live_names]

    colors = {
        "戶外踏青": "#2E7D32", "文青咖啡": "#4527A0", "親子同樂": "#E65100",
        "運動健身": "#1565C0", "吃喝玩樂": "#C62828",
        "市集展覽": "#6A1B9A", "表演音樂": "#AD1457",
    }
    color = colors.get(category, "#FF8C42")
    area_label = f"（{area}）" if area else ""
    cats = list(_ACTIVITY_DB.keys())
    next_cat = cats[(cats.index(category) + 1) % len(cats)]  # noqa: F841
    weekend_label = _get_coming_weekend_label()

    # ── 3. 即時活動依日期由近到遠排序（無日期排最後）──
    _far_future = _dt.date(2099, 12, 31)
    live_events.sort(key=lambda x: x.get("_date") or _far_future)

    # ── 4. 建立 bubble 內容項目的 helper ──
    def _make_items(acts: list) -> list:
        items = []
        for i, act in enumerate(acts):
            is_live = act.get("is_live", False)
            date_info = act.get("date_short", "")
            day_info = act.get("day", "")
            if is_live and date_info:
                tag = f"🆕 {date_info}"
            elif is_live and day_info:
                tag = f"🆕 週{day_info}"
            elif is_live:
                tag = "🔄 進行中"   # 無明確日期 → 長期展覽/持續活動
            else:
                tag = "📌 推薦"
            detail_btn = (
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📅 活動頁面",
                            "uri": act.get("url") or "https://www.accupass.com"}}
                if is_live else
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📍 地圖",
                            "uri": _maps_url(act["name"], act.get("area", ""))}}
            )
            # 分享文字：這個活動 + bot 邀請（壓短避免超過 LINE URI 1000 字元限制）
            _act_name = act["name"][:20]
            _act_date = act.get("date_short") or (f"週{act.get('day','')}" if act.get("day") else "")
            _date_str = f" {_act_date}" if _act_date else ""
            _invite = f"\n👉 搜「生活優轉」也來查" if not LINE_BOT_ID else f"\nhttps://line.me/ti/p/{LINE_BOT_ID}"
            _share_raw = f"📍 揪你去！\n🎪 {_act_name}{_date_str}{_invite}"
            _share_url_act = "https://line.me/R/share?text=" + urllib.parse.quote(_share_raw)
            share_btn = {"type": "button", "style": "link", "height": "sm", "flex": 1,
                         "action": {"type": "uri", "label": "📤 揪朋友去", "uri": _share_url_act}}

            # 截短描述，避免某頁撐太高導致其他頁留白
            desc_raw = act.get("desc", "")
            desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
            items += [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": f"• {act['name']}", "weight": "bold",
                     "size": "sm", "color": color, "flex": 4, "wrap": True,
                     "maxLines": 2},
                    {"type": "text", "text": tag, "size": "xxs",
                     "color": "#888888", "flex": 2, "align": "end"},
                ]},
                {"type": "text", "text": desc, "size": "xs",
                 "color": "#555555", "wrap": True, "margin": "xs",
                 "maxLines": 2},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [detail_btn, share_btn]},
            ]
            if i < len(acts) - 1:
                items.append({"type": "separator", "margin": "sm"})
        return items

    def _make_bubble(title_line2: str, acts: list, is_first: bool = False) -> dict:
        bubble = {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                *([ {"type": "text", "text": f"{category} — {weekend_label}",
                                     "color": "#8892B0", "size": "xs", "margin": "xs"} ] if is_first else []),
                                {"type": "text", "text": title_line2,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                     "contents": _make_items(acts)},
        }
        return bubble

    # ── 5. 合併即時＋靜態，一起分頁 ──
    bubbles = []
    MAX_PER_BUBBLE = 8

    # 即時活動：每分類每城市上限 10 筆，每 8 筆一頁
    live_capped = live_events[:10]
    if live_capped:
        for chunk_start in range(0, len(live_capped), MAX_PER_BUBBLE):
            chunk = live_capped[chunk_start:chunk_start + MAX_PER_BUBBLE]
            label = "🆕 近期活動"
            if len(live_capped) > MAX_PER_BUBBLE:
                page = chunk_start // MAX_PER_BUBBLE + 1
                label += f"（{page}）"
            bubbles.append(_make_bubble(label, chunk, is_first=(len(bubbles) == 0)))

    # 靜態推薦景點：只取前 5 個
    if static_dedup:
        top_static = static_dedup[:5]
        bubbles.append(_make_bubble("📌 推薦景點", top_static, is_first=(len(bubbles) == 0)))

    # 最後一個 bubble 加上 footer 導航按鈕
    if bubbles:
        # 分享文字（壓短避免超過 LINE URI 1000 字元限制）
        _share_acts = (live_events[:2] or static_dedup[:2])
        _share_names = "、".join([e['name'][:12] for e in _share_acts])
        _invite = f"\nhttps://line.me/ti/p/{LINE_BOT_ID}" if LINE_BOT_ID else "\n👉 搜「生活優轉」"
        _share_text = f"🗓️ {area_label}好去處！\n{_share_names}{_invite}"
        _act_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
        _cat_icons = {
            "戶外踏青": "🌿", "文青咖啡": "☕", "親子同樂": "👶",
            "運動健身": "🏃", "吃喝玩樂": "🍜", "市集展覽": "🎨", "表演音樂": "🎵",
        }
        _other_cats = [c for c in cats if c != category]
        _area_suf = f" {area}" if area else ""
        # 每3個一排
        _cat_rows = []
        for i in range(0, len(_other_cats), 3):
            chunk = _other_cats[i:i+3]
            _cat_rows.append({
                "type": "box", "layout": "horizontal", "spacing": "xs",
                "contents": [
                    {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                     "action": {"type": "message",
                                "label": f"{_cat_icons.get(c,'')} {c}",
                                "text": f"周末 {c}{_area_suf}"}}
                    for c in chunk
                ]
            })
        bubbles[-1]["footer"] = {
            "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "text", "text": "換個類型看看 👇",
                 "size": "xs", "color": "#888888", "margin": "sm"},
                *_cat_rows,
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "message", "label": "← 回選單",
                                "text": "周末去哪"}},
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "uri", "label": "📤 分享",
                                "uri": _act_share_url}},
                ]},
            ]}

    # 如果完全沒有活動
    if not bubbles:
        bubbles = [{
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": f"目前 {area} 沒有找到 {category} 相關活動",
                 "size": "sm", "color": "#555555", "wrap": True},
            ]},
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                 "action": {"type": "message", "label": "← 回選單", "text": "周末去哪"}},
            ]},
        }]

    if len(bubbles) == 1:
        return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
                 "contents": bubbles[0]}]
    return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
             "contents": {"type": "carousel", "contents": bubbles}}]
