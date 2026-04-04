"""
fetch_products.py — 全自動 3C 產品資料更新
=============================================
從 PChome 搜尋 API 抓取最新產品（品名、價格、規格），
自動生成 products.json 供前端 index.html 使用。

搭配 GitHub Actions 每天自動執行，完全不需要人工維護。

執行方式：
  python fetch_products.py              # 正式執行
  python fetch_products.py --dry-run    # 測試模式（不寫檔）

需要套件：
  pip install requests
"""

import json
import re
import sys
import time
import random
import urllib.parse
from datetime import datetime
from pathlib import Path

import io
# Windows 終端 UTF-8 支援
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("Missing: pip install requests")
    sys.exit(1)

# ════════════════════════════════════════════════
#  搜尋關鍵字（按類別）
# ════════════════════════════════════════════════
QUERIES = {
    "laptop": [
        "ASUS 筆電 2025", "ASUS 筆電 2026",
        "Apple MacBook Air", "Apple MacBook Pro",
        "Lenovo ThinkPad", "Lenovo IdeaPad",
        "Acer Swift 筆電", "Acer Aspire",
        "Dell XPS", "Dell Inspiron 筆電",
        "Samsung Galaxy Book",
        "MSI 筆電 電競", "HP 筆電",
    ],
    "phone": [
        "iPhone 17", "iPhone 16",
        "Samsung Galaxy S25", "Samsung Galaxy S24",
        "Samsung Galaxy A", "Google Pixel 9",
        "ASUS Zenfone", "ASUS ROG Phone",
        "Sony Xperia", "小米 手機",
        "OPPO Find", "OPPO Reno",
        "vivo X200", "Redmi Note",
    ],
    "tablet": [
        "iPad Air", "iPad Pro M", "iPad mini",
        "Samsung Galaxy Tab S",
        "小米 平板", "Xiaomi Pad",
        "Microsoft Surface Pro",
        "Microsoft Surface Go",
        "Lenovo Tab",
    ],
}

# 每個類別最多保留幾筆
MAX_PER_CATEGORY = 20

# ════════════════════════════════════════════════
#  品牌對照表
# ════════════════════════════════════════════════
BRAND_MAP = {
    "asus": "ASUS", "apple": "Apple", "samsung": "Samsung",
    "lenovo": "Lenovo", "acer": "Acer", "hp": "HP",
    "dell": "Dell", "sony": "Sony", "google": "Google",
    "xiaomi": "Xiaomi", "小米": "Xiaomi", "mi": "Xiaomi",
    "oppo": "OPPO", "vivo": "vivo", "huawei": "Huawei",
    "microsoft": "Microsoft", "msi": "MSI", "razer": "Razer",
    "realme": "realme", "nothing": "Nothing",
    "紅米": "Xiaomi", "redmi": "Xiaomi",
}

# ════════════════════════════════════════════════
#  PChome API
# ════════════════════════════════════════════════
PCHOME_API = "https://ecshweb.pchome.com.tw/search/v4.3/all/results"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
})


def search_pchome(query: str, rows: int = 20) -> list:
    """呼叫 PChome 搜尋 API v4.3"""
    params = {
        "q": query,
        "page": "1",
        "sort": "rnk/dc",
        "fields": "Id,Nick,Price,Brand,Pic",
    }
    try:
        r = SESSION.get(PCHOME_API, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        prods = data.get("Prods", [])
        result = []
        for p in prods[:rows]:
            name = p.get("Name") or p.get("Nick", "")
            # 過濾福利品、二手、配件
            if re.search(r"福利品|二手|整新|中古|保護殼|保護貼|充電器|傳輸線|皮套|鏡頭貼", name):
                continue
            price_val = p.get("Price", 0)
            if isinstance(price_val, dict):
                price_val = price_val.get("M") or price_val.get("P") or 0
            result.append({
                "Nick": name,
                "Price": {"M": int(price_val) if price_val else 0},
                "Brand": p.get("Brand", ""),
                "Id": p.get("Id", ""),
                "Describe": p.get("Describe", ""),
            })
        return result
    except Exception as e:
        print(f"  ⚠ API 錯誤：{e}")
        return []


# ════════════════════════════════════════════════
#  規格解析（從產品名稱）
# ════════════════════════════════════════════════
CPU_PATTERNS = [
    (r"Core Ultra \d+ \w+", None),
    (r"Core Ultra \d+", None),
    (r"Core i\d[- ]\d{4,5}\w*", None),
    (r"Ryzen \w+ \d+ \w+", None),
    (r"Ryzen \d+ \d{4}\w*", None),
    (r"Apple M\d(?: Pro| Max| Ultra)?", None),
    (r"Snapdragon \d+ \w+", None),
    (r"Snapdragon \d+", None),
    (r"Dimensity \d+", "MediaTek "),
    (r"Exynos \d+", "Samsung "),
    (r"Kirin \d+", "HiSilicon "),
    (r"Tensor G\d", "Google "),
    (r"Celeron N\d{4}", "Intel "),
    (r"Intel N\d{3}", None),
    (r"Pentium \w+", "Intel "),
    (r"A\d{2} Pro", "Apple "),
    (r"A\d{2} Bionic", "Apple "),
]

def parse_cpu(text: str) -> str:
    for pattern, prefix in CPU_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            cpu = m.group(0)
            if prefix:
                cpu = prefix + cpu
            return cpu
    return ""


def parse_ram(text: str) -> str:
    """
    解析 RAM，處理多種格式：
    - "16GB RAM" / "16GB LPDDR5"
    - "(i5/16G/512G)" — 斜線分隔，取第二個數字
    - "8G/256G" — 手機格式，取第一個（較小的）
    """
    # 明確標記 RAM
    m = re.search(r"(\d{1,3})\s*GB?\s*(?:RAM|記憶體|LPDDR|DDR)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}GB"

    # 斜線格式：找所有 /數字G 的組合
    slash_nums = re.findall(r"(?:^|/)(\d{1,3})G(?:B)?(?=/|[)\s,]|$)", text)
    if len(slash_nums) >= 2:
        # 通常格式是 CPU/RAM/SSD，RAM 是第一個小數字
        nums = [int(n) for n in slash_nums]
        # RAM 通常是 4,6,8,12,16,32,64
        ram_candidates = [n for n in nums if n in (2,3,4,6,8,12,16,32,64,128)]
        if ram_candidates:
            return f"{ram_candidates[0]}GB"
    elif len(slash_nums) == 1:
        # 只有一個，且值合理就當 RAM
        val = int(slash_nums[0])
        if val in (4,6,8,12,16,32,64):
            return f"{val}GB"

    # 括號格式：(8G/256G)
    m = re.search(r"\((\d{1,3})G\s*/\s*(\d{2,4})G", text)
    if m:
        return f"{m.group(1)}GB"

    return ""


def parse_ssd(text: str) -> str:
    """
    解析儲存容量：
    - "1TB SSD" / "512GB NVMe"
    - "(i5/16G/512G)" — 斜線格式，取最大的數字
    - "(8G/256G)" — 手機格式，取第二個（較大的）
    """
    # 明確標記 SSD
    m = re.search(r"(\d+)\s*(TB)\s*(?:SSD|NVMe|PCIe|M\.2|儲存)?", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}TB"
    m = re.search(r"(\d{3,4})\s*GB?\s*(?:SSD|NVMe|PCIe|M\.2)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}GB"

    # 括號格式 (8G/256G) — 取較大的
    m = re.search(r"\(\d{1,3}G\s*/\s*(\d{2,4})G", text)
    if m:
        val = int(m.group(1))
        if val >= 64:
            return f"{val}GB"

    # 斜線格式：取最大的合理儲存值（>=64G）
    slash_nums = re.findall(r"(?:^|/)(\d{2,4})G(?:B)?(?=/|[)\s,]|$)", text)
    if slash_nums:
        nums = [int(n) for n in slash_nums if int(n) >= 64]
        if nums:
            return f"{max(nums)}GB"

    return ""


def parse_brand(raw_brand: str, name: str) -> str:
    """從品牌欄位或名稱判斷品牌"""
    # 先從 PChome 的 Brand 欄位
    for key, val in BRAND_MAP.items():
        if key in raw_brand.lower():
            return val
    # 從名稱判斷
    name_lower = name.lower()
    for key, val in BRAND_MAP.items():
        if name_lower.startswith(key):
            return val
    return raw_brand[:15] if raw_brand else "其他"


# ════════════════════════════════════════════════
#  自動生成優缺點 / 標籤
# ════════════════════════════════════════════════
def generate_pros_cons(brand: str, category: str, price: int, cpu: str, name: str) -> tuple:
    """回傳 (pros, cons)"""
    brand_lower = brand.lower()
    cpu_lower = cpu.lower()
    name_lower = name.lower()

    pros_parts = []
    cons_parts = []

    # 品牌特色
    if brand_lower == "apple":
        if category == "laptop":
            pros_parts.append("macOS 生態完整，電池續航佳")
        elif category == "phone":
            pros_parts.append("iOS 流暢穩定，隱私安全佳")
        else:
            pros_parts.append("iPadOS 應用豐富，Apple Pencil 支援")
        cons_parts.append("價格較高，擴充受限")
    elif brand_lower == "asus":
        pros_parts.append("台灣品牌，全台維修據點多")
        if "rog" in name_lower:
            pros_parts.append("電競效能頂尖，散熱優秀")
            cons_parts.append("偏重，外型較電競風")
    elif brand_lower == "samsung":
        pros_parts.append("螢幕色彩絕美（AMOLED）")
        if category == "phone":
            pros_parts.append("AI 功能豐富")
    elif brand_lower == "google":
        if category == "phone":
            pros_parts.append("拍照業界頂尖，純淨 Android，7年更新保證")
            cons_parts.append("台灣無實體門市")
    elif brand_lower == "xiaomi":
        pros_parts.append("規格堆料足，CP值極高")
        cons_parts.append("台灣保固需確認")
    elif brand_lower == "lenovo":
        if "thinkpad" in name_lower:
            pros_parts.append("商務鍵盤業界最佳，軍規認證")
        else:
            pros_parts.append("性價比高，品質穩定")
    elif brand_lower == "sony":
        pros_parts.append("螢幕色彩專業級，音響效果佳")
        cons_parts.append("台灣通路較少")
    elif brand_lower == "msi":
        pros_parts.append("電競品牌，散熱與效能兼顧")
    elif brand_lower in ("oppo", "vivo"):
        pros_parts.append("快充速度快，外型設計感佳")
    elif brand_lower == "microsoft":
        pros_parts.append("完整 Windows 系統，觸控筆支援")
        cons_parts.append("配件需另購")

    # CPU 等級
    if re.search(r"ultra 7|ultra 9|m4|m3 pro|ryzen 9|i9|snapdragon 8 elite", cpu_lower):
        pros_parts.append("頂級處理器，效能極強")
    elif re.search(r"ultra 5|m3|m2|ryzen 7|i7|snapdragon 8 gen", cpu_lower):
        pros_parts.append("高階處理器，多工流暢")
    elif re.search(r"i5|ryzen 5|a1[789]|snapdragon 7", cpu_lower):
        pros_parts.append("主流處理器，日常夠用")

    # 價格
    if price < 15000:
        pros_parts.append("價格親民，入門好選擇")
    elif price > 50000:
        cons_parts.append("售價偏高")

    # 預設 cons
    if not cons_parts:
        cons_parts.append("規格詳見商品頁")

    return ("，".join(pros_parts[:3]), "，".join(cons_parts[:2]))


def generate_tag(brand: str, category: str, price: int, cpu: str, name: str) -> str:
    """根據規則生成標籤"""
    brand_lower = brand.lower()
    name_lower = name.lower()

    if brand_lower == "apple":
        return "🍎 蘋果生態"
    if "rog" in name_lower:
        return "🎮 電競首選"
    if "thinkpad" in name_lower:
        return "🏢 商務首選"
    if brand_lower == "google":
        return "🤖 AI 智慧"

    if price < 10000:
        return "💰 超值入門"
    if price < 18000:
        return "💰 高CP值"
    if price < 30000:
        return "👍 主流推薦"
    if price < 50000:
        return "⭐ 品質優選"
    return "🏆 旗艦頂規"


# ════════════════════════════════════════════════
#  主解析流程
# ════════════════════════════════════════════════
def parse_product(raw: dict, category: str) -> dict | None:
    """將 PChome API 回傳的單筆資料轉為我們的格式"""
    name = (raw.get("Nick") or "").strip()
    if not name:
        return None

    # 價格
    price_val = 0
    price_obj = raw.get("Price", {})
    if isinstance(price_obj, dict):
        price_val = price_obj.get("M") or price_obj.get("P") or price_obj.get("Low") or 0
    elif isinstance(price_obj, (int, float)):
        price_val = int(price_obj)
    if not price_val or price_val < 3000 or price_val > 200000:
        return None

    # 品牌
    brand = parse_brand(raw.get("Brand", ""), name)

    # 合併名稱 + Describe 來解析規格（更多資訊）
    full_text = name + " " + (raw.get("Describe") or "")

    # 規格
    cpu = parse_cpu(full_text)
    ram = parse_ram(full_text)
    ssd = parse_ssd(full_text)

    # 名稱清理（截短，去掉品牌前綴重複）
    clean_name = name[:55]

    # 自動生成
    pros, cons = generate_pros_cons(brand, category, price_val, cpu, clean_name)
    tag = generate_tag(brand, category, price_val, cpu, clean_name)

    # 商品連結
    prod_id = raw.get("Id", "")
    url = f"https://24h.pchome.com.tw/prod/{prod_id}" if prod_id else ""

    return {
        "brand": brand,
        "name": clean_name,
        "price": f"NT${price_val:,}",
        "cpu": cpu or "詳見商品頁",
        "ram": ram or "—",
        "ssd": ssd or "—",
        "battery": "—",
        "weight": "—",
        "pros": pros,
        "cons": cons,
        "tag": tag,
        "url": url,
    }


def dedupe_products(products: list) -> list:
    """去重：相同名稱（前25字）只保留最低價"""
    seen = {}
    for p in products:
        key = p["name"].lower()[:25]
        existing = seen.get(key)
        if existing is None:
            seen[key] = p
        else:
            # 保留較低價的
            old_price = int(re.sub(r"[^0-9]", "", existing["price"]))
            new_price = int(re.sub(r"[^0-9]", "", p["price"]))
            if new_price < old_price:
                seen[key] = p
    return list(seen.values())


# ════════════════════════════════════════════════
#  桌機資料（自組不在 PChome 賣，維持寫死）
# ════════════════════════════════════════════════
DESKTOP_DATA = [
    {
        "name": "入門文書機", "total_price": "NT$16,000", "tag": "📝 文書首選",
        "cpu": "Intel Core i3-14100", "motherboard": "B760M WIFI",
        "ram": "DDR5 16GB", "ssd": "512GB NVMe Gen4",
        "gpu": "內顯 UHD 730", "psu": "450W 80+ Bronze",
        "pros": "預算最低、耗電省、文書辦公綽綽有餘", "cons": "無獨顯，不適合遊戲",
        "for_user": ["child", "student", "senior", "general"],
    },
    {
        "name": "中階全能機", "total_price": "NT$32,000", "tag": "⚡ 全能推薦",
        "cpu": "AMD Ryzen 7 9700X", "motherboard": "B850M-A WIFI",
        "ram": "DDR5 32GB 6000MHz", "ssd": "1TB NVMe Gen4",
        "gpu": "RTX 5060", "psu": "750W 80+ Gold",
        "pros": "CP值極高，遊戲剪片全能勝任", "cons": "桌面空間需求較大",
        "for_user": ["student", "work", "create", "game", "general"],
    },
    {
        "name": "高階電競創作機", "total_price": "NT$55,000", "tag": "🎮 電競首選",
        "cpu": "AMD Ryzen 9 9900X", "motherboard": "X870E HERO",
        "ram": "DDR5 64GB 6400MHz", "ssd": "2TB NVMe Gen5",
        "gpu": "RTX 5070 Ti", "psu": "850W 80+ Platinum",
        "pros": "頂規效能，3A遊戲最高畫質、4K剪輯零壓力", "cons": "價格較高，耗電量大",
        "for_user": ["create", "game"],
    },
    {
        "name": "旗艦專業工作站", "total_price": "NT$90,000", "tag": "🏆 旗艦工作站",
        "cpu": "Intel Core i9-14900K", "motherboard": "Z790 AORUS Master",
        "ram": "DDR5 128GB 7200MHz", "ssd": "4TB NVMe Gen5",
        "gpu": "RTX 5090", "psu": "1200W 80+ Titanium",
        "pros": "最頂規，AI運算、3D渲染專業首選", "cons": "售價高昂，一般用途不划算",
        "for_user": ["create", "work"],
    },
]


# ════════════════════════════════════════════════
#  主流程
# ════════════════════════════════════════════════
def run(dry_run: bool = False):
    output_path = Path(__file__).parent / "products.json"

    print(f"\n{'=' * 55}")
    print(f"  3C 產品全自動更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 55}")

    result = {
        "meta": {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "counts": {},
        },
        "desktop": DESKTOP_DATA,
    }

    total_fetched = 0
    total_kept = 0

    for category, queries in QUERIES.items():
        print(f"\n📦 類別：{category}")
        all_products = []

        for query in queries:
            print(f"  🔍 搜尋：{query} ...", end=" ")
            raws = search_pchome(query, rows=20)
            print(f"取得 {len(raws)} 筆")
            total_fetched += len(raws)

            for raw in raws:
                p = parse_product(raw, category)
                if p:
                    all_products.append(p)

            # 禮貌性延遲
            time.sleep(random.uniform(1.0, 2.5))

        # 去重 + 限制數量
        deduped = dedupe_products(all_products)
        # 按價格排序
        deduped.sort(key=lambda p: int(re.sub(r"[^0-9]", "", p["price"])))
        # 限制數量
        final = deduped[:MAX_PER_CATEGORY]
        total_kept += len(final)

        result[category] = final
        result["meta"]["counts"][category] = len(final)
        print(f"  ✅ {category}：{len(all_products)} 筆 → 去重 {len(deduped)} → 保留 {len(final)}")

    print(f"\n{'=' * 55}")
    print(f"  📊 總計：抓取 {total_fetched} 筆，最終保留 {total_kept} 筆")

    if dry_run:
        print(f"  (dry-run：不寫入檔案)")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
    else:
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  📄 已寫入：{output_path}")

    print(f"{'=' * 55}\n")
    return result


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
