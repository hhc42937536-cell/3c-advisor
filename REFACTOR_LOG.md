# Refactor Log

## 2026-04-21

本輪整理重點是先穩住正式主線 `line-bot`，避免一次大搬家造成 LINE Bot 行為回歸。

### 已完成

- 將 `line-bot/api/webhook.py` 的文字路由拆成 `line-bot/api/handlers/` 多個小模組。
- 將 `line-bot/api/modules/food.py` 的共用工具抽到 `line-bot/api/modules/food_utils.py`。
- 將 feedback / suggestion 邏輯集中在 `line-bot/api/handlers/feedback_routes.py`，`food.py` 只保留相容用薄包裝。
- 補回中文 feedback 關鍵字支援，例如 `回報`、`建議`、`好吃`、`倒閉`、`歇業`。
- 新增 `line-bot/verify_core.py`，可快速檢查核心檔案編譯、中文 feedback handler、基本 food Flex builder。
- 將多人聚餐推薦拆到 `line-bot/api/modules/food_group_dining.py`，`food.py` 保留原本 `build_group_dining_message()` 相容入口。
- 將今天吃什麼主選單、類型選單、精選選單、地區/城市 picker 拆到 `line-bot/api/modules/food_menu_builders.py`。
- 將地方特色小吃與特色名店搜尋拆到 `line-bot/api/modules/food_specialties.py`，`food.py` 以 dependency injection 傳入季節判斷、餐廳 fallback、Places 搜尋與餐廳 bubble builder。
- 將必比登推薦卡片拆到 `line-bot/api/modules/food_bib_gourmand.py`，`food.py` 保留相容入口並注入資料、近期推薦記錄與地圖 URL builder。
- 將 Google Places Text Search、Places photo URL、餐廳 bubble、在地餐廳推薦卡拆到 `line-bot/api/modules/food_restaurants.py`。
- 將一般食物推薦卡與時段/季節過濾拆到 `line-bot/api/modules/food_recommendations.py`。
- 將 Accupass 美食活動卡片拆到 `line-bot/api/modules/food_events.py`。
- 將 `build_food_message()` 主路由拆到 `line-bot/api/modules/food_router.py`，`food.py` 只負責注入資料與 builder callback。
- 擴充 `line-bot/verify_core.py`，改為自動編譯 `line-bot/api/modules/*.py` 與 `line-bot/api/handlers/*.py`。
- 清理 `line-bot/api/modules/food.py` 拆分後留下的未使用匯入、多餘空白區塊與不可達 `return`。
- 擴充 `line-bot/verify_core.py`，加入 `build_food_message("今天吃什麼")`、`build_food_message("吃什麼 選類型")`、`build_group_dining_message("聚餐 台北 火鍋")` 的快速路由檢查。
- 將天氣地區/城市 picker 與早安城市 picker 拆到 `line-bot/api/modules/weather_pickers.py`。
- 將天氣圖示、穿搭建議、UV 估算等純邏輯拆到 `line-bot/api/modules/weather_advice.py`。
- 將早安摘要的邀請文字、每日 hash、全台好康、在地優惠、行動建議選取邏輯拆到 `line-bot/api/modules/weather_morning_helpers.py`。
- 將 `surprise_cache.json` 與 `accupass_cache.json` 的 lazy cache 載入拆到 `line-bot/api/modules/weather_cache.py`。
- 將 CWA 天氣、AQI、油價、匯率等外部資料抓取拆到 `line-bot/api/modules/weather_fetchers.py`。
- 清理 `line-bot/api/modules/weather.py` 拆分後不再使用的 import。
- 將一般天氣 Flex 卡片拆到 `line-bot/api/modules/weather_flex.py`，`weather.py` 保留相容入口並注入 fetch/advice helpers。
- 將早安摘要 Flex builder 拆到 `line-bot/api/modules/weather_morning_summary.py`，`weather.py` 保留相容入口並注入城市、快取、天氣、油價、匯率、優惠等 helper。
- 將早安摘要用的大型靜態資料池拆到 `line-bot/api/modules/weather_morning_data.py`，使 `weather.py` 從大型混合檔轉為入口/依賴注入層。
- 擴充 `line-bot/verify_core.py`，加入 weather picker 與 `build_weather_message("天氣")` 的快速路由檢查。
- 將停車模組的地理工具拆到 `line-bot/api/modules/parking_geo.py`，包含距離計算、座標推 TDX 城市、TWD97 轉 WGS84。
- 將停車模組的 TDX token、TDX GET、停車結果快取 key/peek 拆到 `line-bot/api/modules/parking_tdx.py`。
- 擴充 `line-bot/verify_core.py`，加入 `build_parking_flex(25.0478, 121.5170, "台北")` 的快速檢查。
- 將停車後附近美食推薦與餐廳 bubble 拆到 `line-bot/api/modules/parking_food.py`。
- 將停車主 Flex 卡片拆到 `line-bot/api/modules/parking_flex.py`，`parking.py` 保留相容入口並注入 cache/API helper。
- 將 TDX、新北、台南、宜蘭、新竹、桃園等停車資料來源與多來源整合拆到 `line-bot/api/modules/parking_sources.py`。
- 將 3C 選購問卷 wizard 與情境推薦選單拆到 `line-bot/api/modules/tech_wizard.py`。
- 將 3C 硬體升級諮詢（RAM/SSD/GPU/效能分析）拆到 `line-bot/api/modules/tech_upgrade.py`。
- 擴充 `line-bot/verify_core.py`，加入 tech wizard parser 與硬體升級路由 smoke test。
- 將 3C 規格解釋、選購指南、比價搜尋卡片拆到 `line-bot/api/modules/tech_guides.py`。
- 擴充 `line-bot/verify_core.py`，加入 3C 規格解釋、選購指南、比價路由 smoke test。
- 將 3C 產品資料載入、預算/裝置/用途解析、產品過濾、產品卡片、推薦與適配檢查拆到 `line-bot/api/modules/tech_products.py`，讓 `tech.py` 成為相容匯出入口。
- 擴充 `line-bot/verify_core.py`，加入 3C 產品過濾與產品 Flex builder 的本地 smoke test。
- 將信用卡優惠資料、信用卡選單與推薦結果拆到 `line-bot/api/modules/money_credit_cards.py`。
- 將油價與匯率查詢拆到 `line-bot/api/modules/money_rates.py`。
- 將花費決策卡片與超支提醒拆到 `line-bot/api/modules/money_spending.py`。
- 擴充 `line-bot/verify_core.py`，加入 money 選單、信用卡推薦、花費決策與 money router smoke test。
- 將活動 cache、日期解析、地圖 URL、用戶城市記憶 helper 拆到 `line-bot/api/modules/activity_utils.py`。
- 將活動選單、區域 picker、城市 picker 拆到 `line-bot/api/modules/activity_pickers.py`。
- 將活動靜態 fallback 資料拆到 `line-bot/api/modules/activity_data.py`。
- 將活動 Flex 卡片 builder 拆到 `line-bot/api/modules/activity_flex.py`，讓 `activity.py` 成為活動主路由入口。
- 擴充 `line-bot/verify_core.py`，加入活動選單、城市 picker、活動 Flex 與 activity router smoke test。
- 將健康 BMI、水分、睡眠、飲食、壓力等基本建議拆到 `line-bot/api/modules/health_basic.py`。
- 將熱量查詢與運動消耗查詢拆到 `line-bot/api/modules/health_nutrition.py`。
- 將心情支持卡片拆到 `line-bot/api/modules/health_mood.py`。
- 擴充 `line-bot/verify_core.py`，加入健康 BMI、熱量、運動、心情支持、健康選單與 health router smoke test。
- 將詐騙資料載入、詐騙分析、詐騙說明與風險結果卡片拆到 `line-bot/api/modules/safety_fraud.py`。
- 將法律常識入口、法律 QA 資料與法律回答卡片拆到 `line-bot/api/modules/safety_legal.py`。
- 將安全工具總選單拆到 `line-bot/api/modules/safety_menu.py`。
- 擴充 `line-bot/verify_core.py`，加入詐騙分析、詐騙結果、法律指南、法律回答與安全工具選單 smoke test。
- 將 `food.py` 內的大型食物 fallback 資料、必比登資料、城市特色資料與地區/城市資料拆到 `line-bot/api/modules/food_data.py`。
- 將 `food.py` 的環境設定、餐廳快取、最近推薦記錄、CWA 天氣季節判斷與使用者城市記憶拆到 `line-bot/api/modules/food_runtime.py`。
- 清理 `food.py` 拆分後的未使用 import 與殘留暫存變數，使其成為美食功能相容入口與依賴注入層。
- 將停車 TDX 與宜蘭資料來源拆到 `line-bot/api/modules/parking_tdx_sources.py`。
- 將新北、台南、新竹、桃園等縣市停車資料來源拆到 `line-bot/api/modules/parking_city_sources.py`。
- 將 `line-bot/api/modules/parking_sources.py` 收斂為多來源停車資料聚合入口，並保留原有來源函式匯出相容性。
- 將新北路外與路邊停車資料來源拆到 `line-bot/api/modules/parking_ntpc_sources.py`。
- 將台南、新竹、桃園停車資料來源拆到 `line-bot/api/modules/parking_local_sources.py`。
- 將 `line-bot/api/modules/parking_city_sources.py` 收斂為城市停車來源相容匯出入口。
- 將 3C 產品資料載入、預算/裝置/用途解析、產品過濾與規格文字整理拆到 `line-bot/api/modules/tech_product_data.py`。
- 將 3C 產品 Flex 卡片與購物/分享 footer 拆到 `line-bot/api/modules/tech_product_cards.py`。
- 將 3C 產品適配檢查與規格檢查清單拆到 `line-bot/api/modules/tech_product_suitability.py`。
- 將 `line-bot/api/modules/tech_products.py` 收斂為產品推薦路由與相容匯出入口。
- 將 3C 硬體升級的 RAM/SSD/GPU/效能檢查卡片拆到 `line-bot/api/modules/tech_upgrade_cards.py`，讓 `tech_upgrade.py` 保留選單與 router。
- 擴充 `line-bot/verify_core.py`，加入 RAM/SSD/GPU/效能檢查升級卡片 smoke test。
- 將花費決策的刷卡/超支輔助卡片拆到 `line-bot/api/modules/money_spending_cards.py`。
- 將花費決策的商品行情規則與品項匹配拆到 `line-bot/api/modules/money_spending_logic.py`。
- 將 `line-bot/api/modules/money_spending.py` 收斂為主要消費決策訊息 builder。
- 維持所有核心檔案可編譯。

### 目前核心檔案

- `line-bot/api/webhook.py`: LINE webhook 入口與主路由協調。
- `line-bot/api/handlers/static_messages.py`: 固定文字/靜態訊息。
- `line-bot/api/handlers/text_routes.py`: 文字路由輔助。
- `line-bot/api/handlers/precise_text_routes.py`: 精準文字指令。
- `line-bot/api/handlers/wizard_routes.py`: 多步驟狀態流程。
- `line-bot/api/handlers/intent_routes.py`: intent dispatch。
- `line-bot/api/handlers/fallback_routes.py`: fallback 與裝置預算推薦。
- `line-bot/api/handlers/feedback_routes.py`: 回報與建議。
- `line-bot/api/modules/food.py`: 美食功能主邏輯。
- `line-bot/api/modules/food_utils.py`: 美食功能共用工具。
- `line-bot/api/modules/food_group_dining.py`: 多人聚餐城市/類型/結果卡片。
- `line-bot/api/modules/food_menu_builders.py`: 今天吃什麼選單與地區/城市選擇卡片。
- `line-bot/api/modules/food_specialties.py`: 地方特色小吃與特色名店搜尋卡片。
- `line-bot/api/modules/food_bib_gourmand.py`: 必比登推薦卡片。
- `line-bot/api/modules/food_restaurants.py`: Google Places 搜尋、餐廳照片 URL、餐廳 bubble、在地餐廳推薦卡片。
- `line-bot/api/modules/food_recommendations.py`: 一般食物推薦卡與時段/季節過濾。
- `line-bot/api/modules/food_events.py`: Accupass 美食活動卡片。
- `line-bot/api/modules/food_router.py`: 今天吃什麼文字主路由。
- `line-bot/api/modules/food_data.py`: 美食 fallback 資料、必比登資料、城市特色資料與地區資料。
- `line-bot/api/modules/food_runtime.py`: 美食功能環境設定、快取、天氣季節判斷與使用者城市狀態。
- `line-bot/api/modules/weather.py`: 天氣主功能入口，目前保留 API/快取與主要 Flex builder。
- `line-bot/api/modules/weather_pickers.py`: 天氣地區/城市 picker 與早安城市 picker。
- `line-bot/api/modules/weather_advice.py`: 天氣圖示、穿搭建議與 UV 估算。
- `line-bot/api/modules/weather_morning_helpers.py`: 早安摘要的每日選取邏輯。
- `line-bot/api/modules/weather_cache.py`: 天氣相關 JSON cache lazy loaders。
- `line-bot/api/modules/weather_fetchers.py`: CWA、AQI、油價與匯率外部資料抓取。
- `line-bot/api/modules/weather_flex.py`: 一般天氣 Flex 卡片。
- `line-bot/api/modules/weather_morning_summary.py`: 早安摘要 Flex 卡片。
- `line-bot/api/modules/weather_morning_data.py`: 早安摘要靜態資料池。
- `line-bot/api/modules/parking.py`: 停車功能入口，目前保留各城市資料整合與 Flex builder。
- `line-bot/api/modules/parking_geo.py`: 停車地理計算與座標轉換。
- `line-bot/api/modules/parking_tdx.py`: TDX token/API 與停車結果快取輔助。
- `line-bot/api/modules/parking_food.py`: 停車後附近美食推薦與餐廳 bubble。
- `line-bot/api/modules/parking_flex.py`: 停車主 Flex 卡片。
- `line-bot/api/modules/parking_sources.py`: 各縣市停車資料來源與多來源整合。
- `line-bot/api/modules/parking_tdx_sources.py`: TDX 與宜蘭停車資料來源。
- `line-bot/api/modules/parking_city_sources.py`: 新北、台南、新竹、桃園停車資料來源。
- `line-bot/api/modules/parking_ntpc_sources.py`: 新北路外與路邊停車資料來源。
- `line-bot/api/modules/parking_local_sources.py`: 台南、新竹、桃園停車資料來源。
- `line-bot/api/modules/tech.py`: 3C 選購相容匯出入口。
- `line-bot/api/modules/tech_wizard.py`: 3C 選購問卷與情境推薦選單。
- `line-bot/api/modules/tech_upgrade.py`: 硬體升級諮詢卡片與路由。
- `line-bot/api/modules/tech_upgrade_cards.py`: RAM/SSD/GPU/效能檢查升級卡片。
- `line-bot/api/modules/tech_guides.py`: 3C 規格解釋、選購指南與比價搜尋卡片。
- `line-bot/api/modules/tech_products.py`: 3C 產品資料、推薦卡片與適配檢查。
- `line-bot/api/modules/tech_product_data.py`: 3C 產品資料載入、文字解析與過濾。
- `line-bot/api/modules/tech_product_cards.py`: 3C 產品 Flex 卡片。
- `line-bot/api/modules/tech_product_suitability.py`: 3C 產品適配檢查卡片。
- `line-bot/api/modules/money.py`: 理財功能相容入口與主路由。
- `line-bot/api/modules/money_credit_cards.py`: 信用卡優惠選單與推薦結果。
- `line-bot/api/modules/money_rates.py`: 油價與匯率查詢。
- `line-bot/api/modules/money_spending.py`: 花費決策與超支提醒卡片。
- `line-bot/api/modules/money_spending_cards.py`: 花費決策輔助卡片。
- `line-bot/api/modules/money_spending_logic.py`: 花費決策商品行情規則與匹配。
- `line-bot/api/modules/activity.py`: 活動功能主路由入口。
- `line-bot/api/modules/activity_utils.py`: 活動 cache、日期、地圖與用戶城市 helper。
- `line-bot/api/modules/activity_pickers.py`: 活動選單、區域 picker 與城市 picker。
- `line-bot/api/modules/activity_data.py`: 活動靜態 fallback 資料。
- `line-bot/api/modules/activity_flex.py`: 活動 Flex 卡片 builder。
- `line-bot/api/modules/health.py`: 健康功能主路由入口。
- `line-bot/api/modules/health_basic.py`: BMI、水分、睡眠、飲食、壓力等基本健康建議。
- `line-bot/api/modules/health_nutrition.py`: 熱量與運動消耗查詢。
- `line-bot/api/modules/health_mood.py`: 心情支持卡片。
- `line-bot/api/modules/safety.py`: 安全工具相容匯出入口。
- `line-bot/api/modules/safety_fraud.py`: 詐騙分析與反詐騙卡片。
- `line-bot/api/modules/safety_legal.py`: 法律常識指南與 QA 卡片。
- `line-bot/api/modules/safety_menu.py`: 安全工具總選單。

### 驗證

已執行：

```powershell
python -m py_compile line-bot\api\webhook.py line-bot\api\modules\food.py line-bot\api\modules\food_utils.py
python line-bot\verify_core.py
```

並針對 `line-bot/api/modules/*.py`、`line-bot/api/handlers/*.py`、`line-bot/api/webhook.py` 做整批編譯檢查。

### 後續建議

- 繼續拆 `food.py` 的餐廳推薦、地區選擇、多人聚餐三大區塊。
- 將正式主線外的歷史副本依 `ARCHIVE_PLAN.md` 封存。
- 安裝或修復本機 `git` 指令後，再做版本差異檢查與提交。
