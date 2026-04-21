"""Fraud detection and anti-scam Flex builders."""

from __future__ import annotations

import json as _json
import os as _os


def _load_fraud_data() -> dict:
    path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data", "fraud_patterns.json")
    try:
        with open(path, encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {"patterns": [], "trends": []}


_FRAUD_DATA = _load_fraud_data()


FRAUD_PATTERNS: list[tuple[list[str], int, str]] = [
    (p["keywords"], p["points"], p["label"]) for p in _FRAUD_DATA.get("patterns", [])
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


_FRAUD_TRENDS: list[dict] = _FRAUD_DATA.get("trends", [])


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
