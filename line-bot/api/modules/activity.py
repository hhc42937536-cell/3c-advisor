from __future__ import annotations

"""近期活動推薦模組

提供以下公開介面：
    build_activity_message(text, user_id=None)  ← 主路由，webhook 呼叫此函式
    build_activity_flex(category, area="")
    build_activity_menu(city="")
    build_activity_region_picker(category)
    build_activity_area_picker(category, region="")
    build_activity_city_picker(category="")
"""

import datetime as _dt
import json
import os
import re
import urllib.parse

from utils.redis import redis_set as _redis_set_raw

# ── LINE Bot ID（用於分享連結）──
LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")


# ── Redis 包裝（與 webhook.py 一致的 _redis_set 介面）──
def _redis_set(key: str, value, ttl: int = 300) -> None:
    """存值到 Upstash Redis（JSON），ttl 秒後過期"""
    _redis_set_raw(key, value, ttl=ttl)


# ─── 近期活動推薦 ──────────────────────────────────────

def _load_accupass_cache() -> dict:
    """載入 Accupass 爬蟲快取（accupass_cache.json）"""
    try:
        # 從 api/ 上一層找 accupass_cache.json
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_path = os.path.join(base, "accupass_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", {})
    except Exception:
        return {}


_ACCUPASS_CACHE = None  # lazy-loaded on first use（省冷啟動時間）


def _get_accupass_cache() -> dict:
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        _ACCUPASS_CACHE = _load_accupass_cache()
    return _ACCUPASS_CACHE


_ACTIVITY_DB = {
    "戶外踏青": [
        # 台北
        {"name": "陽明山國家公園", "desc": "火山地形、花海、登山步道，四季皆宜", "area": "台北"},
        {"name": "象山步道", "desc": "101 正面視角、夕陽夜景，市區就能爬山", "area": "台北"},
        {"name": "貓空纜車", "desc": "搭纜車俯瞰台北盆地，終點喝茶超愜意", "area": "台北"},
        {"name": "北投溫泉親水公園", "desc": "免費泡腳、溪流戲水，家庭週末好去處", "area": "台北"},
        # 新北
        {"name": "九份老街", "desc": "山城夜景、紅燈籠、芋圓必吃", "area": "新北"},
        {"name": "北海岸野柳地質公園", "desc": "女王頭、奇岩怪石，地球奇景就在台灣", "area": "新北"},
        {"name": "平溪天燈老街", "desc": "放天燈許願、瀑布健行，超浪漫", "area": "新北"},
        {"name": "福隆海水浴場", "desc": "沙雕節、衝浪、烤肉，北部最棒沙灘", "area": "新北"},
        # 台中
        {"name": "大雪山森林遊樂區", "desc": "賞鳥天堂、帝雉、黑長尾雉出沒", "area": "台中"},
        {"name": "福壽山農場", "desc": "蘋果園、高山蔬菜，秋冬楓紅超美", "area": "台中"},
        {"name": "武陵農場", "desc": "春天賞櫻第一名，溪流釣魚也很棒", "area": "台中"},
        {"name": "高美濕地", "desc": "夕陽倒影、風車海景，台中最美景點", "area": "台中"},
        # 台南
        {"name": "七股鹽山", "desc": "鹽田生態、台灣鹽博物館，老少皆宜", "area": "台南"},
        {"name": "曾文水庫", "desc": "南台灣最大水庫，環湖步道、湖光山色", "area": "台南"},
        {"name": "烏山頭水庫風景區", "desc": "八田與一紀念園區、環湖自行車道", "area": "台南"},
        {"name": "虎頭埤風景區", "desc": "划船、環湖步道，台南人的後花園", "area": "台南"},
        {"name": "走馬瀨農場", "desc": "露營、草皮、飛行傘，南部最大農場", "area": "台南"},
        {"name": "關子嶺溫泉", "desc": "泥漿溫泉全台唯一，泡完皮膚超好", "area": "台南"},
        # 高雄
        {"name": "壽山自然公園", "desc": "獼猴、海景步道、市區旁輕鬆踏青", "area": "高雄"},
        {"name": "茂林國家風景區", "desc": "紫蝶幽谷、峽谷瀑布，南台灣秘境", "area": "高雄"},
        {"name": "桃源區梅山", "desc": "春天梅花盛開，高山部落景致迷人", "area": "高雄"},
        {"name": "旗山老街", "desc": "香蕉之鄉、巴洛克建築、香蕉冰必吃", "area": "高雄"},
        # 其他縣市
        {"name": "太平山國家森林遊樂區", "desc": "雲海、檜木林、原始森林，超療癒", "area": "宜蘭"},
        {"name": "合歡山", "desc": "高山草原、冬天賞雪，壯觀視野", "area": "南投"},
        {"name": "日月潭環湖", "desc": "腳踏車環湖、船遊水社，湖光山色", "area": "南投"},
        {"name": "花蓮太魯閣", "desc": "峽谷地形、步道健行，台灣最壯觀景點", "area": "花蓮"},
        {"name": "墾丁國家公園", "desc": "海灘、珊瑚礁、熱帶風情，全年可玩", "area": "屏東"},
        {"name": "阿里山森林鐵路", "desc": "雲海、神木、日出，台灣高山代表", "area": "嘉義"},
        {"name": "奮起湖", "desc": "老街、森林鐵路便當，小鎮氛圍超好", "area": "嘉義"},
        {"name": "司馬庫斯部落", "desc": "巨木群、神木步道，遠離塵囂的秘境", "area": "新竹"},
        {"name": "清境農場", "desc": "高山牧場、歐式風情、雲霧繚繞", "area": "南投"},
    ],
    "文青咖啡": [
        # 台北
        {"name": "赤峰街商圈", "desc": "台北文青聖地，老屋改造咖啡廳密集", "area": "台北"},
        {"name": "富錦街", "desc": "台北最美林蔭道，歐式咖啡廳 + 選品店", "area": "台北"},
        {"name": "永康街商圈", "desc": "台北最有味道的老街，咖啡廳 + 書店", "area": "台北"},
        {"name": "松山文創園區", "desc": "老煙草工廠、設計展覽、咖啡廳", "area": "台北"},
        {"name": "華山1914文創園區", "desc": "酒廠改造、展演空間、假日市集超熱鬧", "area": "台北"},
        {"name": "中山站咖啡廳一條街", "desc": "從中山站到雙連，全台咖啡密度最高", "area": "台北"},
        # 台中
        {"name": "審計新村", "desc": "台中文創聚落，週末市集 + 質感小店", "area": "台中"},
        {"name": "台中第四信用合作社", "desc": "老銀行改造的質感咖啡廳，必拍打卡點", "area": "台中"},
        {"name": "范特喜微創文化", "desc": "貨櫃屋文創市集，小店密集超好逛", "area": "台中"},
        {"name": "忠信市場", "desc": "老市場改造藝文空間，展覽 + 咖啡", "area": "台中"},
        {"name": "草悟道", "desc": "台中最美大道，咖啡廳 + 書店連成一線", "area": "台中"},
        # 台南
        {"name": "神農街", "desc": "台南百年老街、文創小店、咖啡廳林立", "area": "台南"},
        {"name": "藍晒圖文創園區", "desc": "台南文創地標，特色商店 + 裝置藝術", "area": "台南"},
        {"name": "台南林百貨", "desc": "日治時代百貨，頂樓神社 + 文創選品", "area": "台南"},
        {"name": "正興街", "desc": "巷弄小店密集，老宅咖啡 + 創意甜點", "area": "台南"},
        {"name": "海安路藝術街", "desc": "街頭壁畫藝術、酒吧咖啡廳，文青必訪", "area": "台南"},
        {"name": "孔廟文化園區周邊", "desc": "府城老街巷弄，老宅咖啡 + 文史空間", "area": "台南"},
        {"name": "水交社文化園區", "desc": "眷村改造、黑膠咖啡、文化展覽", "area": "台南"},
        # 高雄
        {"name": "駁二藝術特區", "desc": "高雄港邊倉庫改造，藝術展覽 + 咖啡", "area": "高雄"},
        {"name": "前金老街咖啡廳群", "desc": "高雄文青新聚落，老屋改造咖啡超密集", "area": "高雄"},
        {"name": "新濱碼頭老街", "desc": "港口旁百年街區，老屋咖啡 + 文史散步", "area": "高雄"},
        {"name": "鹽埕區老街", "desc": "高雄最老商圈，懷舊風格小店 + 咖啡廳", "area": "高雄"},
        # 其他
        {"name": "勝利星村", "desc": "屏東眷村改造，慢活咖啡 + 特色小店", "area": "屏東"},
        {"name": "三峽老街", "desc": "清朝古厝、牛角麵包、悠閒午後", "area": "新北"},
        {"name": "鹿港老街", "desc": "鳳眼糕、蚵仔煎、台灣傳統工藝小鎮", "area": "彰化"},
        {"name": "大溪老街", "desc": "日式建築、豆干名產、桃園文青好去處", "area": "桃園"},
    ],
    "親子同樂": [
        # 台北
        {"name": "臺灣科學教育館", "desc": "互動展覽、科學實驗，小孩最愛", "area": "台北"},
        {"name": "兒童新樂園", "desc": "遊樂設施、摩天輪、週末親子首選", "area": "台北"},
        {"name": "故宮博物院", "desc": "翠玉白菜、肉形石，帶孩子認識台灣歷史", "area": "台北"},
        {"name": "台北市立天文科學教育館", "desc": "天象儀、太陽望遠鏡，假日免費開放", "area": "台北"},
        {"name": "台北市立動物園", "desc": "貓熊、無尾熊、企鵝館，半天玩不完", "area": "台北"},
        # 台中
        {"name": "麗寶樂園", "desc": "遊樂園 + 水樂園，暑假必去", "area": "台中"},
        {"name": "國立自然科學博物館", "desc": "恐龍、太空、生命科學館，必去", "area": "台中"},
        {"name": "台中兒童藝術館", "desc": "0-12歲互動展覽，雨天親子首選", "area": "台中"},
        # 台南
        {"name": "台南市立動物園", "desc": "免費入場、動物種類多，台南親子必去", "area": "台南"},
        {"name": "南科考古館", "desc": "8000年前遺址、古代生活互動體驗", "area": "台南"},
        {"name": "奇美博物館", "desc": "歐式建築、藝術 + 自然史展覽，台南必去", "area": "台南"},
        {"name": "台南市兒童交通安全公園", "desc": "兒童模擬開車、騎車，寓教於樂免費入場", "area": "台南"},
        {"name": "台灣歷史博物館", "desc": "台灣史互動展覽，適合國小以上小孩", "area": "台南"},
        # 高雄
        {"name": "義大遊樂世界", "desc": "高雄最大樂園，刺激設施超豐富", "area": "高雄"},
        {"name": "科工館（國立科學工藝博物館）", "desc": "科技互動展，假日親子活動多", "area": "高雄"},
        {"name": "夢時代購物中心（摩天輪）", "desc": "室內逛街 + 頂樓摩天輪，雨天也能玩", "area": "高雄"},
        # 其他
        {"name": "海生館（國立海洋生物博物館）", "desc": "全台最大水族館，企鵝 + 鯊魚超壯觀", "area": "屏東"},
        {"name": "新竹市立動物園", "desc": "全台最老動物園，小而美，免費入場", "area": "新竹"},
        {"name": "小人國主題樂園", "desc": "縮小版台灣景點模型，孩子玩一整天", "area": "桃園"},
        {"name": "礁溪溫泉公園", "desc": "免費泡腳池、戶外溫泉廣場，親子輕鬆遊", "area": "宜蘭"},
    ],
    "運動健身": [
        # 台北
        {"name": "大安森林公園", "desc": "台北市中心綠洲，跑步 + 戶外瑜伽", "area": "台北"},
        {"name": "大佳河濱公園", "desc": "腳踏車道、跑步步道、河岸風光", "area": "台北"},
        {"name": "關渡自然公園", "desc": "賞鳥 + 自行車，兼顧運動與自然生態", "area": "台北"},
        {"name": "象山步道", "desc": "爬完可以看101夜景，市區最佳運動路線", "area": "台北"},
        # 台中
        {"name": "大坑登山步道", "desc": "台中都市裡的健行天堂，1-10號難度各異", "area": "台中"},
        {"name": "東豐自行車綠廊", "desc": "舊鐵道改造，景色優美，適合全家", "area": "台中"},
        {"name": "后豐鐵馬道", "desc": "鐵橋 + 自行車道，接連東豐，風景漂亮", "area": "台中"},
        # 台南
        {"name": "台南都會公園", "desc": "慢跑步道、單車道、生態池，南部最大公園", "area": "台南"},
        {"name": "安平運動公園", "desc": "環境清幽、器材完善，早晨運動首選", "area": "台南"},
        {"name": "成功大學榕園（開放時段）", "desc": "百年榕樹慢跑步道，文青感十足", "area": "台南"},
        {"name": "鹽水八角樓自行車道", "desc": "古蹟騎乘路線，欣賞在地農村風光", "area": "台南"},
        # 高雄
        {"name": "愛河自行車道", "desc": "高雄愛河沿岸，夜晚也很美", "area": "高雄"},
        {"name": "左營蓮池潭", "desc": "環潭慢跑、龍虎塔打卡，假日熱鬧", "area": "高雄"},
        {"name": "旗津海岸公園", "desc": "沙灘慢跑、風車、海景，高雄週末好去處", "area": "高雄"},
        {"name": "澄清湖", "desc": "環湖自行車道 + 散步，高雄最大淡水湖", "area": "高雄"},
        # 其他
        {"name": "羅東運動公園", "desc": "草皮廣大、慢跑步道、湖畔風景優美", "area": "宜蘭"},
        {"name": "集集綠色隧道", "desc": "樟樹林蔭大道，騎車穿越超愜意", "area": "南投"},
        {"name": "新店碧潭", "desc": "泛舟 + 吊橋散步，台北近郊輕運動", "area": "新北"},
        {"name": "虎頭山公園", "desc": "桃園輕鬆爬山、視野好，假日常見跑者", "area": "桃園"},
    ],
    "吃喝玩樂": [
        # 台北
        {"name": "士林夜市", "desc": "台灣最大夜市，必吃大餅包小餅、士林大香腸", "area": "台北"},
        {"name": "饒河街觀光夜市", "desc": "台北知名夜市，胡椒餅不能錯過", "area": "台北"},
        {"name": "寧夏夜市", "desc": "蚵仔煎、古早味豬血糕、台北最在地夜市", "area": "台北"},
        {"name": "通化夜市", "desc": "天津蔥抓餅發源地，台北南區必逛", "area": "台北"},
        # 台中
        {"name": "逢甲夜市", "desc": "台中最熱鬧夜市，創意小吃層出不窮", "area": "台中"},
        {"name": "忠孝夜市", "desc": "台中在地人去的夜市，平價好吃不觀光", "area": "台中"},
        {"name": "一中商圈", "desc": "學生聚集地、手搖飲 + 小吃密集", "area": "台中"},
        # 台南
        {"name": "花園夜市", "desc": "台南最大夜市，週四六日才有，必訪", "area": "台南"},
        {"name": "林森夜市", "desc": "台南在地人才知道的夜市，不觀光不踩雷", "area": "台南"},
        {"name": "武聖夜市", "desc": "週二四日開，推薦蚵仔麵線和鹽酥雞", "area": "台南"},
        {"name": "大東夜市", "desc": "週一三五開，台南最多元的夜市", "area": "台南"},
        {"name": "安平老街", "desc": "蚵仔酥、蝦餅、劍獅伴手禮一條買齊", "area": "台南"},
        {"name": "赤崁樓周邊小吃", "desc": "擔仔麵、棺材板、杏仁豆腐，府城精華", "area": "台南"},
        # 高雄
        {"name": "六合夜市", "desc": "高雄觀光夜市，海鮮 + 在地小吃", "area": "高雄"},
        {"name": "瑞豐夜市", "desc": "高雄在地人愛去的夜市，週末才開", "area": "高雄"},
        {"name": "鳳山商圈夜市", "desc": "鳳山在地小吃激戰區，隱藏版美食多", "area": "高雄"},
        {"name": "三鳳中街", "desc": "南北雜貨批發街，年節前必來掃貨", "area": "高雄"},
        # 其他
        {"name": "廟口夜市", "desc": "基隆海鮮小吃集中地，天婦羅、鼎邊銼必吃", "area": "基隆"},
        {"name": "羅東夜市", "desc": "宜蘭特色小吃，三星蔥餅、卜肉超好吃", "area": "宜蘭"},
        {"name": "新竹城隍廟商圈", "desc": "貢丸湯、米粉炒，新竹小吃一次掃完", "area": "新竹"},
        {"name": "嘉義文化路夜市", "desc": "雞肉飯、火雞肉飯，嘉義人的驕傲", "area": "嘉義"},
    ],
    "市集展覽": [
        # 台北
        {"name": "華山文創市集", "desc": "設計師手作、藝術品、文創選物，假日必逛", "area": "台北"},
        {"name": "松菸誠品市集", "desc": "選品質感高、獨立品牌集中，台北文青首選", "area": "台北"},
        {"name": "台北當代藝術館", "desc": "當代藝術展覽，老建築新靈魂", "area": "台北"},
        {"name": "信義公民會館假日市集", "desc": "農夫市集 + 手作小物，親子友善", "area": "台北"},
        # 台中
        {"name": "審計新村週末市集", "desc": "文創小物、手作甜點、台中最有氣質市集", "area": "台中"},
        {"name": "國立台灣美術館", "desc": "免費入場，常設展 + 特展輪替，台中必去", "area": "台中"},
        {"name": "台中市集（草悟廣場）", "desc": "戶外市集、街頭表演，週末活力滿點", "area": "台中"},
        {"name": "台中文創園區（舊酒廠）", "desc": "台中文化部文創園區，不定期市集與展覽", "area": "台中"},
        {"name": "興大有機農夫市集", "desc": "每週六在中興大學，有機蔬果 + 手作食品", "area": "台中"},
        {"name": "豐原廟東創意市集", "desc": "老廟前的創意小攤，在地特色小物與小吃", "area": "台中"},
        {"name": "台中市纖維工藝博物館", "desc": "纖維與布藝主題展覽，特展常態輪替", "area": "台中"},
        {"name": "勤美術館週末展覽", "desc": "草悟道旁的戶外藝術裝置 + 期間特展", "area": "台中"},
        # 台南
        {"name": "藍晒圖文創園區市集", "desc": "週末小市集、手作體驗、台南文青聖地", "area": "台南"},
        {"name": "台南文化中心特展", "desc": "各類主題展覽，適合全家親子同遊", "area": "台南"},
        {"name": "神農街週末創意市集", "desc": "府城老街手作市集，在地藝術家聚集", "area": "台南"},
        {"name": "奇美博物館特展", "desc": "藝術 + 自然史，台南最高規格展覽空間", "area": "台南"},
        {"name": "台南美術館", "desc": "南美館1館+2館，台南藝術新地標", "area": "台南"},
        # 高雄
        {"name": "駁二藝術特區特展", "desc": "港邊倉庫展覽空間，藝術裝置輪替不重複", "area": "高雄"},
        {"name": "高雄市立美術館", "desc": "免費入場，戶外雕塑公園 + 室內特展", "area": "高雄"},
        {"name": "衛武營藝術文化中心", "desc": "國家級表演廳，也有免費戶外展演", "area": "高雄"},
        {"name": "三鳳中街文創市集", "desc": "傳統與文創融合，高雄獨特市集體驗", "area": "高雄"},
        # 其他
        {"name": "宜蘭傳統藝術中心", "desc": "傳統工藝、老街、假日表演，親子必去", "area": "宜蘭"},
        {"name": "嘉義鐵道藝術村", "desc": "舊倉庫改造，藝術展覽 + 創意市集", "area": "嘉義"},
    ],
    "表演音樂": [
        # 台北
        {"name": "台北小巨蛋", "desc": "大型演唱會主場地，各大歌手常駐", "area": "台北"},
        {"name": "國家音樂廳", "desc": "古典樂、交響樂、歌劇，殿堂級表演", "area": "台北"},
        {"name": "Legacy Taipei", "desc": "中型演唱會、獨立樂團首選場地", "area": "台北"},
        {"name": "河岸留言", "desc": "台北獨立音樂聖地，每週末都有現場演出", "area": "台北"},
        {"name": "The Wall", "desc": "搖滾、indie 音樂，台灣地下音樂重鎮", "area": "台北"},
        # 台中
        {"name": "台中國家歌劇院", "desc": "世界級建築、高規格表演，台中驕傲", "area": "台中"},
        {"name": "Legacy Taichung", "desc": "台中版 Legacy，中型演唱會場地", "area": "台中"},
        {"name": "中山堂（台中）", "desc": "平價演出、在地樂團，接地氣的表演場所", "area": "台中"},
        # 台南
        {"name": "台南文化中心演藝廳", "desc": "台南最大表演廳，各類演出都有", "area": "台南"},
        {"name": "衛屋茶事（文化沙龍）", "desc": "小型音樂會、說書、台南慢生活體驗", "area": "台南"},
        {"name": "甲仙阿里山音樂節", "desc": "戶外音樂祭，南台灣年度盛事", "area": "台南"},
        {"name": "台南人劇團", "desc": "台灣最活躍劇團之一，實驗劇場演出", "area": "台南"},
        # 高雄
        {"name": "衛武營國家藝術文化中心", "desc": "南台灣最大表演場館，音樂劇、芭蕾、演唱會", "area": "高雄"},
        {"name": "駁二大義倉庫", "desc": "戶外演唱會、市集音樂節，港邊最佳氛圍", "area": "高雄"},
        {"name": "春天吶喊（墾丁）", "desc": "台灣最大搖滾音樂祭，每年春假必去", "area": "屏東"},
        # 其他
        {"name": "海洋音樂祭（貢寮）", "desc": "夏天在海邊聽搖滾，全台最熱血音樂節", "area": "新北"},
        {"name": "簡單生活節", "desc": "台北年度生活風格音樂祭，文青必去", "area": "台北"},
    ],
}


def _maps_url(keyword: str, area: str = "", **_kw) -> str:
    """產生 Google Maps 搜尋連結"""
    if area:
        q = urllib.parse.quote(f"{area} {keyword}")
    else:
        q = urllib.parse.quote(f"{keyword} 附近")
    return f"https://www.google.com/maps/search/{q}/"


def _set_user_city(user_id: str, city: str) -> None:
    """將用戶城市偏好存入 Redis（90 天）"""
    if user_id and city:
        _redis_set(f"user_city:{user_id}", city, ttl=86400 * 90)


def _parse_event_date(date_str: str):
    """解析活動日期字串，回傳 date 物件；失敗回傳 None"""
    if not date_str:
        return None
    # 支援範圍格式：取結束日期（例如 "04/10-04/13" 取 "04/13"）
    range_m = re.search(r'(\d{1,2})[/\-.](\d{1,2})\s*[~～\-–]\s*(\d{1,2})[/\-.](\d{1,2})', date_str)
    if range_m:
        try:
            end_date = _dt.date(
                _dt.date.today().year,
                int(range_m.group(3)), int(range_m.group(4))
            )
            return end_date
        except ValueError:
            pass
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%m/%d", "%m.%d"):
        try:
            cleaned = re.split(r'[\s(（~～]', date_str)[0].strip()
            d = _dt.datetime.strptime(cleaned, fmt)
            if fmt in ("%m/%d", "%m.%d"):
                d = d.replace(year=_dt.date.today().year)
            return d.date()
        except ValueError:
            continue
    return None


def _is_event_past(date_str: str) -> bool:
    """判斷活動是否已過期（結束日在 3 天前以上）
    - 3 天緩衝：保留本週末還在進行的活動
    - 無日期 → 保留（可能是長期展覽）
    - 超過 60 天前開始且無明確結束日 → 視為過期
    """
    today = _dt.date.today()
    d = _parse_event_date(date_str)
    if d is None:
        return False  # 無法解析 → 保留
    # 超過 3 天前（含）視為過期
    return d < (today - _dt.timedelta(days=3))


def _parse_event_weekday(date_str: str) -> str:
    """嘗試從活動日期字串解析星期幾，回傳 '五'/'六'/'日' 或空字串"""
    if not date_str:
        return ""
    d = _parse_event_date(date_str)
    if d:
        return {4: "五", 5: "六", 6: "日"}.get(d.weekday(), "")
    # 嘗試從括號裡直接抓 (六) (日) 等
    m = re.search(r'[（(]([\u4e00-\u9fff])[)）]', date_str)
    if m and m.group(1) in ("五", "六", "日"):
        return m.group(1)
    return ""


def _get_coming_weekend_label() -> str:
    """回傳最近週末的日期標示，例如 '4/11(五)–4/13(日)'"""
    today = _dt.date.today()
    wd = today.weekday()  # 0=Mon
    days_until_fri = (4 - wd) % 7
    if days_until_fri == 0 and wd == 4:
        days_until_fri = 0
    elif wd in (5, 6):
        days_until_fri = 0  # 已經是週末
    fri = today + _dt.timedelta(days=days_until_fri)
    if wd == 5:
        fri = today - _dt.timedelta(days=1)
    elif wd == 6:
        fri = today - _dt.timedelta(days=2)
    sun = fri + _dt.timedelta(days=2)
    return f"{fri.month}/{fri.day}(五)–{sun.month}/{sun.day}(日)"


# 全台 22 縣市分區
_AREA_REGIONS = {
    "北部": ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部": ["台中", "彰化", "南投", "雲林"],
    "南部": ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}
_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]


def build_activity_flex(category: str, area: str = "") -> list:
    """列出所有活動推薦（即時＋推薦景點），用 carousel 多頁呈現"""
    area2 = area[:2] if area else ""

    # ── 1. 從 Accupass 快取取得即時活動 ──
    live_events = []
    skipped_past = 0
    _ac = _get_accupass_cache()
    if _ac and area2:
        city_cache = _ac.get(area, _ac.get(area2, {}))
        live_raw = city_cache.get(category, [])
        for e in live_raw:
            date_str = e.get("date", "")
            # ── 過濾已過期活動（結束日在 3 天前以上）──
            if _is_event_past(date_str):
                skipped_past += 1
                continue
            day_label = _parse_event_weekday(date_str)
            date_short = date_str.split(" ")[0] if date_str else ""
            event_date = _parse_event_date(date_str)  # 用於排序
            live_events.append({
                "name":       e.get("name", ""),
                "desc":       e.get("desc", ""),
                "area":       area,
                "url":        e.get("url", ""),
                "is_live":    True,
                "day":        day_label,
                "date_short": date_short,
                "_date":      event_date,   # 內部排序用，不顯示
            })
    if skipped_past:
        print(f"[activity] 過濾掉 {skipped_past} 筆已過期活動")

    # ── 2. 從靜態資料庫取得推薦景點 ──
    static_pool = _ACTIVITY_DB.get(category, [])
    if area2:
        static_filtered = [a for a in static_pool if area2 in a.get("area", "")]
        if not static_filtered:
            static_filtered = static_pool
    else:
        static_filtered = static_pool

    live_names = {e["name"] for e in live_events}
    static_dedup = [e for e in static_filtered if e["name"] not in live_names]

    colors = {
        "戶外踏青": "#2E7D32", "文青咖啡": "#4527A0", "親子同樂": "#E65100",
        "運動健身": "#1565C0", "吃喝玩樂": "#C62828",
        "市集展覽": "#6A1B9A", "表演音樂": "#AD1457",
    }
    color = colors.get(category, "#FF8C42")
    area_label = f"（{area}）" if area else ""
    cats = list(_ACTIVITY_DB.keys())
    next_cat = cats[(cats.index(category) + 1) % len(cats)]  # noqa: F841
    weekend_label = _get_coming_weekend_label()

    # ── 3. 即時活動依日期由近到遠排序（無日期排最後）──
    _far_future = _dt.date(2099, 12, 31)
    live_events.sort(key=lambda x: x.get("_date") or _far_future)

    # ── 4. 建立 bubble 內容項目的 helper ──
    def _make_items(acts: list) -> list:
        items = []
        for i, act in enumerate(acts):
            is_live = act.get("is_live", False)
            date_info = act.get("date_short", "")
            day_info = act.get("day", "")
            if is_live and date_info:
                tag = f"🆕 {date_info}"
            elif is_live and day_info:
                tag = f"🆕 週{day_info}"
            elif is_live:
                tag = "🔄 進行中"   # 無明確日期 → 長期展覽/持續活動
            else:
                tag = "📌 推薦"
            detail_btn = (
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📅 活動頁面",
                            "uri": act.get("url") or "https://www.accupass.com"}}
                if is_live else
                {"type": "button", "style": "link", "height": "sm", "flex": 1,
                 "action": {"type": "uri", "label": "📍 地圖",
                            "uri": _maps_url(act["name"], act.get("area", ""))}}
            )
            # 分享文字：這個活動 + bot 邀請（壓短避免超過 LINE URI 1000 字元限制）
            _act_name = act["name"][:20]
            _act_date = act.get("date_short") or (f"週{act.get('day','')}" if act.get("day") else "")
            _date_str = f" {_act_date}" if _act_date else ""
            _invite = f"\n👉 搜「生活優轉」也來查" if not LINE_BOT_ID else f"\nhttps://line.me/ti/p/{LINE_BOT_ID}"
            _share_raw = f"📍 揪你去！\n🎪 {_act_name}{_date_str}{_invite}"
            _share_url_act = "https://line.me/R/share?text=" + urllib.parse.quote(_share_raw)
            share_btn = {"type": "button", "style": "link", "height": "sm", "flex": 1,
                         "action": {"type": "uri", "label": "📤 揪朋友去", "uri": _share_url_act}}

            # 截短描述，避免某頁撐太高導致其他頁留白
            desc_raw = act.get("desc", "")
            desc = (desc_raw[:40] + "…") if len(desc_raw) > 42 else desc_raw
            items += [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": f"• {act['name']}", "weight": "bold",
                     "size": "sm", "color": color, "flex": 4, "wrap": True,
                     "maxLines": 2},
                    {"type": "text", "text": tag, "size": "xxs",
                     "color": "#888888", "flex": 2, "align": "end"},
                ]},
                {"type": "text", "text": desc, "size": "xs",
                 "color": "#555555", "wrap": True, "margin": "xs",
                 "maxLines": 2},
                {"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": [detail_btn, share_btn]},
            ]
            if i < len(acts) - 1:
                items.append({"type": "separator", "margin": "sm"})
        return items

    def _make_bubble(title_line2: str, acts: list, is_first: bool = False) -> dict:
        bubble = {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                *([ {"type": "text", "text": f"{category} — {weekend_label}",
                                     "color": "#8892B0", "size": "xs", "margin": "xs"} ] if is_first else []),
                                {"type": "text", "text": title_line2,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                     "contents": _make_items(acts)},
        }
        return bubble

    # ── 5. 合併即時＋靜態，一起分頁 ──
    bubbles = []
    MAX_PER_BUBBLE = 8

    # 即時活動：每分類每城市上限 10 筆，每 8 筆一頁
    live_capped = live_events[:10]
    if live_capped:
        for chunk_start in range(0, len(live_capped), MAX_PER_BUBBLE):
            chunk = live_capped[chunk_start:chunk_start + MAX_PER_BUBBLE]
            label = "🆕 近期活動"
            if len(live_capped) > MAX_PER_BUBBLE:
                page = chunk_start // MAX_PER_BUBBLE + 1
                label += f"（{page}）"
            bubbles.append(_make_bubble(label, chunk, is_first=(len(bubbles) == 0)))

    # 靜態推薦景點：只取前 5 個
    if static_dedup:
        top_static = static_dedup[:5]
        bubbles.append(_make_bubble("📌 推薦景點", top_static, is_first=(len(bubbles) == 0)))

    # 最後一個 bubble 加上 footer 導航按鈕
    if bubbles:
        # 分享文字（壓短避免超過 LINE URI 1000 字元限制）
        _share_acts = (live_events[:2] or static_dedup[:2])
        _share_names = "、".join([e['name'][:12] for e in _share_acts])
        _invite = f"\nhttps://line.me/ti/p/{LINE_BOT_ID}" if LINE_BOT_ID else "\n👉 搜「生活優轉」"
        _share_text = f"🗓️ {area_label}好去處！\n{_share_names}{_invite}"
        _act_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_share_text)
        _cat_icons = {
            "戶外踏青": "🌿", "文青咖啡": "☕", "親子同樂": "👶",
            "運動健身": "🏃", "吃喝玩樂": "🍜", "市集展覽": "🎨", "表演音樂": "🎵",
        }
        _other_cats = [c for c in cats if c != category]
        _area_suf = f" {area}" if area else ""
        # 每3個一排
        _cat_rows = []
        for i in range(0, len(_other_cats), 3):
            chunk = _other_cats[i:i+3]
            _cat_rows.append({
                "type": "box", "layout": "horizontal", "spacing": "xs",
                "contents": [
                    {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                     "action": {"type": "message",
                                "label": f"{_cat_icons.get(c,'')} {c}",
                                "text": f"周末 {c}{_area_suf}"}}
                    for c in chunk
                ]
            })
        bubbles[-1]["footer"] = {
            "type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "text", "text": "換個類型看看 👇",
                 "size": "xs", "color": "#888888", "margin": "sm"},
                *_cat_rows,
                {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "message", "label": "← 回選單",
                                "text": "周末去哪"}},
                    {"type": "button", "style": "link", "flex": 1, "height": "sm",
                     "action": {"type": "uri", "label": "📤 分享",
                                "uri": _act_share_url}},
                ]},
            ]}

    # 如果完全沒有活動
    if not bubbles:
        bubbles = [{
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                       "contents": [
                           {"type": "box", "layout": "vertical", "width": "4px",
                            "cornerRadius": "4px", "backgroundColor": color, "contents": []},
                           {"type": "box", "layout": "vertical", "flex": 1,
                            "paddingStart": "12px", "contents": [
                                {"type": "text", "text": f"🗓️ 近期活動{area_label}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": f"目前 {area} 沒有找到 {category} 相關活動",
                 "size": "sm", "color": "#555555", "wrap": True},
            ]},
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                 "action": {"type": "message", "label": "← 回選單", "text": "周末去哪"}},
            ]},
        }]

    if len(bubbles) == 1:
        return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
                 "contents": bubbles[0]}]
    return [{"type": "flex", "altText": f"近期活動 — {category}{area_label}",
             "contents": {"type": "carousel", "contents": bubbles}}]


def build_activity_menu(city: str = "") -> list:
    """近期活動 — 主選單"""
    ACCENT = "#5C6BC0"
    suf = f" {city}" if city else ""
    city_hint = f"📍 {city} — 選一個你想玩的類型 👇" if city else "選一個你想玩的類型 👇"
    return [{"type": "flex", "altText": "近期活動",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A",
                            "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": "🗓️ 近期活動？",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "幫你找好玩的地方！",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "backgroundColor": "#FFFFFF",
                          "contents": [
                     {"type": "text", "text": city_hint,
                      "size": "sm", "color": "#1A1F3A", "weight": "bold", "wrap": True},
                     {"type": "text", "text": "也可以說「台南 戶外踏青」「台北 文青咖啡」",
                      "size": "xs", "color": "#8892B0", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "backgroundColor": "#FFFFFF",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🌿 戶外踏青", "text": f"周末 戶外踏青{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "☕ 文青咖啡", "text": f"周末 文青咖啡{suf}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "👶 親子同樂", "text": f"周末 親子同樂{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🏃 運動健身", "text": f"周末 運動健身{suf}"}},
                     ]},
                     {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🍜 吃喝玩樂", "text": f"周末 吃喝玩樂{suf}"}},
                         {"type": "button", "style": "primary", "color": ACCENT, "flex": 1,
                          "height": "sm", "action": {"type": "message", "label": "🎨 市集展覽", "text": f"周末 市集展覽{suf}"}},
                     ]},
                     {"type": "button", "style": "primary", "color": "#1A1F3A", "height": "sm",
                      "action": {"type": "message", "label": "🎵 表演音樂", "text": f"周末 表演音樂{suf}"}},
                 ]},
             }}]


def build_activity_region_picker(category: str) -> list:
    """近期活動 — 第一步：選擇區域"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    regions = list(_AREA_REGIONS.keys())
    buttons = [
        {"type": "button", "style": "primary", "color": color, "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}",
                    "text": f"活動 {category} 地區 {r}"}}
        for r in regions
    ]
    return [{"type": "flex", "altText": f"近期{category}在哪個地區？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": "🗓️ 你在哪個地區？",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_activity_area_picker(category: str, region: str = "") -> list:
    """近期活動 — 第二步：選擇城市"""
    colors = {"戶外踏青": "#43A047", "文青咖啡": "#795548", "親子同樂": "#1E88E5",
              "運動健身": "#E53935", "吃喝玩樂": "#FB8C00",
              "市集展覽": "#8E24AA", "表演音樂": "#D81B60"}
    color = colors.get(category, "#5B9BD5")
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    buttons = []
    for i in range(0, len(areas), 3):
        row = areas[i:i+3]
        buttons.append({
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                 "action": {"type": "message", "label": a, "text": f"周末 {category} {a}"}}
                for a in row
            ]
        })
    # 加一個「← 重選地區」按鈕
    buttons.append({
        "type": "button", "style": "link", "height": "sm",
        "action": {"type": "message", "label": "← 重選地區",
                   "text": f"周末 {category}"}
    })
    return [{"type": "flex", "altText": f"近期{category}在哪個城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical", "backgroundColor": color,
                            "contents": [
                                {"type": "text", "text": f"🗓️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": f"選擇後推薦你附近的「{category}」活動",
                                 "color": "#FFFFFFBB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": buttons},
             }}]


def build_activity_city_picker(category: str = "") -> list:
    """近期活動 — 問城市（按北中南東離島分區顯示）"""
    ACCENT = "#5C6BC0"
    cat_suffix = f" {category}" if category else ""

    def _btn(c, primary=False):
        btn = {"type": "button",
               "style": "primary" if primary else "secondary",
               "height": "sm", "flex": 1,
               "action": {"type": "message", "label": c,
                          "text": f"近期活動{cat_suffix} {c}"}}
        if primary:
            btn["color"] = ACCENT
        return btn

    def _rows(cities, primary=False):
        btns = [_btn(c, primary) for c in cities]
        return [{"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": btns[i:i+3]}
                for i in range(0, len(btns), 3)]

    def _section(label, cities, primary=False):
        header = {"type": "text", "text": label, "size": "xs",
                  "color": "#8892B0", "margin": "md"}
        return [header] + _rows(cities, primary)

    region_order = [
        ("🏙️ 北部", ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"], True),
        ("🌾 中部", ["台中", "彰化", "南投", "雲林"], False),
        ("☀️ 南部", ["嘉義", "台南", "高雄", "屏東"], False),
        ("🏔️ 東部 ＋ 離島", ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"], False),
    ]

    body_contents = []
    for label, cities, primary in region_order:
        body_contents.extend(_section(label, cities, primary))

    return [{"type": "flex", "altText": "近期活動 — 你在哪個城市？",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "🗓️ 近期活動",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                {"type": "text", "text": "你在哪個城市？",
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": body_contents},
             }}]


def build_activity_message(text: str, user_id: str = None) -> list:
    """近期活動 — 主路由"""
    text_s = text.strip()

    # 解析類別
    category = None
    for cat in _ACTIVITY_DB.keys():
        if cat in text_s:
            category = cat
            break
    if not category:
        if any(w in text_s for w in ["爬山", "踏青", "健行", "大自然"]):
            category = "戶外踏青"
        elif any(w in text_s for w in ["咖啡", "文青", "藝文"]):
            category = "文青咖啡"
        elif any(w in text_s for w in ["小孩", "親子", "家庭", "帶小孩"]):
            category = "親子同樂"
        elif any(w in text_s for w in ["運動", "跑步", "騎車", "健身"]):
            category = "運動健身"
        elif any(w in text_s for w in ["夜市", "美食", "吃", "逛街"]):
            category = "吃喝玩樂"
        elif any(w in text_s for w in ["市集", "展覽", "展", "博物館", "美術館"]):
            category = "市集展覽"
        elif any(w in text_s for w in ["演唱會", "音樂", "表演", "演出", "音樂節", "livehouse"]):
            category = "表演音樂"

    # 解析區域（支援全台 22 縣市）
    area = ""
    all_cities_pattern = "|".join(_ALL_CITIES)
    area_match = re.search(rf'({all_cities_pattern})', text_s)
    if area_match:
        area = area_match.group(0)
        _set_user_city(user_id, area[:2])  # 記住用戶明確指定的城市

    # 解析地區（北部/中部/南部/東部離島）
    region = ""
    for r in _AREA_REGIONS:
        if r in text_s:
            region = r
            break

    if not category:
        # 沒指定類別 → 有城市先選類型，沒城市先選城市
        if area:
            return build_activity_menu(area)
        return build_activity_city_picker()
    # 有類別 + 有城市 → 直接顯示活動
    if area:
        return build_activity_flex(category, area)
    # 有類別 + 有地區 → 顯示該地區城市選擇
    if region:
        return build_activity_area_picker(category, region)
    # 有類別但沒地區 → 先問城市
    return build_activity_city_picker(category)
