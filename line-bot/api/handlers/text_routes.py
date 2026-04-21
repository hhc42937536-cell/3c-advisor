"""Helper routes for simple text-message dispatch."""

from __future__ import annotations


def route_static_text_sections(
    text: str,
    text_lower: str,
    user_id: str,
    *,
    build_welcome_message,
    log_usage,
    build_mood_support,
    build_scenario_menu,
    build_spec_explainer,
    build_purchase_guide_message,
    build_spending_decision,
    build_compare_price_message,
):
    """Handle simple keyword-driven text routes before precise flows."""
    greetings = ["你好", "嗨", "hi", "hello", "哈囉", "安安", "開始", "幫助", "help", "選單", "功能"]
    if any(text_lower == g or text_lower.startswith(g) for g in greetings):
        return build_welcome_message()

    mood_keywords = [
        "心情不好", "心情差", "好煩", "煩死", "煩透了", "超煩",
        "好累", "累死", "累透了", "超累", "好疲憊", "疲憊",
        "難過", "不開心", "很鬱悶", "鬱悶", "低落", "很喪",
        "不想出門", "不想動", "沒動力", "提不起勁",
        "無聊死", "好無聊", "超無聊", "不知道幹嘛", "沒事幹",
        "焦慮", "壓力大", "壓力好大", "很有壓力", "喘不過氣",
        "沒目標", "沒有目標", "人生沒目標", "不知道目標",
        "什麼都不想做", "甚麼都不想做", "什麼都不想", "甚麼都不想",
        "活著沒意思", "沒意思", "沒意義", "人生無聊", "迷茫", "迷失",
        "被罵", "被念", "被嗆", "被兇", "被罵慘", "被罵死",
        "吵架", "吵起來", "跟他吵", "跟她吵", "又吵", "大吵",
        "被說", "被批評", "被否定", "被嫌", "被討厭",
        "被欺負", "被霸凌", "被排擠", "被孤立", "沒有朋友",
        "考不好", "考差了", "成績差", "成績不好", "考砸了", "被當掉",
        "被老師罵", "老師罵我", "作業寫不完", "功課好難", "不想上學",
        "讀書好累", "唸書好累", "考試壓力",
    ]
    if any(w in text for w in mood_keywords):
        log_usage(user_id, "mood_support")
        return build_mood_support(text)

    if any(w in text for w in ["情境推薦", "不知道", "幫我選", "給誰用", "哪種適合"]):
        return build_scenario_menu()

    if any(w in text for w in [
        "看懂規格", "規格", "處理器", "記憶體", "儲存", "螢幕", "電池",
        "cpu", "ram", "ssd", "oled", "hz", "mah", "什麼意思", "看不懂",
    ]):
        return build_spec_explainer(text)

    if any(w in text for w in ["購買指南", "購買須知", "買之前", "注意事項", "怎麼買"]):
        return build_purchase_guide_message()

    spend_keywords = [
        "划算嗎", "划算", "值得買嗎", "值得買", "要買嗎", "該買嗎", "值得嗎",
        "貴嗎", "太貴嗎", "消費決策", "信用卡還是現金", "刷卡還是現金",
        "刷卡或現金", "要不要買", "可以買嗎", "買得起嗎",
    ]
    spend_items = [
        "手機", "筆電", "平板", "電視", "冷氣", "冰箱", "洗衣機",
        "耳機", "相機", "沙發", "包包", "課程", "保險",
        "iphone", "ipad", "macbook",
    ]
    has_amount = any(ch.isdigit() for ch in text)
    if any(w in text_lower for w in spend_keywords) or (any(w in text_lower for w in spend_items) and has_amount):
        return build_spending_decision(text)

    if any(w in text for w in ["比價", "最便宜", "哪裡買便宜", "價格比較", "biggo", "飛比"]):
        return build_compare_price_message(text)

    return None
