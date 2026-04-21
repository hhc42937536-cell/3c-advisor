"""Hardware-specific upgrade guidance cards."""

from __future__ import annotations


def build_upgrade_ram() -> list:
    """RAM 升級指南"""
    return [{"type": "flex", "altText": "💾 RAM 升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1565C0",
            "contents": [
                {"type": "text", "text": "💾 RAM 升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "什麼時候值得加 RAM？",
                 "color": "#BBDEFB", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "✅ 適合升級 RAM 的情況",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 多開視窗/分頁時電腦明顯變慢\n"
                     "• 工作管理員顯示 RAM 使用率 > 80%\n"
                     "• 同時用 Chrome + Office + Zoom 很卡\n"
                     "• 影片剪輯/設計軟體跑不動\n"
                     "• 遊戲時有明顯 Lag 或讀取卡頓"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "❌ 加 RAM 幫助不大的情況",
                 "weight": "bold", "size": "sm", "color": "#C62828"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• CPU 使用率長期 > 90%（瓶頸在 CPU）\n"
                     "• RAM 使用率正常但電腦還是很慢\n"
                     "  → 瓶頸可能是 HDD，換 SSD 比較有用\n"
                     "• 遊戲幀數低（瓶頸通常在 GPU）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📊 RAM 容量建議",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "8GB  → 勉強夠，日常瀏覽 OK\n"
                     "16GB → 主流標配，絕大多數使用者夠用 ✅\n"
                     "32GB → 剪片/設計/工程師推薦\n"
                     "64GB+ → 專業工作站等級"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 升級前請確認",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 主機板支援的 RAM 類型（DDR4 / DDR5）\n"
                     "② 主機板最大支援容量（查規格書）\n"
                     "③ 筆電確認插槽數量（部分焊死不可升級）\n"
                     "④ 雙通道效能 > 單條大容量（盡量成對插）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 CP 值最高選擇",
                 "weight": "bold", "size": "sm", "color": "#4527A0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "DDR4 16GB（8GB × 2）：約 NT$500-800\n"
                     "DDR5 16GB（8GB × 2）：約 NT$1,200-1,800\n"
                     "品牌推薦：Kingston / Crucial / G.Skill\n\n"
                     "⚠️ 筆電升級建議找原廠或有保固的店家安裝"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#1565C0", "height": "sm",
                 "action": {"type": "message", "label": "💿 換 SSD 更快嗎？", "text": "升級 SSD"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "📊 整機效能分析", "text": "電腦效能分析"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_ssd() -> list:
    """SSD 升級指南"""
    return [{"type": "flex", "altText": "💿 SSD 升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#1B5E20",
            "contents": [
                {"type": "text", "text": "💿 SSD 升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "最有感的升級！開機從 2 分鐘變 10 秒",
                 "color": "#C8E6C9", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🔥 HDD → SSD 效果最明顯",
                 "weight": "bold", "size": "sm", "color": "#1B5E20"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 開機速度：120 秒 → 10 秒\n"
                     "• 軟體載入：5-10 秒 → 1-2 秒\n"
                     "• 檔案複製：快 5-10 倍\n"
                     "• 整體「感覺」快非常多\n\n"
                     "👉 舊電腦還在用 HDD，換 SSD 比買新電腦划算！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📊 SSD 種類比較",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "SATA SSD（舊介面）\n"
                     "  速度 500 MB/s，便宜，適合替換舊 HDD\n\n"
                     "M.2 NVMe（新介面）✅ 推薦\n"
                     "  速度 3,000-7,000 MB/s，是 SATA 的 6-14 倍\n"
                     "  價格不貴，主流選擇\n\n"
                     "⚠️ 先確認主機板/筆電支援哪種介面！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 2026 年 CP 值推薦",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "500GB NVMe：約 NT$800-1,200（入門夠用）\n"
                     "1TB NVMe：約 NT$1,200-1,800 ✅ 最推薦\n"
                     "2TB NVMe：約 NT$2,000-3,000（創作者）\n\n"
                     "品牌推薦：Samsung 990 / WD SN770 / Crucial P3\n"
                     "避開：不知名小廠（壽命不穩定）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "📋 升級步驟",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 確認電腦支援的介面（SATA 或 M.2）\n"
                     "② 購買對應 SSD\n"
                     "③ 用「Macrium Reflect」免費軟體克隆硬碟\n"
                     "④ 換上 SSD，舊 HDD 可當外接硬碟用\n"
                     "⑤ 開機，直接享受 10 倍速！"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#1B5E20", "height": "sm",
                 "action": {"type": "message", "label": "💾 RAM 要加嗎？", "text": "升級 RAM"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_gpu() -> list:
    """GPU 顯卡升級指南"""
    return [{"type": "flex", "altText": "🎮 GPU 顯卡升級指南", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#4A148C",
            "contents": [
                {"type": "text", "text": "🎮 GPU 顯卡升級指南", "color": "#FFFFFF",
                 "size": "lg", "weight": "bold"},
                {"type": "text", "text": "遊戲/剪片/AI 運算的核心",
                 "color": "#CE93D8", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "✅ 適合升級 GPU 的情況",
                 "weight": "bold", "size": "sm", "color": "#4A148C"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "• 遊戲幀數不足 60fps（特效開低還是卡）\n"
                     "• 想玩 4K / 高畫質遊戲\n"
                     "• 影片剪輯/3D 渲染速度太慢\n"
                     "• 跑 AI / Stable Diffusion 本機模型\n"
                     "• 顯卡老舊（超過 5 年）"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "⚠️ 升級前要確認",
                 "weight": "bold", "size": "sm", "color": "#C62828"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 電源供應器（PSU）瓦數夠嗎？\n"
                     "   RTX 4070 建議 650W 以上\n"
                     "   RTX 4080/4090 建議 850W 以上\n"
                     "② 機殼能放下顯卡（長度/高度）？\n"
                     "③ CPU 不要太舊（否則 CPU 卡脖子）\n"
                     "④ 筆電：顯卡通常無法升級！"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💰 2026 年 GPU 推薦",
                 "weight": "bold", "size": "sm", "color": "#E65100"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "入門（1080p 遊戲）：\n"
                     "  RTX 4060 / RX 7600 — 約 NT$6,000-8,000\n\n"
                     "主流（1440p 遊戲 / 剪片）✅ 推薦：\n"
                     "  RTX 4070 Super — 約 NT$14,000-16,000\n\n"
                     "高階（4K / AI 運算）：\n"
                     "  RTX 4080 Super — 約 NT$28,000-33,000\n\n"
                     "二手市場：上一代 RTX 3080 性價比高"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 N 卡 vs A 卡怎麼選？",
                 "weight": "bold", "size": "sm", "color": "#1565C0"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "NVIDIA（RTX）：遊戲相容性好、DLSS 技術、\n"
                     "  AI/CUDA 支援佳 → 大多數人首選\n\n"
                     "AMD（RX）：同價位效能好，但 AI/串流軟體\n"
                     "  相容性稍差 → 純遊戲用戶可考慮"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#4A148C", "height": "sm",
                 "action": {"type": "message", "label": "📊 整機效能分析", "text": "電腦效能分析"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]


def build_upgrade_performance_check() -> list:
    """整機效能分析 — 找出瓶頸"""
    return [{"type": "flex", "altText": "📊 電腦效能分析", "contents": {
        "type": "bubble", "size": "mega",
        "header": {
            "type": "box", "layout": "vertical",
            "backgroundColor": "#37474F",
            "contents": [
                {"type": "text", "text": "📊 找出電腦真正的瓶頸",
                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                {"type": "text", "text": "打開工作管理員，1 分鐘診斷法",
                 "color": "#90A4AE", "size": "xs", "margin": "sm"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text", "text": "🖥️ 步驟：按 Ctrl+Shift+Esc",
                 "weight": "bold", "size": "sm", "color": "#37474F"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": "開啟工作管理員 → 點「效能」頁籤 → 在電腦最卡的時候查看各項使用率"},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "🔍 診斷結果解讀",
                 "weight": "bold", "size": "sm", "color": "#37474F"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "CPU 使用率 > 90%\n"
                     "→ 瓶頸在處理器，考慮換 CPU 或整機\n\n"
                     "RAM 使用率 > 80%（或「可用」< 1GB）\n"
                     "→ 瓶頸在記憶體，加 RAM 立即見效 ✅\n\n"
                     "磁碟使用率長期 100%\n"
                     "→ 瓶頸在 HDD，換 SSD 效果最明顯 ✅\n\n"
                     "GPU 使用率 > 95%（遊戲時）\n"
                     "→ 瓶頸在顯卡，升 GPU 才有用 ✅\n\n"
                     "全部都很低但還是很卡？\n"
                     "→ 可能是病毒、啟動程式太多、或系統問題"
                 )},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": "💡 免費優化先試試",
                 "weight": "bold", "size": "sm", "color": "#2E7D32"},
                {"type": "text", "size": "xs", "color": "#555555", "wrap": True,
                 "text": (
                     "① 工作管理員 → 啟動 → 停用不必要的程式\n"
                     "② 清除暫存（Win+R → 輸入 %temp% → 全刪）\n"
                     "③ 更新驅動程式（尤其是顯卡驅動）\n"
                     "④ 重灌系統（最乾淨但最耗時）\n\n"
                     "以上試過還是慢，再考慮硬體升級！"
                 )},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#1565C0", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "💾 加 RAM", "text": "升級 RAM"}},
                     {"type": "button", "style": "primary", "color": "#1B5E20", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "💿 換 SSD", "text": "升級 SSD"}},
                 ]},
                {"type": "button", "style": "primary", "color": "#4A148C", "height": "sm",
                 "action": {"type": "message", "label": "🎮 升顯卡", "text": "升級 GPU"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "← 升級選單", "text": "硬體升級"}},
            ]
        }
    }}]
