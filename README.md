# 生活優轉 Workspace

這個工作區目前不是單一乾淨 repo，而是「正式主線 + 多份歷史副本 + 工具工作樹」的集合。

## 正式主線

目前建議視為正式主線的專案是：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot`

理由：

- 目錄命名清楚，非隨機名稱
- 具備完整部署結構：`api/`、`vercel.json`、`pyproject.toml`
- 有主要功能模組、工具模組、資料檔與測試腳本
- 是目前最像正式營運版本的資料夾

## 這個專案在做什麼

`line-bot` 是一個部署在 Vercel 的 Python LINE Bot，主要提供：

- 美食推薦
- 停車查詢
- 天氣資訊
- 健康小工具
- 理財建議
- 活動推薦
- 3C 推薦
- 防詐與法律資訊

核心入口：

- `H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\webhook.py`

## 架構摘要

```text
LINE User
  -> LINE Messaging API
  -> Vercel Python webhook
  -> intent/router logic
  -> feature modules
  -> Redis / Supabase / Google Places / TDX / CWA
  -> LINE reply / push
```

重要程式位置：

- Webhook 入口：`H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\webhook.py`
- 功能模組：`H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\modules`
- 共用工具：`H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\utils`
- 靜態資料：`H:\我的雲端硬碟\開發軟體\生活優轉\line-bot\api\data`
- 根目錄商品抓取：`H:\我的雲端硬碟\開發軟體\生活優轉\fetch_products.py`

## 文件導覽

- 工作區分析：`H:\我的雲端硬碟\開發軟體\生活優轉\WORKSPACE_MAP.md`
- 封存策略：`H:\我的雲端硬碟\開發軟體\生活優轉\ARCHIVE_PLAN.md`

## 目前建議

1. 將 `line-bot` 明定為唯一正式主線
2. 將隨機命名資料夾視為歷史副本或實驗版
3. 所有新功能優先回到 `line-bot`
4. 逐步拆分 `api/webhook.py` 與 `api/modules/food.py`
