# Workspace Map

## 總覽

工作區 `H:\我的雲端硬碟\開發軟體\生活優轉` 目前包含三種類型內容：

1. 正式主線專案
2. 歷史副本 / 平行實驗目錄
3. 工具與自動化資產

## 1. 正式主線專案

### `line-bot`

建議作為唯一正式主線。

關鍵檔案：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\webhook.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\food.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\weather.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\verify_core.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\vercel.json`
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\pyproject.toml`

主要責任：

- LINE webhook
- 功能路由
- API 整合
- 快取與紀錄
- Rich menu / deploy / self-test

### 功能模組地圖

目前 `line-bot/api/modules` 已經重構為「薄入口 + 子模組」模式。

主要入口：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\food.py`: 美食相容入口與依賴注入。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\weather.py`: 天氣入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking.py`: 停車入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\activity.py`: 活動入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\money.py`: 理財入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\health.py`: 健康入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\safety.py`: 安全工具入口。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\tech.py`: 3C 相容入口。

資料/大型靜態內容：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\food_data.py`: 美食 fallback、必比登、城市特色與地區資料。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\weather_morning_data.py`: 早安摘要靜態資料。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\activity_data.py`: 活動 fallback 資料。

外部 API / runtime / source 類：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\food_runtime.py`: 美食環境設定、cache、天氣季節與使用者城市狀態。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\weather_fetchers.py`: 天氣、AQI、油價、匯率 fetchers。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking_sources.py`: 停車多來源聚合。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking_tdx_sources.py`: TDX/宜蘭停車來源。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking_ntpc_sources.py`: 新北停車來源。
- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules\parking_local_sources.py`: 台南、新竹、桃園停車來源。

目前建議不要再拆的類型：

- 純資料檔，例如 `food_data.py`、`weather_morning_data.py`。
- 單一 Flex builder 檔，除非超過約 400 行且內部有明確重複邏輯。
- 相容匯出入口，例如 `tech_products.py`、`parking_city_sources.py`。

### 驗證方式

快速核心驗證：

```powershell
python line-bot\verify_core.py
```

目前驗證範圍：

- 編譯 `line-bot/api/webhook.py`
- 編譯 `line-bot/api/handlers/*.py`
- 編譯 `line-bot/api/modules/*.py`
- smoke test feedback、food、weather、parking、money、activity、health、safety、tech 主要 builder/router。

## 2. 根目錄資料與自動化

### 商品資料流

- `H:\我的雲端硬碟\開發軟體\生活優轉\fetch_products.py`
- `H:\我的雲端硬碟\開發軟體\生活優轉\products.json`
- `H:\我的雲端硬碟\開發軟體\生活優轉\products_db.json`

用途：

- 從 PChome 類型來源抓取 3C 商品資料
- 供 3C 推薦功能或前期資料處理使用

### GitHub Actions

- `H:\我的雲端硬碟\開發軟體\生活優轉\.github\workflows\update-products.yml`
- `H:\我的雲端硬碟\開發軟體\生活優轉\.github\workflows\update-activities.yml`
- `H:\我的雲端硬碟\開發軟體\生活優轉\.github\workflows\update-surprises.yml`
- `H:\我的雲端硬碟\開發軟體\生活優轉\.github\workflows\warm_cache.yml`
- `H:\我的雲端硬碟\開發軟體\生活優轉\.github\workflows\auto-merge-to-main.yml`

## 3. 歷史副本 / 平行實驗目錄

這些資料夾高度疑似為不同階段的複製版或實驗版：

- `H:\我的雲端硬碟\開發軟體\生活優轉\happy-dirac-568d21`
- `H:\我的雲端硬碟\開發軟體\生活優轉\adoring-mayer-c713ee`
- `H:\我的雲端硬碟\開發軟體\生活優轉\ecstatic-tharp-b05dec`
- `H:\我的雲端硬碟\開發軟體\生活優轉\pedantic-wilbur-934ea2`
- `H:\我的雲端硬碟\開發軟體\生活優轉\reverent-keller-b430cf`
- `H:\我的雲端硬碟\開發軟體\生活優轉\frosty-darwin-7b1b8b`
- `H:\我的雲端硬碟\開發軟體\生活優轉\priceless-dhawan-17f2db`
- `H:\我的雲端硬碟\開發軟體\生活優轉\upbeat-yonath-c81b8d`
- `H:\我的雲端硬碟\開發軟體\生活優轉\competent-sinoussi-140e16`
- `H:\我的雲端硬碟\開發軟體\生活優轉\silly-cartwright-74a91b`

判定理由：

- 目錄內容高度重複
- 皆有完整子專案複本
- 命名呈現工作樹/分支暱稱風格

其中 `H:\我的雲端硬碟\開發軟體\生活優轉\silly-cartwright-74a91b` 看起來像較新的實驗版本，因為最後修改時間最新。

## 4. 工具工作樹

### `.claude`

`H:\我的雲端硬碟\開發軟體\生活優轉\.claude`

用途：

- 本地工具設定
- worktrees
- 排程/啟動設定

這不是正式產品程式來源，應視為工具資產。

## 5. 目前主要風險

- 歷史副本過多，容易改錯位置
- 測試仍以 smoke script 為主，尚未形成完整 pytest/CI 回歸測試制度
- 工作區層級混放主線與歷史目錄，不利交接
- 部分大型檔案其實是純資料或單一 Flex builder，繼續拆分收益有限

## 6. 收斂建議

目前不建議再做無限拆分。

較有價值的後續工作：

1. 將 `line-bot\verify_core.py` 納入部署前檢查或 CI。
2. 依 `ARCHIVE_PLAN.md` 封存歷史副本，避免改錯專案。
3. 若本機修好 `git`，先建立重構提交點。
4. 針對高風險功能補更具體測試，例如停車 API fallback、food router 指令解析、weather 外部資料失敗 fallback。
