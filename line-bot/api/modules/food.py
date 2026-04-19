"""
食物相關功能模組
包含：今天吃什麼、聚餐推薦、必比登推介、城市特色小吃、餐廳回饋
"""

import json
import os
import re
import random as _random
import datetime
import urllib.parse
import urllib.request

# ── 外部工具（utils 模組）──
from utils.redis import redis_get as _redis_get, redis_set as _redis_set
from utils.line_api import push_message
from utils.google_places import nearby_places as _nearby_places

# ── 環境變數 ──
ADMIN_USER_ID        = os.environ.get("ADMIN_USER_ID", "")
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
CWA_API_KEY          = os.environ.get("CWA_API_KEY", "")

# ── 全台 22 縣市分區 ──
_AREA_REGIONS = {
    "北部":   ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部":   ["台中", "彰化", "南投", "雲林"],
    "南部":   ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}
_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]

# ── 氣象署城市對照表 ──
_CWA_CITY_MAP = {
    "台北": "臺北市", "台中": "臺中市", "台南": "臺南市", "高雄": "高雄市",
    "新北": "新北市", "桃園": "桃園市", "基隆": "基隆市",
    "新竹": "新竹縣", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "嘉義": "嘉義縣",
    "屏東": "屏東縣", "宜蘭": "宜蘭縣", "花蓮": "花蓮縣",
    "台東": "臺東縣", "澎湖": "澎湖縣", "金門": "金門縣", "連江": "連江縣",
}

# ─── 聚餐推薦資料 ─────────────────────────────────────────

_GROUP_DINING_CITIES = [
    "台北", "新北", "桃園", "新竹", "台中", "台南", "高雄", "其他"
]

_GROUP_DINING_TYPES = {
    "火鍋":   {"emoji": "🍲", "color": "#C62828", "note": "可分鍋、顧到每個人口味"},
    "燒肉":   {"emoji": "🥩", "color": "#BF360C", "note": "熱鬧氣氛最強、適合慶祝"},
    "日式":   {"emoji": "🍣", "color": "#1565C0", "note": "壽司/割烹/居酒屋皆宜"},
    "合菜台菜": {"emoji": "🥘", "color": "#2E7D32", "note": "大圓桌共享，長輩最愛"},
    "西式":   {"emoji": "🍽️", "color": "#4527A0", "note": "排餐/義式，正式感強"},
    "熱炒":   {"emoji": "🍺", "color": "#E65100", "note": "平價下酒、台味十足"},
    "港式飲茶": {"emoji": "🥟", "color": "#00838F", "note": "點心共享，假日家庭聚餐首選"},
    "海鮮餐廳": {"emoji": "🦞", "color": "#00695C", "note": "台灣海味，尾牙大桌必選"},
    "吃到飽":  {"emoji": "🍽️", "color": "#558B2F", "note": "不用點餐，公司/生日最省事"},
    "餐酒館":  {"emoji": "🍷", "color": "#6A1B9A", "note": "輕鬆不正式，年輕朋友聚會"},
    "不限":    {"emoji": "🍴", "color": "#455A64", "note": "幫我推薦最適合的"},
}

_GROUP_SEARCH_TEMPLATES = {
    "火鍋":     "{city} 火鍋 聚餐 推薦 包廂 高評價",
    "燒肉":     "{city} 燒肉 聚餐 推薦 包廂 高評價",
    "日式":     "{city} 日式料理 聚餐 推薦 包廂",
    "合菜台菜": "{city} 台菜 合菜 聚餐 推薦 大圓桌",
    "西式":     "{city} 西餐 排餐 聚餐 推薦 包廂",
    "熱炒":     "{city} 熱炒 海鮮 聚餐 推薦 高評價",
    "港式飲茶": "{city} 港式飲茶 早茶 聚餐 推薦",
    "海鮮餐廳": "{city} 海鮮餐廳 聚餐 推薦 高評價",
    "吃到飽":  "{city} 吃到飽 餐廳 聚餐 推薦",
    "餐酒館":  "{city} 餐酒館 bistro 聚餐 推薦",
    "不限":     "{city} 聚餐 推薦 包廂 高評價 必吃",
}

# ─── 今天吃什麼 ──────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_json(filename: str, default):
    """從 data/ 目錄讀取 JSON，失敗時回傳 default。"""
    try:
        with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as _f:
            return json.load(_f)
    except Exception:
        return default


# ── 食物關鍵字分類（入口觸發 + 分類解析共用）──
_STYLE_KEYWORDS: dict = _load_json("style_keywords.json", {})
if not _STYLE_KEYWORDS:
    _STYLE_KEYWORDS = {
    "便當": ["便當", "排骨", "雞腿", "控肉", "滷肉飯", "自助餐",
             "燒臘", "豬腳", "雞肉飯", "焢肉", "魯肉飯", "飯", "燒肉飯", "咖哩飯"],
    "麵食": ["麵", "拉麵", "牛肉麵", "乾麵", "河粉", "義大利",
             "鍋燒", "涼麵", "麵線", "切仔", "米粉", "粄條", "刀削", "餛飩", "炒麵",
             "擔仔麵", "陽春麵", "酸辣"],
    "小吃": ["小吃", "蚵仔", "臭豆腐", "肉圓", "鹽酥雞", "雞排", "滷味", "水餃", "鍋貼",
             "鹹水雞", "潤餅", "蔥油餅", "蔥抓餅", "大腸包小腸", "豬血糕", "碗粿",
             "米糕", "筒仔米糕", "麻糬", "地瓜球", "春捲", "炸物", "香腸",
             "關東煮", "雞蛋糕", "車輪餅", "紅豆餅", "章魚燒"],
    "火鍋": ["火鍋", "麻辣", "薑母鴨", "羊肉爐", "豆腐鍋",
             "涮涮鍋", "鍋物", "石頭鍋", "酸菜白肉", "牛奶鍋", "藥膳", "螃蟹鍋",
             "壽喜燒", "泡菜鍋", "麻油雞"],
    "日韓": ["日式", "日韓", "壽司", "丼飯", "韓式", "燒肉", "居酒屋", "咖哩",
             "生魚片", "定食", "韓式炸雞", "拌飯", "炸豬排", "天婦羅",
             "烏龍", "味噌", "鰻魚", "炸蝦", "石鍋", "部隊鍋", "年糕"],
    "早午餐": ["早午餐", "早餐", "蛋餅", "飯糰", "燒餅", "吐司", "三明治",
               "豆漿", "蘿蔔糕", "粥", "漢堡", "鬆餅", "可頌", "brunch",
               "法式吐司", "班尼迪克蛋", "歐姆蛋"],
    "飲料甜點": ["飲料", "甜點", "珍奶", "珍珠", "蛋糕", "咖啡", "豆花", "冰", "果汁", "奶茶",
                 "仙草", "愛玉", "抹茶", "冰淇淋", "芋圓", "手搖", "茶", "可可",
                 "鬆餅", "銅鑼燒", "甜湯", "紅豆湯", "花生湯", "湯圓"],
    "輕食": ["輕食", "沙拉", "健康", "低卡", "減脂", "清爽", "優格", "燕麥",
             "水煮餐", "蔬食", "素食", "無糖", "蛋白質", "健身餐", "貝果"],
}  # fallback
# 扁平化所有食物關鍵字（供入口觸發用）
# 排除太通用的短詞，避免誤觸（這些詞仍用於分類解析）
_FOOD_TRIGGER_SKIP = {"麵", "飯", "冰", "茶", "粥", "健康", "早餐", "清爽"}
_ALL_FOOD_KEYWORDS: set = set()
for _kws in _STYLE_KEYWORDS.values():
    _ALL_FOOD_KEYWORDS.update(w for w in _kws if w not in _FOOD_TRIGGER_SKIP)

_FOOD_DB: dict = _load_json("food_db.json", {})
if not _FOOD_DB:
    # m: "M"=早餐限定  "D"=午餐以後  "N"=晚餐消夜限定  ""=全天
    _FOOD_DB = {
    "便當": [
        {"name": "排骨便當", "desc": "炸得香脆大排骨，台式便當之王", "price": "~100–140元", "key": "排骨便當", "m": "D"},
        {"name": "雞腿便當", "desc": "滷雞腿或炸雞腿，便當店人氣王", "price": "~100–140元", "key": "雞腿便當", "m": "D"},
        {"name": "控肉飯", "desc": "油亮滷汁入口即化，淋白飯上超滿足", "price": "~80–130元", "key": "控肉飯", "m": "D"},
        {"name": "焢肉飯", "desc": "厚切五花肉滷到透亮，經典台式", "price": "~80–120元", "key": "焢肉飯", "m": "D"},
        {"name": "燒臘雙拼飯", "desc": "港式叉燒鴨配油飯，大份量", "price": "~100–150元", "key": "燒臘飯", "m": "D"},
        {"name": "自助餐", "desc": "自選菜色打包走，外食族日常主食", "price": "~75–120元", "key": "自助餐便當", "m": "D"},
        {"name": "豬腳飯", "desc": "滷豬腳膠質滿滿，配酸菜解膩", "price": "~100–150元", "key": "豬腳飯", "m": "D"},
        {"name": "雞肉飯", "desc": "嘉義式雞肉飯，油蔥雞汁超香", "price": "~40–70元", "key": "雞肉飯", "m": "D"},
        {"name": "滷肉飯", "desc": "台灣庶民之光，便宜飽足又療癒", "price": "~35–60元", "key": "滷肉飯", "m": "D"},
        {"name": "超商便當", "desc": "加熱90秒上桌，不用挑不用等", "price": "~55–90元", "key": "超商便當", "m": ""},
        {"name": "咖哩飯", "desc": "日式濃厚咖哩淋白飯，配福神漬超搭", "price": "~100–160元", "key": "咖哩飯", "m": "D"},
        {"name": "燒肉飯", "desc": "炭烤醬燒肉片鋪飯上，鹹香停不下來", "price": "~90–130元", "key": "燒肉飯", "m": "D"},
        {"name": "魯肉飯＋排骨湯", "desc": "滷肉飯加碗排骨湯，台灣人的日常奢華", "price": "~70–100元", "key": "魯肉飯", "m": "D"},
    ],
    "麵食": [
        {"name": "牛肉麵", "desc": "大塊牛腱＋濃郁湯底，台灣魂料理", "price": "~120–200元", "key": "牛肉麵", "m": "D"},
        {"name": "日式拉麵", "desc": "濃厚豚骨湯底，叉燒入口即化", "price": "~200–300元", "key": "拉麵", "m": "D"},
        {"name": "乾麵＋貢丸湯", "desc": "麵攤2分鐘上桌，台灣最快一餐", "price": "~60–85元", "key": "乾麵", "m": "D"},
        {"name": "鍋燒意麵", "desc": "魚板貢丸意麵，暖胃又滿足", "price": "~70–110元", "key": "鍋燒意麵", "m": "D"},
        {"name": "切仔麵", "desc": "湯清麵Q配黑白切，快又飽", "price": "~70–100元", "key": "切仔麵", "m": "D"},
        {"name": "義大利麵", "desc": "白醬紅醬青醬任選，簡餐店好選擇", "price": "~150–250元", "key": "義大利麵", "m": "D"},
        {"name": "涼麵", "desc": "夏天消暑首選，醬汁控制就很清爽", "price": "~60–80元", "key": "涼麵", "m": "D"},
        {"name": "蚵仔麵線", "desc": "滑溜麵線配大腸蚵仔，5分鐘吃完", "price": "~50–75元", "key": "蚵仔麵線", "m": "D"},
        {"name": "越南河粉", "desc": "清湯底蔬菜多，飽足感意外高", "price": "~100–140元", "key": "越南河粉", "m": "D"},
        {"name": "魚片湯麵", "desc": "清湯不油，腸胃弱也能吃", "price": "~100–130元", "key": "魚片湯麵", "m": "D"},
        {"name": "擔仔麵", "desc": "台南經典，肉燥蝦仁小碗精緻", "price": "~50–80元", "key": "擔仔麵", "m": "D"},
        {"name": "米粉湯", "desc": "清湯米粉配黑白切，台式速食", "price": "~40–70元", "key": "米粉湯", "m": "D"},
        {"name": "炒麵", "desc": "醬油炒麵加荷包蛋，簡單但超香", "price": "~50–80元", "key": "炒麵", "m": "D"},
        {"name": "餛飩湯麵", "desc": "薄皮大餡鮮肉餛飩，湯鮮麵Q", "price": "~70–100元", "key": "餛飩麵", "m": "D"},
        {"name": "刀削麵", "desc": "手削厚實麵條，嚼勁十足配牛肉", "price": "~100–150元", "key": "刀削麵", "m": "D"},
    ],
    "小吃": [
        {"name": "蚵仔煎", "desc": "鮮蚵配甜辣醬，夜市經典第一名", "price": "~60–80元", "key": "蚵仔煎", "m": "D"},
        {"name": "臭豆腐", "desc": "台灣魔力食物，聞著考驗吃著上癮", "price": "~60–100元", "key": "臭豆腐", "m": "D"},
        {"name": "肉圓", "desc": "蒸的炸的各有風味，一顆解饞", "price": "~40–60元", "key": "肉圓", "m": "D"},
        {"name": "鹽酥雞", "desc": "夜市靈魂，九層塔蒜頭辣粉缺一不可", "price": "~80–150元", "key": "鹽酥雞", "m": "N"},
        {"name": "雞排", "desc": "超大炸雞排，外酥內嫩一口咬下超爽", "price": "~70–90元", "key": "雞排", "m": "N"},
        {"name": "滷味", "desc": "夾了就走，雞腿海帶豆干自己配", "price": "~80–130元", "key": "滷味攤", "m": "N"},
        {"name": "水餃", "desc": "20顆水餃＋酸辣湯，10分鐘搞定", "price": "~65–90元", "key": "水餃店", "m": "D"},
        {"name": "鍋貼", "desc": "煎得金黃配蛋花湯，10分鐘飽足", "price": "~70–90元", "key": "鍋貼", "m": "D"},
        {"name": "割包", "desc": "台版漢堡，控肉花生粉酸菜", "price": "~50–80元", "key": "刈包", "m": "D"},
        {"name": "胡椒餅", "desc": "炭烤酥皮包蔥肉，排隊也值得", "price": "~50–60元", "key": "胡椒餅", "m": "D"},
        {"name": "肉粽", "desc": "南部粽北部粽，帶著走的飽足感", "price": "~35–60元", "key": "肉粽", "m": ""},
        {"name": "鹹水雞", "desc": "冰鎮雞肉配蒜蓉醬油，夏天必吃涼食", "price": "~80–150元", "key": "鹹水雞", "m": "N"},
        {"name": "潤餅", "desc": "薄皮包花生粉豆芽蛋酥，清明不限定", "price": "~50–70元", "key": "潤餅", "m": "D"},
        {"name": "蔥油餅", "desc": "煎到金黃酥脆，加蛋更邪惡", "price": "~30–50元", "key": "蔥油餅", "m": "D"},
        {"name": "大腸包小腸", "desc": "糯米腸夾香腸，夜市雙拼經典", "price": "~60–80元", "key": "大腸包小腸", "m": "N"},
        {"name": "豬血糕", "desc": "花生粉香菜醬油膏，外國人怕台灣人愛", "price": "~30–50元", "key": "豬血糕", "m": "D"},
        {"name": "碗粿", "desc": "軟嫩米漿蒸糕配醬油膏，南部經典", "price": "~30–50元", "key": "碗粿", "m": "D"},
        {"name": "筒仔米糕", "desc": "糯米蒸進竹筒，配甜辣醬超對味", "price": "~40–60元", "key": "筒仔米糕", "m": "D"},
        {"name": "地瓜球", "desc": "QQ彈彈炸地瓜球，越吃越涮嘴", "price": "~40–60元", "key": "地瓜球", "m": "D"},
        {"name": "關東煮", "desc": "蘿蔔竹輪魚板，暖呼呼一碗搞定", "price": "~50–80元", "key": "關東煮", "m": "D"},
        {"name": "車輪餅", "desc": "奶油紅豆芋頭，銅板甜點隨買隨吃", "price": "~15–25元", "key": "車輪餅", "m": "D"},
        {"name": "香腸", "desc": "烤得焦香配蒜頭，夜市散步必拿", "price": "~40–60元", "key": "烤香腸", "m": "N"},
    ],
    "火鍋": [
        {"name": "個人小火鍋", "desc": "一個人也能吃，湯底自選料夠多", "price": "~150–250元", "key": "個人小火鍋", "m": "D"},
        {"name": "麻辣鍋", "desc": "又麻又辣出一身汗，壓力全釋放", "price": "~300–500元", "key": "麻辣鍋", "m": "N"},
        {"name": "薑母鴨", "desc": "米酒薑香暖身，秋冬必吃", "price": "~300–450元", "key": "薑母鴨", "m": "N"},
        {"name": "羊肉爐", "desc": "當歸薑片羊肉湯，冬天暖身首選", "price": "~250–400元", "key": "羊肉爐", "m": "N"},
        {"name": "酸菜白肉鍋", "desc": "酸菜湯底配白肉，清爽解膩", "price": "~250–400元", "key": "酸菜白肉鍋", "m": "N"},
        {"name": "韓式豆腐鍋", "desc": "豆腐蔬菜蛋，低卡高蛋白暖胃", "price": "~150–200元", "key": "韓式豆腐鍋", "m": "D"},
        {"name": "海鮮鍋", "desc": "蝦蟹蛤蜊鮮甜湯底，海味滿滿", "price": "~300–500元", "key": "海鮮火鍋", "m": "N"},
        {"name": "涮涮鍋", "desc": "一人一鍋現涮現吃，清湯養生", "price": "~200–350元", "key": "涮涮鍋", "m": "D"},
        {"name": "壽喜燒", "desc": "甜鹹醬汁涮牛肉裹蛋液，日式經典", "price": "~300–500元", "key": "壽喜燒", "m": "N"},
        {"name": "麻油雞", "desc": "麻油薑香暖全身，冬天進補首選", "price": "~200–350元", "key": "麻油雞", "m": "N"},
        {"name": "泡菜鍋", "desc": "韓式辣泡菜配豬肉豆腐，酸辣開胃", "price": "~150–250元", "key": "泡菜鍋", "m": "D"},
        {"name": "牛奶鍋", "desc": "濃郁奶香湯底，小朋友也愛", "price": "~200–300元", "key": "牛奶鍋", "m": "D"},
    ],
    "日韓": [
        {"name": "壽司", "desc": "迴轉壽司或超商壽司，清爽方便", "price": "~60–300元", "key": "壽司", "m": ""},
        {"name": "日式丼飯", "desc": "牛丼親子丼豬排丼，一碗搞定", "price": "~120–200元", "key": "丼飯", "m": "D"},
        {"name": "日式定食", "desc": "烤魚豆腐套餐，蒸煮為主蔬菜豐富", "price": "~150–200元", "key": "日式定食", "m": "D"},
        {"name": "韓式炸雞", "desc": "外酥內嫩甜辣醬，越吃越停不下來", "price": "~200–300元", "key": "韓式炸雞", "m": "N"},
        {"name": "燒肉", "desc": "日式燒肉配飯配味噌湯，超滿足", "price": "~200–400元", "key": "燒肉定食", "m": "N"},
        {"name": "咖哩飯", "desc": "日式咖哩配白飯，一盤解決", "price": "~120–180元", "key": "咖哩飯", "m": "D"},
        {"name": "居酒屋", "desc": "下班小酌串燒配啤酒，辛苦值了", "price": "~300–500元", "key": "居酒屋", "m": "N"},
        {"name": "韓式拌飯", "desc": "石鍋拌飯蔬菜蛋肉均衡，營養滿分", "price": "~150–250元", "key": "韓式拌飯", "m": "D"},
        {"name": "炸豬排", "desc": "厚切酥炸豬排配高麗菜絲，吃完超滿足", "price": "~180–280元", "key": "炸豬排", "m": "D"},
        {"name": "天婦羅", "desc": "炸蝦炸蔬菜輕薄酥脆，沾醬油最對味", "price": "~150–250元", "key": "天婦羅", "m": "D"},
        {"name": "鰻魚飯", "desc": "蒲燒鰻魚配醬汁飯，奢華但值得", "price": "~300–500元", "key": "鰻魚飯", "m": "D"},
        {"name": "生魚片丼", "desc": "新鮮生魚片鋪滿醋飯，海味滿滿", "price": "~200–400元", "key": "生魚片丼", "m": "D"},
        {"name": "部隊鍋", "desc": "泡麵年糕香腸起司大雜燴，韓式暖胃", "price": "~250–400元", "key": "部隊鍋", "m": "N"},
    ],
    "早午餐": [
        {"name": "班尼迪克蛋", "desc": "水波蛋配荷蘭醬，Brunch 咖啡廳必點", "price": "~180–320元", "key": "班尼迪克蛋", "m": ""},
        {"name": "鬆餅早午餐", "desc": "鬆餅配培根蛋，週末慢慢吃最享受", "price": "~150–250元", "key": "鬆餅 早午餐", "m": ""},
        {"name": "法式吐司", "desc": "蛋液浸吐司煎到金黃，淋蜂蜜楓糖", "price": "~100–180元", "key": "法式吐司", "m": ""},
        {"name": "荷蘭鬆餅", "desc": "歐式鬆餅配水果蜂蜜，假日 Brunch 首選", "price": "~150–280元", "key": "鬆餅", "m": ""},
        {"name": "漢堡排套餐", "desc": "自製漢堡排配沙拉薯條，Brunch 咖啡廳熱門", "price": "~200–350元", "key": "漢堡排", "m": ""},
        {"name": "歐姆蛋套餐", "desc": "滑嫩法式歐姆蛋配沙拉吐司，早午餐精緻版", "price": "~120–200元", "key": "歐姆蛋", "m": ""},
        {"name": "可頌三明治", "desc": "酥脆可頌夾火腿起司蛋，法式 Brunch 必備", "price": "~80–150元", "key": "可頌", "m": ""},
        {"name": "酪梨吐司", "desc": "酪梨泥抹厚吐司配水煮蛋，健康 Brunch", "price": "~130–220元", "key": "酪梨吐司", "m": ""},
        {"name": "格子鬆餅", "desc": "外酥內軟格子鬆餅，配冰淇淋或莓果醬", "price": "~120–200元", "key": "格子鬆餅", "m": ""},
        {"name": "貝果三明治", "desc": "烤貝果夾奶油乳酪煙燻鮭魚，紐約風早午餐", "price": "~120–180元", "key": "貝果", "m": ""},
        {"name": "早午餐拼盤", "desc": "培根、炒蛋、烤番茄、麵包一次滿足", "price": "~200–380元", "key": "早午餐 拼盤", "m": ""},
        {"name": "帕尼尼", "desc": "壓紋麵包夾火腿起司蔬菜，義式咖啡廳定番", "price": "~100–160元", "key": "帕尼尼", "m": ""},
        {"name": "鹹派", "desc": "奶蛋培根菠菜烤成一片，法式鹹派配沙拉", "price": "~120–180元", "key": "鹹派 早午餐", "m": ""},
    ],
    "飲料甜點": [
        {"name": "珍珠奶茶", "desc": "台灣國飲，心情不好來一杯就解決", "price": "~50–80元", "key": "珍珠奶茶", "m": "", "s": ""},
        {"name": "咖啡", "desc": "美式拿鐵卡布，提神醒腦必備", "price": "~50–150元", "key": "咖啡廳", "m": "", "s": ""},
        {"name": "蛋糕甜點", "desc": "蛋糕配咖啡犒賞自己，超療癒", "price": "~100–200元", "key": "蛋糕店", "m": "", "s": ""},
        {"name": "豆花", "desc": "綿密豆花加花生粉圓，古早味甜品", "price": "~40–60元", "key": "豆花", "m": "D", "s": ""},
        {"name": "鮮奶茶", "desc": "用鮮奶不用奶精，喝起來就是不一樣", "price": "~55–80元", "key": "鮮奶茶", "m": "", "s": ""},
        {"name": "果汁", "desc": "現打果汁補充維他命，健康解渴", "price": "~50–80元", "key": "現打果汁", "m": "", "s": ""},
        {"name": "抹茶拿鐵", "desc": "日本宇治抹茶配鮮奶，苦甜平衡剛好", "price": "~80–130元", "key": "抹茶拿鐵", "m": "", "s": ""},
        {"name": "楊枝甘露", "desc": "芒果椰汁西米露，港式甜品經典", "price": "~80–150元", "key": "港式甜品", "m": "D", "s": ""},
        {"name": "手搖飲", "desc": "四季春烏龍鮮奶茶，下午三點必來一杯", "price": "~40–70元", "key": "手搖飲", "m": "", "s": ""},
        # 夏天限定 (5-10月)
        {"name": "剉冰", "desc": "芒果冰紅豆冰，台灣夏天消暑第一名", "price": "~50–100元", "key": "剉冰", "m": "D", "s": "hot"},
        {"name": "愛玉檸檬", "desc": "現搖愛玉配新鮮檸檬汁，夏日必喝", "price": "~40–65元", "key": "愛玉", "m": "D", "s": "hot"},
        {"name": "仙草凍飲", "desc": "仙草加鮮奶清涼退火，夏天消暑聖品", "price": "~45–65元", "key": "仙草", "m": "", "s": "hot"},
        {"name": "冰淇淋", "desc": "義式濃縮口味多樣，夏日隨心情換口味", "price": "~80–180元", "key": "冰淇淋", "m": "D", "s": "hot"},
        {"name": "楊桃汁", "desc": "古早味鹹楊桃汁，台南夏日傳統飲料", "price": "~30–50元", "key": "楊桃汁", "m": "D", "s": "hot"},
        {"name": "粉粿冰", "desc": "台南古早粉粿加黑糖，消暑又扎實", "price": "~40–70元", "key": "粉粿冰", "m": "D", "s": "hot"},
        # 冬天限定 (11-4月)
        {"name": "燒仙草", "desc": "熱燒仙草配芋圓湯圓，冬天最暖心", "price": "~50–80元", "key": "燒仙草", "m": "D", "s": "cold"},
        {"name": "紅豆湯＋湯圓", "desc": "冬至必吃，暖呼呼甜湯補充元氣", "price": "~40–70元", "key": "紅豆湯 湯圓", "m": "D", "s": "cold"},
        {"name": "花生湯", "desc": "綿密花生甜湯，古早味暖胃甜品", "price": "~40–60元", "key": "花生湯", "m": "D", "s": "cold"},
        {"name": "薑母茶", "desc": "老薑麻油糖，手腳冰冷喝了馬上暖", "price": "~50–80元", "key": "薑母茶", "m": "D", "s": "cold"},
        {"name": "熱可可", "desc": "濃郁巧克力配棉花糖，冬天療癒聖品", "price": "~80–150元", "key": "熱可可 巧克力", "m": "", "s": "cold"},
        {"name": "地瓜湯圓", "desc": "薑汁地瓜配小湯圓，甜蜜蜜暖意滿滿", "price": "~40–65元", "key": "地瓜湯圓", "m": "D", "s": "cold"},
    ],
    "輕食": [
        {"name": "沙拉", "desc": "雞胸肉沙拉，超商或輕食店都有", "price": "~80–150元", "key": "沙拉 輕食", "m": ""},
        {"name": "御飯糰", "desc": "超商三角飯糰，帶著走最方便", "price": "~25–40元", "key": "御飯糰", "m": ""},
        {"name": "關東煮", "desc": "超商自選配料，控制熱量又暖胃", "price": "~50–80元", "key": "關東煮", "m": ""},
        {"name": "烤地瓜", "desc": "超商健康選擇，飽足感高熱量低", "price": "~35–55元", "key": "烤地瓜", "m": ""},
        {"name": "優格", "desc": "膳食纖維補充站，早餐下午茶都適合", "price": "~40–70元", "key": "優格", "m": ""},
        {"name": "燕麥飲", "desc": "膳食纖維＋低糖，健康族首選", "price": "~30–50元", "key": "燕麥牛奶", "m": ""},
        {"name": "水煮餐", "desc": "健身族最愛，雞胸花椰菜糙米", "price": "~100–150元", "key": "水煮餐", "m": "D"},
        {"name": "蔬食便當", "desc": "素食自助餐，自選蔬菜控制油量", "price": "~80–110元", "key": "素食自助餐", "m": "D"},
        {"name": "貝果", "desc": "嚼勁十足配酪梨或鮪魚，健康又飽足", "price": "~60–120元", "key": "貝果", "m": "M"},
        {"name": "雞胸肉便當", "desc": "低脂高蛋白，健身族外食首選", "price": "~100–150元", "key": "健身餐", "m": "D"},
        {"name": "豆腐料理", "desc": "涼拌豆腐或紅燒豆腐，高蛋白低熱量", "price": "~60–100元", "key": "豆腐料理", "m": "D"},
    ],
}  # fallback

# ── 米其林必比登推介（由 update_bib_in_webhook.py 自動更新）──
_BIB_GOURMAND: dict = _load_json("bib_gourmand.json", {})
if not _BIB_GOURMAND:
    _BIB_GOURMAND = {
    "台北": [
        {"name": "胖塔可", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/pang"},
        {"name": "Tableau by Craig Yang", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tableau-by-craig-yang"},
        {"name": "巷子龍家常菜", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/talking-heads"},
        {"name": "醉楓園小館", "type": "", "desc": "松山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tsui-feng-yuan"},
        {"name": "天下三絕", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/tien-hsia-san-chueh"},
        {"name": "小小樹食 (大安路)", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/little-tree-food-da-an-road"},
        {"name": "金賞軒", "type": "", "desc": "松山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/jin-shang-hsuan"},
        {"name": "茂園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/mao-yuan"},
        {"name": "雲川水月", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/clavius"},
        {"name": "鼎泰豐 (信義路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/din-tai-fung-xinyi-road"},
        {"name": "軟食力", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/soft-power"},
        {"name": "雄記蔥抓餅", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiung-chi-scallion-pancake"},
        {"name": "杭州小籠湯包 (大安)", "type": "", "desc": "大安區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hang-zhou-xiao-long-bao-da-an"},
        {"name": "雞家莊 (長春路)", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/chi-chia-chuang-changchun-road"},
        {"name": "雙月食品 (青島東路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/shuang-yue-food"},
        {"name": "祥和蔬食 (中正)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/serenity"},
        {"name": "小品雅廚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/xiao-ping-kitchen"},
        {"name": "小酌之家", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiao-cho-chih-chia"},
        {"name": "人和園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/jen-ho-yuan"},
        {"name": "黃記魯肉飯", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/huang-chi-lu-rou-fan"},
        {"name": "隱食家", "type": "", "desc": "中山區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/inn-s"},
        {"name": "宋朝", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/song-jhao"},
        {"name": "欣葉小聚 (南港)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/shin-yeh-shiao-ju-nangang"},
        {"name": "無名推車燒餅", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/unnamed-clay-oven-roll"},
        {"name": "老山東牛肉家常麵店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/lao-shan-dong-homemade-noodles"},
        {"name": "吾旺再季", "type": "", "desc": "中正區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/wu-wang-tsai-chi"},
        {"name": "賣麵炎仔", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/mai-mien-yen-tsai"},
        {"name": "大橋頭老牌筒仔米糕 (延平北路)", "type": "", "desc": "大同區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/da-qiao-tou-tube-rice-pudding"},
        {"name": "HUGH dessert dining", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hugh"},
        {"name": "阿爸の芋圓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/a-ba-s-taro-ball"},
        {"name": "一甲子餐飲", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/yi-jia-zi"},
        {"name": "客家小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/garden-h"},
        {"name": "永和佳香豆漿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/yonghe-chia-hsiang-soy-milk"},
        {"name": "蔡家牛肉麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/tsai-chia-beef-noodles"},
        {"name": "源芳刈包", "type": "", "desc": "萬華區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/yuan-fang-guabao"},
        {"name": "小王煮瓜", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/hsiao-wang-steamed-minced-pork-with-pickles-in-broth"},
        {"name": "蘇來傳", "type": "", "desc": "萬華區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/su-lai-chuan"},
        {"name": "鍾家原上海生煎包", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/chung-chia-sheng-jian-bao"},
        {"name": "好朋友涼麵", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/good-friend-cold-noodles"},
        {"name": "店小二 (大同北路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/dian-xiao-er-datong-north-road"},
        {"name": "賴岡山羊肉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/lai-kang-shan"},
        {"name": "山東小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/san-tung"},
        {"name": "超人鱸魚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/superman"},
        {"name": "光興腿庫", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/guang-xing-pork-knuckle"},
        {"name": "葉家藥燉排骨", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/yeh-chia-pork-ribs-medicinal-herbs-soup"},
        {"name": "番紅花印度美饌", "type": "", "desc": "士林區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/saffron"},
        {"name": "上好雞肉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/shang-hao"},
        {"name": "松竹園", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/sung-chu-yuan"},
        {"name": "珍品餐飲坊", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/jhen-pin"},
        {"name": "三姐妹農家樂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/northern-taiwan/new-taipei-city_2853082/restaurant/san-chieh-mei-nung-chia-le"},
    ],
    "台中": [
        {"name": "曙光居", "type": "", "desc": "西屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/house-of-dawn"},
        {"name": "可口牛肉麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/ke-kou-beef-noodles"},
        {"name": "裡小樓", "type": "", "desc": "西屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/li-xiao-lou"},
        {"name": "夜間部爌肉飯", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/night-school-braised-pork-rice"},
        {"name": "功夫上海手工魚丸", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/kung-fu-shanghai-fish-ball"},
        {"name": "富狀元豬腳", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-juang-yuan"},
        {"name": "羅家古早味 (南屯)", "type": "", "desc": "南屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/lou-s-nantun"},
        {"name": "繡球", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/ajisai"},
        {"name": "滬舍餘味 (南屯)", "type": "", "desc": "南屯區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/shanghai-food"},
        {"name": "好菜 (西區)", "type": "", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/kuisine"},
        {"name": "馨苑 (西區)", "type": "台菜", "desc": "西區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/shin-yuan"},
        {"name": "富鼎旺 (中區)", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-din-wang-central"},
        {"name": "富貴亭", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/fu-kuei-ting"},
        {"name": "阿坤麵", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/a-kun-mian"},
        {"name": "上海未名麵點", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/no-name-noodles"},
        {"name": "范記金之園 (中區)", "type": "", "desc": "中區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/chin-chih-yuan"},
        {"name": "醉月樓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/moon-pavilion"},
        {"name": "台中肉員", "type": "", "desc": "南區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/taichung-meatball"},
        {"name": "彭城堂", "type": "台菜", "desc": "太平區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/peng-cheng-tang"},
        {"name": "鳳記鵝肉老店", "type": "", "desc": "沙鹿區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/feng-chi-goose"},
        {"name": "老士官擀麵", "type": "", "desc": "清水區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/lao-shih-kuan-noodles"},
        {"name": "牛稼莊", "type": "", "desc": "東勢區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niou-jia-juang"},
        {"name": "鮨承", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/sushi-noru"},
        {"name": "肉料理 · 福", "type": "", "desc": "北區｜米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/taichung-region/taichung/restaurant/niku-ryouri-fuku"},
    ],
    "台南": [
        {"name": "大勇街無名鹹粥", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/dayong-street-no-name-congee"},
        {"name": "吃麵吧", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/jai-mi-ba"},
        {"name": "阿文米粿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-wen-rice-cake"},
        {"name": "無名羊肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/no-name-lamb-soup"},
        {"name": "阿星鹹粥", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-hsing-congee"},
        {"name": "八寶彬圓仔惠 (國華街)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yuan-zai-hui-guohua-street"},
        {"name": "葉家小卷米粉", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yeh-jia-calamari-rice-noodle-soup"},
        {"name": "誠實鍋燒意麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/cheng-shi"},
        {"name": "筑馨居", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/zhu-xin-ju"},
        {"name": "黃家蝦捲", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/huang-chia-shrimp-roll"},
        {"name": "一味品", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yi-wei-pin"},
        {"name": "好農家米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/hao-nung-chia-migao"},
        {"name": "小公園擔仔麵", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/small-park-danzai-noodles"},
        {"name": "博仁堂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/po-jen-tang"},
        {"name": "添厚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/eat-to-fat"},
        {"name": "阿興虱目魚", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/a-xing-shi-mu-yu"},
        {"name": "落成米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lo-cheng-migao"},
        {"name": "福泰飯桌第三代", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/fu-tai-table-third-generation"},
        {"name": "麥謎食驗室", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/bue-mi-lab"},
        {"name": "謝掌櫃", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/xie-shopkeeper"},
        {"name": "西羅殿牛肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/hsi-lo-tien-beef-soup"},
        {"name": "三好一公道當歸鴨", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/san-hao-yi-kung-tao-angelica-duck"},
        {"name": "尚好吃牛肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/shang-hao-chih-beef-soup"},
        {"name": "葉桑生炒鴨肉焿", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/yeh-san-duck-thick-soup"},
        {"name": "開元紅燒土魠魚羮", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/kaiyuan-fried-spanish-mackerel-thick-soup"},
        {"name": "鮮蒸蝦仁肉圓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/shian-jeng-shrimp-bawan"},
        {"name": "東香台菜海味料理", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/dong-shang-taiwanese-seafood"},
        {"name": "蓮霧腳羊肉湯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lien-wu-chiao-lamb-soup"},
        {"name": "Lumière", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/lumiere-1245897"},
        {"name": "咩灣裡羊肉店", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/tainan-region/tainan/restaurant/baa-wanli-goat"},
    ],
    "高雄": [
        {"name": "小燉食室", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/simmer-house"},
        {"name": "米院子油飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/mi-yuan-tzu-steamed-glutinous-rice"},
        {"name": "春蘭割包", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/chun-lan-gua-bao"},
        {"name": "泰元", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/thai-yuan"},
        {"name": "牛老大涮牛肉 (自強二路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/beef-chief-zihciang-2nd-road"},
        {"name": "菜粽李", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/caizong-li"},
        {"name": "前金肉燥飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/cianjin-brasied-pork-rice"},
        {"name": "昭明海產家庭料理", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/chao-ming"},
        {"name": "永筵小館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/yung-yen"},
        {"name": "侯記鴨肉飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hou-chi-duck-rice"},
        {"name": "白玉樓", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/pale-jade-pavilion"},
        {"name": "北港蔡三代筒仔米糕 (鹽埕)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/bei-gang-tsai-rice-tube-yancheng"},
        {"name": "良佳豬腳", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/liang-chia-pig-knuckle"},
        {"name": "貳哥食堂", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/erge-shih-tang"},
        {"name": "賣塩順", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/mai-yen-shun"},
        {"name": "正宗鴨肉飯", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/cheng-tsung-duck-rice"},
        {"name": "弘記肉燥飯舖", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hung-chi-rice-shop"},
        {"name": "楊寶寶蒸餃 (朝明路)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/yang-bao-bao-nanzih"},
        {"name": "廖記米糕", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/liao-chi-migao"},
        {"name": "橋仔頭黃家肉燥飯 (橋頭)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/ciao-zai-tou-huang-s-braised-pork-rice-ciaotou"},
        {"name": "舊市羊肉 (岡山)", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/joes-gangshan"},
        {"name": "湖東牛肉館", "type": "", "desc": "米其林必比登推介", "url": "https://guide.michelin.com/tw/zh_TW/kaohsiung-region/kaohsiung/restaurant/hu-dong-beef"},
    ],
}  # fallback

# ─── 城市特色食物（觀光客/外地人必吃）──────────────────────
_CITY_SPECIALTIES: dict = _load_json("city_specialties.json", {})
if not _CITY_SPECIALTIES:
    _CITY_SPECIALTIES = {
    "台北": [
        {"name": "臭豆腐", "desc": "士林夜市必吃，外酥內嫩配泡菜，越臭越香", "key": "台北 臭豆腐", "s": ""},
        {"name": "蚵仔煎", "desc": "飽滿蚵仔加米漿皮，夜市人氣王", "key": "台北 蚵仔煎", "s": ""},
        {"name": "刈包", "desc": "台灣虎咬豬，軟饅頭夾控肉酸菜花生", "key": "台北 刈包", "s": ""},
        {"name": "豬血糕", "desc": "士林夜市限定體驗，花生粉香菜大爆發", "key": "台北 豬血糕", "s": ""},
        {"name": "滷肉飯", "desc": "台北靈魂飯，油蔥香氣一口就上癮", "key": "台北 滷肉飯", "s": ""},
        {"name": "公館粉圓", "desc": "師大夜市周邊古早味粉圓冰，消暑必吃", "key": "台北 粉圓冰", "s": "hot"},
        {"name": "紅豆餅", "desc": "街頭現烤車輪餅，紅豆奶油口味各有擁護者", "key": "台北 車輪餅", "s": ""},
    ],
    "新北": [
        {"name": "三峽金牛角", "desc": "三峽老街必買，酥脆牛角麵包香甜不膩", "key": "三峽 金牛角", "s": ""},
        {"name": "深坑臭豆腐", "desc": "深坑老街名物，炸臭豆腐外酥內嫩全台聞名", "key": "深坑 臭豆腐", "s": ""},
        {"name": "淡水魚丸", "desc": "淡水老街必吃，魚漿包肉餡Q彈有嚼勁", "key": "淡水 魚丸", "s": ""},
        {"name": "淡水阿給", "desc": "油豆腐填冬粉加魚漿封口，淡水獨有名點", "key": "淡水 阿給", "s": ""},
        {"name": "九份芋圓", "desc": "九份老街海景配芋圓，暖熱冰涼都好吃", "key": "九份 芋圓", "s": ""},
        {"name": "鶯歌陶瓷碗公冰", "desc": "鶯歌陶博館周邊，陶瓷碗盛裝復古剉冰", "key": "鶯歌 冰", "s": "hot"},
    ],
    "基隆": [
        {"name": "鼎邊銼", "desc": "基隆廟口第一名，米漿刮鍋邊煮成的獨特小吃", "key": "基隆 鼎邊銼", "s": ""},
        {"name": "天婦羅", "desc": "基隆港邊魚漿炸物，沾甜辣醬超對味", "key": "基隆 天婦羅", "s": ""},
        {"name": "泡泡冰", "desc": "基隆獨有冰品，轉出泡泡造型，花生芋頭口味人氣高", "key": "基隆 泡泡冰", "s": "hot"},
        {"name": "三明治（基隆式）", "desc": "基隆夜市古早味三明治，蛋沙拉夾吐司超厚實", "key": "基隆 三明治", "s": ""},
        {"name": "豆簽羹", "desc": "廟口名物，豆粉做成豆簽配海鮮羹，古早又暖胃", "key": "基隆 豆簽羹", "s": ""},
        {"name": "營養三明治", "desc": "炸麵包夾蛋沙拉番茄，基隆人的早餐記憶", "key": "基隆 營養三明治", "s": ""},
    ],
    "桃園": [
        {"name": "大溪豆干", "desc": "大溪老街百年豆干，滷得入味帶勁香", "key": "大溪 豆干", "s": ""},
        {"name": "客家粄條", "desc": "龍潭、楊梅客家粄條，米香軟Q配豬油蔥", "key": "桃園 客家粄條", "s": ""},
        {"name": "復興山豬肉", "desc": "復興鄉原住民風味，山豬肉香辣下飯", "key": "復興 山豬肉 原住民", "s": ""},
        {"name": "石門活魚", "desc": "石門水庫旁現撈活魚，三吃吃法各有風味", "key": "石門水庫 活魚", "s": ""},
        {"name": "龍潭花生糖", "desc": "客家傳統花生糖，香甜不黏牙伴手禮首選", "key": "龍潭 花生糖", "s": ""},
        {"name": "蘆竹米干", "desc": "緬甸風味米干，桃園東南亞移民帶來的滋味", "key": "桃園 米干", "s": ""},
    ],
    "新竹": [
        {"name": "貢丸湯", "desc": "新竹貢丸Q彈有嚼勁，湯底清甜暖胃", "key": "新竹 貢丸湯", "s": ""},
        {"name": "新竹米粉", "desc": "新竹九降風吹出細如絲的米粉，炒或煮都香", "key": "新竹 米粉", "s": ""},
        {"name": "柿餅", "desc": "新竹九降風吹出的古早味，秋冬最甜最香", "key": "新竹 柿餅", "s": "cold"},
        {"name": "潤餅", "desc": "新竹傳統潤餅捲，花生糖粉＋蛋＋豆芽料多實在", "key": "新竹 潤餅", "s": ""},
        {"name": "城隍廟廟口小吃", "desc": "新竹城隍廟周邊肉燥飯、湯圓、貢丸一條街", "key": "新竹城隍廟 小吃", "s": ""},
        {"name": "仙草雞", "desc": "關西仙草產地直送，仙草燉雞清潤去火", "key": "關西 仙草雞", "s": ""},
    ],
    "苗栗": [
        {"name": "客家湯圓", "desc": "苗栗客家湯圓包豬肉，油蔥拌炒香氣滿滿", "key": "苗栗 客家湯圓", "s": "cold"},
        {"name": "梅干扣肉", "desc": "客家媽媽的味道，梅干菜吸飽豬油滷汁超下飯", "key": "苗栗 梅干扣肉", "s": ""},
        {"name": "薑絲大腸", "desc": "客家名菜，嫩大腸配嫩薑絲酸辣開胃", "key": "苗栗 薑絲大腸", "s": ""},
        {"name": "銅鑼杭菊茶", "desc": "銅鑼杭菊產地，秋冬菊花茶清香退火", "key": "銅鑼 杭菊茶", "s": "cold"},
        {"name": "大湖草莓", "desc": "大湖草莓園採摘體驗，冬季限定最甜", "key": "大湖 草莓", "s": "cold"},
        {"name": "南庄桂花釀", "desc": "南庄老街桂花系列飲品甜點，香氣迷人", "key": "南庄 桂花", "s": ""},
    ],
    "台中": [
        {"name": "太陽餅", "desc": "台中伴手禮一號，酥皮麥芽糖內餡香甜", "key": "台中 太陽餅", "s": ""},
        {"name": "珍珠奶茶（發源地）", "desc": "珍珠奶茶在台中春水堂發明，原汁原味", "key": "台中 春水堂 珍珠奶茶", "s": ""},
        {"name": "逢甲夜市鹹酥雞", "desc": "逢甲夜市必逛，現炸鹹酥雞配九層塔", "key": "逢甲夜市 鹹酥雞", "s": ""},
        {"name": "草莓大福", "desc": "新社草莓季必吃，新鮮草莓包白玉麻糬", "key": "台中 草莓大福", "s": "cold"},
        {"name": "肉蛋吐司", "desc": "台中早餐象徵，鐵板蛋＋貢丸＋吐司超滿足", "key": "台中 肉蛋吐司", "s": ""},
        {"name": "宮原眼科冰淇淋", "desc": "台中網紅景點，古典建築配義式冰淇淋塔", "key": "台中 宮原眼科 冰淇淋", "s": "hot"},
        {"name": "三時茶房鳳梨酥", "desc": "宮原集團出品，台中土鳳梨酥送禮超體面", "key": "台中 鳳梨酥", "s": ""},
    ],
    "彰化": [
        {"name": "彰化肉圓", "desc": "彰化名物，蒸熟軟Q外皮包筍丁豬肉，醬汁甘甜", "key": "彰化 肉圓", "s": ""},
        {"name": "爌肉飯", "desc": "彰化老字號，整塊控肉滷到入骨超下飯", "key": "彰化 爌肉飯", "s": ""},
        {"name": "貓鼠麵", "desc": "彰化百年老店，意麵配豬雜湯獨特古早味", "key": "彰化 貓鼠麵", "s": ""},
        {"name": "王功蚵仔", "desc": "王功漁港現撈蚵仔，鮮甜肥美直接吃最過癮", "key": "王功 蚵仔 海鮮", "s": ""},
        {"name": "溪湖羊肉", "desc": "溪湖羊肉爐聞名全台，冬季進補必來", "key": "溪湖 羊肉爐", "s": "cold"},
        {"name": "鹿港蚵仔煎", "desc": "鹿港老街必吃，蚵仔新鮮肥大，米漿外皮香脆", "key": "鹿港 蚵仔煎", "s": ""},
        {"name": "鹿港鳳眼糕", "desc": "鹿港傳統糕點，米粉製成細緻香甜", "key": "鹿港 鳳眼糕", "s": ""},
    ],
    "南投": [
        {"name": "竹筒飯", "desc": "信義鄉原住民竹筒飯，現烤竹香滲入米飯", "key": "南投 竹筒飯 原住民", "s": ""},
        {"name": "紹興酒蛋", "desc": "埔里紹興酒廠名物，酒香濃郁滷蛋入味", "key": "埔里 紹興酒蛋", "s": ""},
        {"name": "日月潭紅茶", "desc": "日月潭阿薩姆紅茶，茶色艷紅滋味甘醇", "key": "日月潭 紅茶", "s": ""},
        {"name": "埔里米粉", "desc": "埔里盆地好水製成米粉，煮炒皆宜", "key": "埔里 米粉", "s": ""},
        {"name": "廬山溫泉烤玉米", "desc": "廬山路邊現烤玉米，甜脆噴香", "key": "南投 烤玉米", "s": ""},
        {"name": "水里蛇窯陶藝餐", "desc": "水里特色體驗，陶甕料理視覺味覺雙享受", "key": "水里 陶藝 料理", "s": ""},
    ],
    "雲林": [
        {"name": "斗六意麵", "desc": "雲林特色麵食，鹼水意麵配肉燥湯頭鮮甜", "key": "斗六 意麵", "s": ""},
        {"name": "虎尾毛巾蛋糕", "desc": "虎尾毛巾工廠轉型，毛巾造型蛋糕超可愛", "key": "虎尾 毛巾蛋糕", "s": ""},
        {"name": "北港花生", "desc": "北港農產直銷花生糖、花生酥，香氣四溢", "key": "北港 花生糖", "s": ""},
        {"name": "口湖烏魚子", "desc": "口湖漁港鮮製烏魚子，送禮自用兩相宜", "key": "口湖 烏魚子", "s": "cold"},
        {"name": "古坑咖啡", "desc": "古坑台灣咖啡產地，現烤咖啡豆香氣迷人", "key": "古坑 台灣咖啡", "s": ""},
        {"name": "西螺醬油", "desc": "西螺百年醬油文化，原釀醬油拌飯超香", "key": "西螺 醬油 小吃", "s": ""},
    ],
    "嘉義": [
        {"name": "火雞肉飯", "desc": "嘉義市標誌美食，火雞腿絲淋滷汁超香", "key": "嘉義 火雞肉飯", "s": ""},
        {"name": "方塊酥", "desc": "嘉義特色零食，酥脆鹹甜一口接一口停不下來", "key": "嘉義 方塊酥", "s": ""},
        {"name": "阿里山愛玉", "desc": "阿里山天然愛玉自己搓，配蜂蜜檸檬超純淨", "key": "阿里山 愛玉", "s": "hot"},
        {"name": "奮起湖便當", "desc": "阿里山鐵路便當，竹製餐盒古早香名聞全台", "key": "奮起湖便當", "s": ""},
        {"name": "東石蚵仔", "desc": "東石漁港現撈蚵仔，蚵仔麵線蚵仔煎都鮮", "key": "東石 蚵仔", "s": ""},
        {"name": "嘉義布丁", "desc": "嘉義特色古早味布丁，雞蛋奶香焦糖濃郁", "key": "嘉義 布丁", "s": ""},
    ],
    "台南": [
        {"name": "紅磚布丁", "desc": "台南排隊名物，古早味雞蛋布丁冷吃最香", "key": "台南 紅磚布丁", "s": ""},
        {"name": "虱目魚粥", "desc": "台南早餐靈魂，鮮甜虱目魚配清粥無腥味", "key": "台南 虱目魚粥", "s": ""},
        {"name": "擔仔麵", "desc": "台南百年老味道，度小月湯頭鮮甜不膩", "key": "台南 擔仔麵", "s": ""},
        {"name": "鱔魚意麵", "desc": "台南獨有大火炒法，鑊氣十足滑嫩入味", "key": "台南 鱔魚意麵", "s": ""},
        {"name": "碗粿", "desc": "軟Q米食加肉燥蒸熟，沾蒜蓉醬超下飯", "key": "台南 碗粿", "s": ""},
        {"name": "土魠魚羹", "desc": "台灣鯧魚炸酥後加羹，鮮甜濃郁台南招牌", "key": "台南 土魠魚羹", "s": ""},
        {"name": "粉粿", "desc": "古早粉粿加黑糖水，夏天消暑必吃", "key": "台南 粉粿", "s": "hot"},
        {"name": "棺材板", "desc": "延平街名物，厚吐司挖空填濃郁白醬海鮮", "key": "台南 棺材板", "s": ""},
    ],
    "高雄": [
        {"name": "木瓜牛奶", "desc": "高雄鹽埕傳統木瓜牛奶，甜而不膩消暑聖品", "key": "高雄 木瓜牛奶", "s": ""},
        {"name": "旗魚黑輪", "desc": "旗津海邊必吃，現炸旗魚黑輪卡卡脆", "key": "高雄 旗魚黑輪", "s": ""},
        {"name": "鹽埕肉圓", "desc": "高雄老城區古早味，外皮Q彈肉餡飽滿", "key": "高雄 鹽埕 肉圓", "s": ""},
        {"name": "岡山羊肉爐", "desc": "岡山三寶之一，羊肉爐配蒜苗冬季必補", "key": "岡山 羊肉爐", "s": "cold"},
        {"name": "美濃板條", "desc": "美濃客家粄條，豬油蔥拌炒米香撲鼻", "key": "美濃 板條 粄條", "s": ""},
        {"name": "旗山香蕉", "desc": "旗山香蕉之鄉，香蕉冰淇淋香蕉蛋糕超值得買", "key": "旗山 香蕉 冰淇淋", "s": ""},
        {"name": "六合夜市海鮮", "desc": "高雄夜市全覽，生猛海鮮炒飯烤肉一條街", "key": "高雄 六合夜市 海鮮", "s": ""},
    ],
    "屏東": [
        {"name": "潮州燒冷冰", "desc": "屏東潮州名物，熱湯澆剉冰獨特吃法超特別", "key": "屏東 潮州 燒冷冰", "s": "hot"},
        {"name": "萬巒豬腳", "desc": "萬巒豬腳全台聞名，皮Q肉嫩滷汁入骨", "key": "萬巒 豬腳", "s": ""},
        {"name": "東港黑鮪魚", "desc": "東港黑鮪魚季（4-6月）生魚片最鮮最肥", "key": "東港 黑鮪魚", "s": "hot"},
        {"name": "屏東起司蛋糕", "desc": "屏東牧場直送鮮奶，起司蛋糕濃郁香滑", "key": "屏東 起司蛋糕", "s": ""},
        {"name": "恆春洋蔥", "desc": "恆春半島特產，洋蔥甜脆多汁，各式料理皆宜", "key": "恆春 洋蔥料理", "s": ""},
        {"name": "小琉球烤小卷", "desc": "小琉球海邊烤小卷，現烤鮮甜配蒜蓉醬", "key": "小琉球 烤小卷 海鮮", "s": ""},
    ],
    "宜蘭": [
        {"name": "鴨賞", "desc": "宜蘭三星特產，煙燻鴨肉切薄片超下酒", "key": "宜蘭 鴨賞", "s": ""},
        {"name": "牛舌餅", "desc": "宜蘭形狀像牛舌的甜餅，酥脆香甜伴手禮", "key": "宜蘭 牛舌餅", "s": ""},
        {"name": "糕渣", "desc": "外脆內燙的宜蘭名點，雞肉濃湯凝固炸酥", "key": "宜蘭 糕渣", "s": ""},
        {"name": "卜肉", "desc": "里肌裹地瓜粉油炸，外酥內嫩宜蘭獨有", "key": "宜蘭 卜肉", "s": ""},
        {"name": "三星蔥餅", "desc": "宜蘭三星蔥現烤蔥餅，香氣撲鼻超誘人", "key": "宜蘭 三星蔥餅", "s": ""},
        {"name": "羅東夜市小吃", "desc": "羅東夜市炭烤、肉羹、蒜味肉排，夜晚必訪", "key": "羅東夜市 小吃", "s": ""},
        {"name": "蘇澳冷泉蝦", "desc": "蘇澳天然冷泉養殖蝦，鮮甜清甜口感細嫩", "key": "蘇澳 冷泉蝦", "s": ""},
    ],
    "花蓮": [
        {"name": "麻糬", "desc": "花蓮必帶伴手禮，芝麻花生口味人氣最高", "key": "花蓮 麻糬", "s": ""},
        {"name": "奶油酥條", "desc": "花蓮特產，奶香濃厚酥脆不油膩", "key": "花蓮 奶油酥條", "s": ""},
        {"name": "原住民風味餐", "desc": "小米酒、烤山豬肉、吉拿富，體驗阿美族文化", "key": "花蓮 原住民料理", "s": ""},
        {"name": "東坡肉便當", "desc": "花蓮名產控肉便當，軟爛入味超下飯", "key": "花蓮 東坡肉便當", "s": ""},
        {"name": "芋頭冰淇淋", "desc": "花蓮芋頭細緻甜香，冰淇淋口感迷人", "key": "花蓮 芋頭冰淇淋", "s": "hot"},
        {"name": "公正包子", "desc": "花蓮老字號，大顆肉包皮薄餡多排隊必吃", "key": "花蓮 公正包子", "s": ""},
        {"name": "壽豐鮭魚料理", "desc": "壽豐鮭魚產地，生魚片握壽司鮮甜肥美", "key": "壽豐 鮭魚 生魚片", "s": ""},
    ],
    "台東": [
        {"name": "釋迦", "desc": "台東最出名水果，果肉甜如蜜，產季必吃", "key": "台東 釋迦", "s": ""},
        {"name": "黑糖麻糬", "desc": "池上黑糖麻糬，現做Q彈甜蜜蜜", "key": "台東 黑糖麻糬", "s": ""},
        {"name": "關山便當", "desc": "台東縱谷米飯超香，關山火車便當排隊名物", "key": "關山便當", "s": ""},
        {"name": "旗魚米苔目", "desc": "台東在地早餐，旗魚湯頭加Q彈米苔目", "key": "台東 米苔目", "s": ""},
        {"name": "卑南豬血湯", "desc": "台東特色早餐，豬血鮮嫩湯底清甜暖胃", "key": "台東 豬血湯", "s": ""},
        {"name": "都蘭薯餅", "desc": "都蘭部落風味薯餅，地瓜香甜嚼勁十足", "key": "台東 都蘭 薯餅", "s": ""},
        {"name": "成功旗魚飯糰", "desc": "成功漁港新鮮旗魚製成旗魚飯糰，海味十足", "key": "成功 旗魚飯糰", "s": ""},
    ],
    "澎湖": [
        {"name": "仙人掌冰", "desc": "澎湖夏季限定！天然仙人掌汁製成紫紅冰棒", "key": "澎湖 仙人掌冰", "s": "hot"},
        {"name": "現撈海鮮", "desc": "小管、龍蝦、九孔現撈直送，新鮮無比", "key": "澎湖 海鮮", "s": ""},
        {"name": "花生糖", "desc": "澎湖傳統花生糖，香甜不黏牙代代相傳", "key": "澎湖 花生糖", "s": ""},
        {"name": "黑糖糕", "desc": "澎湖名產Q彈黑糖麻糬口感，送禮首選", "key": "澎湖 黑糖糕", "s": ""},
        {"name": "丁香魚飯", "desc": "澎湖丁香魚炸酥配白飯，鮮鹹下飯超獨特", "key": "澎湖 丁香魚", "s": ""},
        {"name": "澎湖文蛤", "desc": "澎湖養殖文蛤肉厚鮮甜，蒸或煮都一絕", "key": "澎湖 文蛤 海鮮", "s": ""},
    ],
    "金門": [
        {"name": "貢糖", "desc": "金門必帶伴手禮，花生芝麻酥脆香甜", "key": "金門 貢糖", "s": ""},
        {"name": "高粱酒料理", "desc": "金門高粱酒入菜，醉雞醉蝦風味獨特", "key": "金門 高粱 料理", "s": ""},
        {"name": "金門麵線", "desc": "金門傳統曬麵線，湯頭鮮甜麵條細緻", "key": "金門 麵線", "s": ""},
        {"name": "蚵仔麵線", "desc": "金門蚵仔肥美配細麵線，鮮甜濃郁", "key": "金門 蚵仔麵線", "s": ""},
        {"name": "廣東粥", "desc": "金門早餐文化，食材豐富粥底綿密", "key": "金門 廣東粥", "s": ""},
    ],
    "連江": [
        {"name": "老酒麵線", "desc": "馬祖紅糟老酒入麵線，酒香濃郁暖胃", "key": "馬祖 老酒麵線", "s": "cold"},
        {"name": "繼光餅", "desc": "馬祖傳統硬餅，夾蛋夾肉都好吃", "key": "馬祖 繼光餅", "s": ""},
        {"name": "淡菜", "desc": "馬祖海域現撈淡菜，肉質肥美鮮甜", "key": "馬祖 淡菜 海鮮", "s": ""},
        {"name": "魚麵", "desc": "馬祖傳統魚漿製成的魚麵，Q彈有嚼勁", "key": "馬祖 魚麵", "s": ""},
        {"name": "芙蓉酥", "desc": "馬祖傳統糕點，鬆軟香甜帶花香", "key": "馬祖 芙蓉酥", "s": ""},
    ],
}  # fallback

# ── 餐廳資料庫（觀光署開放資料）──
_RESTAURANT_CACHE: dict = {}
try:
    _rest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "restaurant_cache.json"
    )
    if os.path.isfile(_rest_path):
        with open(_rest_path, encoding="utf-8") as _rf:
            _rest_data = json.load(_rf)
            _RESTAURANT_CACHE = _rest_data.get("restaurants", {})
except Exception:
    _RESTAURANT_CACHE = {}

# ── 使用者回饋暫存 ──
_FEEDBACK_LOG: list = []

# ── 記住最近推薦過的品項，避免連續重複 ──
_food_recent: dict = {}  # {style: [上次推薦的 name 列表]}

# ── Accupass 快取（lazy-load）──
_ACCUPASS_CACHE = None


def _get_accupass_cache() -> dict:
    """載入並快取 Accupass 爬蟲資料"""
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        try:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cache_path = os.path.join(base, "accupass_cache.json")
            if os.path.exists(cache_path):
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                _ACCUPASS_CACHE = data.get("events", {})
            else:
                _ACCUPASS_CACHE = {}
        except Exception:
            _ACCUPASS_CACHE = {}
    return _ACCUPASS_CACHE


# ─── 工具函式 ──────────────────────────────────────────

def _maps_url(keyword: str, area: str = "", **_kw) -> str:
    """產生 Google Maps 搜尋連結"""
    if area:
        q = urllib.parse.quote(f"{area} {keyword}")
    else:
        q = urllib.parse.quote(f"{keyword} 附近")
    return f"https://www.google.com/maps/search/{q}/"


def _tw_meal_period() -> tuple:
    """回傳 (時段代碼, 中文標籤)，依台灣時間（UTC+8）
    M=早餐(5-10)  D=午餐/下午(10-17)  N=晚餐(17-22)  L=消夜(22-5)
    """
    h = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).hour
    if 5 <= h < 10:
        return "M", "早餐推薦"
    elif 10 <= h < 14:
        return "D", "午餐推薦"
    elif 14 <= h < 17:
        return "D", "下午點心推薦"
    elif 17 <= h < 22:
        return "N", "晚餐推薦"
    else:
        return "L", "消夜推薦"


def _tw_season(city: str = "") -> str:
    """依實際氣溫判斷季節（優先查天氣 API，fallback 月份）
    max_t >= 27°C → hot；<= 22°C → cold；23-26 → 依月份（4-10 hot）
    """
    if city:
        try:
            w = _fetch_cwa_weather(city)
            max_t = w.get("max_t")
            if max_t is not None:
                if max_t >= 27:
                    return "hot"
                if max_t <= 22:
                    return "cold"
        except Exception:
            pass
    m = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).month
    return "hot" if 4 <= m <= 10 else "cold"


def _fetch_cwa_weather(city: str) -> dict:
    """呼叫中央氣象署 F-C0032-001 取得36小時天氣預報（Redis cache 15 分鐘）"""
    if not CWA_API_KEY:
        return {"ok": False, "error": "no_key"}
    try:
        cached = _redis_get(f"cwa_wx:{city}")
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        pass
    cwb_name = _CWA_CITY_MAP.get(city, city + "市")
    url = (
        "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        f"?Authorization={CWA_API_KEY}"
        f"&locationName={urllib.parse.quote(cwb_name)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        locs = data.get("records", {}).get("location", [])
        if not locs:
            return {"ok": False, "error": "no_data"}
        elems = {e["elementName"]: e["time"] for e in locs[0]["weatherElement"]}

        def _get(key, idx, default="—"):
            try:
                return elems[key][idx]["parameter"]["parameterName"]
            except Exception:
                return default

        result = {
            "ok": True, "city": city,
            "wx": _get("Wx", 0), "pop": int(_get("PoP", 0, "0")),
            "min_t": int(_get("MinT", 0, "20")), "max_t": int(_get("MaxT", 0, "25")),
            "wx_night": _get("Wx", 1), "pop_night": int(_get("PoP", 1, "0")),
            "wx_tom": _get("Wx", 2), "pop_tom": int(_get("PoP", 2, "0")),
            "min_tom": int(_get("MinT", 2, "20")), "max_tom": int(_get("MaxT", 2, "25")),
        }
        try:
            _redis_set(f"cwa_wx:{city}", json.dumps(result), ttl=900)
        except Exception:
            pass
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _filter_food_by_time(pool: list, period: str, city: str = "") -> list:
    """依時段 + 季節過濾食物；若剩不足3筆則 fallback 全部"""
    season = _tw_season(city)
    if period == "M":
        ok = [p for p in pool if p.get("m", "") in ("", "M")]
    elif period == "D":
        ok = [p for p in pool if p.get("m", "") in ("", "D")]
        if len(ok) < 3:
            ok = [p for p in pool if p.get("m", "") in ("", "D", "N")]
    else:  # N/L
        ok = [p for p in pool if p.get("m", "") in ("", "D", "N")]
    seasonal = [p for p in ok if p.get("s", "") in ("", season)]
    return seasonal if len(seasonal) >= 1 else ok if len(ok) >= 1 else pool


def _text_search_places(query: str, max_results: int = 5) -> list:
    """Google Places Text Search — 用關鍵字搜名店（不需座標）"""
    if not GOOGLE_PLACES_API_KEY:
        return []
    try:
        url = (
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
            f"?query={urllib.parse.quote(query)}"
            "&language=zh-TW"
            f"&key={GOOGLE_PLACES_API_KEY}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = []
        for p in data.get("results", [])[:max_results]:
            photo_ref = (p.get("photos") or [{}])[0].get("photo_reference", "")
            loc = p.get("geometry", {}).get("location", {})
            results.append({
                "name":               p.get("name", ""),
                "addr":               p.get("formatted_address", ""),
                "rating":             p.get("rating", 0),
                "user_ratings_total": p.get("user_ratings_total", 0),
                "lat":                loc.get("lat"),
                "lng":                loc.get("lng"),
                "place_id":           p.get("place_id", ""),
                "photo_ref":          photo_ref,
                "open_now":           (p.get("opening_hours") or {}).get("open_now"),
                "_source":            "text_search",
            })
        return results
    except Exception as e:
        print(f"[text_search] error: {e}")
        return []


def _places_photo_url(photo_ref: str, max_width: int = 400) -> str:
    """產生 Google Places 照片 URL"""
    if not photo_ref or not GOOGLE_PLACES_API_KEY:
        return ""
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photo_reference={photo_ref}"
        f"&key={GOOGLE_PLACES_API_KEY}"
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """兩點距離（公尺），Haversine 公式"""
    import math
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


def _build_restaurant_bubble(r: dict, lat, lon, city: str,
                              eaten_set: set, subtitle: str = "") -> dict:
    """單間餐廳 Flex Bubble（含照片 hero、評分、導航、吃過了按鈕）"""
    name = r.get("name", "")
    addr = r.get("addr", "") or r.get("town", "")
    rating = r.get("rating", 0)
    reviews = r.get("user_ratings_total", 0)
    eaten = name in eaten_set

    dist_str = ""
    dist_m = r.get("dist")
    if dist_m is None and lat and lon and r.get("lat") and r.get("lng"):
        dist_m = _haversine(lat, lon, r["lat"], r["lng"])
    if dist_m is not None:
        walk_min = max(1, round(dist_m / 80))
        if dist_m < 1000:
            dist_str = f"步行約{walk_min}分鐘（{int(dist_m)}m）"
        else:
            dist_str = f"步行約{walk_min}分鐘（{dist_m/1000:.1f}km）"

    if r.get("lat") and r.get("lng"):
        gmap_uri = f"https://maps.google.com/?q={r['lat']},{r['lng']}&query={urllib.parse.quote(name)}"
    elif r.get("place_id"):
        gmap_uri = f"https://maps.google.com/?q=place_id:{r['place_id']}"
    else:
        gmap_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(name + ' ' + city)}"

    tag = subtitle
    if not tag:
        if rating >= 4.5 and reviews >= 100:
            tag = "🔥 Google 高評分"
        elif rating >= 4.3:
            tag = "⭐ 評價優良"
        else:
            tag = "👥 在地人推薦"

    if rating >= 4.5 and reviews >= 100:
        rating_color = "#E53935"
        rating_str = f"★{rating}  ({reviews}則)"
    elif rating >= 4.0:
        rating_color = "#F57C00"
        rating_str = f"★{rating}  ({reviews}則)" if reviews else f"★{rating}"
    elif rating:
        rating_color = "#888888"
        rating_str = f"★{rating}"
    else:
        rating_color = "#888888"
        rating_str = ""

    safe_name = name or "未命名餐廳"
    safe_tag  = tag  or "👥 在地推薦"
    safe_dist = dist_str or (addr[:20] if addr else (city[:2] if city else "附近美食"))
    safe_addr = addr[:28] if addr else ""

    body_contents = [
        {"type": "text", "text": safe_tag, "size": "xxs", "weight": "bold",
         "color": "#B8860B" if "必比登" in safe_tag else "#E65100", "margin": "none"},
        {"type": "text", "text": safe_name, "size": "md", "weight": "bold",
         "wrap": True, "maxLines": 2,
         "color": "#3D2B1F" if not eaten else "#AAAAAA", "margin": "xs"},
        {"type": "text", "text": safe_dist, "size": "xs",
         "color": "#1565C0", "wrap": False, "margin": "xs"},
    ]
    if rating_str:
        body_contents.append(
            {"type": "text", "text": rating_str, "size": "xs",
             "color": rating_color, "margin": "xs"}
        )
    if safe_addr:
        body_contents.append(
            {"type": "text", "text": safe_addr, "size": "xxs",
             "color": "#AAAAAA", "wrap": True, "maxLines": 1, "margin": "xs"}
        )

    eaten_data = f"ate:{name}:{city[:5]}"
    bubble: dict = {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "none",
            "paddingAll": "14px", "contents": body_contents,
        },
        "footer": {
            "type": "box", "layout": "vertical", "spacing": "xs", "paddingAll": "10px",
            "contents": [
                {"type": "button", "style": "primary", "height": "sm",
                 "color": "#FF6B35",
                 "action": {"type": "uri", "label": "📍 導航前往", "uri": gmap_uri}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "postback",
                            "label": "🍽 吃過這間" if not eaten else "📅 7天內去過",
                            "data": eaten_data,
                            "displayText": f"記住！{name} 吃過了"}},
            ],
        },
    }
    photo_url = ""
    if r.get("photo_ref"):
        photo_url = _places_photo_url(r["photo_ref"])
    if photo_url:
        bubble["hero"] = {
            "type": "image", "url": photo_url,
            "size": "full", "aspectRatio": "20:13", "aspectMode": "cover",
        }
    return bubble


def _get_user_city(user_id: str) -> str:
    """從 Redis 取得用戶上次使用的城市"""
    if not user_id:
        return ""
    cached = _redis_get(f"user_city:{user_id}")
    if cached and isinstance(cached, str):
        return cached
    return ""


def _set_user_city(user_id: str, city: str) -> None:
    """將用戶城市偏好存入 Redis（90 天）"""
    if user_id and city:
        _redis_set(f"user_city:{user_id}", city, ttl=86400 * 90)


def _set_user_loc(user_id: str, lat: float, lon: float) -> None:
    """存入用戶最後位置（1 天），供後續距離排序用"""
    if user_id:
        _redis_set(f"user_loc:{user_id}", f"{lat},{lon}", ttl=86400)


def _get_user_loc(user_id: str) -> tuple:
    """取得用戶最後位置，回傳 (lat, lon) 或 (None, None)"""
    if not user_id:
        return None, None
    val = _redis_get(f"user_loc:{user_id}")
    if val and "," in val:
        try:
            lat, lon = val.split(",", 1)
            return float(lat), float(lon)
        except ValueError:
            pass
    return None, None


def _btn3d(label: str, text: str, main_c: str, shadow_c: str,
           txt_c: str = "#FFFFFF", flex: int = None) -> dict:
    """3D 凸起按鈕：外層陰影色 + 內層主色，paddingBottom 露出陰影造成立體感"""
    inner = {
        "type": "box", "layout": "vertical",
        "backgroundColor": main_c, "cornerRadius": "8px",
        "paddingTop": "13px", "paddingBottom": "13px",
        "paddingStart": "8px", "paddingEnd": "8px",
        "contents": [{"type": "text", "text": label,
                       "color": txt_c, "align": "center",
                       "weight": "bold", "size": "sm", "wrap": False}],
    }
    outer = {
        "type": "box", "layout": "vertical",
        "backgroundColor": shadow_c, "cornerRadius": "10px",
        "paddingBottom": "5px",
        "action": {"type": "message", "label": label[:20], "text": text},
        "contents": [inner],
    }
    if flex is not None:
        outer["flex"] = flex
    return outer


# ─── 聚餐推薦函式 ──────────────────────────────────────

def build_group_dining_message(text: str) -> list:
    """聚餐推薦主路由"""
    text_s = text.strip()
    city_found, type_found = "", ""
    for c in _GROUP_DINING_CITIES:
        if c in text_s:
            city_found = c
            break
    for t in _GROUP_DINING_TYPES:
        if t in text_s:
            type_found = t
            break
    if city_found and type_found:
        return _build_group_result(city_found, type_found)
    if city_found:
        return _build_group_type_picker(city_found)
    return _build_group_city_picker()


def _build_group_city_picker() -> list:
    city_btns = []
    row = []
    for i, c in enumerate(_GROUP_DINING_CITIES):
        row.append({
            "type": "button", "style": "secondary", "height": "sm", "flex": 1,
            "action": {"type": "message", "label": c, "text": f"聚餐 {c}"}
        })
        if len(row) == 4 or i == len(_GROUP_DINING_CITIES) - 1:
            city_btns.append({"type": "box", "layout": "horizontal",
                               "spacing": "sm", "contents": row})
            row = []
    return [{"type": "flex", "altText": "🍽️ 聚餐餐廳推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                             "contents": [
                                 {"type": "text", "text": "🍽️ 聚餐餐廳推薦",
                                  "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                 {"type": "text", "text": "朋友聚會、家庭圓桌、公司聚餐都適用",
                                  "color": "#8892B0", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "16px",
                          "contents": [
                              {"type": "text", "text": "📍 在哪個城市聚餐？",
                               "size": "sm", "weight": "bold", "color": "#333333"},
                          ] + city_btns},
             }}]


def _build_group_type_picker(city: str) -> list:
    type_rows = []
    items = list(_GROUP_DINING_TYPES.items())
    for i in range(0, len(items), 2):
        pair = items[i:i+2]
        row_contents = []
        for t, info in pair:
            row_contents.append({
                "type": "box", "layout": "vertical", "flex": 1,
                "backgroundColor": info["color"] + "22",
                "cornerRadius": "12px", "paddingAll": "12px", "spacing": "xs",
                "action": {"type": "message", "label": t, "text": f"聚餐 {city} {t}"},
                "contents": [
                    {"type": "text", "text": info["emoji"], "size": "xxl", "align": "center"},
                    {"type": "text", "text": t, "size": "sm", "weight": "bold",
                     "align": "center", "color": info["color"]},
                    {"type": "text", "text": info["note"], "size": "xxs",
                     "align": "center", "color": "#888888", "wrap": True},
                ]
            })
        type_rows.append({"type": "box", "layout": "horizontal",
                           "spacing": "sm", "contents": row_contents})
    return [{"type": "flex", "altText": f"🍽️ {city} 聚餐類型",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                             "contents": [
                                 {"type": "text", "text": f"🍽️ {city} 聚餐",
                                  "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                 {"type": "text", "text": "想吃哪一種？",
                                  "color": "#8892B0", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "14px", "contents": type_rows},
             }}]


_GROUP_TYPE_KEYWORDS: dict[str, list[str]] = {
    "火鍋":     ["火鍋", "鍋"],
    "燒肉":     ["燒肉", "烤肉"],
    "日式":     ["日式", "壽司", "拉麵", "日本", "居酒屋", "丼"],
    "合菜台菜": ["台菜", "合菜", "客家", "熱炒"],
    "西式":     ["西式", "義大利", "法式", "美式", "西餐"],
    "熱炒":     ["熱炒", "海鮮", "快炒"],
    "港式飲茶": ["港式", "飲茶", "點心", "港點"],
    "海鮮餐廳": ["海鮮", "活魚", "漁港", "蟹", "蝦"],
    "吃到飽":  ["吃到飽", "buffet", "自助"],
    "餐酒館":  ["餐酒", "bistro", "酒吧", "bar"],
    "不限":     [],
}


def _build_group_result(city: str, dining_type: str) -> list:
    """城市 + 類型 → 必比登精選卡（依類型過濾）+ Google 高評分 + 搜尋建議卡"""
    info = _GROUP_DINING_TYPES.get(dining_type, _GROUP_DINING_TYPES["不限"])
    color = info["color"]
    emoji = info["emoji"]
    bib_pool = _BIB_GOURMAND.get(city[:2], [])
    # 依類型關鍵字過濾必比登
    kws = _GROUP_TYPE_KEYWORDS.get(dining_type, [])
    if kws and bib_pool:
        typed = [r for r in bib_pool if any(k in r.get("type", "") for k in kws)]
        bib_pool = typed if len(typed) >= 2 else bib_pool
    bib_picks = _random.sample(bib_pool, min(3, len(bib_pool))) if bib_pool else []
    # Google Places 高評分
    gp_picks: list[dict] = []
    if GOOGLE_PLACES_API_KEY:
        raw = _text_search_places(f"{city} {dining_type} 聚餐", max_results=6)
        gp_picks = [p for p in raw if (p.get("rating") or 0) >= 4.0][:3]
    query_str = _GROUP_SEARCH_TEMPLATES.get(dining_type, "{city} 聚餐").format(city=city)
    gmap_url = "https://www.google.com/maps/search/" + urllib.parse.quote(query_str)
    gmap_url_pkg = "https://maps.google.com/?q=" + urllib.parse.quote(f"{city} {dining_type} 聚餐 包廂")
    google_rank_url = f"https://www.google.com/search?q={urllib.parse.quote(f'{city} {dining_type} 聚餐 推薦 排名 必吃')}"
    walker_url  = f"https://www.walkerland.com.tw/search?keyword={urllib.parse.quote(f'{city} {dining_type} 聚餐')}&sort=rating"
    ipeen_url   = f"https://www.ipeen.com.tw/search/all/{urllib.parse.quote(city)}/0-0-0-0/1?q={urllib.parse.quote(dining_type + ' 聚餐')}"
    eztable_url = f"https://www.eztable.com.tw/restaurants/?q={urllib.parse.quote(city + ' ' + dining_type)}"
    tips = {
        "火鍋":     ["✅ 確認是否可分鍋（素食/葷食同桌）", "✅ 問有無包廂或半包廂", "✅ 人多可問有無固定套餐"],
        "燒肉":     ["✅ 確認是桌邊烤還是個人烤", "✅ 生日通常有驚喜服務，記得告知", "✅ 提前訂位，熱門店假日爆滿"],
        "日式":     ["✅ 告知有無海鮮過敏", "✅ 居酒屋通常不適合帶長輩", "✅ 高檔割烹建議事先告知人數"],
        "合菜台菜": ["✅ 確認圓桌人數上限（通常 8-12 人）", "✅ 可請店家推薦合菜套餐", "✅ 長輩場合首選"],
        "西式":     ["✅ 正式場合建議著裝整齊", "✅ 提前預約，部分店家需訂金", "✅ 問有無無麩質/素食選項"],
        "熱炒":     ["✅ 人數多可包場，記得詢問", "✅ 下酒菜齊全，適合輕鬆聚會", "✅ 結帳通常可以分開"],
        "港式飲茶": ["✅ 假日建議提早訂位，人潮多", "✅ 可請服務員推薦招牌點心", "✅ 適合長輩與家庭，氣氛輕鬆"],
        "海鮮餐廳": ["✅ 事先確認活體海鮮定價（避免爭議）", "✅ 大桌可請店家搭配合菜套餐", "✅ 訂位時告知人數方便備料"],
        "吃到飽":  ["✅ 確認結束時間，別訂太晚", "✅ 部分店家有時段限制，記得確認", "✅ 人多更划算，AA 制最方便"],
        "餐酒館":  ["✅ 多為酒水搭餐，確認不喝酒的人有無選擇", "✅ 部分需訂位，熱門時段較難臨時入場", "✅ 氣氛輕鬆，適合小聚、慶生"],
        "不限":     ["✅ 先確認人數再訂位", "✅ 有特殊需求（壽星/長輩）提前告知", "✅ 訂位時詢問有無停車場"],
    }
    tip_list = tips.get(dining_type, tips["不限"])
    tip_items = [{"type": "text", "text": t, "size": "xs",
                  "color": "#555555", "wrap": True} for t in tip_list]
    share_text = f"🍽️ {city} {dining_type} 聚餐\n朋友來找餐廳，用「生活優轉」幫你選！\n{gmap_url_pkg}"
    share_url  = "https://line.me/R/share?text=" + urllib.parse.quote(share_text)
    return [{"type": "flex", "altText": f"🍽️ {city} {dining_type} 聚餐推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                             "backgroundColor": color, "paddingAll": "16px",
                             "contents": [
                                 {"type": "text", "text": f"{emoji} {city} {dining_type} 聚餐",
                                  "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                 {"type": "text", "text": info["note"],
                                  "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                             ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "16px",
                          "contents": (
                              ([
                                  {"type": "text", "text": "🏅 必比登精選（米其林認證）",
                                   "weight": "bold", "size": "sm", "color": "#B71C1C"},
                                  {"type": "text", "text": "品質有保證，可作為聚餐起點",
                                   "size": "xs", "color": "#888888", "margin": "xs"},
                              ] + [
                                  {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                                   "action": {"type": "uri", "label": f"🏅 {r['name']}", "uri": r["url"]}}
                                  for r in bib_picks
                              ] + [{"type": "separator", "margin": "md"}])
                              if bib_picks else []
                          ) + (
                              (
                                  [{"type": "separator", "margin": "md"}] if bib_picks else []
                              ) + [
                                  {"type": "text", "text": "⭐ Google 高評分餐廳",
                                   "weight": "bold", "size": "sm", "color": "#E65100",
                                   "margin": "md"},
                                  {"type": "text", "text": "評分 4.0 以上，真實評價最可信",
                                   "size": "xs", "color": "#888888", "margin": "xs"},
                              ] + [
                                  {"type": "box", "layout": "horizontal", "spacing": "sm",
                                   "margin": "sm",
                                   "action": {"type": "uri", "label": p["name"],
                                              "uri": "https://www.google.com/maps/search/"
                                                     + urllib.parse.quote(f"{p['name']} {p.get('addr','')}")},
                                   "contents": [
                                       {"type": "text", "text": p["name"], "size": "sm",
                                        "flex": 1, "wrap": True, "color": "#1A1F3A"},
                                       {"type": "text",
                                        "text": f"⭐{p['rating']}（{p.get('user_ratings_total',0)}則）",
                                        "size": "xs", "color": "#FF9800", "flex": 0, "align": "end"},
                                   ]}
                                  for p in gp_picks
                              ] + [{"type": "separator", "margin": "md"}]
                              if gp_picks else []
                          ) + [
                              {"type": "text", "text": "📋 訂位前確認",
                               "weight": "bold", "size": "sm", "color": "#333333",
                               "margin": "md" if (bib_picks or gp_picks) else "none"},
                          ] + tip_items + [
                              {"type": "separator", "margin": "md"},
                              {"type": "text", "text": "🔍 依評價找更多餐廳",
                               "weight": "bold", "size": "sm", "color": "#333333", "margin": "md"},
                              {"type": "text", "text": "按評價排序，快速鎖定高分店家",
                               "size": "xs", "color": "#888888"},
                          ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                             "paddingAll": "12px",
                             "contents": [
                                 {"type": "button", "style": "primary", "color": color, "height": "sm",
                                  "action": {"type": "uri", "label": "⭐ 網友推薦排行", "uri": google_rank_url}},
                                 {"type": "button", "style": "primary", "color": color, "height": "sm",
                                  "action": {"type": "uri", "label": f"🗺️ Google Maps 找{dining_type}", "uri": gmap_url}},
                                 {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                                      "action": {"type": "uri", "label": "📝 窩客島評價", "uri": walker_url}},
                                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                                      "action": {"type": "uri", "label": "📅 EZTABLE訂位", "uri": eztable_url}},
                                 ]},
                                 {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                                      "action": {"type": "uri", "label": "🍽️ 愛評網", "uri": ipeen_url}},
                                 ]},
                                 {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                                     {"type": "button", "style": "link", "flex": 1, "height": "sm",
                                      "action": {"type": "message", "label": "← 換類型", "text": f"聚餐 {city}"}},
                                     {"type": "button", "style": "link", "flex": 1, "height": "sm",
                                      "action": {"type": "uri", "label": "📤 揪朋友", "uri": share_url}},
                                 ]},
                             ]},
             }}]


# ─── 必比登函式 ──────────────────────────────────────────

def build_bib_gourmand_flex(area: str = "") -> list:
    """米其林必比登推薦"""
    area2 = area[:2] if area else ""
    pool = _BIB_GOURMAND.get(area2, [])
    if not pool:
        cities = list(_BIB_GOURMAND.keys())
        buttons = [
            {"type": "button", "style": "primary", "color": "#B71C1C", "height": "sm",
             "action": {"type": "message", "label": f"🏅 {c}", "text": f"必比登 {c}"}}
            for c in cities
        ]
        return [{"type": "flex", "altText": "米其林必比登推介",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#B71C1C",
                                "contents": [
                                    {"type": "text", "text": "🏅 米其林必比登推介",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    {"type": "text", "text": "每餐 NT$1,000 以內的超值好味道",
                                     "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                              "contents": [
                                  {"type": "text", "text": "選擇城市 👇", "size": "sm", "color": "#555555"},
                              ] + buttons},
                 }}]

    bib_key = f"bib_{area2}"
    last_bib = set(_food_recent.get(bib_key, []))
    fresh_bib = [p for p in pool if p["name"] not in last_bib]
    if len(fresh_bib) < 5:
        fresh_bib = pool
    picks = _random.sample(fresh_bib, min(5, len(fresh_bib)))
    _food_recent[bib_key] = [p["name"] for p in picks]

    color = "#B71C1C"
    items = []
    for i, r in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"🏅 {r['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3, "wrap": True},
                {"type": "text", "text": r["type"], "size": "xxs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": r.get("desc", ""), "size": "xs",
             "color": "#555555", "margin": "xs"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": _maps_url(r["name"], area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍",
                            "text": f"回報 好吃 {r['name']}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌",
                            "text": f"回報 倒閉 {r['name']}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    return [{"type": "flex", "altText": f"必比登推介 — {area2}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏅 必比登推介（{area2}）",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "米其林認證 · 每餐 NT$1,000 以內",
                                 "color": "#FFCDD2", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"必比登 {area2}"}},
                         {"type": "button", "style": "secondary", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍽️ 回主選單",
                                                      "text": "今天吃什麼"}},
                     ]},
                 ]},
             }}]


# ─── 回饋函式 ──────────────────────────────────────────

def handle_food_feedback(text: str, user_id: str = "") -> list:
    """處理使用者對餐廳的回饋（好吃/倒閉），並推播通知開發者"""
    ts = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    if "好吃" in text:
        shop = text.replace("回報", "").replace("好吃", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "good", "time": ts})
        if ADMIN_USER_ID:
            push_message(ADMIN_USER_ID, [{"type": "text",
                "text": f"👍 使用者回報好吃\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"👍 感謝推薦！已記錄「{shop}」為好吃店家 🎉\n"
                 f"你的回饋會幫助其他使用者找到更好的餐廳！"}]
    elif "倒閉" in text or "歇業" in text:
        shop = text.replace("回報", "").replace("倒閉", "").replace("歇業", "").strip()
        _FEEDBACK_LOG.append({"shop": shop, "type": "closed", "time": ts})
        if ADMIN_USER_ID:
            push_message(ADMIN_USER_ID, [{"type": "text",
                "text": f"❌ 使用者回報歇業\n店家：{shop}\n時間：{ts}\nUID：{user_id[:10]}..."}])
        return [{"type": "text", "text":
                 f"❌ 感謝回報！已標記「{shop}」可能歇業 📝\n"
                 f"我們會在下次更新時確認並移除，謝謝你！"}]
    return []


def build_feedback_intro() -> list:
    """顯示回饋/許願引導卡片"""
    return [{"type": "flex", "altText": "💡 許願 & 回報",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#6C5CE7", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "💡 許願池 & 問題回報",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "20px",
                          "contents": [
                              {"type": "text", "text": "想要新功能？遇到問題？都可以告訴我！",
                               "wrap": True, "size": "sm", "color": "#555555"},
                              {"type": "separator", "margin": "md"},
                              {"type": "text", "text": "✨ 許願（想要新功能）", "weight": "bold",
                               "size": "sm", "margin": "md", "color": "#6C5CE7"},
                              {"type": "text", "wrap": True, "size": "xs", "color": "#888888",
                               "text": "建議 希望有記帳功能\n建議 天氣可以顯示紫外線"},
                              {"type": "text", "text": "🐛 回報（功能異常）", "weight": "bold",
                               "size": "sm", "margin": "md", "color": "#E74C3C"},
                              {"type": "text", "wrap": True, "size": "xs", "color": "#888888",
                               "text": "回報 吃什麼沒反應\n回報 天氣顯示錯誤"},
                          ]},
             }}]


def handle_general_report(text: str, user_id: str = "") -> list:
    """處理通用回報，推播通知開發者"""
    ts = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    content = text.replace("回報", "").strip()
    if len(content) < 2:
        return build_feedback_intro()
    if any(w in content for w in ["bug", "壞", "錯誤", "失敗", "沒反應", "當掉", "跑不出來", "無法", "不能"]):
        tag = "🐛 Bug"
    elif any(w in content for w in ["慢", "卡", "lag", "等很久", "超時", "timeout"]):
        tag = "🐌 效能"
    else:
        tag = "📋 回報"
    if ADMIN_USER_ID:
        push_message(ADMIN_USER_ID, [{"type": "flex", "altText": f"{tag} 使用者回報",
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {"type": "box", "layout": "vertical",
                           "backgroundColor": "#E74C3C", "paddingAll": "16px",
                           "contents": [
                               {"type": "text", "text": f"{tag} 使用者回報",
                                "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                           ]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md",
                         "paddingAll": "20px",
                         "contents": [
                             {"type": "text", "text": content, "wrap": True, "size": "md", "weight": "bold"},
                             {"type": "separator", "margin": "md"},
                             {"type": "box", "layout": "vertical", "margin": "md", "spacing": "sm",
                              "contents": [
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"👤 {user_id[:10]}..."},
                                  {"type": "text", "size": "xs", "color": "#888888", "text": f"🕐 {ts}"},
                              ]},
                         ]},
            }}])
    return [{"type": "text", "text": f"📋 收到你的回報！\n\n「{content}」\n\n已通知開發者，會盡快處理 🙏"}]


def handle_user_suggestion(text: str, user_id: str, display_name: str = "") -> list:
    """處理使用者功能建議，推播通知給開發者"""
    ts = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    content = text
    for kw in ["建議", "許願", "功能建議", "我想要", "希望有", "回饋"]:
        content = content.replace(kw, "").strip()
    if len(content) < 2:
        return build_feedback_intro()
    reply = [{"type": "text", "text":
              f"💡 收到你的建議！\n\n「{content}」\n\n已送達開發者，感謝你讓生活優轉變得更好 🙏"}]
    if ADMIN_USER_ID:
        name_str = f"（{display_name}）" if display_name else ""
        push_message(ADMIN_USER_ID, [{"type": "flex", "altText": "💡 新功能建議",
            "contents": {
                "type": "bubble", "size": "mega",
                "header": {"type": "box", "layout": "vertical",
                           "backgroundColor": "#6C5CE7", "paddingAll": "16px",
                           "contents": [
                               {"type": "text", "text": "💡 新功能建議",
                                "color": "#FFFFFF", "size": "lg", "weight": "bold"}
                           ]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md",
                         "paddingAll": "20px",
                         "contents": [
                             {"type": "text", "text": content, "wrap": True, "size": "md", "weight": "bold"},
                             {"type": "separator", "margin": "md"},
                             {"type": "box", "layout": "vertical", "margin": "md", "spacing": "sm",
                              "contents": [
                                  {"type": "text", "size": "xs", "color": "#888888",
                                   "text": f"👤 {user_id[:10]}...{name_str}"},
                                  {"type": "text", "size": "xs", "color": "#888888", "text": f"🕐 {ts}"},
                              ]},
                         ]},
            }}])
    return reply


# ─── 食物推薦函式 ──────────────────────────────────────

def build_food_flex(style: str, area: str = "") -> list:
    """隨機挑 3 道推薦，依時段過濾，避免與上次重複"""
    pool = _FOOD_DB.get(style, _FOOD_DB["便當"])
    period, meal_label = _tw_meal_period()
    filtered = _filter_food_by_time(pool, period, city=area[:2] if area else "")
    last = set(_food_recent.get(style, []))
    fresh = [p for p in filtered if p["name"] not in last]
    if len(fresh) < 3:
        fresh = filtered
    picks = _random.sample(fresh, min(3, len(fresh)))
    # 記住最近 2 批（6 個）避免重複
    prev = _food_recent.get(style, [])
    _food_recent[style] = (prev + [p["name"] for p in picks])[-6:]
    area_label = f"（{area}附近）" if area else ""
    colors = {"台式早餐": "#F57F17", "便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00",
              "火鍋": "#D32F2F", "日韓": "#1565C0", "早午餐": "#FF8F00",
              "飲料甜點": "#6A1B9A", "輕食": "#2E7D32", "燒烤": "#BF360C", "夜市小吃": "#37474F"}
    color = colors.get(style, "#FF8C42")
    icons = {"台式早餐": "🥚", "便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗",
             "燒烤": "🔥", "夜市小吃": "🌙"}
    icon = icons.get(style, "🍽️")
    items = []
    for i, p in enumerate(picks):
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {p['name']}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 3},
                {"type": "text", "text": p["price"], "size": "xs",
                 "color": "#888888", "flex": 1, "align": "end"},
            ]},
            {"type": "text", "text": p["desc"], "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📍 Google Maps 搜附近",
                        "uri": _maps_url(p["key"], area, open_now=True)}},
        ]
        if i < len(picks)-1:
            items.append({"type": "separator", "margin": "sm"})
    _style_list = list(_FOOD_DB.keys())
    _si = _style_list.index(style) if style in _style_list else 0
    next_style = _style_list[(_si + 1) % len(_style_list)]
    _share_names = "、".join([p["name"] for p in picks])
    _share_text = (f"🍽️ 今天吃{style}！\n推薦：{_share_names}\n\n"
                   f"用「生活優轉」3秒決定吃什麼 👆")
    _share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
    return [{"type": "flex", "altText": f"今天吃什麼 — {icon}{style}版",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🍽️ {meal_label}{area_label}",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": f"{icon} {style}版推薦",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": color, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                                      "text": f"吃什麼 {style} {area}"}},
                         {"type": "button", "style": "primary", "color": "#1A1F3A", "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": f"換{next_style}版",
                                                      "text": f"吃什麼 {next_style} {area}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🌤️ 今日天氣", "text": "天氣"}},
                         {"type": "button", "style": "link", "flex": 1, "height": "sm",
                          "action": {"type": "message", "label": "🗓️ 近期活動", "text": "周末去哪"}},
                     ]},
                     {"type": "button", "style": "link", "height": "sm",
                      "action": {"type": "uri", "label": "📤 分享推薦給朋友", "uri": _share_url}},
                 ]},
             }}]


def build_food_restaurant_flex(area: str, food_type: str = "", user_id: str = "") -> list:
    """從觀光署餐廳資料推薦在地餐廳；有上次位置時按距離由近到遠排序"""
    import math as _math

    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000
        p = _math.pi / 180
        a = (0.5 - _math.cos((lat2 - lat1) * p) / 2
             + _math.cos(lat1 * p) * _math.cos(lat2 * p)
             * (1 - _math.cos((lon2 - lon1) * p)) / 2)
        return 2 * R * _math.asin(_math.sqrt(a))

    area2 = area[:2] if area else ""
    pool = _RESTAURANT_CACHE.get(area, _RESTAURANT_CACHE.get(area2, []))
    if not pool:
        return build_food_flex("便當", area)
    if food_type:
        typed = [r for r in pool if food_type in r.get("type", "")]
        if len(typed) >= 3:
            pool = typed

    # 有上次位置 → 優先用 Google Places Nearby Search 取真實附近餐廳
    u_lat, u_lon = _get_user_loc(user_id) if user_id else (None, None)
    if u_lat and u_lon:
        kw = f"餐廳 {food_type}" if food_type else "餐廳 小吃 美食"
        gp = _nearby_places(u_lat, u_lon, radius=2000, keyword=kw)
        if len(gp) >= 3:
            picks = []
            for r in gp[:5]:
                rating = r.get("rating", 0)
                cnt = r.get("user_ratings_total", 0)
                desc = f"評分 {rating}⭐（{cnt} 則評價）" if rating else ""
                picks.append({
                    "name": r["name"], "type": "其他",
                    "desc": desc, "addr": r.get("addr", ""), "town": "",
                    "lat": r["lat"], "lng": r["lng"],
                    "place_id": r.get("place_id", ""),
                })
        else:
            # Google Places 沒結果 → fallback 按距離篩快取
            with_dist = []
            no_dist = []
            for r in pool:
                if r.get("lat") and r.get("lng"):
                    d = _haversine(u_lat, u_lon, float(r["lat"]), float(r["lng"]))
                    with_dist.append((d, r))
                else:
                    no_dist.append(r)
            with_dist.sort(key=lambda x: x[0])
            picks = [r for _, r in with_dist[:5]]
            if len(picks) < 5:
                picks += _random.sample(no_dist, min(5 - len(picks), len(no_dist)))
    else:
        rest_key = f"rest_{area}_{food_type}"
        last_rest = set(_food_recent.get(rest_key, []))
        fresh_rest = [p for p in pool if p["name"] not in last_rest]
        if len(fresh_rest) < 5:
            fresh_rest = pool
        picks = _random.sample(fresh_rest, min(5, len(fresh_rest)))
        _food_recent[rest_key] = [p["name"] for p in picks]
    period, meal_label = _tw_meal_period()
    area_label = f"（{area}）" if area else ""
    color = "#6D4C41"
    type_icons = {
        "中式": "🍚", "日式": "🍣", "西式": "🍝", "素食": "🥬",
        "海鮮": "🦐", "小吃": "🧆", "火鍋": "🍲", "地方特產": "⭐", "其他": "🍴",
    }
    items = []
    for i, r in enumerate(picks):
        rtype = r.get("type", "其他")
        icon = type_icons.get(rtype, "🍴")
        desc_raw = r.get("desc", "")
        desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
        addr = r.get("addr", "")
        town = r.get("town", "")
        sub_info = f"{icon}{rtype}"
        if town:
            sub_info += f" · {town}"
        # 有距離時顯示
        if u_lat and u_lon and r.get("lat") and r.get("lng"):
            dist_m = _haversine(u_lat, u_lon, float(r["lat"]), float(r["lng"]))
            walk_min = max(1, round(dist_m / 80))
            dist_label = (f"步行約{walk_min}分（{int(dist_m)}m）"
                          if dist_m < 1000 else f"步行約{walk_min}分（{dist_m/1000:.1f}km）")
            sub_info += f"  📍{dist_label}"
        rname = r['name']
        items += [
            {"type": "text", "text": f"• {rname}", "weight": "bold",
             "size": "sm", "color": color, "wrap": True, "maxLines": 2},
            {"type": "text", "text": sub_info, "size": "xxs", "color": "#888888", "margin": "xs"},
            {"type": "text", "text": desc, "size": "xs", "color": "#555555", "wrap": True,
             "margin": "xs", "maxLines": 2} if desc else {"type": "filler"},
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                {"type": "button", "style": "link", "height": "sm", "flex": 3,
                 "action": {"type": "uri", "label": "📍 導航",
                            "uri": _maps_url(rname, area2, open_now=True)}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "👍", "text": f"回報 好吃 {rname}"}},
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": "❌", "text": f"回報 倒閉 {rname}"}},
            ]},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})
    available_types = list({r.get("type", "") for r in _RESTAURANT_CACHE.get(area, _RESTAURANT_CACHE.get(area2, []))})
    type_buttons = []
    for t in ["小吃", "中式", "日式", "海鮮", "火鍋"][:3]:
        if t in available_types:
            type_buttons.append(
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": f"{type_icons.get(t,'🍴')} {t}",
                            "text": f"餐廳 {t} {area}"}}
            )
    footer_contents = [
        {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
            {"type": "button", "style": "primary", "color": color, "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🔄 再換一組",
                                         "text": f"餐廳 {food_type} {area}"}},
            {"type": "button", "style": "secondary", "flex": 1,
             "height": "sm", "action": {"type": "message", "label": "🍽️ 品項推薦",
                                         "text": f"吃什麼 便當 {area}"}},
        ]},
    ]
    if type_buttons:
        footer_contents.append(
            {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": type_buttons}
        )
    return [{"type": "flex", "altText": f"在地餐廳推薦{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🏪 {meal_label}{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text",
                                 "text": "在地餐廳推薦" + (f" · {food_type}" if food_type else ""),
                                 "color": "#FFFFFFCC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": footer_contents},
             }}]


def build_live_food_events(area: str) -> list:
    """從 Accupass 快取拉吃喝玩樂即時活動（給「本週美食活動」用）"""
    area2 = area[:2] if area else ""
    city_cache = _get_accupass_cache().get(area, _get_accupass_cache().get(area2, {}))
    events = city_cache.get("吃喝玩樂", [])
    if not events:
        return []
    picks = events[:4]
    color = "#D84315"
    _OFFICIAL_DOMAINS = (
        "accupass.com", "kktix.com", "kktix.cc",
        "huashan1914.com", "pier2.org", "tnam.museum",
        ".gov.tw", "travel.taipei", "culture.tw",
    )

    def _is_official_url(url: str) -> bool:
        return any(d in url for d in _OFFICIAL_DOMAINS)

    items = []
    for i, e in enumerate(picks):
        url = e.get("url", "")
        source_label = e.get("source", "")
        show_source = source_label and (not url or not _is_official_url(url))
        link_uri = url if url else "https://www.accupass.com"
        items += [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"{i+1}. {e.get('name','')}", "weight": "bold",
                 "size": "sm", "color": color, "flex": 4, "wrap": True},
                {"type": "text", "text": "🆕", "size": "xs", "color": "#888888", "flex": 0},
            ]},
            {"type": "text", "text": e.get("desc", ""), "size": "xs",
             "color": "#555555", "wrap": True, "margin": "xs"},
            *([ {"type": "text", "text": f"來源：{source_label}", "size": "xxs",
                 "color": "#AAAAAA", "margin": "xs"} ] if show_source else []),
            {"type": "button", "style": "link", "height": "sm",
             "action": {"type": "uri", "label": "📅 查看活動詳情", "uri": link_uri}},
        ]
        if i < len(picks) - 1:
            items.append({"type": "separator", "margin": "sm"})

    area_label = f"（{area}）" if area else ""
    return [{"type": "flex", "altText": f"本週美食活動{area_label}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🎉 本週美食活動{area_label}",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "Accupass 即時更新 · 吃喝玩樂精選",
                                 "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": items},
                 "footer": {"type": "box", "layout": "vertical", "contents": [
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": "🍽️ 回到今天吃什麼",
                                 "text": "今天吃什麼"}},
                 ]},
             }}]


def build_food_menu(city: str = "", user_id: str = "") -> list:
    """今天吃什麼 — 主選單（精簡 4 按鈕版）"""
    if user_id:
        _redis_set(f"food_locate:{user_id}", "1", ttl=180)
    period, meal_label = _tw_meal_period()
    suf = f" {city}" if city else ""
    city2 = city[:2] if city else ""
    meal_hints = {
        "M": "輕一點最美味 ☕",
        "D": "飽足感第一 🍱",
        "N": "好好犒賞自己 🎉",
        "L": "消夜就要簡單吃 🌙",
    }
    hint = meal_hints.get(period, "外食族救星！")
    header_sub = f"{city2} · {hint}" if city2 else hint
    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#E65100",
                     "paddingTop": "22px", "paddingBottom": "18px", "paddingAll": "20px",
                     "contents": [
                         {"type": "text", "text": "🍜 今天吃什麼？",
                          "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                         {"type": "text", "text": f"{meal_label} · {header_sub}",
                          "color": "#FFD0B0", "size": "sm", "margin": "sm", "wrap": True},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "16px", "spacing": "md",
                     "contents": [
                         _btn3d("🎲 幫我決定！（隨機推薦）",
                                f"吃什麼 隨機{suf}", "#27AE60", "#1A6E35"),
                         _btn3d("📍 分享位置，推薦附近美食",
                                "📍 我要分享位置找美食", "#1565C0", "#0A3D8A"),
                         {"type": "separator", "margin": "md", "color": "#E0E0E0"},
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                              _btn3d("🍽️ 選類型", f"吃什麼 選類型{suf}",
                                     "#BF360C", "#7A1F05", flex=1),
                              _btn3d("🏅 評鑑推薦", f"吃什麼 特殊需求{suf}",
                                     "#6A1B9A", "#3E0B6B", flex=1),
                          ]},
                     ]},
             }}]


def build_food_type_picker(city: str = "") -> list:
    """第二層：選類型（依早/午/晚/消夜四時段調整順序與標題）"""
    period, meal_label = _tw_meal_period()
    suf = f" {city}" if city else ""
    _period_cfg = {
        "M": (["台式早餐", "早午餐", "輕食",    "飲料甜點"],
              "☀️ 早餐時間，吃好一點開始今天"),
        "D": (["便當",    "麵食",   "小吃",    "日韓", "輕食", "飲料甜點", "火鍋"],
              "🌞 午餐時間，飽足感優先"),
        "N": (["火鍋",    "日韓",   "燒烤",    "麵食", "小吃", "飲料甜點"],
              "🌙 晚餐時間，好好犒賞自己"),
        "L": (["夜市小吃", "麵食",   "火鍋",    "日韓", "飲料甜點"],
              "🌃 消夜時間，簡單吃就好"),
    }
    order, hint = _period_cfg.get(period, _period_cfg["D"])
    _row_colors = [
        ("#D84315", "#8A2400"),
        ("#6D4C41", "#3E2723"),
        ("#37474F", "#1C3039"),
    ]
    rows = []
    for ri, i in enumerate(range(0, len(order), 3)):
        chunk = order[i:i+3]
        mc, sc = _row_colors[min(ri, len(_row_colors) - 1)]
        rows.append({"type": "box", "layout": "horizontal", "spacing": "sm",
                     "contents": [_btn3d(k, f"吃什麼 {k}{suf}", mc, sc, flex=1)
                                   for k in chunk]})
    return [{"type": "flex", "altText": "選類型推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#BF360C",
                     "paddingAll": "16px", "paddingTop": "18px",
                     "contents": [
                         {"type": "text", "text": f"🍽️ {meal_label} — 選類型",
                          "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                         {"type": "text", "text": hint,
                          "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "12px", "spacing": "sm",
                     "contents": rows + [
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "← 回主選單",
                                     "text": f"今天吃什麼{suf}"}},
                     ]},
             }}]


def build_food_special_picker(city: str = "") -> list:
    """第二層：精選評鑑（必比登 / 在地餐廳 / 聚餐 / 美食活動）"""
    suf = f" {city}" if city else ""
    return [{"type": "flex", "altText": "精選評鑑推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "hero": {
                     "type": "box", "layout": "vertical",
                     "backgroundColor": "#4A148C",
                     "paddingAll": "16px", "paddingTop": "18px",
                     "contents": [
                         {"type": "text", "text": "🏅 精選評鑑推薦",
                          "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                         {"type": "text", "text": "評鑑認可 / 多人聚餐 / 近期美食活動",
                          "color": "#CE93D8", "size": "xs", "margin": "xs"},
                     ]},
                 "body": {
                     "type": "box", "layout": "vertical", "paddingAll": "12px", "spacing": "sm",
                     "contents": [
                         _btn3d("⭐ 必比登", f"必比登{suf}", "#E65100", "#8A3000"),
                         {"type": "box", "layout": "horizontal", "spacing": "sm",
                          "contents": [
                              _btn3d("🍻 多人聚餐", "聚餐", "#C62828", "#7B1515", flex=1),
                              _btn3d("🎪 美食活動", "本週美食活動", "#6A1B9A", "#3E0B6B", flex=1),
                          ]},
                         _btn3d("🌏 地方特色小吃", f"地方特色{suf}", "#00695C", "#003D36"),
                         {"type": "button", "style": "link", "height": "sm",
                          "action": {"type": "message", "label": "← 回主選單",
                                     "text": f"今天吃什麼{suf}"}},
                     ]},
             }}]


def build_city_specialties(city: str) -> list:
    """第一步：城市特色清單（點按後搜名店）"""
    city2 = city[:2] if city else ""
    season = _tw_season(city2)
    pool = _CITY_SPECIALTIES.get(city, _CITY_SPECIALTIES.get(city2, []))
    if not pool:
        return build_food_restaurant_flex(city)
    items = [p for p in pool if p.get("s", "") in ("", season)]
    if not items:
        items = pool

    def _bubble(item):
        tag = ("🌞 夏季限定" if item.get("s") == "hot"
               else ("🧥 冬季限定" if item.get("s") == "cold" else "🗺️ 在地特色"))
        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#1A1F3A", "paddingAll": "10px",
                "contents": [
                    {"type": "text", "text": item["name"],
                     "color": "#FFFFFF", "size": "md", "weight": "bold", "wrap": True},
                    {"type": "text", "text": tag,
                     "color": "#8892B0", "size": "xxs", "margin": "xs"},
                ]},
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "12px",
                "contents": [
                    {"type": "text", "text": item["desc"],
                     "size": "sm", "color": "#444444", "wrap": True},
                ]},
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "10px",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#FF6B35", "height": "sm",
                     "action": {"type": "message", "label": "🏆 找名店推薦",
                                "text": f"特色名店 {city2} {item['name']}"}},
                ]},
        }

    bubbles = [_bubble(item) for item in items[:8]]
    return [{"type": "flex", "altText": f"{city2} 特色美食",
             "contents": {"type": "carousel", "contents": bubbles}}]


_STYLE_GPLACE_KW: dict = {
    "台式早餐": "早餐店 豆漿 蛋餅",
    "便當":   "便當店 自助餐",
    "麵食":   "麵食 牛肉麵 湯麵",
    "小吃":   "小吃 台式料理",
    "火鍋":   "火鍋",
    "日韓":   "日式料理 韓式料理",
    "早午餐": "早午餐 brunch 咖啡廳",
    "飲料甜點": "飲料店 甜點咖啡",
    "輕食":   "輕食 健康餐 沙拉",
    "燒烤":   "燒烤 烤肉",
    "夜市小吃": "夜市 鹽酥雞 滷味",
}
_STYLE_ICON: dict = {
    "台式早餐": "🥚", "便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
    "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗",
    "燒烤": "🔥", "夜市小吃": "🌙",
}


def build_food_real_restaurants(style: str, city: str, user_id: str = "") -> list:
    """使用者明確指定食物類型 → Google Places 搜附近真實店家"""
    city2 = city[:2] if city else ""
    kw = _STYLE_GPLACE_KW.get(style, style)
    icon = _STYLE_ICON.get(style, "🍽️")
    u_lat, u_lon = _get_user_loc(user_id) if user_id else (None, None)

    if u_lat and u_lon and GOOGLE_PLACES_API_KEY:
        places = _nearby_places(u_lat, u_lon, radius=2000, keyword=kw)
    elif GOOGLE_PLACES_API_KEY:
        places = _text_search_places(f"{city2} {kw}", max_results=5)
    else:
        places = []

    if not places:
        return build_food_flex(style, city)  # fallback 靜態建議

    eaten_set: set = set()
    bubbles = []
    for r in places[:5]:
        b = _build_restaurant_bubble(r, u_lat, u_lon, city2, eaten_set,
                                     subtitle=f"{icon} 附近{style}")
        bubbles.append(b)
    return [{"type": "flex", "altText": f"{style}推薦 {city2}",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_specialty_shops(city: str, food_name: str) -> list:
    """第二步：用 Google Places Text Search 搜該城市的食物名店"""
    city2 = city[:2] if city else ""
    query = f"{city2} {food_name}"
    shops = _text_search_places(query, max_results=5)
    if not shops:
        gmap_uri = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}/"
        return [{"type": "text",
                 "text": f"搜尋「{query}」名店中...\n目前無法取得即時資料，點下方連結用 Google Maps 搜尋 👇\n{gmap_uri}"}]
    eaten_set: set = set()
    bubbles = []
    for r in shops:
        r["dist"] = None
        b = _build_restaurant_bubble(r, None, None, city2, eaten_set,
                                     subtitle=f"🏆 {city2}{food_name}名店")
        bubbles.append(b)
    return [{"type": "flex", "altText": f"{query} 名店推薦",
             "contents": {"type": "carousel", "contents": bubbles}}]


# ─── 地區/城市選擇器 ──────────────────────────────────────

def _build_food_entry_region_picker(user_id: str = "") -> list:
    """今天吃什麼 — 分享位置優先，備用地區選擇"""
    if user_id:
        _redis_set(f"food_locate:{user_id}", "1", ttl=180)
    keys = list(_AREA_REGIONS.keys())
    region_rows = []
    for i in range(0, len(keys), 3):
        row_btns = [
            {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
             "action": {"type": "message", "label": r, "text": f"今天吃什麼 選城市 {r}"}}
            for r in keys[i:i+3]
        ]
        region_rows.append({"type": "box", "layout": "horizontal",
                             "spacing": "sm", "contents": row_btns})
    _quick_items = [
        {"type": "action", "action": {"type": "location", "label": "📍 分享我的位置"}},
        {"type": "action", "action": {"type": "message", "label": "北部", "text": "今天吃什麼 選城市 北部"}},
        {"type": "action", "action": {"type": "message", "label": "中部", "text": "今天吃什麼 選城市 中部"}},
        {"type": "action", "action": {"type": "message", "label": "南部", "text": "今天吃什麼 選城市 南部"}},
        {"type": "action", "action": {"type": "message", "label": "東部離島", "text": "今天吃什麼 選城市 東部離島"}},
    ]
    return [{"type": "flex", "altText": "今天吃什麼？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "🍽️ 今天吃什麼？",
                                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                {"type": "text", "text": "分享位置，秒推 1.5km 內美食地圖",
                                 "color": "#FFCCAA", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "14px",
                          "contents": [
                              {"type": "button", "style": "primary", "color": "#E65100",
                               "action": {"type": "message",
                                          "label": "📍 分享位置，立即推薦附近美食",
                                          "text": "📍 我要分享位置找美食"}},
                              {"type": "separator"},
                              {"type": "text", "text": "或選擇地區", "size": "xs",
                               "color": "#AAAAAA", "align": "center"},
                              *region_rows,
                          ]},
             },
             "quickReply": {"items": _quick_items}}]


def _build_food_entry_city_picker(region: str) -> list:
    """今天吃什麼（無城市）— 第二步：選城市"""
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    rows = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        rows.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"今天吃什麼 {a}"}}
                for a in row
            ]
        })
    rows.append(
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "message", "label": "← 重選地區", "text": "今天吃什麼"}}
    )
    return [{"type": "flex", "altText": f"{region} — 選擇城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": "#E65100",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": f"🍽️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": rows},
             }}]


def build_food_region_picker(style: str) -> list:
    """今天吃什麼 — 選擇地區（第一步）"""
    colors = {"台式早餐": "#F57F17", "便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00",
              "火鍋": "#D32F2F", "日韓": "#1565C0", "早午餐": "#FF8F00",
              "飲料甜點": "#6A1B9A", "輕食": "#2E7D32", "燒烤": "#BF360C",
              "夜市小吃": "#37474F", "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    icons = {"台式早餐": "🥚", "便當": "🍱", "麵食": "🍜", "小吃": "🥘", "火鍋": "🍲",
             "日韓": "🍣", "早午餐": "☕", "飲料甜點": "🧋", "輕食": "🥗",
             "燒烤": "🔥", "夜市小吃": "🌙", "餐廳": "🏪"}
    icon = icons.get(style, "🍽️")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    regions = list(_AREA_REGIONS.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"{trigger} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"你在哪個地區？{icon}{style}推薦",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🍽️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的{icon} {style}美食",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_food_area_picker(style: str, region: str = "") -> list:
    """今天吃什麼 — 選擇城市（第二步）"""
    colors = {"台式早餐": "#F57F17", "便當": "#C62828", "麵食": "#E65100", "小吃": "#F57C00",
              "火鍋": "#D32F2F", "日韓": "#1565C0", "早午餐": "#FF8F00",
              "飲料甜點": "#6A1B9A", "輕食": "#2E7D32", "燒烤": "#BF360C",
              "夜市小吃": "#37474F", "餐廳": "#6D4C41"}
    color = colors.get(style, "#E65100")
    trigger = "餐廳" if style == "餐廳" else f"吃什麼 {style}"
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"{trigger} {a}"}}
                for a in row
            ]
        })
    buttons.append(
        {"type": "button", "style": "link", "height": "sm",
         "action": {"type": "message", "label": "← 重選地區", "text": trigger}}
    )
    return [{"type": "flex", "altText": f"{region}有哪些城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🍽️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


# ─── 主路由 ──────────────────────────────────────────────

def build_food_message(text: str, user_id: str = None) -> list:
    """今天吃什麼 — 主路由"""
    text_s = text.strip()

    # ── 解析區域（支援全台 22 縣市）──
    area = ""
    all_cities_pat = "|".join(_ALL_CITIES)
    area_match = re.search(rf'({all_cities_pat})\S{{0,6}}', text_s)
    if area_match:
        area = area_match.group(0)
        _set_user_city(user_id, area[:2])
    area_city = area[:2] if area else ""

    # ── 若用戶沒指定城市，自動帶入上次使用的城市 ──
    if not area_city and user_id:
        saved = _get_user_city(user_id)
        if saved:
            area_city = saved
            area = saved

    # ── 解析地區（北部/中部/南部/東部離島）──
    region = ""
    for r in _AREA_REGIONS:
        if r in text_s:
            region = r
            break

    # ── 必比登推介 ──
    if "必比登" in text_s or "米其林" in text_s:
        return build_bib_gourmand_flex(area)

    # ── 在地餐廳路由 ──
    is_restaurant = "餐廳" in text_s or "在地餐廳" in text_s
    if is_restaurant:
        food_type = ""
        for ft in ["小吃", "中式", "日式", "西式", "海鮮", "火鍋", "素食", "地方特產"]:
            if ft in text_s:
                food_type = ft
                break
        if area_city:
            return build_food_restaurant_flex(area_city, food_type, user_id=user_id)
        if region:
            return build_food_area_picker("餐廳", region)
        return build_food_region_picker("餐廳")

    # ── 隨機推薦（幫我決定 / 隨機 / 隨便）──
    if any(w in text_s for w in ["隨機", "幫我決定", "隨便吃", "不知道吃什麼"]):
        _rand_pool = (
            ["早午餐", "輕食", "飲料甜點"]
            if _tw_meal_period()[0] == "M"
            else ["便當", "麵食", "小吃", "火鍋", "日韓", "輕食"]
        )
        return build_food_flex(_random.choice(_rand_pool), area_city)

    # ── 解析食物類型 ──
    style = ""
    for cat, kws in _STYLE_KEYWORDS.items():
        if any(w in text_s for w in kws):
            style = cat
            break
    if not style:
        style = "便當"

    # ── 本週美食活動（Accupass 即時）──
    if "本週美食" in text_s or "美食活動" in text_s:
        if not area_city and region:
            areas = _AREA_REGIONS.get(region, [])
            buttons = []
            for i in range(0, len(areas), 3):
                row = areas[i:i+3]
                buttons.append({"type": "box", "layout": "horizontal", "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                         "action": {"type": "message", "label": a, "text": f"本週美食活動 {a}"}}
                        for a in row
                    ]})
            return [{"type": "flex", "altText": f"本週美食活動 — {region}",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": f"🎉 {region} — 選城市",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        if not area_city:
            buttons = [
                {"type": "button", "style": "primary", "color": "#D84315", "height": "sm",
                 "action": {"type": "message", "label": f"📍 {r}",
                            "text": f"本週美食活動 地區 {r}"}}
                for r in _AREA_REGIONS.keys()
            ]
            return [{"type": "flex", "altText": "本週美食活動 — 選地區",
                     "contents": {"type": "bubble", "size": "mega",
                         "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                    "contents": [
                                        {"type": "text", "text": "🎉 本週美食活動",
                                         "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                        {"type": "text", "text": "選擇地區查看近期美食活動",
                                         "color": "#FFCCBC", "size": "xs", "margin": "xs"},
                                    ]},
                         "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                                  "contents": buttons},
                     }}]
        live_area = area_city
        result = build_live_food_events(live_area)
        if result:
            return result
        return [{"type": "flex", "altText": f"{live_area}目前沒有美食活動",
                 "contents": {
                     "type": "bubble", "size": "mega",
                     "header": {"type": "box", "layout": "vertical", "backgroundColor": "#D84315",
                                "contents": [
                                    {"type": "text", "text": f"🎉 {live_area} 美食活動",
                                     "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                ]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text", "text": f"目前 {live_area} 沒有近期美食活動 😢",
                          "size": "sm", "color": "#555555", "wrap": True},
                         {"type": "text", "text": "試試其他方式找好吃的 👇",
                          "size": "xs", "color": "#888888", "margin": "sm"},
                     ]},
                     "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                         {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                             {"type": "button", "style": "primary", "color": "#6D4C41", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "在地餐廳",
                                                          "text": f"餐廳 {live_area}"}},
                             {"type": "button", "style": "primary", "color": "#C62828", "flex": 1,
                              "height": "sm", "action": {"type": "message", "label": "享樂版推薦",
                                                          "text": f"吃什麼 享樂 {live_area}"}},
                         ]},
                         {"type": "button", "style": "secondary", "height": "sm",
                          "action": {"type": "message", "label": "回主選單", "text": "今天吃什麼"}},
                     ]},
                 }}]

    # ── 分享位置快捷 ──
    if "我要分享位置找美食" in text_s:
        if user_id:
            _redis_set(f"food_locate:{user_id}", "1", ttl=180)
        return [{
            "type": "text",
            "text": "好的！請分享你的位置，我馬上幫你找附近美食 📍",
            "quickReply": {
                "items": [
                    {"type": "action", "action": {"type": "location", "label": "📍 分享我的位置"}},
                ]
            }
        }]

    # ── 純呼叫主選單 ──
    _food_bare = ["今天吃什麼", "晚餐吃什麼", "午餐吃什麼", "吃什麼", "晚餐推薦", "午餐推薦"]
    if any(text_s == b or text_s.startswith(b + " ") or text_s.startswith(b + "\n")
           for b in _food_bare):
        _sel_match = re.search(r'選城市\s+(' + '|'.join(_AREA_REGIONS.keys()) + r')', text_s)
        if _sel_match:
            return _build_food_entry_city_picker(_sel_match.group(1))
        if "選類型" in text_s:
            return build_food_type_picker(area_city)
        if "特殊需求" in text_s:
            return build_food_special_picker(area_city)
        if "地方特色" in text_s:
            if area_city:
                return build_city_specialties(area_city)
            return build_food_special_picker("")
        explicit_style = style and (style != "便當" or "便當" in text_s)
        if explicit_style and area_city:
            return build_food_real_restaurants(style, area_city, user_id or "")
        if area_city:
            return build_food_menu(city=area_city, user_id=user_id or "")
        return _build_food_entry_region_picker(user_id or "")

    # ── 有風格 + 有城市 → 直接推薦 ──
    if area:
        return build_food_real_restaurants(style, area, user_id or "")

    # ── 有風格 + 有地區 → 選城市 ──
    if region:
        return build_food_area_picker(style, region)

    # ── 有風格但沒城市 → 先問地區 ──
    has_style_kw = style != "便當" or any(w in text_s for w in ["便當"])
    is_internal = text_s.startswith("吃什麼 ")
    if has_style_kw and not is_internal:
        return build_food_region_picker(style)

    return build_food_real_restaurants(style, area, user_id or "") if area else build_food_flex(style, area)
