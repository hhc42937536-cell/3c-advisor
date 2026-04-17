"""
modules/safety.py — 防詐辨識 & 法律常識 & 工具選單模組
包含：
  - FRAUD_PATTERNS 詐騙關鍵字資料庫（2025-2026）
  - analyze_fraud()          文字詐騙風險評分
  - build_fraud_intro()      防詐辨識引導介面
  - build_fraud_trends()     最新詐騙手法 TOP 8
  - build_fraud_result()     詐騙分析結果 Flex
  - LEGAL_QA                 法律問答資料庫
  - build_legal_guide_intro() 法律常識入口
  - build_legal_answer()     特定法律主題說明
  - build_tools_menu()       所有功能磚塊格選單
"""

from __future__ import annotations


# ════════════════════════════════════════════════
# 防詐辨識模組
# ════════════════════════════════════════════════

FRAUD_PATTERNS: list[tuple[list[str], int, str]] = [
    # ── 金錢操作 ──────────────────────────────────────────
    (["轉帳", "匯款", "解除分期", "ATM", "存款", "帳戶異常", "保證金", "手續費",
      "儲值", "點數卡", "禮物卡", "代墊", "墊付", "先付", "退款操作"], 2, "要求金錢操作"),

    # ── 投資詐騙 ──────────────────────────────────────────
    (["穩賺", "高報酬", "翻倍", "保本", "穩定獲利", "零風險", "日賺", "月入",
      "獲利截圖", "跟我操作", "內部消息", "飆股", "私募", "下單就賺"], 2, "高獲利誘惑"),

    # ── 中獎話術 ──────────────────────────────────────────
    (["你中獎", "恭喜獲得", "抽中", "得獎", "領獎", "幸運獲選",
      "恭喜您", "您已入選", "免費獲得", "獨家贈品"], 2, "中獎話術"),

    # ── 索取個資 ──────────────────────────────────────────
    (["身分證", "帳號密碼", "驗證碼", "個人資料", "銀行卡",
      "健保卡", "護照號碼", "戶籍謄本", "存摺封面", "網路銀行密碼"], 2, "索取個資"),

    # ── 假冒政府機關 ──────────────────────────────────────
    (["警察", "檢察官", "法院", "調查局", "金管會", "健保署", "國稅局", "刑事局",
      "內政部", "移民署", "海關", "地檢署", "廉政署", "洗錢防制"], 2, "假冒政府機關"),

    # ── 假冒身份 ──────────────────────────────────────────
    (["假冒", "冒充", "台灣電力", "台灣大哥大客服", "銀行客服",
      "LINE客服", "Meta客服", "蝦皮客服", "momo客服", "官方帳號",
      "平台客服", "賣家客服", "假帳號"], 2, "假冒身份"),

    # ── 製造緊迫感 ────────────────────────────────────────
    (["今天截止", "立即處理", "馬上", "限時", "24小時", "緊急通知",
      "帳號將被停用", "今日最後", "逾期將", "即將凍結", "請立即"], 1, "製造緊迫感"),

    # ── 引導點擊加群 ──────────────────────────────────────
    (["點擊連結", "掃描QR", "下載APP", "點此", "加好友", "加入群組",
      "加LINE", "加我好友", "私訊我", "加入頻道", "進群"], 1, "引導點擊或加群"),

    # ── 工作詐騙 ──────────────────────────────────────────
    (["在家工作", "輕鬆賺", "高薪兼職", "每天賺", "不用出門", "代購",
      "刷單", "養號", "按讚賺錢", "任務賺錢", "接單賺錢", "兼差"], 1, "工作詐騙誘餌"),

    # ── 投資話術 ──────────────────────────────────────────
    (["老師帶你", "跟著操作", "跟單", "投資群組", "帶單",
      "名師推薦", "大師預測", "AI選股", "量化交易", "跟單平台"], 1, "投資詐騙話術"),

    # ── 要求保密 ──────────────────────────────────────────
    (["不要告訴", "保密", "別讓家人知道", "私下處理", "不要聲張",
      "不要跟別人說", "這是秘密", "只有你知道"], 2, "要求保密"),

    # ── 境外金融 ──────────────────────────────────────────
    (["海外", "境外", "虛擬貨幣", "加密貨幣", "USDT", "比特幣",
      "以太幣", "幣安", "交易所", "冷錢包", "NFT投資"], 1, "境外金融操作"),

    # ── 情感詐騙（新增）──────────────────────────────────
    (["認識一下", "交個朋友", "緣分", "我很孤單", "異國戀",
      "外國人", "在台灣工作", "軍人", "工程師在海外", "我喜歡你"], 1, "情感詐騙話術"),

    # ── 假網拍詐騙（新增）────────────────────────────────
    (["私下交易", "面交", "不走平台", "直接匯款給我", "帳號被停權",
      "系統問題", "請直接轉帳", "跳過平台"], 2, "假網拍私下交易"),

    # ── AI換臉／深偽（新增）──────────────────────────────
    (["視訊驗證", "開鏡頭", "裸照", "私密影片", "截圖勒索",
      "散布影片", "付錢才不發出去"], 3, "勒索詐騙"),
]


def analyze_fraud(text: str) -> dict:
    """分析文字詐騙風險。

    回傳包含 score、risk（low/medium/high）、patterns 的字典。
    """
    score = 0
    patterns_found: list[str] = []
    for keywords, pts, label in FRAUD_PATTERNS:
        if any(kw in text for kw in keywords):
            score += pts
            patterns_found.append(label)
    if score >= 4:
        risk = "high"
    elif score >= 2:
        risk = "medium"
    else:
        risk = "low"
    return {"score": score, "risk": risk, "patterns": patterns_found}


def build_fraud_intro() -> list:
    """防詐辨識：引導用戶貼上可疑內容。"""
    return [{
        "type": "flex", "altText": "防詐辨識",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#C0392B",
                "contents": [
                    {"type": "text", "text": "🔍 防詐辨識", "color": "#FFFFFF",
                     "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "幫你分析可疑訊息是否為詐騙",
                     "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text",
                     "text": "📋 使用方式",
                     "size": "sm", "weight": "bold", "color": "#3E2723"},
                    {"type": "text",
                     "text": "把可疑的訊息、LINE 對話、簡訊內容\n複製後直接貼給我，我來幫你分析！",
                     "size": "sm", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "⚡ 常見詐騙類型", "size": "sm",
                     "weight": "bold", "color": "#3E2723", "margin": "md"},
                    {"type": "text",
                     "text": "• 假冒政府/銀行/電信客服\n• 投資高報酬誘惑\n• 假交友引導投資\n• 中獎詐騙\n• 工作詐騙（在家高薪）\n• 解除分期付款",
                     "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text",
                     "text": "⚠️ 記住：不管對方說什麼，先打 165 問！",
                     "size": "xs", "color": "#C0392B", "wrap": True, "weight": "bold"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#C0392B",
                     "action": {"type": "message", "label": "🚨 最新詐騙手法 TOP 8",
                                "text": "最新詐騙手法"}},
                    {"type": "button", "style": "primary", "color": "#E74C3C",
                     "action": {"type": "uri", "label": "📞 撥打 165 反詐專線",
                                "uri": "tel:165"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🔄 回主選單", "text": "你好"}},
                ]
            }
        }
    }]


# ── 2025-2026 最新詐騙手法（定期更新）──
_FRAUD_TRENDS = [
    {"rank": 1, "name": "假投資詐騙", "emoji": "📈",
     "desc": "假冒名人（黃仁勳、謝金河）邀加 LINE 群「飆股向前衝」，推薦虛擬貨幣/AI 基金，先小額獲利再騙大筆",
     "sign": "保證獲利、老師帶單、LINE 群組"},
    {"rank": 2, "name": "網路購物詐騙", "emoji": "🛒",
     "desc": "假冒蝦皮/momo 客服說要「解除分期付款」，引導到 ATM 操作或提供帳號密碼",
     "sign": "低於市價、限時限量、客服來電要求操作 ATM"},
    {"rank": 3, "name": "AI 深偽詐騙", "emoji": "🤖",
     "desc": "用 AI 換臉/變聲假冒親友視訊通話，騙你匯款救急。2026 年暴增趨勢",
     "sign": "緊急借錢、視訊畫質異常、不願多聊"},
    {"rank": 4, "name": "愛情交友詐騙", "emoji": "💕",
     "desc": "交友 App 認識→培養感情→推薦投資平台。「養套殺」模式，跨平台操縱",
     "sign": "異國軍人/商人、很快示愛、引導到其他平台投資"},
    {"rank": 5, "name": "假冒公務機關", "emoji": "🏛️",
     "desc": "自稱警察/檢察官/健保局，說你涉案或個資外洩，要求轉帳到「安全帳戶」",
     "sign": "政府絕不會要求轉帳、+號開頭的電話"},
    {"rank": 6, "name": "求職打工詐騙", "emoji": "💼",
     "desc": "「在家輕鬆月入10萬」、代購代付、虛擬帳戶洗錢，你可能變成車手共犯",
     "sign": "高薪低門檻、要求提供帳戶、先墊款"},
    {"rank": 7, "name": "簡訊釣魚詐騙", "emoji": "📱",
     "desc": "假冒 ETC/郵局/稅務局發簡訊，附短網址要你「補繳費用」，騙取信用卡資料",
     "sign": "短網址、限時繳費、政府不會用簡訊催繳"},
    {"rank": 8, "name": "遊戲點數詐騙", "emoji": "🎮",
     "desc": "假冒遊戲客服或玩家，低價賣帳號/道具，付款後消失。或要求買點數卡抵債",
     "sign": "私下交易、要求購買點數卡、遊戲外溝通"},
]


def build_fraud_trends() -> list:
    """最新詐騙手法排行（2025-2026 TOP 8）。"""
    items = []
    for f in _FRAUD_TRENDS:
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{f['emoji']} #{f['rank']} {f['name']}",
                 "weight": "bold", "size": "sm", "color": "#C0392B", "flex": 4, "wrap": True},
            ]},
            {"type": "text", "text": f["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs", "maxLines": 3},
            {"type": "text", "text": f"⚠️ 特徵：{f['sign']}", "size": "xxs",
             "color": "#888888", "wrap": True, "margin": "xs"},
            {"type": "separator", "margin": "sm"},
        ]
    # Remove last separator
    if items and items[-1].get("type") == "separator":
        items.pop()

    return [{"type": "flex", "altText": "2025-2026 最新詐騙手法",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#C0392B",
                            "contents": [
                                {"type": "text", "text": "🚨 最新詐騙手法 TOP 8",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "2025-2026 警政署 165 彙整",
                                 "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "button", "style": "primary", "color": "#C0392B", "height": "sm",
                      "action": {"type": "uri", "label": "📞 撥打 165 反詐專線", "uri": "tel:165"}},
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": "🔍 我有可疑訊息要分析", "text": "防詐辨識"}},
                 ]},
             }}]


def build_fraud_result(text: str) -> list:
    """回傳詐騙風險分析結果 Flex 訊息。"""
    result = analyze_fraud(text)
    risk = result["risk"]
    patterns = result["patterns"]

    if risk == "high":
        header_color = "#C0392B"
        risk_emoji = "🚨"
        risk_title = "高度疑似詐騙！"
        risk_desc = "這則訊息含有多項詐騙特徵，請勿轉帳、提供個資或點擊任何連結！"
        action_text = "立即封鎖對方，並撥打 165 反詐騙專線舉報"
        btn_label = "🚨 立即撥打 165"
    elif risk == "medium":
        header_color = "#E67E22"
        risk_emoji = "⚠️"
        risk_title = "發現可疑特徵"
        risk_desc = "這則訊息有部分可疑跡象，請先向家人或親友確認，勿急著回應。"
        action_text = "不要急著採取行動，先冷靜向身邊的人確認"
        btn_label = "📞 撥打 165 諮詢"
    else:
        header_color = "#27AE60"
        risk_emoji = "✅"
        risk_title = "未發現明顯詐騙特徵"
        risk_desc = "目前未偵測到明顯詐騙跡象，但仍請保持警覺。"
        action_text = "如仍有疑慮，隨時可撥打 165 詢問"
        btn_label = "📞 撥打 165 確認"

    pattern_text = "、".join(patterns) if patterns else "無明顯特徵"
    short_text = text[:40] + "…" if len(text) > 40 else text

    return [{
        "type": "flex", "altText": f"{risk_emoji} 詐騙風險分析",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": header_color,
                "contents": [
                    {"type": "text", "text": f"{risk_emoji} {risk_title}",
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text", "text": f"分析內容：「{short_text}」",
                     "color": "#FFFFFFCC", "size": "xs", "wrap": True},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": [
                    {"type": "text", "text": risk_desc,
                     "size": "sm", "color": "#3E2723", "wrap": True, "weight": "bold"},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "🔎 偵測到的特徵",
                     "size": "xs", "weight": "bold", "color": "#8D6E63", "margin": "md"},
                    {"type": "text", "text": pattern_text,
                     "size": "xs", "color": "#5D4037", "wrap": True},
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": f"💡 建議：{action_text}",
                     "size": "xs", "color": "#5D4037", "wrap": True, "margin": "md"},
                    {"type": "text",
                     "text": "⚠️ 本工具僅供參考，無法取代專業判斷。有疑慮請撥 165。",
                     "size": "xs", "color": "#BBBBBB", "wrap": True, "margin": "md"},
                ]
            },
            "footer": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#C0392B",
                     "action": {"type": "uri", "label": btn_label, "uri": "tel:165"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🔍 再分析一則",
                                "text": "防詐辨識"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "uri", "label": "⚖️ 法律求助資訊",
                                "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                ]
            }
        }
    }]


# ════════════════════════════════════════════════
# 法律常識模組
# ════════════════════════════════════════════════

def build_legal_guide_intro() -> list:
    """法律常識入口 Flex 訊息。"""
    return [{
        "type": "flex", "altText": "法律常識小幫手",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1C2B4A",
                "contents": [
                    {"type": "text", "text": "⚖️ 法律常識小幫手", "color": "#FFFFFF",
                     "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "白話解釋你的法律權益",
                     "color": "#FFFFFFCC", "size": "sm"},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "常見問題，點一個開始：",
                     "size": "sm", "color": "#8D6E63"},
                    {"type": "button", "style": "secondary", "margin": "sm",
                     "action": {"type": "message", "label": "🏠 租屋糾紛怎麼辦？",
                                "text": "法律 租屋糾紛"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💼 被公司欠薪/違法解僱",
                                "text": "法律 勞資糾紛"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🛍️ 買到假貨/商品有問題",
                                "text": "法律 消費者保護"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "🚗 發生車禍怎麼處理",
                                "text": "法律 交通事故"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "💰 被詐騙了可以怎麼做",
                                "text": "法律 詐騙求助"}},
                    {"type": "button", "style": "secondary",
                     "action": {"type": "message", "label": "👨‍👩‍👧 離婚/家暴/監護權",
                                "text": "法律 家事"}},
                    {"type": "separator", "margin": "md"},
                    {"type": "button", "style": "primary", "color": "#1C2B4A",
                     "margin": "md",
                     "action": {"type": "uri", "label": "🌐 開啟完整法律常識網站",
                                "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                ]
            }
        }
    }]


LEGAL_QA: dict[str, dict[str, str]] = {
    "租屋糾紛": {
        "title": "🏠 租屋糾紛",
        "content": (
            "【房東不退押金】\n"
            "• 搬出前拍照存證（每個房間、每件家具）\n"
            "• 租約結束後 → 房東須於 30 天內退押金\n"
            "• 拒不退還 → 發存證信函，再提小額訴訟\n\n"
            "【房東突然漲租/趕人】\n"
            "• 租約期間內，房東不得任意漲租或趕人\n"
            "• 違反租約 → 可要求損害賠償\n\n"
            "【緊急求助】\n"
            "• 內政部租屋糾紛申訴：1999\n"
            "• 法律扶助基金會：412-8518"
        )
    },
    "勞資糾紛": {
        "title": "💼 勞資糾紛",
        "content": (
            "【被欠薪】\n"
            "• 保留薪資單、轉帳紀錄、通訊對話\n"
            "• 向勞工局申訴（免費，雇主壓力大）\n"
            "• 勞工局電話：1955\n\n"
            "【違法解僱】\n"
            "• 解僱須有法定事由，否則為違法\n"
            "• 可要求復職或資遣費補償\n"
            "• 年資每滿一年給 1 個月平均工資\n\n"
            "【加班費沒給】\n"
            "• 平日加班：前 2 小時 × 1.34 倍，之後 × 1.67 倍\n"
            "• 可申請勞動局調解"
        )
    },
    "消費者保護": {
        "title": "🛍️ 消費者保護",
        "content": (
            "【買到假貨/瑕疵品】\n"
            "• 網購：7 天內無條件退貨（猶豫期）\n"
            "• 實體購買：可依消保法要求修補、換貨或退款\n"
            "• 保留發票、對話紀錄、照片\n\n"
            "【商家不退款】\n"
            "• 先向消保官申訴：1950\n"
            "• 或向消費者保護委員會申訴\n\n"
            "【信用卡爭議】\n"
            "• 向發卡銀行申請「帳單爭議」\n"
            "• 銀行須在 30 天內回覆處理結果"
        )
    },
    "交通事故": {
        "title": "🚗 交通事故",
        "content": (
            "【現場處理】\n"
            "• 先確認人員安全，有傷亡立即撥 110/119\n"
            "• 拍照：車輛位置、損傷、現場環境\n"
            "• 交換資料：姓名、車牌、保險公司\n"
            "• 不要急著移車（除非造成交通危險）\n\n"
            "【理賠】\n"
            "• 強制險（傷亡）→ 對方保險公司\n"
            "• 第三責任險（財損）→ 視過失比例\n"
            "• 傷亡可申請強制險：醫療費最高 20 萬\n\n"
            "【對方逃逸】\n"
            "• 記車牌，立即報警，可申請犯罪被害補償"
        )
    },
    "詐騙求助": {
        "title": "💰 被詐騙了怎麼辦",
        "content": (
            "【已經轉帳了】\n"
            "1. 立即撥打 165，請求凍結帳戶\n"
            "2. 打給你的銀行，請求止付/攔截\n"
            "3. 到警察局報案（越快越好）\n"
            "4. 保留所有對話紀錄、交易紀錄\n\n"
            "【還沒轉帳，但對方一直催】\n"
            "• 立即封鎖對方\n"
            "• 撥打 165 確認是否詐騙\n\n"
            "【重要求助電話】\n"
            "• 165 反詐騙：24 小時\n"
            "• 警政署反詐騙官網：可線上舉報\n"
            "• 法律扶助基金會：412-8518"
        )
    },
    "家事": {
        "title": "👨‍👩‍👧 家事法律",
        "content": (
            "【離婚】\n"
            "• 協議離婚：兩人合意 + 2 位證人簽名\n"
            "• 訴訟離婚：須有法定事由（外遇、惡意遺棄等）\n\n"
            "【監護權】\n"
            "• 離婚後可協議或由法院判決\n"
            "• 法院以「子女最佳利益」為原則\n"
            "• 非監護方有探視權\n\n"
            "【家暴】\n"
            "• 撥打 113 家暴保護專線（24 小時）\n"
            "• 可申請保護令（禁止對方接近）\n"
            "• 到地方法院聲請，費用全免"
        )
    },
}


def build_legal_answer(topic: str) -> list:
    """回傳特定法律主題的說明 Flex 訊息。

    topic 對應 LEGAL_QA 的鍵（例如「租屋糾紛」），
    若找不到則 fallback 到 build_legal_guide_intro()。
    """
    qa = LEGAL_QA.get(topic)
    if not qa:
        return build_legal_guide_intro()
    return [
        {
            "type": "flex", "altText": qa["title"],
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": "#1C2B4A",
                    "contents": [
                        {"type": "text", "text": qa["title"], "color": "#FFFFFF",
                         "size": "lg", "weight": "bold"},
                        {"type": "text", "text": "以下為一般性說明，非正式法律意見",
                         "color": "#FFFFFFCC", "size": "xs"},
                    ]
                },
                "body": {
                    "type": "box", "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": qa["content"], "size": "sm",
                         "color": "#3E2723", "wrap": True},
                    ]
                },
                "footer": {
                    "type": "box", "layout": "vertical", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "color": "#1C2B4A",
                         "action": {"type": "uri", "label": "🌐 查看完整說明",
                                    "uri": "https://hhc42937536-cell.github.io/legal-guide/"}},
                        {"type": "button", "style": "secondary",
                         "action": {"type": "message", "label": "⚖️ 看其他法律主題",
                                    "text": "法律常識"}},
                    ]
                }
            }
        }
    ]


# ════════════════════════════════════════════════
# 工具選單
# ════════════════════════════════════════════════

def build_tools_menu() -> list:
    """生活工具箱選單 — 磚塊格版（4排×3格）。"""

    def _tile(
        icon: str, name: str, hint: str,
        color: str, light_bg: str, trigger: str
    ) -> dict:
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": light_bg,
            "cornerRadius": "12px",
            "paddingAll": "8px",
            "spacing": "xs",
            "action": {"type": "message", "label": name, "text": trigger},
            "contents": [
                {"type": "text", "text": icon, "size": "xxl", "align": "center"},
                {"type": "text", "text": name, "size": "xs", "weight": "bold",
                 "color": color, "align": "center", "margin": "xs"},
                {"type": "text", "text": hint, "size": "xxs",
                 "color": "#888888", "align": "center"},
            ]
        }

    def _row(tiles: list) -> dict:
        return {
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "margin": "sm", "contents": tiles
        }

    return [{
        "type": "flex", "altText": "🗃️ 所有功能",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                "contents": [
                    {"type": "text", "text": "🗃️ 所有功能",
                     "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                    {"type": "text",
                     "text": "點按鈕，或直接打字告訴我你需要什麼",
                     "color": "#8892B0", "size": "xs", "margin": "xs"},
                    {"type": "box", "layout": "horizontal", "spacing": "sm",
                     "margin": "md", "contents": [
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "天氣", "text": "天氣"},
                          "contents": [{"type": "text", "text": "打「天氣」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "好累", "text": "好累"},
                          "contents": [{"type": "text", "text": "打「好累」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                         {"type": "box", "layout": "vertical", "flex": 1,
                          "backgroundColor": "#FFFFFF18", "cornerRadius": "6px",
                          "paddingAll": "5px",
                          "action": {"type": "message", "label": "吃什麼", "text": "今天吃什麼"},
                          "contents": [{"type": "text", "text": "打「吃什麼」",
                                        "size": "xxs", "color": "#FFFFFFCC",
                                        "align": "center"}]},
                     ]},
                ]
            },
            "body": {
                "type": "box", "layout": "vertical",
                "spacing": "sm", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": "👇 點選功能，馬上開始",
                     "size": "xs", "color": "#777777", "margin": "xs"},
                    # Row 1
                    _row([
                        _tile("🍽️", "吃什麼",  "3秒決定",  "#BF360C", "#FFF0E6", "今天吃什麼"),
                        _tile("🌤️", "天氣",    "出門必看",  "#0277BD", "#E1F5FE", "天氣"),
                        _tile("🗓️", "近期活動", "週末去哪",  "#283593", "#ECEDFF", "近期活動"),
                    ]),
                    # Row 2
                    _row([
                        _tile("🍻", "聚餐地點", "選地點",   "#E65100", "#FFF3EE", "聚餐"),
                        _tile("🌿", "情緒支援", "說說看",   "#2E7D32", "#E8F5E9", "好累"),
                        _tile("🛡️", "防詐辨識", "貼訊息",   "#C62828", "#FFEBEE", "防詐辨識"),
                    ]),
                    # Row 3
                    _row([
                        _tile("⚖️", "法律常識", "應對方式", "#4527A0", "#EDE7F6", "法律常識"),
                        _tile("📱", "3C推薦",  "手機選購",  "#E64A00", "#FFF3EE", "推薦手機"),
                        _tile("💰", "比價",    "不花冤枉錢", "#00695C", "#E0F2F1", "比價"),
                    ]),
                    # Row 4
                    _row([
                        _tile("🤔", "消費決策", "值不值",   "#6A1B9A", "#F3E5F5", "消費決策"),
                        _tile("🔧", "硬體升級", "RAM/SSD", "#37474F", "#ECEFF1", "硬體升級"),
                        _tile("☀️", "早安",    "天氣+提醒", "#F57F17", "#FFFBEA", "早安"),
                    ]),
                    {"type": "separator", "margin": "md"},
                    # 底部小工具列
                    {
                        "type": "box", "layout": "horizontal",
                        "margin": "sm", "paddingTop": "4px",
                        "contents": [
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "許願", "text": "許願"},
                             "contents": [
                                 {"type": "text", "text": "💡", "align": "center", "size": "md"},
                                 {"type": "text", "text": "許願", "size": "xxs",
                                  "color": "#6C5CE7", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "回報", "text": "回報"},
                             "contents": [
                                 {"type": "text", "text": "📋", "align": "center", "size": "md"},
                                 {"type": "text", "text": "回報", "size": "xxs",
                                  "color": "#546E7A", "align": "center"},
                             ]},
                            {"type": "box", "flex": 1, "layout": "vertical",
                             "action": {"type": "message", "label": "選單", "text": "選單"},
                             "contents": [
                                 {"type": "text", "text": "🏠", "align": "center", "size": "md"},
                                 {"type": "text", "text": "回首頁", "size": "xxs",
                                  "color": "#555555", "align": "center"},
                             ]},
                        ]
                    }
                ]
            },
        }
    }]
