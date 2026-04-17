# 生活優轉 LINE Bot — 系統架構文件

**版本**：v1.4  
**更新日期**：2026-04-18  
**適用對象**：開發者、協作者、未來維護者、AI 協作

---

## 版本歷史

| 版本 | 日期 | 主要異動 |
|---|---|---|
| v1.0 | 2026-04-18 | 初版，涵蓋核心模組與架構 |
| v1.1 | 2026-04-18 | 增加系統架構圖、平衡功能描述、新增資料模組與未來規劃章節 |
| v1.2 | 2026-04-18 | 增加部署流程章節（從零部署到上線的完整步驟）|
| v1.3 | 2026-04-18 | 修正本地開發啟動指令、補充 .env 建立說明、新增 Vercel Cron 設定範例、確認 Redis 環境變數名稱 |
| v1.4 | 2026-04-18 | 更新專案結構（模組化重構完成）、修正技術債章節、更新新增功能流程 |

---

## 一、系統架構總覽

```
┌─────────────────────────────────────────────────────────────┐
│                     用戶端（LINE App）                      │
│     文字訊息 / 位置訊息 / Quick Reply / Postback            │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTPS POST（LINE Webhook）
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          Vercel Serverless（api/webhook.py 路由層）          │
│                                                             │
│  ┌─────────┬─────────┬─────────┬─────────┬────────────────┐ │
│  │food.py  │parking  │weather  │health   │money / activity│ │
│  │今天吃啥 │找車位   │天氣穿搭 │健康小幫 │金錢 / 活動     │ │
│  ├─────────┴─────────┴─────────┴─────────┴────────────────┤ │
│  │    tech.py（3C推薦）  │  safety.py（防詐騙/法律）       │ │
│  └──────────┬────────────┴──────────┬──────────────────────┘ │
│             │                       │                        │
│       ┌─────▼─────┐           ┌─────▼──────┐                │
│       │ Google    │           │ TDX 交通部 │                │
│       │ Places    │           │ 停車 API   │                │
│       └─────┬─────┘           └─────┬──────┘                │
│             └──────────┬────────────┘                       │
│                        ▼                                    │
│               ┌─────────────────┐                           │
│               │ Upstash Redis   │  ← 跨 instance 快取       │
│               └───────┬─────────┘                           │
│                       │                                     │
│               ┌───────▼────────┐                            │
│               │ Supabase       │  ← 匿名統計 + 吃過紀錄     │
│               └────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
                        │  reply_message / push_message
                        ▼
              LINE Messaging API
          → Flex Message / Text / Quick Reply
```

### 位置訊息資料流

```
用戶傳送位置
  │
  ├── food_locate flag 存在（來自「今天吃什麼」）
  │     → 清除 flag
  │     → Google Places Nearby Search（1.5km）
  │     → 回傳附近美食 Flex
  │
  └── 一般位置分享（找車位）
        ├── Redis 快取命中（5 分鐘）
        │     → 回傳停車結果 + push 附近美食
        └── 無快取
              → 立即回傳「搜尋中...」
              → 並行呼叫 TDX + Google Places
              → push 停車結果 + 附近美食
```

---

## 二、專案結構

```
line-bot/
├── api/
│   ├── webhook.py              # 路由層（~2,000 行），dispatch 到各模組
│   ├── modules/                # 業務邏輯模組
│   │   ├── food.py             # 今天吃什麼、聚餐推薦、必比登
│   │   ├── parking.py          # 找車位（TDX API）
│   │   ├── weather.py          # 天氣穿搭、早安摘要
│   │   ├── health.py           # 健康小幫手（BMI、熱量、睡眠）
│   │   ├── money.py            # 金錢小幫手（匯率、油價、信用卡）
│   │   ├── activity.py         # 近期活動
│   │   ├── tech.py             # 3C 推薦、硬體升級
│   │   └── safety.py           # 防詐騙、法律常識
│   ├── utils/                  # 共用工具
│   │   ├── redis.py            # Upstash Redis 讀寫
│   │   ├── supabase.py         # 使用統計、吃過紀錄
│   │   ├── line_api.py         # reply / push / verify_signature
│   │   ├── google_places.py    # Nearby Search、Text Search、Photo
│   │   └── intent.py           # 評分制意圖分類器
│   └── data/                   # 靜態資料（JSON，不需改程式碼即可更新）
│       ├── food_db.json         # 8 大食物分類推薦庫
│       ├── bib_gourmand.json    # 米其林必比登推介（台北/台中/台南/高雄）
│       ├── city_specialties.json# 全台 22 縣市特色小吃
│       └── style_keywords.json  # 食物風格關鍵字分類
├── requirements.txt            # 僅 urllib3
├── vercel.json                 # Serverless 路由設定
├── restaurant_cache.json       # 觀光署餐廳資料快取
├── accupass_cache.json         # 活動爬蟲快取
└── scrape_all.py               # 爬蟲更新腳本
```

---

## 三、環境變數

| 變數名稱 | 必填 | 用途 |
|---|---|---|
| `LINE_CHANNEL_SECRET` | 是 | Webhook 簽章驗證 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 是 | LINE Messaging API |
| `GOOGLE_PLACES_API_KEY` | 是 | 附近美食、照片、Text Search |
| `UPSTASH_REDIS_URL` / `UPSTASH_REDIS_TOKEN` | 是 | 跨 instance 快取（注意：不含 `_REST_`，與 Upstash 官方文件命名不同）|
| `TDX_CLIENT_ID` / `TDX_CLIENT_SECRET` | 選 | 停車場資料 |
| `CWA_API_KEY` | 選 | 中央氣象署天氣 |
| `SUPABASE_URL` / `SUPABASE_KEY` | 選 | 使用統計 + 吃過紀錄 |
| `LINE_BOT_ID` | 選 | 好友邀請連結 |
| `ADMIN_USER_ID` | 選 | 管理員廣播 |

---

## 四、API 路由

| 路由 | 方法 | 說明 |
|---|---|---|
| `/api/webhook` | POST | LINE Webhook 主入口 |
| `/api/warm_cache` | GET | 預熱快取 |
| `/api/stats` | GET | 使用統計儀表板 |
| `/api/parking_debug` | GET | 停車功能 debug |
| `/api/setup_richmenu` | GET | Rich Menu 設定 |

---

## 五、資料模型

### Supabase 資料表

**`linebot_usage_logs`**（匿名統計）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | bigint | PK |
| `uid_hash` | varchar(16) | sha256(user_id)[:16] |
| `feature` | varchar | 功能名稱 |
| `sub_action` | varchar | 子動作 |
| `city` | varchar | 城市 |
| `is_success` | boolean | 是否成功回應 |
| `created_at` | timestamptz | 建立時間 |

**`user_eaten_restaurants`**（吃過紀錄）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | bigint | PK |
| `uid_hash` | varchar(16) | sha256(user_id)[:16] |
| `restaurant_name` | varchar(80) | 餐廳名稱 |
| `city` | varchar(10) | 城市 |
| `created_at` | timestamptz | 建立時間（7 天有效期）|

### Redis Key 規範

| Key 格式 | TTL | 用途 |
|---|---|---|
| `tdx_token` | 55 min | TDX OAuth token |
| `tdx_lots_{city}` | 24 h | 停車場靜態清單（city = TDX 英文城市名）|
| `parking:{lat4}:{lon4}` | 5 min | 停車查詢結果 |
| `cwa_wx:{city}` | 15 min | 天氣資料（city = 中文城市名）|
| `morning_rates` | 1 h | 台銀匯率 |
| `morning_oil` | 6 h | 中油 + 台塑油價 |
| `food_locate:{user_id}` | 180 s | 吃什麼位置 flag（原始 user_id）|
| `user_city:{uid_hash}` | 無期限 | 用戶城市記憶 |

### 核心資料結構

**`_FOOD_DB` 食物項目：**

```python
{
    "name":  "排骨便當",
    "desc":  "炸得香脆大排骨，台式便當之王",
    "price": "~100–140元",
    "key":   "排骨便當",       # Google Maps 搜尋關鍵字
    "m":     "D",              # 時段：M=早餐, D=午晚, N=消夜, ""=全天
    "s":     "",               # 季節：hot=夏限定, cold=冬限定, ""=全年
}
```

**Google Places 餐廳物件：**

```python
{
    "name":               "店名",
    "addr":               "地址",
    "rating":             4.5,
    "user_ratings_total": 328,
    "lat":                25.047,
    "lng":                121.517,
    "place_id":           "ChIJ...",
    "photo_ref":          "...",      # 組成 Places Photo URL
    "open_now":           True,       # 可能為 None
    "_source":            "google",
    "dist":               350,        # 公尺，由 _haversine() 注入
}
```

---

## 六、核心功能模組

### 6-1. 今天吃什麼

**觸發關鍵字**：吃什麼、吃甚麼、吃啥、午餐、晚餐、早餐、吃飯、推薦餐廳、必比登、米其林，以及 `_ALL_FOOD_KEYWORDS` 內所有食物詞彙。

**主路由函式**：`build_food_message(text, user_id)`

**主流程**：
1. 解析城市（全台 22 縣市）→ `_set_user_city()` 寫入 Redis
2. 無城市 → 讀 Redis 城市記憶；仍無 → 顯示地區 / 城市選擇器
3. 依關鍵字分支：必比登 / 隨機 / 在地餐廳 / 位置分享 / 食物分類推薦

**8 大食物分類**（含時段過濾）：

| 分類 | 有效時段 | 代表品項 |
|---|---|---|
| 便當 | 午餐後 | 排骨便當、控肉飯、自助餐 |
| 麵食 | 午餐後 | 牛肉麵、拉麵、涼麵 |
| 小吃 | 午 / 消夜 | 蚵仔煎、臭豆腐、鹽酥雞 |
| 火鍋 | 午 / 消夜 | 麻辣鍋、薑母鴨、個人小火鍋 |
| 日韓 | 午 / 消夜 | 壽司、炸豬排、韓式炸雞 |
| 早午餐 | 早餐限定 | 蛋餅+豆漿、燒餅油條、鬆餅 |
| 飲料甜點 | 全天（含季節限定）| 珍奶（全年）、剉冰（夏）、燒仙草（冬）|
| 輕食 | 全天 | 沙拉、御飯糰、水煮餐 |

**位置分享流程**：進入吃什麼任一入口時自動寫入 `food_locate:{user_id}`（TTL 180 秒）。用戶分享位置後，呼叫 Google Places Nearby Search（1.5km），過濾 7 天內吃過的店，依評分排序取前 5 家，回傳含照片的 Flex 卡片。每張卡有「✅ 吃過了」Postback 按鈕寫入 Supabase。

**其他子功能**：必比登推介（`build_bib_gourmand_flex`）、城市地方特色（`build_city_specialties`）、Accupass 美食活動（`build_live_food_events`）。

---

### 6-2. 找車位

**觸發方式**：用戶傳送位置訊息（且無 `food_locate` flag）。

**主路由函式**：`build_parking_flex(lat, lon, city)`

**多來源 Fallback（`_get_nearby_parking()`）**：

```
Step 1：_coords_to_tdx_city() → 判斷所在縣市

Step 2：依縣市選擇資料來源（平行執行，各 timeout 5 秒）

  宜蘭  → 宜蘭縣政府 API
  新北  → 新北路邊停車 API（含即時格位）+ 新北停車場 API（平行）
  桃園  → 桃園市政府 API + TDX 補充（去重）（平行）
  新竹  → 新竹市 API + TDX 補充（平行）
  台南  → 台南市政府 API + TDX 補充（平行）
  其他  → TDX 交通部 API（覆蓋全台主要縣市）

Step 3：結果截斷（路邊最多 8 筆、停車場最多 6 筆）
```

**TDX Token 三層快取**：記憶體（50 min）→ Redis（55 min）→ 重新 OAuth2 取得（約 1–2 秒）

**雙推送**：先 `reply` 停車結果，再 `push` 附近美食，形成「停好車 → 推薦美食」閉環。

---

### 6-3. 健康小幫手

**觸發關鍵字**：BMI、身高體重、熱量、幾卡、失眠、睡不著、運動消耗、喝水量…

**主路由函式**：`build_health_message(text)`

| 子功能 | 函式 | 說明 |
|---|---|---|
| BMI 計算 | `build_bmi_flex()` | 自然語言解析（「165 55」/ 「165cm 55kg」均可）|
| 食物熱量 | `build_calorie_result()` | 內建 ~40 種台灣常見外食 |
| 運動消耗 | `build_exercise_result()` | 運動名稱 + 分鐘，以 60 kg 換算 |
| 每日喝水 | `build_water_intake()` | 體重 × 35 ml |
| 睡眠 / 飲食 / 壓力 | 各自獨立函式 | 固定建議內容 |
| 情緒支持 | `build_mood_support()` | 高優先路由，接住 30+ 種負面情緒詞彙 |

---

### 6-4. 金錢小幫手

**觸發關鍵字**：存錢、理財、月薪、信用卡、匯率、油價、保險、換匯…

**主路由函式**：`build_money_message(text)`

| 子功能 | 函式 | 說明 |
|---|---|---|
| 月薪預算 | `build_budget_plan()` | 50/30/20 法則 |
| 信用卡推薦 | `build_credit_card_result()` | `CREDIT_CARDS_DB`（現金回饋 / 外送 / 加油 / 海外 / 餐飲）|
| 即時匯率 | `build_exchange_rate()` | 台銀 RSS，9 種外幣，Redis 快取 1h |
| 即時油價 | `build_oil_price()` | 中油 + 台塑，Redis 快取 6h |
| 消費決策 | `build_spending_decision()` | 解析品項 + 金額，給出分析 |

---

### 6-5. 天氣穿搭

**觸發關鍵字**：天氣、穿什麼、幾度、下雨嗎、要帶傘…

**主路由函式**：`build_weather_message(text, user_id)`

中央氣象署 API，Redis 快取 15 分鐘。回傳卡片含：最高 / 最低氣溫、降雨機率、AQI（`_fetch_aqi`）、推估紫外線（`_estimate_uvi`）、穿搭建議（`_outfit_advice`）。

---

### 6-6. 近期活動

**觸發關鍵字**：活動、週末、踏青、展覽、咖啡廳、市集、親子、出去玩…

**主路由函式**：`build_activity_message(text, user_id)`

雙軌資料：Accupass 爬蟲快取（含日期 / 報名連結）+ `_ACTIVITY_DB` 靜態景點庫（戶外踏青 / 咖啡廳 / 親子 / 運動 / 文青藝文 / 市集展覽六大類）。以 `_is_event_past()` 過濾已過期活動。

---

### 6-7. 其他功能

| 功能 | 主路由函式 | 說明 |
|---|---|---|
| 3C 推薦 | `build_recommendation_message()` | 4 步問卷（裝置→使用者→用途→預算）|
| 硬體升級 | `build_upgrade_message()` | RAM / SSD / GPU 升級建議，含費用估算 |
| 聚餐推薦 | `build_group_dining_message()` | 依城市 + 類型推薦大桌 / 包廂餐廳 |
| 防詐騙 | `build_fraud_result()` | 2025–2026 詐騙手法，輸入可疑訊息分析 |
| 法律常識 | `build_legal_answer()` | 勞資 / 租賃 / 消保法問答 |
| 早安摘要 | `build_morning_summary()` | 天氣 + 匯率 + 油價 + 每日優惠 |

---

## 七、快取策略

| 資料 | TTL | 備注 |
|---|---|---|
| TDX Token | 55 min | 三層快取（記憶體 → Redis → 重取）|
| 停車查詢結果 | 5 min | 同位置多人共享 |
| 天氣資料 | 15 min | 6 大城市預熱 |
| 匯率 / 油價 | 1h / 6h | 早安摘要共用 |
| 食物定位 flag | 180 s | 自動清除 |

---

## 八、個資處理原則

- `user_id` 一律雜湊後儲存（`sha256(user_id)[:16]`，不可逆）
- 不儲存原始訊息內容，`linebot_usage_logs` 只記錄功能名稱與城市
- Redis 短暫 flag（`food_locate`）使用原始 `user_id`，TTL 180 秒，不持久化
- 第三方 API 結果不持久化入資料庫

---

## 九、費用控制

| API | 計費 | 控制方式 |
|---|---|---|
| Google Places Nearby | $0.032 / 次 | `food_locate` flag 防重複觸發 |
| Google Places Text | $0.032 / 次 | 僅名店搜尋觸發，頻率低 |
| Google Places Photo | $0.007 / 張 | 最多 5 張，`maxwidth=400` |
| TDX 停車 | 免費（有配額）| 24h 清單快取 + 5min 結果快取 |
| 中央氣象署 | 免費 | 15min Redis 快取 |

---

## 十、如何新增功能

1. 在 `api/modules/` 對應模組新增 handler 函式，回傳 `list[dict]`（LINE Message 格式）；若不屬於現有任何模組，新建一個 `modules/xxx.py`
2. 在 `api/webhook.py` 的 `handle_text_message()` 適當優先順序位置加路由規則，並 import 新函式（先出現者優先，注意關鍵字衝突）
3. 若需外部 API：新增環境變數，在 Vercel Project Settings 設定
4. 若需快取：使用 `utils/redis.py` 的 `redis_get` / `redis_set` 並設合理 TTL
5. 在回應路徑呼叫 `log_usage(user_id, "feature_name")`
6. 若有大量靜態資料（清單、關鍵字）：存成 `api/data/xxx.json`，用 `_load_json()` 讀取

**最小範例：新增「今日電影推薦」**

```python
# Step 1：在 api/modules/entertainment.py 新增函式
import random, json, os

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def _load_json(filename, default):
    try:
        with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

_MOVIE_DB = _load_json("movies.json", [
    {"title": "奧本海默", "genre": "傳記/歷史", "rating": "9.0",
     "desc": "原子彈之父的史詩傳記，諾蘭導演三小時鉅作"},
])

def build_movie_message(text: str) -> list:
    movie = random.choice(_MOVIE_DB)
    return [{"type": "text",
             "text": f"🎬 今日推薦：{movie['title']}\n"
                     f"類型：{movie['genre']}  ★{movie['rating']}\n"
                     f"{movie['desc']}"}]

# Step 2：在 api/webhook.py 頂部 import
from modules.entertainment import build_movie_message

# Step 3：在 handle_text_message() 加路由
if any(w in text for w in ["電影推薦", "看什麼電影", "今晚看電影"]):
    log_usage(user_id, "movie")
    return build_movie_message(text)
```

---

## 十一、已知限制與技術債

| 問題 | 影響 | 建議方向 | 狀態 |
|---|---|---|---|
| ~~單檔架構（~10,000 行）~~ | ~~維護困難，多人協作衝突高~~ | ~~模組化拆分（`modules/food.py` 等）~~ | ✅ 已完成（2026-04-18）|
| Vercel 冷啟動 2–3 秒 | 偶爾讓用戶誤以為 Bot 無回應 | `warm_cache` Cron 定時預熱 | 待處理 |
| `user_city` 無 TTL | 用戶旅遊後需手動重選 | 建議加 90 天過期 | 待處理 |
| 信用卡 DB 手工維護 | 回饋比例可能過期 | 每季核對，加 `updated_at` 欄位 | 待處理 |
| `handle_text_message()` 過長 | 超過 50 個 if-elif | 重構為 dispatch table | 待處理 |
| 「幫我決定」文案不直觀 | 新用戶不易理解 | 改為「🎲 隨機推一個」 | 待處理 |

---

## 十二、未來規劃

- 強化「今天吃什麼」個人化推薦（根據歷史紀錄與口味偏好）
- 擴大縣市停車格支援（路邊即時格位資料）
- B2B 模組化（核心功能打包為可客製模組）
- 更多情境化推薦（心情、預算、聚餐人數）
- 優化冷啟動體驗

---

## 十三、部署流程

### 前置準備（第一次部署）

**1. 申請所需帳號與 API 金鑰**

| 服務 | 申請位置 | 取得內容 |
|---|---|---|
| LINE Developers | developers.line.biz → 建立 Messaging API Channel | `Channel Secret`、`Channel Access Token` |
| Google Cloud | console.cloud.google.com → 啟用 Places API | `API Key`（建議限制來源 IP 或 HTTP Referrer）|
| Upstash | console.upstash.com → 建立 Redis 資料庫 | `REST URL`、`REST Token` |
| TDX 交通部 | motc.tw → 申請 API 帳號 | `Client ID`、`Client Secret` |
| 中央氣象署 | opendata.cwa.gov.tw → 申請會員 | `API Key` |
| Supabase | supabase.com → 建立新專案 | `Project URL`、`anon key` |

**2. 建立 Supabase 資料表**

在 Supabase SQL Editor 執行：

```sql
-- 匿名使用統計
CREATE TABLE linebot_usage_logs (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uid_hash   varchar(16),
    feature    varchar,
    sub_action varchar,
    city       varchar,
    is_success boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

-- 吃過紀錄
CREATE TABLE user_eaten_restaurants (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uid_hash         varchar(16),
    restaurant_name  varchar(80),
    city             varchar(10),
    created_at       timestamptz DEFAULT now()
);
```

---

### 部署到 Vercel

**3. 連結 GitHub 並部署**

```
1. 將專案 push 到 GitHub（確認 line-bot/ 目錄在根目錄下）
2. 前往 vercel.com → Import Project → 選擇 GitHub Repo
3. Framework Preset：選「Other」
4. Root Directory：填 line-bot
5. 點擊 Deploy
```

**4. 設定環境變數**

Vercel → Project → Settings → Environment Variables，逐一填入：

```
LINE_CHANNEL_SECRET          = xxxxxxxx
LINE_CHANNEL_ACCESS_TOKEN    = xxxxxxxx
GOOGLE_PLACES_API_KEY        = xxxxxxxx
UPSTASH_REDIS_URL            = https://xxx.upstash.io
UPSTASH_REDIS_TOKEN          = xxxxxxxx
TDX_CLIENT_ID                = xxxxxxxx
TDX_CLIENT_SECRET            = xxxxxxxx
CWA_API_KEY                  = xxxxxxxx
SUPABASE_URL                 = https://xxx.supabase.co
SUPABASE_KEY                 = xxxxxxxx
LINE_BOT_ID                  = @xxxxxxxx
ADMIN_USER_ID                = Uxxxxxxxx
```

**5. 取得 Webhook URL**

部署成功後，Vercel 會給一個網址，例如：

```
https://your-project.vercel.app/api/webhook
```

**6. 設定 LINE Webhook**

LINE Developers → Messaging API → Webhook settings：
- Webhook URL 填入上面的網址
- 開啟「Use webhook」
- 點擊「Verify」確認收到 200 回應

**7. 設定 Rich Menu（選填）**

```
瀏覽器開啟：https://your-project.vercel.app/api/setup_richmenu
出現 {"ok": true} 表示 Rich Menu 建立成功
```

---

### 驗證部署

**8. 功能測試順序**

```
1. 傳「你好」→ 確認收到歡迎選單
2. 傳「吃什麼」→ 確認出現地區選擇
3. 傳「天氣」→ 確認出現城市選擇
4. 傳「165 55 BMI」→ 確認 BMI 計算結果
5. 分享位置 → 確認收到停車 + 美食推送
```

**9. 快取預熱（選填，減少首次使用的延遲）**

手動觸發：
```
瀏覽器開啟：https://your-project.vercel.app/api/warm_cache
等待 10 秒後回傳 {"status": "warmed", "detail": {...}}
```

自動定時執行（Vercel Cron）：在 `line-bot/vercel.json` 的最外層加入 `crons` 欄位：

```json
{
  "version": 2,
  "crons": [
    {
      "path": "/api/warm_cache",
      "schedule": "*/30 * * * *"
    }
  ],
  "builds": [...],
  "routes": [...]
}
```

> Vercel Cron 僅 Pro 方案支援任意排程；Hobby 方案每天只能執行一次（`"schedule": "0 0 * * *"`）。設定後在 Vercel Dashboard → Project → Cron Jobs 可確認狀態。

---

### 本地開發（不依賴 Vercel）

**建立 `.env` 環境變數檔**（repo 內沒有這個檔案，需自行建立，不要 commit）：

```bash
# line-bot/.env
LINE_CHANNEL_SECRET=xxx
LINE_CHANNEL_ACCESS_TOKEN=xxx
GOOGLE_PLACES_API_KEY=xxx
UPSTASH_REDIS_URL=https://xxx.upstash.io
UPSTASH_REDIS_TOKEN=xxx
# 其他選填變數照上方環境變數表填入
```

**方法 A：使用 Vercel CLI（推薦，行為最接近正式環境）**

```bash
npm install -g vercel
cd line-bot
vercel dev          # 自動讀取 .env 並在 localhost:3000 啟動
```

**方法 B：直接執行 Python（快速測試用）**

> `webhook.py` 使用 Python 內建的 `BaseHTTPRequestHandler`，不是靜態檔案伺服器，不能用 `python -m http.server` 啟動。

```bash
cd line-bot
pip install urllib3

# 載入 .env 並啟動
export $(cat .env | xargs)   # macOS / Linux
# Windows PowerShell：
# Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }

python -c "
from http.server import HTTPServer
import sys; sys.path.insert(0, 'api')
from webhook import handler
print('Listening on http://localhost:8000')
HTTPServer(('localhost', 8000), handler).serve_forever()
"
```

**讓 LINE 能打到本機（兩種方法均需要）：**

```bash
ngrok http 8000        # 或 vercel dev 的 port（預設 3000）
# 複製 ngrok 給的 https 網址 → 填入 LINE Developers Webhook URL
```

---

**文件維護說明**：本文件隨功能迭代同步更新，每次重大修改請更新版本號與版本歷史表格。
