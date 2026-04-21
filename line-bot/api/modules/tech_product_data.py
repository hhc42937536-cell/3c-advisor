"""3C product data loading, text parsing, and filtering."""

from __future__ import annotations

import json
import os
import re
import urllib.request


PRODUCTS_URL = os.environ.get(
    "PRODUCTS_URL",
    "https://hhc42937536-cell.github.io/3c-advisor/products.json",
)


_products_cache: dict = {"data": None, "ts": 0}


def load_products() -> dict:
    """從 GitHub Pages 載入最新產品資料（快取 10 分鐘）"""
    import time
    now = time.time()
    if _products_cache["data"] and now - _products_cache["ts"] < 600:
        return _products_cache["data"]
    try:
        req = urllib.request.Request(PRODUCTS_URL, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            _products_cache["data"] = data
            _products_cache["ts"] = now
            return data
    except Exception:
        return _products_cache["data"] or {"laptop": [], "phone": [], "tablet": [], "desktop": []}


DEVICE_KEYWORDS = {
    "laptop":  ["筆電", "筆記型電腦", "laptop", "notebook", "macbook", "vivobook", "zenbook",
                "thinkpad", "ideapad", "swift", "inspiron", "pavilion",
                "asus", "華碩", "lenovo", "聯想", "hp", "dell", "acer", "宏碁", "msi", "微星"],
    "tablet":  ["平板", "tablet", "ipad", "surface", "galaxy tab", "matepad"],
    "desktop": ["桌機", "桌上型電腦", "桌電", "desktop", "主機", "電腦主機", "組裝電腦"],
    "phone":   ["手機", "phone", "iphone", "三星", "samsung", "galaxy", "pixel", "小米", "redmi",
                "紅米", "oppo", "vivo", "sony", "zenfone", "realme", "motorola"],
}


USE_KEYWORDS = {
    "拍照": ["拍照", "相機", "攝影", "鏡頭", "自拍"],
    "遊戲": ["遊戲", "電競", "打game", "lol", "原神", "steam"],
    "追劇": ["追劇", "netflix", "youtube", "影片", "看劇"],
    "長輩": ["長輩", "爸媽", "阿公", "阿嬤", "爺爺", "奶奶", "媽媽", "爸爸", "老人"],
    "學生": ["學生", "上課", "作業", "報告", "念書"],
    "工作": ["工作", "辦公", "上班", "文書", "word", "excel"],
    "輕薄": ["輕薄", "輕巧", "好攜帶", "輕的"],
}


def parse_budget(text: str) -> int:
    """從文字中解析預算，回傳最大金額"""
    # "2萬" → 20000
    m = re.search(r"(\d+)\s*萬", text)
    if m:
        return int(m.group(1)) * 10000
    # "20000" 或 "20,000"
    m = re.search(r"(\d{4,6})", text.replace(",", ""))
    if m:
        val = int(m.group(1))
        if val >= 3000:
            return val
    # 模糊描述
    if any(w in text for w in ["便宜", "省錢", "預算少", "入門", "便宜點"]):
        return 15000
    if any(w in text for w in ["中等", "一般", "普通"]):
        return 30000
    if any(w in text for w in ["好一點", "品質好", "不差錢"]):
        return 60000
    # 不限預算 → 回傳超大值，篩選時等同全部顯示
    if any(w in text for w in ["不限預算", "不限", "隨便", "都可以", "沒差", "高階", "最好", "旗艦", "5萬以上", "無限"]):
        return 999999
    return 0


def detect_device(text: str) -> str:
    """偵測使用者想買什麼裝置"""
    text_lower = text.lower()
    for device, keywords in DEVICE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return device
    return ""


def detect_use(text: str) -> list:
    """偵測使用者的用途偏好"""
    text_lower = text.lower()
    uses = []
    for use, keywords in USE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            uses.append(use)
    return uses


def filter_products(products: list, budget: int, uses: list) -> list:
    """根據預算和用途篩選並排序產品"""
    results = []
    for p in products:
        # 桌機用 total_price，其他用 price
        price_str = p.get("price") or p.get("total_price", "0")
        price = int(re.sub(r"[^0-9]", "", price_str))
        if 0 < budget < 999999 and price > budget * 1.2:
            continue
        if price < 1000:   # 桌機配件不篩掉（桌機最低約 16000）
            continue

        # 計算匹配分數
        score = 0
        name_lower = (p.get("name", "") + p.get("pros", "")).lower()
        for_user = p.get("for_user", [])  # 桌機用此欄位

        if "拍照" in uses and any(w in name_lower for w in ["鏡頭", "攝影", "相機", "拍照", "pixel", "蔡司"]):
            score += 10
        if "遊戲" in uses:
            if any(w in name_lower for w in ["電競", "rog", "gaming", "rtx", "效能"]):
                score += 10
            if "game" in for_user:
                score += 10
        if "工作" in uses:
            if "work" in for_user:
                score += 8
            if any(w in name_lower for w in ["thinkpad", "商務", "business"]):
                score += 5
        if "創作" in uses:
            if "create" in for_user:
                score += 8
            if any(w in name_lower for w in ["pro", "studio", "create", "creator", "m3", "m4", "rtx"]):
                score += 5
        if "追劇" in uses:
            # OLED 螢幕、大螢幕、音效優先
            if any(w in name_lower for w in ["oled", "amoled", "螢幕", "display", "音效", "dolby"]):
                score += 8
            if price < 20000:   # 追劇不需要太貴
                score += 3
        if "閱讀" in uses:
            # 平板輕薄、長續航優先
            if any(w in name_lower for w in ["mini", "air", "輕", "薄", "slim", "oled"]):
                score += 8
            if price < 25000:
                score += 3
        if "學習" in uses or "學生" in uses:
            if "student" in for_user:
                score += 6
        if "長輩" in uses:
            if "senior" in for_user:
                score += 6
            elif price < 20000:
                score += 5
        if "學生" in uses and price < 35000:
            score += 3
        if "輕薄" in uses and any(w in name_lower for w in ["輕", "薄", "air", "slim"]):
            score += 8
        if "日常" in uses or "一般" in uses:
            if "general" in for_user:
                score += 5
            if budget >= 999999 and price <= 50000:
                score += 2

        results.append({**p, "_score": score, "_price": price})

    # 排序：匹配分數高 → 價格低
    results.sort(key=lambda x: (-x["_score"], x["_price"]))
    return results[:5]


def spec_to_plain_line(p: dict) -> str:
    """簡短白話規格（一行版）"""
    parts = []
    cpu = p.get("cpu", "")
    if cpu and cpu != "詳見商品頁":
        if re.search(r"ultra 7|ultra 9|m4|m3|ryzen 9|i9|snapdragon 8 elite", cpu, re.I):
            parts.append("超快處理器")
        elif re.search(r"ultra 5|m2|ryzen 7|i7|snapdragon 8", cpu, re.I):
            parts.append("很快的處理器")
        else:
            parts.append("夠用的處理器")

    ram = p.get("ram", "")
    if ram and ram != "—":
        ram_num = int(re.sub(r"[^0-9]", "", ram) or 0)
        if ram_num >= 16:
            parts.append(f"{ram_num}GB大記憶體")
        elif ram_num >= 8:
            parts.append(f"{ram_num}GB記憶體")

    ssd = p.get("ssd", "")
    if ssd and ssd != "—":
        parts.append(f"{ssd}儲存")

    return " / ".join(parts) if parts else "詳見商品頁"
