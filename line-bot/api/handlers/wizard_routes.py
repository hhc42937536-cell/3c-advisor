"""3C 購買問卷（Wizard）狀態路由"""

from __future__ import annotations


def route_wizard_state(
    text: str,
    *,
    parse_wizard_state,
    build_recommendation_message,
    build_wizard_budget,
    build_wizard_use,
    build_wizard_who,
) -> list | None:
    """解析問卷狀態字串，回傳對應訊息；無匹配回傳 None"""
    state = parse_wizard_state(text)
    if not state:
        return None

    device_name = state["device_name"]

    if "budget" in state:
        who = state.get("who", "自己")
        use = state.get("use", "日常")
        budget = state["budget"]
        use_map = {
            "拍照": ["拍照"], "遊戲": ["遊戲"], "追劇": ["追劇"],
            "工作": ["工作"], "學習": ["學生"], "創作": ["創作"],
            "日常": ["日常"], "閱讀": ["閱讀"],
        }
        uses = use_map.get(use, [])
        if who == "長輩":
            uses.append("長輩")
        elif who == "學生":
            uses.append("學生")
        msgs = build_recommendation_message(state["device"], budget, uses)
        who_label = {"自己": "你", "長輩": "長輩", "學生": "學生", "小孩": "小孩"}.get(who, who)
        use_label = {
            "日常": "日常使用", "拍照": "拍照攝影", "遊戲": "玩遊戲",
            "追劇": "追劇看片", "學習": "學校作業", "工作": "工作文書",
            "創作": "影片剪輯", "閱讀": "閱讀電子書",
        }.get(use, use)
        budget_text = "不限預算" if budget >= 999999 else f"NT${budget:,} 以內"
        intro = {"type": "text",
                 "text": f"根據你的需求幫你找到最適合的 {device_name} 👇\n\n"
                         f"👤 使用者：{who_label}\n"
                         f"🎯 主要用途：{use_label}\n"
                         f"💰 預算：{budget_text}"}
        return [intro] + msgs

    if "use" in state:
        return build_wizard_budget(device_name, state["who"], state["use"])
    if "who" in state:
        return build_wizard_use(device_name, state["who"])
    return build_wizard_who(device_name)
