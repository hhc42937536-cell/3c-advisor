"""Spending decision parsing rules and category helpers."""

from __future__ import annotations


ITEM_RANGES = [
    (["電視", "tv", "液晶"], 3000, 60000, "電視", None),
    (["iphone", "手機", "android", "三星", "samsung", "pixel", "小米"], 5000, 50000, "手機", "推薦手機"),
    (["筆電", "laptop", "macbook", "電腦", "notebook"], 15000, 80000, "筆電", "推薦筆電"),
    (["ipad", "平板", "tablet"], 5000, 40000, "平板", "推薦平板"),
    (["airpods", "耳機"], 500, 15000, "耳機", None),
    (["冷氣", "冰箱", "洗衣機", "烘衣機"], 10000, 80000, "大家電", None),
    (["沙發", "床", "書桌", "椅子", "家具"], 3000, 50000, "家具", None),
    (["包包", "皮包", "名牌包"], 1000, 30000, "包包", None),
    (["球鞋", "運動鞋", "鞋"], 500, 15000, "鞋子", None),
    (["外套", "衣服", "上衣", "褲"], 300, 8000, "衣物", None),
    (["火鍋", "燒肉", "牛排", "壽司", "餐廳", "吃飯", "料理"], 100, 800, "餐飲（每人）", None),
    (["咖啡", "飲料", "下午茶"], 50, 300, "飲品", None),
    (["機票", "飯店", "住宿", "旅遊"], 3000, 50000, "旅遊", None),
    (["課程", "線上課", "補習"], 500, 30000, "課程", None),
    (["保險"], 3000, 30000, "年繳保險", None),
]


def match_spending_item(text: str):
    text_lower = text.lower()
    for keywords, low, high, label, rec_cmd in ITEM_RANGES:
        if any(keyword in text_lower for keyword in keywords):
            return low, high, label, rec_cmd
    return None, None, None, None
