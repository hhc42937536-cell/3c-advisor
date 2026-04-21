"""Auxiliary spending decision cards."""

from __future__ import annotations


def _spend_card(amount: int = 0) -> list:
    installment = ""
    if amount >= 3000:
        m3  = int(amount / 3)
        m6  = int(amount / 6)
        m12 = int(amount / 12)
        installment = f"\n分期參考（0 利率）：\n• 3 期 ≈ 每月 NT${m3:,}\n• 6 期 ≈ 每月 NT${m6:,}\n• 12 期 ≈ 每月 NT${m12:,}"

    return [{"type": "flex", "altText": "刷卡還是付現？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#1A2D50"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💳 刷卡還是付現？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "這樣判斷最省錢",
                      "color": "#AABBDD", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "✅ 刷卡比較划算",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "• 有 1% 以上現金回饋\n• 有 0 利率分期（金額 > 3000）\n• 當月有滿額禮\n• 保固或購物保障較好",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "✅ 付現比較好",
                      "size": "sm", "weight": "bold", "color": "#C62828"},
                     {"type": "text",
                      "text": "• 夜市、攤販、傳統市場\n• 你容易忘繳卡費（循環利息 15%！）\n• 店家加收刷卡手續費\n• 這個月已超出預算",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     *([{"type": "separator", "margin": "sm"},
                        {"type": "text", "text": installment, "size": "sm",
                         "color": "#555555", "wrap": True}] if installment else []),
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "40+ 提醒：信用卡讓你月底才感受到痛苦。如果「不知道錢去哪了」，先付現 2 個月試試。",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "primary", "color": "#1A2D50",
                      "height": "sm",
                      "action": {"type": "message", "label": "💰 金錢小幫手",
                                 "text": "金錢小幫手"}},
                 ]},
             }}]


def _spend_overspent() -> list:
    return [{"type": "flex", "altText": "這週花太多怎麼辦？",
             "contents": {"type": "bubble",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "text", "text": "💸 這週花太多了？",
                      "color": "#FFFFFF", "size": "md", "weight": "bold"},
                     {"type": "text", "text": "不用焦慮，這樣處理",
                      "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                 ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": "40+ 最常見的三個超支陷阱",
                      "size": "sm", "weight": "bold", "color": "#333333"},
                     {"type": "text",
                      "text": "1️⃣ 外食＋飲料 — 每天多花 150 元，一個月就多 4500\n"
                              "2️⃣ 網購衝動 — 加購物車就忘記，月底一次扣\n"
                              "3️⃣ 訂閱服務 — 忘記取消的 Netflix/Spotify/健身房",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text", "text": "今天開始能做的 3 件事",
                      "size": "sm", "weight": "bold", "color": "#2E7D32"},
                     {"type": "text",
                      "text": "✅ 剩下這週改付現金，讓自己感受到「錢在減少」\n"
                              "✅ 把非必要消費延到下週再決定\n"
                              "✅ 今晚花 5 分鐘，把這週最大的 3 筆支出寫下來",
                      "size": "sm", "color": "#444444", "wrap": True, "margin": "xs"},
                     {"type": "separator", "margin": "sm"},
                     {"type": "text",
                      "text": "告訴我這週花最多的是什麼，我幫你分析值不值得 😊",
                      "size": "sm", "color": "#888888", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "看省錢小技巧",
                                     "text": "省錢建議"}},
                         {"type": "button", "style": "link", "flex": 1,
                          "height": "sm",
                          "action": {"type": "message", "label": "💰 金錢小幫手",
                                     "text": "金錢小幫手"}},
                     ]},
                 ]},
             }}]
