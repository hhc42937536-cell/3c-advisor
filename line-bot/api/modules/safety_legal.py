"""Legal guide Flex builders for safety tools."""

from __future__ import annotations


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
                        {"type": "separator", "margin": "md"},
                        {"type": "text", "text": "⚠️ 以上為基本方向，實際情況請洽法律扶助基金會（412-8518）或律師",
                         "size": "xs", "color": "#888888", "wrap": True, "margin": "md"},
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
