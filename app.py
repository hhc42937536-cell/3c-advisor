"""
3C 選購顧問 — Flask 網頁版
執行：python app.py
"""
from flask import Flask, render_template_string, request, session
import re, urllib.parse, json

DISC_HTML = '''<div class="modal-bg" id="disc">
  <div class="modal">
    <div class="modal-t2">📋 免責聲明</div>
    <div class="msec"><div class="msec-t" style="color:#4F8EF7">版權所有</div><div class="msec-p">本應用程式「3C 選購顧問」由 捷啟智慧科技 開發與維護，所有內容、設計、程式碼及資料之著作權均歸 捷啟智慧科技 所有，未經授權不得複製、轉載或作商業用途。</div></div>
    <div class="msec"><div class="msec-t" style="color:#FF8C42">資訊僅供參考</div><div class="msec-p">本應用程式所提供之產品規格、售價、推薦建議等資訊，均以公開資料整理而成，僅供購買參考之用。實際規格、價格及供貨狀況以各販售通路公告為準，本公司不對任何損失負責。</div></div>
    <div class="msec"><div class="msec-t" style="color:#00E5A0">無商業合作關係</div><div class="msec-p">本應用程式與所有列出之品牌廠商、購物平台均無任何商業贊助或合作關係，所有推薦均基於公開資料與中立評估，不涉及廣告或業配。</div></div>
    <div style="text-align:center;font-size:13px;color:#A0A0BB;margin:10px 0">© 2026 捷啟智慧科技  All Rights Reserved.</div>
    <button class="modal-ok" onclick="document.getElementById(&#39;disc&#39;).style.display=&#39;none&#39;">我已閱讀並了解 ✓</button>
  </div>
</div>'''

app = Flask(__name__)
app.secret_key = "3c_advisor_2026"

# ── 資料 ──────────────────────────────────────────────────
STEP_OPTS = {
    "device": [
        ("💻", "筆電",     "帶著走的好夥伴",    "computer"),
        ("📱", "手機",     "口袋裡的宇宙",      "phone"),
        ("📟", "平板",     "螢幕再大一點",      "tablet"),
        ("🖥", "桌機自組", "效能怪獸・自由升級", "desktop"),
    ],
    "user": [
        ("👧", "小朋友",   "學習娛樂兼顧",  "child"),
        ("🎓", "學生",     "報告上課必備",  "student"),
        ("💼", "上班族",   "視訊文書開會",  "work"),
        ("🎨", "創作者",   "剪輯修圖設計",  "create"),
        ("🎮", "遊戲玩家", "電競3A不卡頓",  "game"),
        ("👴", "長輩",     "大字好操作",    "senior"),
        ("🙋", "一般使用", "什麼都用一點",  "general"),
    ],
    "budget": [
        ("🥉", "入門精省",   "日常文書、追劇、小學生作業",     "budget"),
        ("🥈", "主流全能",   "上班族必備、流暢辦公、輕量剪輯", "mid"),
        ("🥇", "頂級效能",   "專業電競、4K剪輯、設計師首選",   "high"),
        ("💎", "不差這點錢", "旗艦規格、頂配無妥協",           "pro"),
    ],
}

APP_CATS_PC = {
    "📄 文書辦公": {
        "📄 文書辦公 / Office":  12000,
        "💻 程式開發 / IDE":     28000,
    },
    "🎮 遊戲": {
        "🎮 英雄聯盟 / 輕量遊戲": 18000,
        "🔥 絕地求生 / 3A大作":   35000,
    },
    "🎬 影音創作": {
        "🎬 4K影片剪輯":       42000,
        "🎨 Photoshop / 設計": 25000,
        "📹 直播 / OBS":       30000,
    },
    "🧠 AI / 專業": {
        "🧠 AI / 機器學習": 50000,
    },
}
APP_CATS_PHONE = {
    "📱 社群娛樂": {
        "📱 社群（IG / TikTok / 抖音）": 10000,
        "📺 影音串流（Netflix/YouTube）": 8000,
        "🎵 音樂串流（Spotify/KKBOX）":   8000,
    },
    "🎮 手遊": {
        "🎮 傳說對決 / 輕度手遊": 12000,
        "⚡ 原神 / 重度手遊":     20000,
    },
    "📸 拍照創作": {
        "📸 拍照 / 修圖（Snapseed）":   15000,
        "🤳 短影音創作（剪映/CapCut）": 18000,
    },
    "🛠 日常工具": {
        "💬 LINE / 通訊軟體":         8000,
        "🗺 導航 / Google Maps":      8000,
        "💳 行動支付（街口/悠遊付）": 8000,
    },
}

DEMO = {
    "laptop": [
        {"brand":"ASUS",   "name":"Vivobook S15 OLED 2026",   "price":"NT$32,900",
         "cpu":"Intel Core Ultra 7 258V","ram":"32GB LPDDR5X","ssd":"1TB PCIe 4.0",
         "battery":"約14hr","weight":"1.6kg","tag":"CP值之王",
         "pros":"OLED螢幕色彩極艷，AI效能晶片，輕薄長效","cons":"維修據點較少"},
        {"brand":"Apple",  "name":"MacBook Air M4 13吋",       "price":"NT$39,900",
         "cpu":"Apple M4（10核心）","ram":"16GB","ssd":"512GB",
         "battery":"約18hr","weight":"1.24kg","tag":"蘋果首選",
         "pros":"靜音無風扇，電池超耐，macOS生態完整","cons":"擴充埠少，不支援Windows遊戲"},
        {"brand":"Acer",   "name":"Swift X 14 AI 2026",        "price":"NT$36,900",
         "cpu":"AMD Ryzen AI 9 HX 370","ram":"32GB LPDDR5X","ssd":"1TB NVMe",
         "battery":"約12hr","weight":"1.5kg","tag":"AI效能王",
         "pros":"AMD AI晶片，獨顯RTX 4060，CP值超高","cons":"散熱略吵"},
        {"brand":"Lenovo", "name":"ThinkPad X1 Carbon Gen 13", "price":"NT$52,900",
         "cpu":"Intel Core Ultra 7 265U","ram":"32GB LPDDR5","ssd":"1TB PCIe 4.0",
         "battery":"約15hr","weight":"1.12kg","tag":"商務首選",
         "pros":"超輕1.12kg，軍規認證，鍵盤業界最佳","cons":"售價偏高"},
        {"brand":"Dell",   "name":"XPS 13 Plus 2026",           "price":"NT$49,900",
         "cpu":"Intel Core Ultra 7 268V","ram":"32GB LPDDR5X","ssd":"1TB PCIe 4.0",
         "battery":"約14hr","weight":"1.23kg","tag":"設計極品",
         "pros":"工藝極致，OLED觸控，超輕薄設計","cons":"擴充埠極少，售價偏高"},
        {"brand":"Dell",   "name":"Inspiron 15 2026",            "price":"NT$28,900",
         "cpu":"Intel Core i7-13620H","ram":"16GB DDR5","ssd":"512GB NVMe",
         "battery":"約10hr","weight":"1.8kg","tag":"商務實用",
         "pros":"螢幕大，鍵盤舒適，商務辦公首選","cons":"重量稍重"},
    ],
    "phone": [
        {"brand":"Apple",   "name":"iPhone 17 Pro",   "price":"NT$39,900",
         "cpu":"A19 Pro","ram":"12GB","ssd":"256GB",
         "battery":"約兩天","weight":"195g","tag":"旗艦首選",
         "pros":"攝影系統升級，鈦金屬邊框，AI功能強","cons":"價格偏高"},
        {"brand":"Apple",   "name":"iPhone 17",        "price":"NT$29,900",
         "cpu":"A19","ram":"8GB","ssd":"128GB",
         "battery":"一天半","weight":"170g","tag":"均衡之選",
         "pros":"全新薄型設計，前鏡頭升級，流暢穩定","cons":"無Pro級攝影功能"},
        {"brand":"Samsung", "name":"Galaxy S25 Ultra", "price":"NT$45,900",
         "cpu":"Snapdragon 8 Elite","ram":"12GB","ssd":"256GB",
         "battery":"約兩天","weight":"218g","tag":"Android旗艦",
         "pros":"S Pen內建，AI功能豐富，7倍望遠","cons":"偏重偏大"},
        {"brand":"Samsung", "name":"Galaxy S25",        "price":"NT$27,900",
         "cpu":"Snapdragon 8 Elite","ram":"12GB","ssd":"256GB",
         "battery":"一天以上","weight":"162g","tag":"Android均衡",
         "pros":"輕薄旗艦晶片，Google AI整合，充電快","cons":"相機不如Ultra"},
        {"brand":"Google",  "name":"Pixel 9 Pro",       "price":"NT$34,900",
         "cpu":"Google Tensor G4","ram":"16GB","ssd":"256GB",
         "battery":"約兩天","weight":"199g","tag":"AI拍照王",
         "pros":"Google AI功能最強，拍照業界頂尖，7年更新","cons":"台灣無實體門市"},
        {"brand":"Xiaomi",  "name":"小米 15 Ultra",      "price":"NT$32,900",
         "cpu":"Snapdragon 8 Elite","ram":"16GB","ssd":"512GB",
         "battery":"約兩天","weight":"226g","tag":"規格怪獸",
         "pros":"徠卡四鏡頭，規格超級堆料，充電120W超快","cons":"MIUI廣告偏多"},
        {"brand":"Xiaomi",  "name":"Redmi Note 14 Pro",  "price":"NT$10,900",
         "cpu":"Snapdragon 7s Gen 3","ram":"8GB","ssd":"256GB",
         "battery":"約兩天","weight":"190g","tag":"超值首選",
         "pros":"CP值極高，2億像素鏡頭，大電池超耐用","cons":"更新週期較短，系統廣告"},
    ],
    "tablet": [
        {"brand":"Apple",     "name":"iPad Air M3 13吋",  "price":"NT$26,900",
         "cpu":"Apple M3","ram":"8GB","ssd":"128GB",
         "battery":"約10hr","weight":"617g","tag":"創作首選",
         "pros":"M3晶片跑最新AI應用，螢幕大色準高","cons":"配件另購價高"},
        {"brand":"Apple",     "name":"iPad mini A17 Pro", "price":"NT$16,900",
         "cpu":"Apple A17 Pro","ram":"8GB","ssd":"128GB",
         "battery":"約10hr","weight":"293g","tag":"隨身首選",
         "pros":"超輕巧，A17 Pro晶片，Apple Intelligence","cons":"螢幕較小"},
        {"brand":"Samsung",   "name":"Galaxy Tab S10+",    "price":"NT$31,900",
         "cpu":"Snapdragon 8 Gen 3","ram":"12GB","ssd":"256GB",
         "battery":"約13hr","weight":"581g","tag":"影音首選",
         "pros":"AMOLED色彩絕美，S Pen隨附，Samsung DeX","cons":"售價偏高"},
        {"brand":"Xiaomi",    "name":"Xiaomi Pad 7",        "price":"NT$10,900",
         "cpu":"Snapdragon 7+ Gen 3","ram":"8GB","ssd":"256GB",
         "battery":"約12hr","weight":"500g","tag":"CP值之王",
         "pros":"3K螢幕色彩亮眼，規格超殺","cons":"系統廣告偏多"},
        {"brand":"Microsoft", "name":"Surface Pro 11",      "price":"NT$52,900",
         "cpu":"Snapdragon X Elite","ram":"16GB","ssd":"512GB",
         "battery":"約14hr","weight":"879g","tag":"平板變筆電",
         "pros":"完整 Windows 11，可跑所有 PC 軟體","cons":"需另購鍵盤蓋，售價偏高"},
    ],
    "desktop": [
        {"name":"入門文書機","total_price":"NT$16,000","tag":"文書首選",
         "cpu":"Intel Core i3-14100","motherboard":"B760M WIFI",
         "ram":"DDR5 16GB","ssd":"512GB NVMe Gen4","gpu":"內顯 UHD 730","psu":"450W 80+ Bronze"},
        {"name":"中階全能機","total_price":"NT$32,000","tag":"全能推薦",
         "cpu":"AMD Ryzen 7 9700X","motherboard":"B850M-A WIFI",
         "ram":"DDR5 32GB 6000MHz","ssd":"1TB NVMe Gen4","gpu":"RTX 5060","psu":"750W 80+ Gold"},
        {"name":"電競高階機","total_price":"NT$55,000","tag":"電競首選",
         "cpu":"AMD Ryzen 9 9900X","motherboard":"X870E HERO",
         "ram":"DDR5 64GB 6400MHz","ssd":"2TB NVMe Gen5","gpu":"RTX 5070 Ti","psu":"850W 80+ Platinum"},
    ],
}

def perf(p):
    s = (p.get("cpu","") + " " + p.get("gpu","") + " " + p.get("ram","") + " " + p.get("ssd","")).lower()
    o, g, e = 0.75, 0.30, 0.30
    if any(x in s for x in ["ultra 7","ultra 9","m4","m3","ryzen 9","i9"]): o=1.0;e=0.90;g=max(g,.60)
    elif any(x in s for x in ["ultra 5","m2","ryzen 7","i7"]): o=0.92;e=0.75;g=max(g,.50)
    elif any(x in s for x in ["i5","a17","a18","a19","snapdragon 8 elite"]): o=0.85;e=0.55;g=max(g,.40)
    elif any(x in s for x in ["i3","exynos"]): o=0.70;e=0.35;g=max(g,.25)
    if any(x in s for x in ["rtx 5070 ti","rtx 5080"]): g=1.0;e=1.0
    elif any(x in s for x in ["rtx 5060","rtx 4070"]): g=0.85;e=0.80
    elif "rtx 4060" in s: g=0.75;e=0.70
    elif "rtx" in s: g=0.65;e=0.60
    if "64gb" in s: e=min(e+.10,1.0)
    elif "32gb" in s: e=min(e+.05,1.0)
    return {"office":round(o,2),"game":round(g,2),"edit":round(e,2)}

def freshness(p):
    s = (p.get("cpu","") + " " + p.get("gpu","")).lower()
    if any(x in s for x in ["ultra 7","ultra 9","m4","m3","rtx 5","ryzen 9 9","a19","snapdragon 8 elite"]):
        return "當季新品，五年不落伍", "#00E5A0", "#0A2018"
    if any(x in s for x in ["ultra 5","m2","rtx 4","i7-13","a18","a17","snapdragon 8 gen 3"]):
        return "主流世代，三年夠用", "#FFD700", "#1E1800"
    return "規格偏舊，價格夠低再考慮", "#FF4D6D", "#200808"

def price_color(price_str):
    nums = re.findall(r'\d+', price_str.replace(',',''))
    if not nums: return "#555570"
    p = int(''.join(nums))
    if p < 20000: return "#00E5A0"
    if p < 35000: return "#4F8EF7"
    if p < 60000: return "#FF8C42"
    return "#FF4D6D"

def shop_links(brand, name):
    q = urllib.parse.quote(f"{brand} {name}")
    return [
        ("PChome", f"https://ecshweb.pchome.com.tw/search/v3.3/?q={q}", "#4F8EF7"),
        ("momo",   f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={q}", "#FF4D6D"),
        ("Yahoo",  f"https://tw.buy.yahoo.com/search/product?p={q}", "#FFB300"),
        ("蝦皮",   f"https://shopee.tw/search?keyword={q}", "#FF8C42"),
    ]

def filter_products(products, user_type, budget_key):
    bmap = {"budget":15000,"mid":30000,"high":50000,"pro":99999}
    bval = bmap.get(budget_key, 99999)
    result = []
    for p in products:
        nums = re.findall(r'\d+', p.get("price","0").replace(',',''))
        pval = int(nums[0]) if nums else 0
        if pval <= bval * 1.3:
            result.append(p)
    boosts = {"game":lambda p:perf(p)["game"],"create":lambda p:perf(p)["edit"],
              "work":lambda p:perf(p)["office"],"student":lambda p:perf(p)["office"]}
    if user_type in boosts:
        result.sort(key=boosts[user_type], reverse=True)
    return result[:6]

# ── HTML Base ─────────────────────────────────────────────
BASE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>3C 選購顧問 — 捷啟智慧科技</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0A0A0F;color:#F0F0FF;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft JhengHei",sans-serif;min-height:100vh}
a{text-decoration:none;color:inherit}
.hdr{background:#12121A;border-bottom:1px solid #2A2A40;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.hdr-t{font-size:17px;font-weight:bold}.hdr-s{font-size:13px;color:#A0A0BB}
.wrap{max-width:900px;margin:0 auto;padding:16px 16px 60px}
.stepper{display:flex;align-items:center;gap:4px;padding:16px 0 8px;overflow-x:auto}
.sd{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;flex-shrink:0}
.sd.done{background:#00E5A0;color:#000}.sd.active{background:#4F8EF7;color:#fff}.sd.idle{background:#22223A;color:#A0A0BB}
.sl{font-size:13px;color:#C0C0D8;white-space:nowrap}.sln{width:14px;height:2px;background:#2A2A40;flex-shrink:0}
.sec-t{font-size:20px;font-weight:bold;margin:16px 0 4px}.sec-s{font-size:14px;color:#C8C8E0;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;margin-top:12px}
@media(max-width:600px){.grid{grid-template-columns:1fr 1fr}}
.opt{background:#1A1A26;border:2px solid #2A2A40;border-radius:14px;padding:18px 10px;cursor:pointer;transition:all .18s;text-align:center;user-select:none}
.opt:hover{border-color:#4F8EF7;transform:translateY(-2px)}.opt.sel{border-color:#4F8EF7;background:#161E3A;box-shadow:0 0 18px #4F8EF728}
.opt-em{font-size:28px;margin-bottom:8px;line-height:1.2}.opt-nm{font-size:15px;font-weight:bold}.opt-ds{font-size:13px;color:#C0C0D8;margin-top:4px}
.btn-n{background:linear-gradient(135deg,#4F8EF7,#7C5CFC);color:#fff;border:none;border-radius:14px;padding:14px;font-size:15px;font-weight:bold;cursor:pointer;margin-top:20px;width:100%}
.btn-n:disabled{opacity:.38;cursor:not-allowed}.btn-b{background:#22223A;color:#C0C0D8;border:none;border-radius:10px;padding:9px 18px;font-size:13px;cursor:pointer;margin-top:8px}
.cat-t{font-size:12px;font-weight:bold;color:#4F8EF7;background:#22223A;border-radius:8px;padding:6px 10px;margin:14px 0 8px;display:inline-block}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px}
.chip{background:#1A1A26;border:1.5px solid #2A2A40;border-radius:20px;padding:8px 16px;font-size:13px;cursor:pointer;color:#D0D0E8;transition:all .15s;user-select:none}
.chip:hover{border-color:#7C5CFC;color:#F0F0FF}.chip.sel{background:#1A1A40;border-color:#7C5CFC;color:#7C5CFC;font-weight:bold}
.pcard{background:#1A1A26;border:1px solid #2A2A40;border-radius:18px;padding:20px;margin-bottom:16px}
.pcard.top{border-color:#7C5CFC;border-width:2px;box-shadow:0 0 24px #4F8EF728}
.prow{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px}
.pbr{font-size:12px;color:#4F8EF7;font-weight:bold}.pnm{font-size:18px;font-weight:bold;margin:4px 0}
.ptag{display:inline-block;background:#22223A;color:#C8C8E0;border-radius:6px;padding:3px 10px;font-size:12px;margin-bottom:6px}
.ppr{font-size:22px;font-weight:bold;color:#fff}.psp{font-size:13px;color:#A0A0BB;margin-top:4px}
.fresh{border-radius:10px;padding:10px 14px;margin:10px 0;font-size:12px;font-weight:bold}
.srow{margin:5px 0}.slb{display:flex;justify-content:space-between;font-size:13px;color:#C0C0D8;margin-bottom:2px}
.sbg{background:#12121A;border-radius:3px;height:5px;overflow:hidden}.sfill{height:100%;border-radius:3px}
.shoprow{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.sh{border-radius:10px;padding:8px 14px;font-size:12px;font-weight:bold;transition:opacity .15s}.sh:hover{opacity:.75}
.pc{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
@media(max-width:500px){.pc{grid-template-columns:1fr}}
.pros{background:#0F1F18;border-radius:10px;padding:10px}.cons{background:#1F160A;border-radius:10px;padding:10px}
.pros-t{font-size:12px;color:#00E5A0;font-weight:bold;margin-bottom:4px}.cons-t{font-size:12px;color:#FF8C42;font-weight:bold;margin-bottom:4px}
.pc-tx{font-size:14px;color:#C0C0D8}
.bcard{background:#1A1A26;border:1px solid #2A2A40;border-radius:16px;padding:20px;margin-bottom:14px}
.bparts{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.bpart{background:#22223A;border-radius:8px;padding:8px 12px;min-width:145px}
.bpl{font-size:13px;color:#A0A0BB}.bpv{font-size:12px;color:#F0F0FF;font-weight:500}
.sharebox{background:#1A1A26;border:1px solid #2A2A40;border-radius:16px;padding:20px;margin-top:24px}
.share-t{font-size:15px;font-weight:bold;margin-bottom:14px}.share-bs{display:flex;flex-wrap:wrap;gap:10px}
.sbtn{border-radius:14px;padding:0;font-size:13px;font-weight:bold;color:#fff;transition:all .18s;display:inline-flex;flex-direction:column;align-items:center;justify-content:center;width:76px;height:76px;gap:5px;position:relative;overflow:hidden;box-shadow:0 4px 14px rgba(0,0,0,.45);border:none;cursor:pointer}.sbtn::after{content:"";position:absolute;top:0;left:0;right:0;height:50%;background:linear-gradient(180deg,rgba(255,255,255,.18) 0%,rgba(255,255,255,0) 100%);border-radius:14px 14px 0 0}.sbtn:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,.55)}.sbtn:active{transform:translateY(0px)}.sbtn-icon{font-size:26px;line-height:1;position:relative;z-index:1}.sbtn-label{font-size:11px;font-weight:bold;position:relative;z-index:1;letter-spacing:.3px}
.warn{background:#1F1400;border:1px solid #FF8C4255;border-radius:10px;padding:12px;margin-bottom:12px;font-size:12px;color:#FF8C42}
.sumbar{background:#22223A;border-radius:12px;padding:12px 16px;margin-bottom:16px;font-size:14px;color:#C8C8E0}
.div{height:1px;background:#2A2A40;margin:10px 0}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:999;display:flex;align-items:center;justify-content:center;padding:16px}
.modal{background:#1A1A26;border-radius:18px;max-width:460px;width:100%;padding:24px;max-height:85vh;overflow-y:auto}
.modal-t2{font-size:18px;font-weight:bold;margin-bottom:16px}
.msec{background:#22223A;border-radius:10px;padding:12px;margin-bottom:12px}
.msec-t{font-size:12px;font-weight:bold;margin-bottom:5px}.msec-p{font-size:14px;color:#C0C0D8;line-height:1.65}
.modal-ok{background:#4F8EF7;color:#fff;border:none;border-radius:12px;padding:12px;font-size:14px;font-weight:bold;cursor:pointer;width:100%;margin-top:8px}
.wm{position:fixed;right:12px;bottom:12px;font-size:11px;color:#ffffff1A;pointer-events:none}
</style>
</head>
<body>
{{ disclaimer | safe }}
<div class="hdr">
  <div><div class="hdr-t">🔍 3C 選購顧問</div><div class="hdr-s">捷啟智慧科技</div></div>
  <a href="/"><button class="btn-b">🏠 回首頁</button></a>
</div>
<div class="wrap">{{ body | safe }}</div>
<div class="wm">© 捷啟智慧科技</div>
<script>
function pick(el, grp, val) {
  document.querySelectorAll('.opt[data-grp="' + grp + '"]').forEach(function(e){ e.classList.remove('sel'); });
  el.classList.add('sel');
  document.querySelector('input[name="' + grp + '"]').value = val;
  var btn = document.getElementById('nxt');
  if (btn) btn.disabled = false;
}
function toggleChip(el) {
  el.classList.toggle('sel');
  var arr = [];
  document.querySelectorAll('.chip.sel').forEach(function(e){ arr.push(e.dataset.val); });
  document.getElementById('apps_input').value = JSON.stringify(arr);
}
</script>
</body></html>"""

def stepper(cur):
    labels = ["裝置","用途","軟體","預算","偏好","結果"]
    h = '<div class="stepper">'
    for i, lb in enumerate(labels):
        if i: h += '<div class="sln"></div>'
        cls = "done" if i<cur else ("active" if i==cur else "idle")
        txt = "✓" if i<cur else str(i+1)
        h += f'<div class="sd {cls}">{txt}</div><span class="sl">{lb}</span>'
    h += '</div>'
    return h

def page_device():
    h = stepper(0)
    h += '<div class="sec-t">您想選購什麼裝置？</div>'
    h += '<div class="sec-s">選一個最符合您需求的類型</div>'
    h += '<form method="POST" action="/step1"><div class="grid">'
    for em, nm, ds, vl in STEP_OPTS["device"]:
        h += f'<div class="opt" data-grp="device" onclick="pick(this,\'device\',\'{vl}\')">'
        h += f'<div class="opt-em">{em}</div><div class="opt-nm">{nm}</div><div class="opt-ds">{ds}</div></div>'
    h += '</div><input type="hidden" name="device" value="">'
    h += '<button type="submit" class="btn-n" id="nxt" disabled>下一步 →</button></form>'
    app_url = "https://your-app.onrender.com"
    enc_url = urllib.parse.quote(app_url)
    share_msg = urllib.parse.quote("免費 3C 選購顧問，幫你找到最適合的裝置！捷啟智慧科技出品。")
    h += f'<div class="sharebox" style="margin-top:32px"><div class="share-t" style="text-align:center">📤 分享給朋友一起用！</div><div class="share-bs" style="justify-content:center">'
    h += f'<a href="https://social-plugins.line.me/lineit/share?url={enc_url}&text={share_msg}" target="_blank" class="sbtn" style="background:#06C755">LINE</a>'
    h += f'<a href="https://www.facebook.com/sharer/sharer.php?u={enc_url}" target="_blank" class="sbtn" style="background:#1877F2">Facebook</a>'
    h += f'<a href="https://www.instagram.com/" target="_blank" class="sbtn" style="background:#C13584">Instagram</a>'
    h += f'<a href="https://www.threads.net/intent/post?text={share_msg}%0A{enc_url}" target="_blank" class="sbtn" style="background:#222">Threads</a>'
    h += '</div></div>'
    return h

def page_user(device):
    h = stepper(1)
    h += '<div class="sec-t">您主要是誰在用？</div>'
    h += '<div class="sec-s">幫我們了解您的使用習慣</div>'
    h += f'<form method="POST" action="/step2"><input type="hidden" name="device" value="{device}"><div class="grid">'
    for em, nm, ds, vl in STEP_OPTS["user"]:
        h += f'<div class="opt" data-grp="user" onclick="pick(this,\'user\',\'{vl}\')">'
        h += f'<div class="opt-em">{em}</div><div class="opt-nm">{nm}</div><div class="opt-ds">{ds}</div></div>'
    h += '</div><input type="hidden" name="user" value="">'
    h += '<button type="submit" class="btn-n" id="nxt" disabled>下一步 →</button>'
    h += '<br><button type="button" class="btn-b" onclick="history.back()">← 上一步</button></form>'
    return h

def page_apps(device, user):
    cats = APP_CATS_PHONE if device == "phone" else APP_CATS_PC
    h = stepper(2)
    h += '<div class="sec-t">您主要用來做什麼？</div>'
    h += '<div class="sec-s">可以複選，不確定可直接跳過</div>'
    h += f'<form method="POST" action="/step3">'
    h += f'<input type="hidden" name="device" value="{device}">'
    h += f'<input type="hidden" name="user" value="{user}">'
    h += '<input type="hidden" name="apps" id="apps_input" value="[]">'
    for cat_name, items in cats.items():
        h += f'<div class="cat-t">{cat_name}</div><div class="chips">'
        for item_name in items:
            safe_name = item_name.replace('"', '&quot;')
            h += f'<div class="chip" data-val="{safe_name}" onclick="toggleChip(this)">{item_name}</div>'
        h += '</div>'
    h += '<button type="submit" class="btn-n" style="margin-top:20px">下一步 →</button>'
    h += '<br><button type="button" class="btn-b" onclick="history.back()">← 上一步</button></form>'
    return h

def page_budget(device, user, apps):
    h = stepper(3)
    h += '<div class="sec-t">您的預算範圍？</div>'
    h += '<div class="sec-s">選一個最符合的方案</div>'
    apps_json = json.dumps(apps, ensure_ascii=False).replace("'", "&#39;")
    h += f'<form method="POST" action="/result">'
    h += f'<input type="hidden" name="device" value="{device}">'
    h += f'<input type="hidden" name="user" value="{user}">'
    h += f'<input type="hidden" name="apps" value="{apps_json}">'
    h += '<div class="grid">'
    for em, nm, ds, vl in STEP_OPTS["budget"]:
        h += f'<div class="opt" data-grp="budget" onclick="pick(this,\'budget\',\'{vl}\')">'
        h += f'<div class="opt-em">{em}</div><div class="opt-nm">{nm}</div><div class="opt-ds">{ds}</div></div>'
    h += '</div><input type="hidden" name="budget" value="">'
    h += '<button type="submit" class="btn-n" id="nxt" disabled>查看推薦結果 🎯</button>'
    h += '<br><button type="button" class="btn-b" onclick="history.back()">← 上一步</button></form>'
    return h

def page_result(device, user, budget, apps):
    dlabels = {"computer":"筆電","phone":"手機","tablet":"平板","desktop":"桌機自組"}
    ulabels = {"child":"小朋友","student":"學生","work":"上班族","create":"創作者","game":"遊戲玩家","senior":"長輩","general":"一般使用"}
    blabels = {"budget":"入門精省","mid":"主流全能","high":"頂級效能","pro":"不差這點錢"}

    h = stepper(5)
    h += f'<div class="sumbar">📋 您的選擇：<b style="color:#4F8EF7">{dlabels.get(device,device)}</b> · <b style="color:#4F8EF7">{ulabels.get(user,user)}</b> · <b style="color:#4F8EF7">{blabels.get(budget,budget)}</b></div>'

    if device == "desktop":
        bmap = {"budget":20000,"mid":35000,"high":60000,"pro":99999}
        bval = bmap.get(budget, 99999)
        for b in DEMO["desktop"]:
            nums = re.findall(r'\d+', b.get("total_price","0").replace(',',''))
            pval = int(nums[0]) if nums else 0
            if pval <= bval * 1.2:
                h += build_card(b)
    else:
        kmap = {"computer":"laptop","phone":"phone","tablet":"tablet"}
        products = DEMO.get(kmap.get(device,"laptop"), [])
        filtered = filter_products(products, user, budget)

        if apps:
            cats = APP_CATS_PHONE if device=="phone" else APP_CATS_PC
            reqs = {}
            for items in cats.values(): reqs.update(items)
            bmap = {"budget":15000,"mid":30000,"high":50000,"pro":99999}
            bval = bmap.get(budget, 0)
            required = max((reqs[a] for a in apps if a in reqs), default=0)
            if required > bval:
                heavy = [a for a in apps if a in reqs and reqs[a] > bval]
                suggested = "NT$35,000" if required <= 42000 else "NT$45,000 以上"
                h += f'<div class="warn">💡 建議：{"、".join(heavy)} 需要較強規格，建議提升至 {suggested}。</div>'

        if not filtered:
            h += '<div style="text-align:center;color:#A0A0BB;padding:40px;font-size:14px">沒有找到符合條件的產品，建議提高預算範圍。</div>'
        else:
            h += f'<div style="font-size:13px;color:#C0C0D8;margin-bottom:12px">為您找到 <b style="color:#4F8EF7">{len(filtered)}</b> 款推薦</div>'
            for i, p in enumerate(filtered):
                h += product_card(p, is_top=(i==0), apps=apps)

    # 分享區塊
    app_url = "https://your-app.onrender.com"
    enc_url = urllib.parse.quote(app_url)
    share_msg = urllib.parse.quote("免費 3C 選購顧問，幫你找到最適合的裝置！捷啟智慧科技出品。")
    h += f'''<div class="sharebox">
  <div class="share-t" style="text-align:center">📤 覺得好用？分享給朋友！</div>
  <div class="share-bs" style="justify-content:center">
    <a href="https://social-plugins.line.me/lineit/share?url={enc_url}&text={share_msg}" target="_blank" class="sbtn" style="background:linear-gradient(145deg,#11DD6B,#06C755);box-shadow:0 4px 14px #06C75566"><span class="sbtn-icon">💬</span><span class="sbtn-label">LINE</span></a>
    <a href="https://www.facebook.com/sharer/sharer.php?u={enc_url}" target="_blank" class="sbtn" style="background:linear-gradient(145deg,#4A9EFF,#1877F2);box-shadow:0 4px 14px #1877F266"><span class="sbtn-icon">📘</span><span class="sbtn-label">Facebook</span></a>
    <a href="https://www.instagram.com/" target="_blank" class="sbtn" style="background:linear-gradient(145deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);box-shadow:0 4px 14px #dc274366"><span class="sbtn-icon">📸</span><span class="sbtn-label">Instagram</span></a>
    <a href="https://www.threads.net/intent/post?text={share_msg}%0A{enc_url}" target="_blank" class="sbtn" style="background:linear-gradient(145deg,#444,#111);box-shadow:0 4px 14px #00000066"><span class="sbtn-icon">🧵</span><span class="sbtn-label">Threads</span></a>
  </div>
</div>'''
    h += '<br><a href="/"><button class="btn-b">← 重新選擇</button></a>'
    return h

def product_card(p, is_top=False, apps=None):
    if apps is None: apps = []
    sc = perf(p)
    fl, fc, fbg = freshness(p)
    pc = price_color(p.get("price",""))
    links = shop_links(p.get("brand",""), p.get("name",""))
    top_cls = " top" if is_top else ""
    top_badge = ' &nbsp;<span style="background:#2A2010;color:#FFD700;border-radius:6px;padding:3px 8px;font-size:11px;font-weight:bold">✦ 編輯首選</span>' if is_top else ""

    def bar(label, val, color):
        pct = int(val*100)
        return f'<div class="srow"><div class="slb"><span>{label}</span><span style="color:{color};font-weight:bold">{pct}%</span></div><div class="sbg"><div class="sfill" style="width:{pct}%;background:{color}"></div></div></div>'

    shops = ''.join(
        f'<a href="{url}" target="_blank" class="sh" style="color:{c};background:{c}18;border:1px solid {c}44">{nm}</a>'
        for nm, url, c in links
    )

    return f'''<div class="pcard{top_cls}">
  <div class="prow">
    <div>
      <div class="pbr">{p.get("brand","")}{top_badge}</div>
      <div class="pnm">{p.get("name","")}</div>
      <span class="ptag">{p.get("tag","")}</span>
      <div class="psp">⚡ {p.get("cpu","—")} &nbsp; 💾 {p.get("ram","—")} &nbsp; 💿 {p.get("ssd","—")}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:11px;font-weight:bold;color:{pc}">售價</div>
      <div class="ppr">{p.get("price","—")}</div>
      <div class="psp">🔋 {p.get("battery","—")} &nbsp; ⚖️ {p.get("weight","—")}</div>
    </div>
  </div>
  <div class="fresh" style="background:{fbg};border:1px solid {fc}55;color:{fc}">{fl}</div>
  <div class="div"></div>
  <div style="font-size:12px;font-weight:bold;margin-bottom:8px">📊 性能體感指標</div>
  {bar("🖥 文書辦公 / 多工", sc["office"], "#4F8EF7")}
  {bar("🎮 遊戲體驗 / 3D",   sc["game"],   "#FF8C42")}
  {bar("🎬 剪輯 / 專業生產",  sc["edit"],   "#7C5CFC")}
  <div class="div"></div>
  <div class="shoprow">{shops}</div>
  <div class="pc">
    <div class="pros"><div class="pros-t">✅ 優點</div><div class="pc-tx">{p.get("pros","—")}</div></div>
    <div class="cons"><div class="cons-t">⚠️ 注意</div><div class="pc-tx">{p.get("cons","—")}</div></div>
  </div>
</div>'''

def build_card(b):
    parts = [("CPU",b.get("cpu","")),("主機板",b.get("motherboard","")),
             ("RAM",b.get("ram","")),("SSD",b.get("ssd","")),
             ("顯卡",b.get("gpu","")),("電源",b.get("psu",""))]
    ph = "".join(f'<div class="bpart"><div class="bpl">{l}</div><div class="bpv">{v}</div></div>' for l,v in parts)
    return f'''<div class="bcard">
  <div class="prow">
    <div><div class="pnm">{b.get("name","")}</div><span class="ptag">{b.get("tag","")}</span></div>
    <div class="ppr" style="color:#00E5A0">{b.get("total_price","")}</div>
  </div>
  <div class="div"></div>
  <div class="bparts">{ph}</div>
</div>'''

# ── Routes ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(BASE, body=page_device(), disclaimer=DISC_HTML)

@app.route("/step1", methods=["POST"])
def step1():
    device = request.form.get("device","computer")
    session["device"] = device
    return render_template_string(BASE, body=page_user(device), disclaimer="")

@app.route("/step2", methods=["POST"])
def step2():
    device = request.form.get("device", session.get("device","computer"))
    user   = request.form.get("user","general")
    session["user"] = user
    return render_template_string(BASE, body=page_apps(device, user), disclaimer="")

@app.route("/step3", methods=["POST"])
def step3():
    device = request.form.get("device", session.get("device","computer"))
    user   = request.form.get("user", session.get("user","general"))
    try:    apps = json.loads(request.form.get("apps","[]"))
    except: apps = []
    session["apps"] = apps
    return render_template_string(BASE, body=page_budget(device, user, apps), disclaimer="")

@app.route("/result", methods=["POST"])
def result():
    device = request.form.get("device", session.get("device","computer"))
    user   = request.form.get("user",   session.get("user","general"))
    budget = request.form.get("budget", "mid")
    try:    apps = json.loads(request.form.get("apps","[]"))
    except: apps = []
    return render_template_string(BASE, body=page_result(device, user, budget, apps), disclaimer="")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
