from __future__ import annotations

from modules.activity_data import _ACTIVITY_DB
from modules.activity_flex import build_activity_flex
from modules.activity_utils import _set_user_city
from modules.activity_pickers import _ALL_CITIES
from modules.activity_pickers import _AREA_REGIONS
from modules.activity_pickers import build_activity_area_picker
from modules.activity_pickers import build_activity_city_picker
from modules.activity_pickers import build_activity_menu
from modules.activity_pickers import build_activity_region_picker

"""近期活動推薦模組

提供以下公開介面：
    build_activity_message(text, user_id=None)  ← 主路由，webhook 呼叫此函式
    build_activity_flex(category, area="")
    build_activity_menu(city="")
    build_activity_region_picker(category)
    build_activity_area_picker(category, region="")
    build_activity_city_picker(category="")
"""

import re


# ── LINE Bot ID（用於分享連結）──


# ─── 近期活動推薦 ──────────────────────────────────────


# 全台 22 縣市分區


def build_activity_message(text: str, user_id: str = None) -> list:
    """近期活動 — 主路由"""
    text_s = text.strip()

    # 解析類別
    category = None
    for cat in _ACTIVITY_DB.keys():
        if cat in text_s:
            category = cat
            break
    if not category:
        if any(w in text_s for w in ["爬山", "踏青", "健行", "大自然"]):
            category = "戶外踏青"
        elif any(w in text_s for w in ["咖啡", "文青", "藝文"]):
            category = "文青咖啡"
        elif any(w in text_s for w in ["小孩", "親子", "家庭", "帶小孩"]):
            category = "親子同樂"
        elif any(w in text_s for w in ["運動", "跑步", "騎車", "健身"]):
            category = "運動健身"
        elif any(w in text_s for w in ["夜市", "美食", "吃", "逛街"]):
            category = "吃喝玩樂"
        elif any(w in text_s for w in ["市集", "展覽", "展", "博物館", "美術館"]):
            category = "市集展覽"
        elif any(w in text_s for w in ["演唱會", "音樂", "表演", "演出", "音樂節", "livehouse"]):
            category = "表演音樂"

    # 解析區域（支援全台 22 縣市）
    area = ""
    all_cities_pattern = "|".join(_ALL_CITIES)
    area_match = re.search(rf'({all_cities_pattern})', text_s)
    if area_match:
        area = area_match.group(0)
        _set_user_city(user_id, area[:2])  # 記住用戶明確指定的城市

    # 解析地區（北部/中部/南部/東部離島）
    region = ""
    for r in _AREA_REGIONS:
        if r in text_s:
            region = r
            break

    if not category:
        # 沒指定類別 → 有城市先選類型，沒城市先選城市
        if area:
            return build_activity_menu(area)
        return build_activity_city_picker()
    # 有類別 + 有城市 → 直接顯示活動
    if area:
        return build_activity_flex(category, area)
    # 有類別 + 有地區 → 顯示該地區城市選擇
    if region:
        return build_activity_area_picker(category, region)
    # 有類別但沒地區 → 先問城市
    return build_activity_city_picker(category)
