"""
生活優轉 LINE Bot — 整合測試腳本
===================================
直接打 Vercel Webhook，模擬真實使用者，測量回應時間。

使用方式：
  python test_bot.py

環境變數（必填）：
  LINE_CHANNEL_SECRET=你的 channel secret
  BOT_URL=https://your-project.vercel.app  （預設讀 vercel.json 的 url）
"""

import sys, io, os, json, hmac, hashlib, base64, time, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 設定 ─────────────────────────────────────────────────────
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
BOT_URL        = os.environ.get("BOT_URL", "https://3c-advisor.vercel.app").rstrip("/")
WEBHOOK_URL    = f"{BOT_URL}/api/webhook"
TIMEOUT        = 20  # 秒

if not CHANNEL_SECRET:
    print("[ERROR] 請設定環境變數 LINE_CHANNEL_SECRET")
    print("  Windows: set LINE_CHANNEL_SECRET=你的secret")
    sys.exit(1)

# ── 工具函式 ─────────────────────────────────────────────────

def make_event(text: str, user_id: str = "Utest0000000000000000000000000001") -> dict:
    """產生 LINE text message event"""
    return {
        "destination": "Utest",
        "events": [{
            "type": "message",
            "replyToken": "test_reply_token_0000000000000000000",
            "source": {"type": "user", "userId": user_id},
            "timestamp": int(time.time() * 1000),
            "message": {"type": "text", "id": "999", "text": text}
        }]
    }

def sign(body: bytes) -> str:
    return base64.b64encode(hmac.new(CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()).decode()

def send(text: str, user_id: str = "Utest0000000000000000000000000001") -> tuple:
    """送出訊息，回傳 (status, elapsed_ms, response_body)"""
    body = json.dumps(make_event(text, user_id)).encode("utf-8")
    sig  = sign(body)
    req  = urllib.request.Request(
        WEBHOOK_URL, data=body, method="POST",
        headers={
            "Content-Type":        "application/json",
            "X-Line-Signature":    sig,
        }
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            elapsed = int((time.time() - t0) * 1000)
            return r.status, elapsed, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - t0) * 1000)
        return e.code, elapsed, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return 0, elapsed, str(e)

# ── 測試案例 ─────────────────────────────────────────────────
# (分類, 描述, 訊息文字, user_id)
TEST_CASES = [
    # 冷啟動暖機
    ("暖機",      "第1次請求（可能冷啟動）",   "你好",              "U001"),

    # 今天吃什麼
    ("吃什麼",    "主選單",                    "今天吃什麼",         "U001"),
    ("吃什麼",    "指定城市",                  "吃什麼 台北",        "U001"),
    ("吃什麼",    "隨機推薦",                  "幫我決定吃什麼",     "U001"),
    ("吃什麼",    "必比登(無城市)",             "必比登推介",         "U001"),
    ("吃什麼",    "必比登台北",                "必比登 台北",        "U001"),
    ("吃什麼",    "拉麵推薦",                  "想吃拉麵",           "U001"),
    ("吃什麼",    "麻辣鍋",                    "想吃麻辣鍋",         "U001"),
    ("吃什麼",    "早餐(飯糰)",                "飯糰推薦",           "U001"),
    ("吃什麼",    "城市特色 台南",             "地方特色 台南",      "U001"),
    ("吃什麼",    "在地餐廳 高雄",             "在地餐廳 高雄",      "U001"),
    ("吃什麼",    "聚餐推薦",                  "聚餐推薦",           "U001"),
    ("吃什麼",    "本週美食活動",              "本週美食活動",       "U001"),

    # 天氣
    ("天氣",      "主選單",                    "天氣",               "U002"),
    ("天氣",      "台北天氣",                  "台北天氣",           "U002"),
    ("天氣",      "穿什麼",                    "今天穿什麼",         "U002"),
    ("天氣",      "早安摘要",                  "早安摘要",           "U002"),

    # 健康
    ("健康",      "BMI計算",                   "165 60 BMI",         "U003"),
    ("健康",      "熱量查詢",                  "珍珠奶茶熱量",       "U003"),
    ("健康",      "運動消耗",                  "跑步30分鐘消耗",     "U003"),
    ("健康",      "喝水量",                    "每天要喝多少水",     "U003"),
    ("健康",      "睡眠建議",                  "失眠怎麼辦",         "U003"),
    ("健康",      "情緒支持",                  "好累好難過",         "U003"),

    # 金錢
    ("金錢",      "主選單",                    "金錢小幫手",         "U004"),
    ("金錢",      "預算規劃",                  "月薪40000怎麼存錢",  "U004"),
    ("金錢",      "信用卡推薦",                "信用卡推薦",         "U004"),
    ("金錢",      "即時匯率",                  "現在匯率",           "U004"),
    ("金錢",      "油價",                      "今天油價",           "U004"),

    # 3C
    ("3C",        "主選單",                    "3C推薦",             "U005"),
    ("3C",        "手機推薦",                  "推薦手機",           "U005"),
    ("3C",        "硬體升級",                  "電腦升級建議",       "U005"),

    # 防詐/法律
    ("防詐法律",  "防詐主選單",                "防詐法律",           "U006"),
    ("防詐法律",  "詐騙辨識",                  "防詐辨識",           "U006"),
    ("防詐法律",  "高風險訊息",                "你好我是警察局，你帳戶涉及犯罪請轉帳到安全帳戶", "U006"),
    ("防詐法律",  "法律常識",                  "法律常識",           "U006"),
    ("防詐法律",  "租屋問題",                  "房東不還押金怎麼辦", "U006"),

    # 找車位
    ("車位",      "說明文字",                  "找車位",             "U007"),

    # 近期活動
    ("活動",      "主選單",                    "近期活動",           "U008"),
    ("活動",      "週末活動",                  "週末去哪玩",         "U008"),
    ("活動",      "台北展覽",                  "台北展覽",           "U008"),
]

# ── 執行測試 ─────────────────────────────────────────────────
print("=" * 60)
print(f"生活優轉 Bot 整合測試")
print(f"目標：{WEBHOOK_URL}")
print("=" * 60)
print()

results   = []
pass_cnt  = 0
fail_cnt  = 0
slow_cnt  = 0
SLOW_MS   = 5000  # 超過此毫秒數標示為慢

last_cat = ""
for cat, desc, text, uid in TEST_CASES:
    if cat != last_cat:
        print(f"\n── {cat} ──")
        last_cat = cat

    status, ms, body = send(text, uid)
    ok   = status == 200
    slow = ms > SLOW_MS

    if ok:
        tag = "🐢" if slow else "✅"
        pass_cnt += 1
        if slow:
            slow_cnt += 1
    else:
        tag = "❌"
        fail_cnt += 1

    print(f"  {tag} [{ms:5d}ms] {desc}（{text[:20]}）", end="")
    if not ok:
        print(f"  → HTTP {status}: {body[:80]}", end="")
    print()

    results.append({"cat": cat, "desc": desc, "text": text, "status": status, "ms": ms, "ok": ok})
    time.sleep(0.3)  # 避免打太快

# ── 摘要 ─────────────────────────────────────────────────────
total = len(results)
ok_results = [r for r in results if r["ok"]]
avg_ms = int(sum(r["ms"] for r in ok_results) / len(ok_results)) if ok_results else 0
max_r  = max(results, key=lambda r: r["ms"])
min_r  = min(results, key=lambda r: r["ms"])

print()
print("=" * 60)
print(f"測試結果：{pass_cnt}/{total} 通過  |  失敗：{fail_cnt}  |  慢（>{SLOW_MS//1000}s）：{slow_cnt}")
print(f"回應時間：平均 {avg_ms}ms  |  最慢 {max_r['ms']}ms（{max_r['desc']}）  |  最快 {min_r['ms']}ms")
print("=" * 60)

if fail_cnt:
    print("\n❌ 失敗清單：")
    for r in results:
        if not r["ok"]:
            print(f"  • {r['desc']}（{r['text'][:30]}）→ HTTP {r['status']}")

if slow_cnt:
    print(f"\n🐢 慢回應（>{SLOW_MS//1000}s）：")
    for r in results:
        if r["ok"] and r["ms"] > SLOW_MS:
            print(f"  • {r['ms']}ms — {r['desc']}")

# 輸出 JSON 報告
report_path = os.path.join(os.path.dirname(__file__), "test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump({"summary": {"total": total, "pass": pass_cnt, "fail": fail_cnt,
                            "slow": slow_cnt, "avg_ms": avg_ms},
               "results": results}, f, ensure_ascii=False, indent=2)
print(f"\n詳細報告：{report_path}")
