"""
modules/weather.py — 天氣＋穿搭建議 ＋ 早安摘要
================================================
從 webhook.py 提取的獨立模組。

對外接口：
  build_weather_message(text, user_id="")   → list[dict]
  build_morning_summary(text, user_id="")   → list[dict]
  build_weather_region_picker()             → list[dict]
  build_weather_city_picker(region="")      → list[dict]
"""

import json
import os
import re
import urllib.parse
import urllib.request

from utils.redis import redis_get as _redis_get, redis_set as _redis_set

# ─── 環境變數 ──────────────────────────────────────────────
_CWA_KEY = os.environ.get("CWA_API_KEY", "")
_MOE_KEY = os.environ.get("MOE_API_KEY", "")
LINE_BOT_ID = os.environ.get("LINE_BOT_ID", "")

# ─── 城市 / 地區資料 ─────────────────────────────────────
_AREA_REGIONS = {
    "北部": ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"],
    "中部": ["台中", "彰化", "南投", "雲林"],
    "南部": ["嘉義", "台南", "高雄", "屏東"],
    "東部離島": ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"],
}
_ALL_CITIES = [c for cities in _AREA_REGIONS.values() for c in cities]

_CWA_CITY_MAP = {
    "台北": "臺北市", "台中": "臺中市", "台南": "臺南市", "高雄": "高雄市",
    "新北": "新北市", "桃園": "桃園市", "基隆": "基隆市",
    "新竹": "新竹縣", "苗栗": "苗栗縣", "彰化": "彰化縣",
    "南投": "南投縣", "雲林": "雲林縣", "嘉義": "嘉義縣",
    "屏東": "屏東縣", "宜蘭": "宜蘭縣", "花蓮": "花蓮縣",
    "台東": "臺東縣", "澎湖": "澎湖縣", "金門": "金門縣", "連江": "連江縣",
}

_WEATHER_CITIES = _ALL_CITIES

_AQI_STATION = {
    "台北": "中正", "台中": "西屯", "台南": "台南", "高雄": "前金",
    "新北": "板橋", "桃園": "桃園", "新竹": "新竹", "苗栗": "苗栗",
    "彰化": "彰化", "嘉義": "嘉義", "屏東": "屏東", "宜蘭": "宜蘭",
    "花蓮": "花蓮", "台東": "台東", "基隆": "基隆", "澎湖": "馬公",
    "南投": "南投", "雲林": "斗六", "金門": "金門", "連江": "馬祖",
}

# ─── 早安摘要資料 ──────────────────────────────────────────
_MORNING_ACTIONS = [
    "🍳 早餐加一顆蛋或豆漿，撐到中午不暴食",
    "💧 今天目標喝水 2000cc 以上",
    "🏃 每工作 50 分鐘起來動一動脖子肩膀",
    "😴 睡前 30 分鐘放下手機，入睡品質提升",
    "🥗 用餐先吃蔬菜，血糖穩定不容易餓",
    "🌞 早上曬 15 分鐘太陽，補維生素 D",
    "🧘 壓力大時做深呼吸：吸 4 秒、憋 7 秒、呼 8 秒",
    "💪 起床先做 2 分鐘伸展，趕走僵硬感",
    "🚶 午餐後走 10 分鐘，血糖控制好 30%",
    "🧠 早上第一小時不看社群，心情會更好",
    "🥜 今天吃一把堅果（約 10 顆），護心又護腦",
    "🚪 早上開窗 10 分鐘，換新鮮空氣",
    "🍵 手搖飲選無糖或少糖，一週省 2000 卡",
    "👁️ 螢幕 20 分鐘就看遠處 20 秒，眼睛謝謝你",
    "🧴 出門記得擦防曬，預防比修復更有效",
    "🍊 吃一顆橘子或奇異果，補充維生素 C",
    "🎵 通勤聽音樂或 podcast，比滑手機減壓",
    "🔋 安排 10 分鐘真正休息，離開螢幕放空",
    "🛏️ 今天固定時間起床，調好生理時鐘",
    "🥤 起床第一件事喝杯溫水，啟動腸胃",
    "📵 吃飯時把手機翻面，專心享受食物",
    "🧊 下午嘴饞選水果代替零食，更健康",
    "🌿 找一個綠色植物看 30 秒，舒緩眼睛疲勞",
    "🎯 今天設一個小目標，完成後獎勵自己",
]

_WEEKLY_DEALS = {
    0: [  # 星期一
        ("☕", "星巴克好友分享日", "指定飲品第二杯半價，揪同事一起喝！"),
        ("🍔", "麥當勞振奮星期一", "大麥克套餐限時優惠，開啟新的一週"),
        ("🛒", "全聯週一生鮮日", "指定蔬果肉品有折扣，下班順路買"),
        ("🧋", "50 嵐週一飲品日", "大杯飲料優惠，Monday Blue 靠它救"),
        ("📺", "Netflix 新片週一上架", "週一通常有新劇、新片上架，追劇開始"),
    ],
    1: [  # 星期二
        ("🧋", "CoCo 週二飲品日", "指定飲品第二杯優惠，下午茶時間到！"),
        ("🍕", "必勝客週二大披薩日", "大披薩外帶特價，晚餐不用煩惱"),
        ("📦", "momo 週二品牌日", "逛逛有沒有需要的東西在特價"),
        ("🍩", "Krispy Kreme 買一送一", "不定期週二推買一送一，粉絲專頁注意"),
        ("🎵", "Spotify 新歌週二更新", "每週新發歌單上架，找首新歌通勤聽"),
    ],
    2: [  # 星期三
        ("🍦", "全家霜淇淋日", "霜淇淋第二件半價，下午來一支消暑"),
        ("☕", "路易莎週三咖啡日", "拿鐵系列有優惠，提神好時機"),
        ("🎬", "威秀影城半價日", "部分場次電影半價，下班看場電影"),
        ("🍣", "壽司郎週三活動日", "不定期推 10 元壽司，社群瘋傳"),
        ("🛒", "Costco 週三特價輪播", "會員 APP 看本週特價，該補貨就衝"),
    ],
    3: [  # 星期四
        ("🍗", "肯德基瘋狂星期四", "V 我 50！指定套餐超值優惠"),
        ("☕", "星巴克數位體驗日", "APP 會員獨享優惠，打開看看有什麼"),
        ("🛍️", "蝦皮週四免運", "滿額免運門檻降低，該補貨的趁今天"),
        ("🍦", "迷客夏週四買一送一", "不定期週四活動，粉專公告"),
        ("🎮", "PS Store 週四更新", "新遊戲特賣、每週精選打折"),
    ],
    4: [  # 星期五
        ("🍺", "TGIF！週五小確幸", "辛苦一週了，下班買杯飲料犒賞自己"),
        ("🎉", "Uber Eats 週五優惠", "外送滿額折扣，在家舒服吃晚餐"),
        ("🎮", "Steam 週末特賣", "看看有沒有想玩的遊戲在打折"),
        ("🍕", "Domino's 週五 Happy Hour", "披薩買大送小，週五聚餐首選"),
        ("📽️", "Apple TV+ 週五新劇", "每週五新劇集更新，訂閱族別錯過"),
    ],
    5: [  # 星期六
        ("🌿", "假日農夫市集", "各地有農夫市集，新鮮蔬果等你逛"),
        ("☕", "cama café 假日優惠", "假日外帶咖啡有折扣，出門帶一杯"),
        ("🎪", "週末市集情報", "搜尋你附近的週末市集，吃喝逛一波"),
        ("🎨", "誠品假日藝文活動", "書店常有作家簽書、小型展覽"),
        ("🏞️", "國家公園免費週六", "部分園區週六免門票，帶家人走走"),
    ],
    6: [  # 星期日
        ("🍳", "週日早午餐提案", "找家好吃的早午餐店，慢慢享受假日"),
        ("📚", "誠品週日閱讀", "逛逛書店，也許會遇到一本好書"),
        ("🛒", "家樂福週日生鮮特價", "一週食材採購日，趁特價補齊"),
        ("🧺", "IKEA 週日家庭日", "一家大小逛逛，順便吃肉丸午餐"),
        ("🎬", "HBO GO 週日新片", "週日晚間新上架電影，佛系追劇"),
    ],
}

_SPECIAL_DEALS = {
    (1, 1):   ("🎊", "新年快樂", "各大通路新年特賣中，逛逛有沒有好康！"),
    (1, 20):  ("🏮", "春節採買潮", "年貨大街、Costco、家樂福年貨特賣全面開跑"),
    (2, 14):  ("💝", "情人節快樂", "各大餐廳、甜點店推出情人節限定，約個人吃飯吧"),
    (3, 8):   ("👩", "婦女節快樂", "不少品牌有女性專屬優惠，犒賞自己"),
    (3, 14):  ("🍫", "白色情人節", "回禮日！甜點烘焙材料特價中"),
    (3, 15):  ("🛋️", "IKEA 會員週", "會員獨享價、熱銷商品特價，逛街順便吃肉丸"),
    (4, 1):   ("😜", "愚人節", "小心被整！不過各品牌常推愚人節限定商品"),
    (4, 4):   ("🧒", "兒童節", "遊樂園、親子餐廳有兒童節優惠"),
    (4, 22):  ("🌍", "世界地球日", "不少品牌推環保主題優惠，自備杯折價再多"),
    (5, 1):   ("💪", "勞動節快樂", "辛苦了！不少店家勞動節有特別優惠"),
    (5, 12):  ("💐", "母親節檔期", "百貨母親節檔期、餐廳套餐預訂高峰"),
    (6, 18):  ("🛒", "618 年中慶", "momo、蝦皮、PChome 年中大促銷，趁機撿便宜"),
    (7, 1):   ("🏖️", "暑假開始", "旅遊平台暑期早鳥優惠最後機會"),
    (8, 8):   ("👨", "父親節", "餐廳套餐、3C 禮盒、威士忌買氣旺"),
    (9, 1):   ("🎓", "開學季", "文具、3C 開學優惠中，學生族群看過來"),
    (9, 15):  ("🥮", "中秋烤肉潮", "金蘭醬油、Costco 烤肉組、月餅禮盒開搶"),
    (10, 10): ("🇹🇼", "國慶日快樂", "百貨週年慶陸續開跑，準備搶好康"),
    (10, 25): ("🛍️", "MUJI 週年慶", "無印良品全面 5~9 折，床包寢具最熱賣"),
    (10, 31): ("🎃", "萬聖節", "超商、餐廳萬聖節限定商品登場"),
    (11, 1):  ("🛍️", "雙11預熱", "各大電商雙11活動開始暖身，先加購物車"),
    (11, 11): ("🛍️", "雙11來了！", "蝦皮/momo/PChome 年度最大折扣日，衝！"),
    (11, 28): ("🖤", "黑色星期五", "Costco 黑五特賣、Apple 官網優惠、國際品牌大降價"),
    (12, 12): ("🛒", "雙12最後一波", "年末最後一波電商大促，錯過等明年"),
    (12, 24): ("🎄", "聖誕快樂", "聖誕大餐/交換禮物/市集，享受節日氣氛"),
    (12, 25): ("🎅", "Merry Christmas", "各大百貨聖誕特賣，甜點店限定款別錯過"),
    (12, 31): ("🎆", "跨年夜", "跨年活動、演唱會、煙火資訊，準備迎接新年！"),
}

_SURPRISES_FALLBACK = [
    ("🎯", "今日挑戰", "中午不滑手機，專心吃飯 15 分鐘，你做得到！"),
    ("📸", "拍照挑戰", "拍一張今天讓你覺得美的東西，記錄小確幸"),
    ("🎲", "午餐冒險", "今天午餐試一家沒吃過的店，也許會有驚喜"),
    ("🎧", "聽首新歌", "打開 Spotify 或 KKBOX 推薦，讓今天有新 BGM"),
    ("✍️", "三件好事", "睡前寫下今天 3 件值得感謝的事，幸福感 UP"),
    ("🍰", "犒賞自己", "完成今天的事之後，買個小甜點獎勵自己"),
]

_CITY_LOCAL_TIPS: dict[str, list[tuple]] = {
    "台南": [
        ("🦐", "台南在地早餐", "虱目魚粥、碗粿加肉燥湯，外地人不一定知道這才是台南早餐精髓"),
        ("🏯", "府城散步提案", "赤崁樓→普濟殿→蜷尾家冰，三點連線剛好走半小時最舒服"),
        ("🌺", "台南季節限定", "五六月鳳凰花盛開，東區巷弄跟成大校園都是拍照好地方"),
        ("🫙", "安平老街必買", "安平豆花、蝦餅、劍獅紀念品，帶回去當伴手禮最道地"),
        ("🌊", "四草綠色隧道", "搭竹筏穿越紅樹林，像台版亞馬遜，周末去記得早點訂位"),
        ("🍜", "台南美食密技", "點牛肉湯要說「現切」才新鮮，早上六點前去最好"),
        ("🎨", "藍晒圖文創園區", "夜晚打燈最漂亮，白天文創小店可以慢慢逛，假日有市集"),
        ("🌸", "總爺藝文中心", "糖廠舊建築改造的文化園區，假日常有特展，免費入場"),
        ("🥐", "神農街夜生活", "老宅咖啡、手工餐酒館聚集，晚上七點後最有氛圍"),
        ("🎪", "台南週末市集", "善化、歸仁、仁德假日都有農夫市集，新鮮蔬果又便宜"),
        ("🦢", "七股黑面琵鷺", "冬天十月到四月是觀鳥季，騎腳踏車繞鹽田最愜意"),
        ("🌅", "漁光島落日", "台南最美日落點之一，傍晚帶杯飲料去坐著看"),
    ],
    "台北": [
        ("🏔️", "陽明山步道", "七星山、擎天崗、冷水坑一日可走完，周末早點出門避人潮"),
        ("🎨", "松山文創園區", "免費逛，不定期有設計展、市集，適合拍照打卡"),
        ("🍜", "永康街小吃", "鼎泰豐旁邊有很多不用排隊的隱藏美食，眼睛張開慢慢找"),
        ("🌿", "大安森林公園", "台北最大城市綠肺，早上有打太極的老人和遛狗人，很有生活感"),
        ("🎭", "兩廳院廣場", "平日中午常有免費快閃音樂或小型表演，路過不妨停下看"),
        ("🦋", "陽明山蝴蝶季", "三四月紫蝶遷徙，花季期間整個山頭花海加蝴蝶，超夢幻"),
        ("🎡", "迪化街假日市集", "南北貨百年老街，周末有小農市集，中藥香加上咖啡香"),
        ("🌊", "淡水老街黃昏", "搭捷運就到，黃昏看觀音山倒影，配一杯阿給是台北人的儀式感"),
        ("🏛️", "故宮博物院", "周三到周五人少，早上九點進去最舒服，翠玉白菜必看"),
        ("☕", "台北咖啡日", "大安區巷弄密度最高的精品咖啡館群，每間風格都不一樣"),
        ("🎵", "河岸留言音樂展演", "平日票價親民，看獨立樂團表演是最台北的夜晚方式"),
        ("🌙", "象山觀景台", "傍晚爬上去看台北101燈光亮起，是免費版的台北夜景最佳點"),
    ],
    "台中": [
        ("🌈", "彩虹眷村", "台中最有名的打卡點，黃永阜爺爺手繪的眷村彩繪，顏色超鮮豔"),
        ("☕", "審計新村文創", "台中文青聚集地，老眷村改造的咖啡街，週末有市集很熱鬧"),
        ("🏞️", "大坑步道", "台中市區最近的爬山選擇，1-10號步道難度不同，適合各年齡"),
        ("🌺", "中科附近花海", "台中花博遺址周邊春天有花海，騎Youbike逛最舒服"),
        ("🎨", "國美館草坪", "假日野餐聖地，草坪常有展演活動，進館看展也是免費"),
        ("🍱", "第二市場早餐", "廬山飯糰、老賴茶棧、王家菜頭粿是老台中人的早餐記憶"),
        ("🌙", "逢甲夜市攻略", "越晚越熱鬧，建議九點後去，人潮稍退比較好走，必吃豆干"),
        ("🏔️", "武陵農場", "春天賞櫻、夏天避暑、冬天霧淞，全年都有理由去一趟"),
        ("🦭", "台中港海鮮", "梧棲漁港周六有現撈海鮮市場，比超市新鮮便宜很多"),
        ("🎪", "東豐自行車道", "廢棄鐵路改建，起終點都有卸車服務，去程騎車回程找人接"),
        ("🌊", "高美濕地", "下午四點後去最美，夕陽倒映在水面風車轉，不輸任何景點"),
    ],
    "高雄": [
        ("🚢", "高雄港渡輪", "搭藍色公路渡輪跨愛河到旗津，來回票才 30 元，附贈港口風景"),
        ("🌉", "夜晚愛河", "晚上沿愛河步道走，燈光倒影加上涼風，是高雄人的約會日常"),
        ("🍢", "六合夜市必吃", "木瓜牛奶、烤玉米、海產粥，觀光客多但有些攤位老店值得排"),
        ("🏖️", "旗津海水浴場", "週末帶水上活動裝備去，或只是吹海風曬太陽也很放鬆"),
        ("🎨", "駁二藝術特區", "倉庫改造的文創園區，周末有表演和市集，假日必去之地"),
        ("🌅", "柴山自然公園", "市區就能看海的山，有台灣獼猴出沒，夕陽超美"),
        ("🎠", "蓮池潭風景區", "龍虎塔是標誌地標，早上有老人運動，租腳踏車繞湖最愜意"),
        ("🍜", "鹽埕埔老攤", "崛江商場周邊老牛肉麵、切仔麵聚集，價格比市區便宜一半"),
        ("🌺", "美濃客家文化", "油紙傘、手工粿、紙傘文化村，離市區 30 分鐘但像另一個世界"),
        ("🏛️", "國立科學工藝博物館", "台灣最大科技博物館，互動展很好玩，假日親子首選"),
    ],
    "新北": [
        ("🎋", "平溪天燈", "不只十分，整條平溪線都美，菁桐車站人少又有氛圍"),
        ("🌊", "野柳地質公園", "女王頭全球知名，早上八點開門前到最少人，拍照不用等"),
        ("🏔️", "烏來溫泉", "台北最近的溫泉區，泡完再吃泰雅族山豬肉，一日遊剛好"),
        ("🦟", "深坑老街豆腐", "整條老街都是豆腐料理，臭豆腐、麻辣豆腐鍋，豆腐控必朝聖"),
        ("🌅", "鶯歌老街陶瓷", "台灣陶瓷重鎮，陶瓷博物館免費，老街可以淘便宜手工陶器"),
        ("☕", "淡水漁人碼頭", "情人橋夕陽是招牌，假日有街頭藝人，配現撈海鮮最完美"),
        ("🌿", "三峽老街", "清朝閩南巴洛克建築保存最完整，比迪化街更有歷史感"),
        ("🏖️", "福隆海水浴場", "夏天必去，沙灘品質是北台灣最好的，附近有福隆便當"),
        ("🌄", "金瓜石九份", "雨天反而最有氣氛，早上九點前去人最少，阿妹茶樓排隊有訣竅"),
    ],
    "桃園": [
        ("🌸", "大溪老街", "老聚落保存完整，週末有木藝市集，大溪豆干是伴手禮首選"),
        ("🌺", "復興鄉角板山", "春天賞梅、夏天避暑、秋天楓紅，四季都有理由上山"),
        ("🏊", "石門水庫", "環湖步道很好走，水庫活魚三吃是在地人推薦必吃"),
        ("🎡", "老街溪河濱公園", "桃園市區難得的休閒綠地，傍晚散步騎車最舒服"),
        ("🦆", "埔心牧場", "台灣最大乳牛牧場，親子體驗擠牛奶、餵動物，假日開放"),
        ("🌙", "中壢夜市文化", "中壢觀光夜市vs新明夜市，在地人去新明，比較不觀光"),
        ("🏛️", "桃園神社", "日據時代保存最完整的神社建築，現在改成忠烈祠，拍照超有感"),
        ("🌿", "小烏來風景區", "有瀑布有吊橋，從市區開車一小時可以到，適合周末一日遊"),
    ],
    "新竹": [
        ("💨", "新竹風城體驗", "新竹風大是台灣第一，海濱風箏季每年吸引全台玩家來"),
        ("🍜", "城隍廟周邊小吃", "貢丸湯、肉圓、潤餅是新竹早餐三寶，城隍廟旁邊聚集最多老店"),
        ("🌊", "南寮漁港", "新竹最大漁港，周六早上有現撈魚市，自行車道繞一圈很舒服"),
        ("🏔️", "尖石鄉泰雅部落", "新竹縣山區，有溫泉、水蜜桃、泰雅族文化，夏天避暑首選"),
        ("🌸", "新竹公園玻璃藝術", "玻璃博物館是新竹地標，周邊公園很適合帶小孩"),
        ("☕", "巨城購物中心", "新竹最大Mall，美食街品牌齊全，下雨天室內逛最划算"),
        ("🌿", "護城河親水公園", "環護城河步道繞一圈 40 分鐘，傍晚有涼風吹，老新竹人的散步路線"),
    ],
    "嘉義": [
        ("🌲", "阿里山日出", "祝山觀日台看日出是一生必看，四五月螢火蟲季更是夢幻"),
        ("🍗", "嘉義火雞肉飯", "文化路夜市旁有好幾家半世紀老店，早餐配火雞肉飯是當地日常"),
        ("🎨", "嘉義市立美術館", "舊酒廠改造，展覽水準高，假日有導覽，完全免費入場"),
        ("🏞️", "太平洋竹崎公園", "阿里山公路旁的隱藏版展望台，可以看到嘉南平原全景"),
        ("🌸", "仁義潭水庫", "嘉義市民散步健行的秘密基地，清晨有薄霧很夢幻"),
        ("🛖", "布袋漁港", "南台灣重要漁港，海鮮直售比市場便宜，假日去要早"),
        ("🎋", "奮起湖老街", "阿里山森林鐵路中途站，便當是特色，搭小火車來回更有趣"),
    ],
    "宜蘭": [
        ("🦞", "宜蘭海鮮", "南方澳漁港是東台灣最大漁港，周六早上現撈海鮮市集超新鮮"),
        ("🌸", "武荖坑風景區", "宜蘭溪旁的免費公園，春天油桐花季，溪邊烤肉很受歡迎"),
        ("🎪", "傳藝中心", "宜蘭最大文化園區，假日有表演，牛舌餅和糕餅是必買"),
        ("🌊", "頭城沙灘", "宜蘭第一個對外開放的海水浴場，夏天浪不小，適合衝浪"),
        ("☕", "礁溪溫泉", "離火車站五分鐘路程，有公共溫泉泡腳池，完全免費"),
        ("🌿", "冬山河親水公園", "宜蘭最大公園，腳踏車道完善，下午去吹風看水很放鬆"),
        ("🏔️", "太平山翠峰湖", "台灣最大的高山湖泊，霧氣繚繞像仙境，秋天楓紅最美"),
    ],
    "花蓮": [
        ("🏔️", "太魯閣國家公園", "清水斷崖、燕子口、九曲洞，台灣最壯觀的峽谷必看"),
        ("🌊", "七星潭礫石灘", "不是沙灘是石灘，獨特景觀，傍晚去看日落最美"),
        ("🍡", "公正包子", "花蓮最有名的早餐，包子現做現賣，一早就排隊是常態"),
        ("🎠", "吉安慶修院", "日據時期建造的廟，保存完整，是花蓮最有特色的文化遺址"),
        ("🌺", "洄瀾灣海邊", "躺在石頭上聽海聲，晚上看星星幾乎無光害，可以看銀河"),
        ("🦋", "賞鯨豚之旅", "花蓮港每天早晚都有賞鯨船，運氣好可以看到飛旋海豚"),
        ("🌿", "光復糖廠冰", "老糖廠改成觀光園區，冰棒是招牌，附近有阿美族文化村"),
    ],
    "台東": [
        ("🌊", "綠島浮潛", "台灣能在海中直接看到珊瑚礁的少數地方，能見度驚人"),
        ("🌅", "伯朗大道", "金城武拍茶樹廣告那條路，騎腳踏車吹風是台東日常"),
        ("🏄", "都蘭海邊衝浪", "台東最受歡迎的衝浪地，有教練課程，初學者也能學"),
        ("🎪", "台東熱氣球嘉年華", "每年六七月舉辦，清晨看熱氣球升空是一生難忘的畫面"),
        ("🌿", "池上米倉", "台灣最高品質稻米產地，走在田間小路，空氣新鮮無比"),
        ("🦌", "鹿野高台", "飛行傘基地，爬上高台可以看花東縱谷全景，風景一流"),
        ("🌺", "知本溫泉", "台東最大溫泉區，溫泉加叢林，泡完吃原住民風味餐超幸福"),
    ],
    "基隆": [
        ("🦑", "廟口夜市", "基隆最有名的夜市，天婦羅、泡泡冰、鼎邊趖是必吃三樣"),
        ("🌊", "正濱漁港彩色屋", "IG超熱門打卡點，彩色倉庫倒映在水面，下午光線最漂亮"),
        ("⚓", "和平島地質公園", "海蝕地形超壯觀，附近有海水游泳池，夏天消暑好去處"),
        ("☕", "八斗子漁港", "新鮮海產比台北便宜一半，假日早去市場挑現撈，下午去看夕陽"),
        ("🌿", "情人湖公園", "基隆市區裡的自然公園，下午散步很放鬆，有水鴨和白鷺鷥"),
        ("🏖️", "外木山海岸", "基隆在地人的私房海邊，夏天在地人都在這游泳，比台北近多了"),
    ],
    "苗栗": [
        ("🌸", "三義木雕", "台灣木雕重鎮，木雕博物館展品精緻，老街有手工藝品可以帶走"),
        ("🎋", "南庄老街", "山城老街加上賽夏族文化，假日市集熱鬧，桂花冰棒超好吃"),
        ("🌺", "薑麻園休閒農場", "薑餅、薑汁湯圓是特色，秋天菊花節也很好看"),
        ("🏔️", "獅頭山風景區", "泰安鄉有溫泉加山景，泡溫泉配水蜜桃是苗栗夏天限定"),
        ("🌊", "通霄海水浴場", "苗栗最長的海灘，貝殼砂很細，沿著自行車道騎到外埔漁港"),
    ],
    "彰化": [
        ("🐄", "彰化肉圓", "北彰化的肉圓偏蒸，南彰化偏炸，口味不同各有擁護者"),
        ("🌺", "田尾公路花園", "全台最大花卉集散地，周末有花市，一盆花比花店便宜一半"),
        ("🏛️", "鹿港老街", "清朝台灣第二大城，三山國王廟、龍山寺、鳳眼糕是三大必訪"),
        ("🌊", "彰化濱海賞鳥", "大肚溪口濕地是候鳥天堂，秋冬有上萬隻水鳥停棲，壯觀"),
        ("🎠", "八卦山大佛", "彰化地標，山頂視野遼闊可看彰化平原，清晨爬山最涼快"),
    ],
    "雲林": [
        ("🧅", "西螺蔬果市場", "台灣最大農產品批發市場，清晨逛可以買到最新鮮的蔬菜"),
        ("☕", "古坑咖啡", "台灣咖啡故鄉，古坑鄉有多家小型咖啡農場可以參觀品嚐"),
        ("🌊", "口湖沿海濕地", "候鳥棲息地，冬天有黑面琵鷺和雁鴨，生態非常豐富"),
        ("🎪", "斗六假日市集", "雲林縣府旁邊假日有農夫市集，在地農產直售超划算"),
        ("🌸", "虎尾糖廠冰", "百年糖廠現在是觀光景點，冰棒現做不加人工色素，排隊值得"),
    ],
    "南投": [
        ("🌊", "日月潭環湖", "租腳踏車環湖約 30 公里，阿薩姆紅茶配邵族料理是在地組合"),
        ("🌲", "溪頭妖怪村", "台大實驗林，鳳凰木下走路超舒服，妖怪主題餐廳很好拍"),
        ("🏔️", "清境農場", "雲海和高山牧場綿羊，清晨五點看日出雲海是南投最美體驗"),
        ("🌺", "埔里紙鄉", "手工造紙傳統工藝，廣興紙寮可以親手做紙，是獨特的在地體驗"),
        ("🌿", "惠蓀林場", "全台最美大學實驗林場之一，楓葉步道秋天金黃，全年開放"),
    ],
    "屏東": [
        ("🐠", "墾丁浮潛", "南灣有珊瑚礁群，浮潛能見度高，租裝備費用比花蓮實惠"),
        ("🌺", "潮州夜市", "屏東人的夜市首選，不觀光，在地人才知道的美食集中地"),
        ("🌊", "大鵬灣國家風景區", "封閉式潟湖，適合水上活動，租帆船或獨木舟很受歡迎"),
        ("🥭", "屏東熱帶農業", "枋寮芒果、鹽埔蜜棗、萬丹紅豆，各鄉鎮都有當季特產農場"),
        ("🦩", "四重溪溫泉", "屏東山中溫泉小鎮，客家文化加溫泉，比墾丁安靜很多"),
    ],
}

_GENERIC_LOCAL_TIPS = [
    ("🗺️", "探索在地", "今天試著走一條沒走過的路，說不定有意外驚喜"),
    ("🌿", "在地市場", "找一個周邊菜市場或夜市逛逛，是認識在地最快的方式"),
    ("📸", "城市觀察", "用相機記錄今天路上最有趣的一個畫面，練習觀察生活"),
    ("☕", "在地咖啡廳", "找一家 Google 評分 4.5 以上的在地小咖啡，勝過連鎖"),
    ("🎯", "今日小冒險", "今天午餐去一家完全沒去過的店，用直覺選"),
]

_CITY_LOCAL_DEALS: dict[str, list[tuple]] = {
    "台北": [
        ("🛒", "南門市場午後特惠", "下午 4 點後熟食區當日特價，點心也便宜，下班順路撿便宜"),
        ("☕", "大安巷弄咖啡 Happy Hour", "永康街、師大附近精品咖啡廳週間下午 2-5 點有優惠"),
        ("🧋", "公館商圈學生優惠", "台大周邊眾多店家有學生折扣，出示學生證即享"),
        ("🌊", "淡水漁港現撈直售", "週末早上現撈漁貨直售，比超市便宜且新鮮，搭捷運就到"),
        ("🎪", "華山文創市集", "不定期創意市集，手作品＋獨立品牌都比定價親民"),
        ("🏙️", "信義商圈週間積點", "新光三越、ATT 百貨週間消費積點加倍，比假日划算"),
        ("🎭", "兩廳院演前折扣票", "當天未售完票演前 2 小時常有折扣，官網或現場詢問"),
        ("🎡", "迪化街農夫市集", "週末有小農市集，中藥香加咖啡香，南北貨直接批發價"),
    ],
    "新北": [
        ("🍜", "三峽老街豆腐直售", "在地豆腐製品直售，平日人少店家有更多時間介紹"),
        ("🌊", "淡水老街平日特惠", "平日來人少，阿給、鐵蛋等小吃攤常有平日優惠"),
        ("♨️", "烏來溫泉平日優惠", "平日泡湯比假日便宜 20-30%，記得先訂，人也少很多"),
        ("🎨", "鶯歌陶瓷老街批發", "平日陶瓷商家有批發優惠，手作體驗費用比假日少"),
        ("🛍️", "板橋大遠百週間", "不定期週間折扣活動，美食街外帶有折扣"),
        ("🦞", "八里渡船頭海鮮", "渡船頭旁海鮮攤平日比假日有更多議價空間"),
        ("🌿", "永和樂華夜市早場", "下午開始營業時段，部分攤位有開市特惠"),
        ("🏔️", "九份老街平日優惠", "平日遊客少，老街商家有時間聊天，更願意議價"),
    ],
    "桃園": [
        ("🌺", "大溪老街平日優惠", "平日木器工藝店家來客少，部分有平日特惠並附贈解說"),
        ("🛍️", "中壢大遠百週間日", "每月特定週間積點加倍或滿額贈，上官網確認活動日期"),
        ("🍎", "觀音農場蔬果直售", "觀音、新屋一帶農場週末有蔬果直售，比市場便宜"),
        ("🏊", "石門水庫農產", "環湖道路旁假日有農民直售，番薯、花生等當季農產品"),
        ("☕", "桃園藝文特區咖啡", "鐵道故事館周邊文創咖啡廳，週間有買一送一"),
        ("🍱", "中壢觀光夜市早場", "下午開市時人少，部分攤位有開攤優惠"),
    ],
    "台中": [
        ("🌈", "審計新村週末市集", "勤美術館旁手作市集，獨立品牌小物＋有機農產品直售"),
        ("🍱", "第二市場早市特惠", "廬山飯糰、老攤販週間早上人少，早到有現做限定品項"),
        ("☕", "草悟道咖啡一條街", "審計新村到勤美廣場沿線，週間外帶有折扣"),
        ("🏪", "台中港三井出清季", "每季末有品牌清倉，折上折可達 3-4 折"),
        ("🌙", "逢甲早場優惠", "逢甲夜市下午 4-6 點剛開市，攤位剛擺好有開市特惠"),
        ("🦭", "梧棲漁港週六早市", "週六早上 6-10 點現撈海鮮直售，比超市便宜且更新鮮"),
        ("🎨", "國美館常設展免費", "國立台灣美術館免費入場，品質不輸付費展覽"),
        ("🌊", "高美濕地農產採買", "梧棲區農家週末有現採蔬菜直售，順路可去高美"),
    ],
    "台南": [
        ("🌺", "花園夜市開市日確認", "花園夜市週四、六、日才開，外地朋友記得確認再出發"),
        ("🦐", "安平漁港直售", "安平漁港周邊漁產直售攤，蝦子、文蛤比超市便宜很多"),
        ("🏛️", "奇美博物館網路票優惠", "官網購票比現場便宜，早上人少，建議預約"),
        ("🌙", "神農街老宅咖啡", "晚上 7-9 點最有氛圍，部分有最低消費優惠組合"),
        ("🎪", "歸仁農夫市集", "歸仁、仁德週末有有機蔬果直售，附近居民錯過可惜"),
        ("☕", "中西區老宅咖啡", "赤崁樓周邊老宅改建咖啡館，週間拿鐵第二杯折扣"),
        ("🛒", "永樂市場布料批發", "週間比假日更願意議價，量多更便宜"),
        ("🍜", "保安路食材行", "散裝販售當地食材，採購量大可議價"),
    ],
    "高雄": [
        ("🌊", "旗津海鮮週末直售", "旗津渡輪旁週末早上特價，風螺、章魚、花枝很便宜"),
        ("🛍️", "夢時代品牌週活動", "週一到週四常有品牌週，美食街午間外帶有折扣"),
        ("🍱", "三鳳中街南北貨批發", "乾貨批發價格比超市實惠，節慶前更划算"),
        ("🌿", "美濃農村直售", "週末農家直售有機蔬菜，菸草文化節期間更熱鬧"),
        ("🎭", "高雄流行音樂中心", "KHMC 常有免費展演活動，河岸景色加免費表演超值"),
        ("🏖️", "西子灣旁海鮮小吃", "周邊在地海鮮攤比觀光區便宜，當地人才知道的位置"),
        ("🌙", "瑞豐夜市開市日", "瑞豐週三四不開，週一二五六日才有，出發前確認"),
        ("🎨", "駁二周邊文創週間", "駁二藝術特區附近文創小店週間人少，有週間優惠"),
    ],
    "新竹": [
        ("🍜", "城隍廟美食早市", "城隍廟周邊貢丸、米粉攤平日比觀光客多的假日便宜"),
        ("🌊", "南寮漁港假日市集", "週末有漁產直售＋手作市集，順遊海邊吹海風"),
        ("🎨", "新竹美術館免費展", "市立美術館多數展覽免費，平日來人更少更舒適"),
        ("🌺", "內灣老街平日優惠", "野薑花粽、客家料理店家平日有時間詳細介紹"),
        ("☕", "竹北文青咖啡館", "竹北咖啡館密集，許多有學生/上班族午間優惠"),
        ("🏢", "竹科周邊午餐優惠", "竹北新竹科學園區周邊餐廳有工作日午餐特惠"),
    ],
    "嘉義": [
        ("🌲", "嘉義農會超市農產", "嘉義農會超市有阿里山高山茶、梅子等產季特價"),
        ("🍜", "文化路夜市早場", "下午 5 點剛開市人少，攤位剛擺好可以慢慢選"),
        ("🏛️", "故宮南院套票優惠", "常設展＋特展套票組合比個別買便宜"),
        ("🍊", "大林番茄、柳丁季", "大林、民雄一帶果農產季路邊直售，剛採超新鮮"),
        ("☕", "嘉義老屋咖啡館", "老屋改建咖啡館週間有下午茶套餐優惠"),
        ("🛒", "東市場早市", "每天早上 5-9 點，生鮮蔬果比大賣場新鮮且便宜"),
    ],
    "屏東": [
        ("🌺", "墾丁平日超值優惠", "民宿、水上活動平日比假日便宜 3-5 成，避開人潮"),
        ("🦐", "東港現撈漁貨", "東港漁港黑鮪魚、旗魚直售，比台北海鮮市場便宜很多"),
        ("🍍", "南州、枋寮農產直售", "鳳梨產季路邊直售，甜度高且比超市親民"),
        ("🐠", "小琉球非假日浮潛", "非假日包船費可砍到假日的 6-7 折，視野也更清晰"),
        ("🌿", "霧台原住民農產", "小米、愛玉、山地蔬菜直售，支持在地部落"),
        ("☕", "屏東市區咖啡街", "勝利路周邊咖啡館近年聚集，週間有買一送一活動"),
    ],
    "宜蘭": [
        ("🦞", "烏石港現撈漁市", "每天上午漁船靠港後有現撈直售，花枝、蝦最便宜"),
        ("♨️", "礁溪溫泉平日優惠", "各大飯店泡湯池平日比假日便宜約 2-3 成，人也少"),
        ("🍎", "礁溪番茄、草莓季", "附近農家產季可直接進農場採買，省掉中間商"),
        ("🎪", "傳藝中心表演優惠", "演前購票有優惠，旺季外的平日人少悠閒"),
        ("🌾", "冬山河花農切花", "周邊花農有切花直售，百合花產季更便宜"),
        ("🧀", "頭城農場體驗優惠", "農村體驗平日有特惠組合，比假日少排隊"),
    ],
    "花蓮": [
        ("🌸", "吉安有機農產直售", "吉安農民直售站有機蔬菜、木瓜、洛神花，比市區便宜"),
        ("🏔️", "太魯閣平日停車", "平日停車容易，建議早上去，光線好且人少"),
        ("🦞", "花蓮漁港現撈市場", "每天早上現撈旗魚、鬼頭刀，比台北超市便宜很多"),
        ("🍞", "花蓮麻糬伴手禮優惠", "在地麻糬店平日有試吃＋組合優惠"),
        ("🌊", "七星潭石花凍早餐", "旁邊小店石花凍＋車輪餅，在地早餐組合超值"),
        ("☕", "花蓮市區老宅咖啡", "中正路周邊老宅改建咖啡館，週間有店長特調優惠"),
    ],
    "台東": [
        ("🌺", "池上農會直售", "池上農會超市有池上米、紅烏龍茶產季特價"),
        ("🦞", "成功漁港現撈", "每天早上現撈旗魚、鬼頭刀，料理店門口超新鮮"),
        ("♨️", "知本溫泉平日優惠", "各旅館泡湯池平日比假日便宜，人也少很多"),
        ("🎪", "台東縱谷農夫市集", "週末台東糖廠附近有有機農夫市集，原住民特色農產"),
        ("🌾", "關山有機米直售", "關山農家有機稻米產季直售，比市區百貨超市便宜"),
        ("☕", "台東火車站周邊咖啡", "老宅改建咖啡館，週間有旅客優惠"),
    ],
    "基隆": [
        ("🦞", "崁仔頂漁市早市", "凌晨 1-5 點漁貨批發市場，早起的人有最新鮮的魚"),
        ("🍜", "廟口夜市平日優惠", "廟口小吃平日遊客少，攤販有更多時間服務，可挑慢慢吃"),
        ("🌊", "正濱漁港彩色屋", "週間人少，附近咖啡廳有午後優惠，景色超美"),
        ("🏔️", "情人湖周邊農產", "周邊農家有機茶葉、蔬菜直售，假日下午有特惠"),
        ("☕", "仁愛區咖啡巷弄", "基隆市區精品咖啡館隱藏在巷弄，週間有特調優惠"),
        ("🛒", "仁愛市場早市", "傳統市場早上 6-9 點最齊全，蔬果比超市便宜"),
    ],
    "苗栗": [
        ("🍓", "大湖草莓季直售", "冬季草莓採摘農場，比市面上便宜且超新鮮，建議平日來"),
        ("🎨", "三義木雕老街", "平日工藝師傅有空可以聊作品，部分有平日特惠"),
        ("🌺", "獅頭山桂花季", "桂花產季農家有桂花釀、糕點直售，價格親民"),
        ("☕", "頭份商圈咖啡", "頭份近年咖啡館增多，週間有買一送一優惠"),
        ("🧺", "公館番茄農場", "公館紅番茄採摘農場產季直售，酸甜剛好"),
        ("🏔️", "南庄老街平日優惠", "假日人潮多，平日來商家有時間介紹手工藝品"),
    ],
    "彰化": [
        ("🐄", "田尾公路花園直售", "花卉直售比花店便宜 3-5 成，假日有更多攤位"),
        ("🌺", "鹿港老街平日優惠", "平日遊客少，鹿港小吃攤、傳統糕餅行服務更好"),
        ("🍱", "彰化肉圓老店", "市區幾家百年老店早上 9 點前就有新鮮現蒸，別錯過"),
        ("☕", "員林商圈午間優惠", "員林百貨周邊餐廳週間有午餐套餐特惠"),
        ("🛒", "彰化第一市場", "彰化市傳統市場早上食材新鮮齊全，比量販店便宜"),
        ("🌿", "埔心牧場平日優惠", "平日入場票較假日便宜，動物互動也更悠閒"),
    ],
    "南投": [
        ("🍵", "鹿谷高山茶直售", "鹿谷茶農產季在農場直售，比市區茶行便宜且可試喝"),
        ("🌊", "日月潭周邊農產", "日月潭周邊邵族農特產直售，紅茶、香菇、木耳"),
        ("🌸", "武陵農場花季", "春天賞梅/賞桃花，平日進場更有空間拍照"),
        ("☕", "埔里咖啡一條街", "埔里精品咖啡發展多年，週間有特調優惠組合"),
        ("🧺", "集集小鎮農產採買", "集集農家有有機蔬菜直售，順遊集集車站"),
        ("🌿", "奧萬大楓葉季", "秋季賞楓，平日門票比假日便宜且不塞車"),
    ],
    "雲林": [
        ("🧅", "西螺蔬果批發直售", "西螺果菜市場周邊農家直售，大蒜、洋蔥超便宜"),
        ("🍊", "古坑柳丁、咖啡", "古坑柳丁產季農場直售，台灣咖啡豆也在這裡"),
        ("🎪", "北港朝天宮廟會", "媽祖誕辰前後廟會熱鬧，周邊小吃攤有廟會特惠"),
        ("☕", "斗六市區咖啡街", "斗六太平老街周邊老宅改咖啡，週間有優惠"),
        ("🛒", "斗南傳統市場", "斗南市場早市蔬果新鮮，供應台北市場的源頭"),
        ("🌺", "虎尾糖廠冰棒", "台灣糖業博物館糖廠冰棒現在也能買到，懷舊"),
    ],
    "澎湖": [
        ("🦞", "馬公漁港現撈直售", "下午漁船靠港後有現撈海鮮，比觀光市場便宜很多"),
        ("🌺", "花火節淡季旅遊", "花火節結束後民宿費用大降，海水一樣清澈"),
        ("🐠", "吉貝浮潛非假日", "非假日包船費較低，海水視野好且安靜"),
        ("☕", "馬公市區古厝咖啡", "老建築改建咖啡館，週間有下午茶套餐優惠"),
        ("🛒", "中央老街海產乾貨", "海產乾貨直接跟店家買比台灣本島便宜"),
        ("🌿", "七美、望安秘境", "離島來回船票平日比假日便宜，人少景更美"),
    ],
}

_GENERIC_LOCAL_DEALS = [
    ("🛒", "傳統市場早市特惠", "傳統市場早上 8 點前攤販最多，蔬果比超市新鮮且便宜"),
    ("♨️", "當地溫泉平日優惠", "若附近有溫泉，平日泡湯比假日便宜約 2-3 成"),
    ("🌿", "農夫直售站採買", "搜尋附近「農產品直售站」，當季農產比超市新鮮且便宜"),
    ("🏔️", "國家公園步道免費", "多數國家公園步道免費，平日人少更好走、好停車"),
    ("🎨", "縣市立美術館免費展", "各縣市文化中心美術館展覽多數免費，平日來更舒適"),
    ("🍜", "老市場隱藏美食", "傳統市場二樓或深處常有低調老攤，價格比周邊餐廳實惠"),
]

# ─── 驚喜快取（module 層級 lazy-load）─────────────────────
_SURPRISE_CACHE: dict | None = None
_ACCUPASS_CACHE: dict | None = None


def _load_surprise_cache() -> dict:
    """載入爬蟲驚喜快取（surprise_cache.json）"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "surprise_cache.json")
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_surprise_cache() -> dict:
    global _SURPRISE_CACHE
    if _SURPRISE_CACHE is None:
        _SURPRISE_CACHE = _load_surprise_cache()
    return _SURPRISE_CACHE


def _load_accupass_cache() -> dict:
    """載入 Accupass 爬蟲快取（accupass_cache.json）"""
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_path = os.path.join(base, "accupass_cache.json")
        if not os.path.exists(cache_path):
            return {}
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", {})
    except Exception:
        return {}


def _get_accupass_cache() -> dict:
    global _ACCUPASS_CACHE
    if _ACCUPASS_CACHE is None:
        _ACCUPASS_CACHE = _load_accupass_cache()
    return _ACCUPASS_CACHE


# ─── 工具函式 ──────────────────────────────────────────────

def _bot_invite_text() -> str:
    """生成 bot 邀請文字"""
    if LINE_BOT_ID:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{LINE_BOT_ID}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"


def _day_city_hash(doy: int, city: str, salt: int = 0) -> int:
    import hashlib
    key = f"{doy}:{city}:{salt}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


def _day_user_city_hash(doy: int, city: str, user_id: str, salt: int = 0) -> int:
    import hashlib
    key = f"{doy}:{city}:{user_id}:{salt}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


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


# ─── 天氣 API 函式 ─────────────────────────────────────────

def _fetch_cwa_weather(city: str) -> dict:
    """呼叫中央氣象署 F-C0032-001 取得36小時天氣預報（Redis cache 15 分鐘）"""
    if not _CWA_KEY:
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
        f"?Authorization={_CWA_KEY}"
        f"&locationName={urllib.parse.quote(cwb_name)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("success") != "true":
            return {"ok": False, "error": "api_error"}
        locs = data["records"]["location"]
        if not locs:
            return {"ok": False, "error": "no_data"}
        elems = {e["elementName"]: e["time"] for e in locs[0]["weatherElement"]}

        def _get(key: str, idx: int, default: str = "—") -> str:
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
        print(f"[weather] {e}")
        return {"ok": False, "error": str(e)}


def _wx_icon(wx: str) -> str:
    if "晴" in wx and "雲" not in wx:  return "☀️"
    if "晴" in wx:                     return "🌤️"
    if "雷" in wx:                     return "⛈️"
    if "雨" in wx:                     return "🌧️"
    if "陰" in wx:                     return "☁️"
    if "多雲" in wx:                   return "⛅"
    if "雪" in wx:                     return "❄️"
    return "🌤️"


def _outfit_advice(max_t: int, min_t: int, pop: int) -> tuple:
    """回傳 (穿搭建議, 補充說明, 雨傘提示)"""
    if max_t >= 32:
        c, n = "輕薄短袖＋透氣材質", "防曬乳必備，帽子加分，小心中暑"
    elif max_t >= 28:
        c, n = "短袖為主，薄外套備著", "室內冷氣強，包包放一件薄外套"
    elif max_t >= 24:
        c, n = "薄長袖或短袖＋輕便外套", "早晚涼，外套放包包最方便"
    elif max_t >= 20:
        c, n = "輕便外套或薄夾克", "早晚溫差大，多一層最安全"
    elif max_t >= 16:
        c, n = "毛衣＋外套", "圍巾帶著，隨時可以拿出來用"
    elif max_t >= 12:
        c, n = "厚外套＋衛衣", "手套、圍巾都考慮帶上"
    else:
        c, n = "羽絨衣＋多層次穿搭", "室內室外差很多，穿脫方便最重要"

    umbrella = ""
    if pop >= 70:    umbrella = "☂️ 雨傘必帶！降雨機率很高"
    elif pop >= 40:  umbrella = "🌂 建議帶折疊傘備用"
    elif pop >= 20:  umbrella = "☁️ 零星降雨可能，輕便傘備著"
    return c, n, umbrella


def _fetch_aqi(city: str) -> dict:
    """從環境部 aqx_p_432 取得即時 AQI（需 MOE_API_KEY）"""
    if not _MOE_KEY:
        return {"ok": False}
    station = _AQI_STATION.get(city, city)
    url = (
        "https://data.moenv.gov.tw/api/v2/aqx_p_432"
        f"?api_key={_MOE_KEY}&limit=3&sort=ImportDate+desc"
        f"&filters=SiteName,EQ,{urllib.parse.quote(station)}"
        "&format=JSON&fields=SiteName,AQI,Status,PM2.5,Pollutant"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LineBot/1.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        recs = data.get("records", [])
        if not recs:
            return {"ok": False}
        rec = recs[0]
        aqi = int(rec.get("AQI") or 0)
        status = rec.get("Status", "")
        pm25 = rec.get("PM2.5", "")
        pollutant = rec.get("Pollutant", "")
        if aqi <= 50:    color, emoji = "#2E7D32", "🟢"
        elif aqi <= 100: color, emoji = "#F9A825", "🟡"
        elif aqi <= 150: color, emoji = "#E65100", "🟠"
        elif aqi <= 200: color, emoji = "#C62828", "🔴"
        else:            color, emoji = "#6A1B9A", "🟣"
        label = f"{emoji} AQI {aqi}　{status}"
        if pm25:      label += f"　PM2.5: {pm25}"
        if pollutant: label += f"　主因: {pollutant}"
        return {"ok": True, "aqi": aqi, "label": label, "color": color}
    except Exception as e:
        print(f"[AQI] {e}")
        return {"ok": False}


def _estimate_uvi(wx: str, max_t: int) -> dict:
    """根據天氣狀況和氣溫估算紫外線等級（不依賴外部 API）"""
    import datetime as _dt
    h = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).hour

    if h < 7 or h > 17:
        return {"ok": True, "label": "☀️ 紫外線：低（日落後）", "emoji": "🟢"}

    if max_t >= 33:   base = 10
    elif max_t >= 30: base = 8
    elif max_t >= 27: base = 6
    elif max_t >= 23: base = 4
    else:             base = 3

    if "雨" in wx:   base = max(1, base - 4)
    elif "陰" in wx: base = max(2, base - 3)
    elif "雲" in wx: base = max(3, base - 1)

    if 10 <= h <= 14:   uvi = base
    elif 9 <= h <= 15:  uvi = max(2, base - 1)
    elif 7 <= h <= 17:  uvi = max(1, base - 2)
    else:               uvi = max(1, base - 3)

    if uvi <= 2:   level = "低量"
    elif uvi <= 5: level = "中量"
    elif uvi <= 7: level = "高量"
    elif uvi <= 10:level = "過量"
    else:          level = "危險"

    advice = ""
    if uvi >= 6:   advice = "建議擦防曬、戴帽子"
    elif uvi >= 3: advice = "外出建議擦防曬"

    label = f"☀️ 紫外線 {level}（UV {uvi}）"
    if advice:
        label += f"　{advice}"
    return {"ok": True, "label": label}


def _fetch_quick_oil() -> dict:
    """輕量抓中油本週 92/95/98 油價（Redis cache 6 小時）"""
    try:
        cached = _redis_get("morning_oil")
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        pass

    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            "https://www.cpc.com.tw/GetOilPriceJson.aspx?type=TodayOilPriceString",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4, context=_ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
        result = {
            "92": data.get("sPrice1", "?"),
            "95": data.get("sPrice2", "?"),
            "98": data.get("sPrice3", "?"),
        }
        try:
            _redis_set("morning_oil", json.dumps(result), ttl=21600)
        except Exception:
            pass
        return result
    except Exception:
        return {}


def _fetch_quick_rates() -> dict:
    """只抓 USD / JPY 即期賣出匯率（台灣銀行 CSV，Redis cache 1 小時）"""
    try:
        cached = _redis_get("morning_rates")
        if cached:
            return json.loads(cached) if isinstance(cached, str) else cached
    except Exception:
        pass

    import csv as _csv
    try:
        req = urllib.request.Request(
            "https://rate.bot.com.tw/xrt/flcsv/0/day",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read().decode("utf-8-sig")
        result = {}
        for row in _csv.reader(raw.strip().split("\n")):
            if len(row) < 14 or row[0] == "幣別":
                continue
            code = row[0].strip()
            if code not in ("USD", "JPY"):
                continue
            try:
                result[code] = {
                    "spot_buy":  float(row[3])  if row[3].strip()  else 0,
                    "spot_sell": float(row[13]) if row[13].strip() else 0,
                }
            except (ValueError, IndexError):
                pass
        try:
            _redis_set("morning_rates", json.dumps(result), ttl=3600)
        except Exception:
            pass
        return result
    except Exception as e:
        print(f"[quick_rates] {e}")
        return {}


def _normalize4(t: tuple) -> tuple:
    return t if len(t) == 4 else (*t, "")


def _get_daily_deal(city: str, seq: int = 0) -> tuple:
    """當日好康（週間優惠 + PTT 熱門話題）：(icon, title, body, url)"""
    import datetime as _dt
    today = _dt.date.today()
    special = _SPECIAL_DEALS.get((today.month, today.day))
    if special:
        return _normalize4(special)
    pool: list[tuple] = []
    for t in _WEEKLY_DEALS.get(today.weekday(), []):
        pool.append(_normalize4(t))
    sc = _get_surprise_cache()
    for deal in (sc.get("deals", []) if sc else []):
        tag = deal.get("tag", "PTT")
        pool.append(("🔥", f"網友熱門（{tag}）", deal.get("title", ""), deal.get("url", "")))
    for t in _SURPRISES_FALLBACK:
        pool.append(_normalize4(t))
    return pool[seq % len(pool)]


def _get_today_song(seq: int = 0) -> tuple:
    """今日歌單：(icon, title, body, url)"""
    sc = _get_surprise_cache()
    songs = sc.get("songs", []) if sc else []
    if not songs:
        return ("🎵", "今日推薦歌單", "搜尋你喜歡的歌手，找首今天的心情歌",
                "https://www.youtube.com/")
    song = songs[seq % len(songs)]
    url = song.get("url", "") or (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(f"{song.get('name','')} {song.get('artist','')} official"))
    return ("🎵", "今日推薦歌單", f"《{song.get('name','')}》— {song.get('artist','')}", url)


def _get_national_deal(city: str, user_id: str = "", seq: int = 0) -> tuple:
    """保留向後相容，實際由 _get_daily_deal 取代"""
    return _get_daily_deal(city, seq)


def _get_city_local_deal(city: str, user_id: str = "", seq: int = 0) -> tuple:
    """當地在地優惠（Accupass 活動 + 靜態優惠輪播）：(icon, title, body, url)"""
    pool: list[tuple] = []

    # Accupass 活動
    _ac = _get_accupass_cache()
    if _ac:
        city_data = _ac.get("events", _ac).get(city, {})
        for cat, evs in city_data.items():
            if isinstance(evs, list):
                for ev in evs:
                    pool.append(("🎉", f"{city}近期活動",
                                 ev.get("name", "精彩活動"), ev.get("url", "")))

    # 靜態城市優惠 + tips
    for t in _CITY_LOCAL_DEALS.get(city, _GENERIC_LOCAL_DEALS):
        pool.append(_normalize4(t))
    for t in _CITY_LOCAL_TIPS.get(city, _GENERIC_LOCAL_TIPS):
        pool.append(_normalize4(t))

    if not pool:
        pool = [_normalize4(t) for t in _GENERIC_LOCAL_DEALS + _GENERIC_LOCAL_TIPS]

    return pool[seq % len(pool)]


def _get_morning_actions() -> list:
    """根據今天日期選 4 條行動建議（每天不同）"""
    import datetime as _dt
    doy = _dt.date.today().timetuple().tm_yday
    n = len(_MORNING_ACTIONS)
    indices = [(doy * 4 + i) % n for i in range(4)]
    seen, result = set(), []
    for idx in indices:
        while idx in seen:
            idx = (idx + 1) % n
        seen.add(idx)
        result.append(_MORNING_ACTIONS[idx])
    return result


# ─── 主要 Flex 建構函式 ────────────────────────────────────

def build_weather_flex(city: str, user_id: str = "") -> list:
    """天氣＋穿搭建議卡片"""
    w = _fetch_cwa_weather(city)
    if not w.get("ok"):
        if w.get("error") == "no_key":
            return [{"type": "text", "text":
                "⚠️ 天氣功能需要設定 CWA API Key\n"
                "請到 Vercel → Settings → Environment Variables\n"
                "加入 CWA_API_KEY\n"
                "申請（免費）：https://opendata.cwa.gov.tw/user/api"}]
        return [{"type": "text", "text": f"😢 目前無法取得 {city} 的天氣資料，請稍後再試"}]

    clothes, note, umbrella = _outfit_advice(w["max_t"], w["min_t"], w["pop"])
    icon = _wx_icon(w["wx"])
    icon_n = _wx_icon(w["wx_night"])
    icon_t = _wx_icon(w["wx_tom"])
    aqi = _fetch_aqi(city)

    if "雨" in w["wx"]:        hdr = "#1565C0"
    elif w["max_t"] >= 30:    hdr = "#E65100"
    elif w["max_t"] >= 24:    hdr = "#F57C00"
    else:                     hdr = "#37474F"

    body = [
        {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{icon} {w['wx']}", "size": "lg", "weight": "bold",
             "color": hdr, "flex": 3, "wrap": True},
            {"type": "text", "text": f"{w['min_t']}–{w['max_t']}°C",
             "size": "lg", "weight": "bold", "color": hdr, "flex": 2, "align": "end"},
        ]},
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": f"💧 降雨 {w['pop']}%", "size": "sm", "color": "#555555", "flex": 1},
            {"type": "text", "text": f"今晚 {icon_n} 雨{w['pop_night']}%",
             "size": "sm", "color": "#555555", "flex": 1, "align": "end"},
        ]},
    ]
    if aqi.get("ok"):
        body.append({"type": "text", "text": aqi["label"], "size": "sm",
                     "color": aqi["color"], "wrap": True, "margin": "xs"})
    body.append({"type": "separator", "margin": "md"})
    body += [
        {"type": "text", "text": "👗 今日穿搭建議", "size": "md", "weight": "bold",
         "color": "#333333", "margin": "md"},
        {"type": "text", "text": clothes, "size": "sm", "color": "#444444",
         "wrap": True, "margin": "xs"},
        {"type": "text", "text": f"💡 {note}", "size": "sm", "color": "#777777",
         "wrap": True, "margin": "xs"},
    ]
    if umbrella:
        body.append({"type": "text", "text": umbrella, "size": "sm",
                     "color": "#1565C0", "weight": "bold", "margin": "sm"})

    uvi = _estimate_uvi(w["wx"], w["max_t"])
    if uvi.get("ok"):
        body.append({"type": "text", "text": uvi["label"], "size": "sm",
                     "color": "#E65100", "wrap": True, "margin": "xs"})

    body.append({"type": "separator", "margin": "md"})

    _suggest = []
    _tdiff = w["max_t"] - w["min_t"]
    if _tdiff >= 10:
        _suggest.append(f"🌡️ 今日溫差 {_tdiff}°C，外出一定要帶外套")
    elif _tdiff >= 7:
        _suggest.append(f"🌡️ 溫差 {_tdiff}°C，早晚記得加衣")

    if "雨" in w["wx"] or w["pop"] >= 60:
        _suggest.append("🏠 雨天最適合咖啡廳、室內逛街或窩在家")
    elif w["max_t"] >= 33:
        _suggest.append("🏊 高溫天，泳池或室內冷氣活動最涼快")
    elif w["max_t"] >= 27 and ("晴" in w["wx"] or "多雲" in w["wx"]):
        _suggest.append("🚴 好天氣！適合騎車、健行、戶外活動")
    elif w["max_t"] <= 20:
        _suggest.append("☕ 涼爽天，逛夜市、喝熱飲、散步心情好")
    else:
        _suggest.append("🌿 天氣舒適，外出走走心情好")

    if aqi.get("ok"):
        if aqi["aqi"] <= 50:
            _suggest.append("💨 空氣品質良好，適合開窗通風")
        elif aqi["aqi"] > 100:
            _suggest.append("😷 空氣品質不佳，外出建議戴口罩")

    _trend = w["max_tom"] - w["max_t"]
    if _trend >= 3:
        _suggest.append(f"📈 明天升溫 +{_trend}°C，越來越熱囉")
    elif _trend <= -3:
        _suggest.append(f"📉 明天降溫 {abs(_trend)}°C，多備一件衣")
    elif "雨" in w["wx_tom"] and "雨" not in w["wx"]:
        _suggest.append("🌧️ 明天有雨，今天記得把衣服收進來")

    if _suggest:
        body.append({"type": "text", "text": "💡 今日建議",
                     "size": "sm", "weight": "bold", "color": "#37474F", "margin": "sm"})
        for _s in _suggest:
            body.append({"type": "text", "text": _s, "size": "xs",
                         "color": "#555555", "wrap": True, "margin": "xs"})

    body += [
        {"type": "separator", "margin": "md"},
        {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
            {"type": "text", "text": "明日", "size": "sm", "color": "#999999", "flex": 1},
            {"type": "text", "text": f"{icon_t} {w['wx_tom']}", "size": "sm",
             "color": "#555555", "flex": 2},
            {"type": "text", "text": f"{w['min_tom']}–{w['max_tom']}°C  雨{w['pop_tom']}%",
             "size": "sm", "color": "#555555", "flex": 3, "align": "end"},
        ]},
    ]

    food_label = "雨天吃什麼" if "雨" in w["wx"] else "今天吃什麼"
    food_text  = "吃什麼 享樂" if "雨" in w["wx"] else "今天吃什麼"

    _umbrella_hint = f"\n{umbrella}" if umbrella else ""
    _weather_share = (
        f"🌤️ {city}今天天氣\n"
        f"{icon} {w['wx']}　{w['min_t']}–{w['max_t']}°C\n"
        f"💧 降雨 {w['pop']}%{_umbrella_hint}\n\n"
        f"👗 穿搭建議：{clothes}\n"
        f"💡 {note}"
        f"{_bot_invite_text()}"
    )
    _weather_share_url = "https://line.me/R/share?text=" + urllib.parse.quote(_weather_share)

    return [{"type": "flex", "altText": f"{city}天氣 {w['min_t']}–{w['max_t']}°C {w['wx']}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "horizontal",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "box", "layout": "vertical", "width": "4px",
                                 "cornerRadius": "4px", "backgroundColor": "#26A69A", "contents": []},
                                {"type": "box", "layout": "vertical", "flex": 1,
                                 "paddingStart": "12px", "contents": [
                                     {"type": "text", "text": f"🌤️ {city}今日天氣",
                                      "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                     {"type": "text", "text": "中央氣象署即時預報＋穿搭建議",
                                      "color": "#8892B0", "size": "xs", "margin": "xs"},
                                 ]},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "xs",
                          "contents": body},
                 "footer": {"type": "box", "layout": "vertical", "spacing": "sm",
                            "contents": [
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "contents": [
                                     {"type": "button", "style": "primary", "color": "#26A69A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message", "label": "重新整理",
                                                 "text": f"{city}天氣"}},
                                     {"type": "button", "style": "primary", "color": "#1A1F3A",
                                      "flex": 1, "height": "sm",
                                      "action": {"type": "message",
                                                 "label": food_label, "text": food_text}},
                                 ]},
                                {"type": "box", "layout": "horizontal", "spacing": "sm",
                                 "contents": [
                                     {"type": "button", "style": "secondary", "flex": 1,
                                      "height": "sm",
                                      "action": {"type": "message", "label": "📍 換城市",
                                                 "text": "換城市"}},
                                     {"type": "button", "style": "link", "flex": 1,
                                      "height": "sm",
                                      "action": {"type": "uri",
                                                 "label": "📤 傳給家人朋友",
                                                 "uri": _weather_share_url}},
                                 ]},
                            ]},
             }}]


def build_weather_region_picker() -> list:
    """天氣 — 選擇地區（第一步）"""
    buttons = [
        {"type": "button", "style": "primary", "color": "#37474F", "height": "sm",
         "action": {"type": "message", "label": f"📍 {r}", "text": f"天氣 地區 {r}"}}
        for r in _AREA_REGIONS.keys()
    ]
    return [{"type": "flex", "altText": "請選擇地區查天氣",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": "🌤️ 天氣＋穿搭建議",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "選擇地區，馬上告訴你今天穿什麼",
                                 "color": "#CFD8DC", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": buttons},
             }}]


def build_weather_city_picker(region: str = "") -> list:
    """天氣 — 選擇城市（第二步）"""
    areas = _AREA_REGIONS.get(region, _ALL_CITIES)
    rows = []
    for i in range(0, len(areas), 3):
        chunk = areas[i:i+3]
        cells = [
            {"type": "box", "layout": "vertical", "flex": 1,
             "backgroundColor": "#EEF2F7", "cornerRadius": "10px",
             "paddingAll": "md",
             "action": {"type": "message", "label": c, "text": f"{c}天氣"},
             "contents": [
                 {"type": "text", "text": c, "align": "center",
                  "size": "md", "color": "#1A2D50", "weight": "bold"}
             ]}
            for c in chunk
        ]
        rows.append({"type": "box", "layout": "horizontal",
                     "spacing": "sm", "contents": cells})
    rows.append({"type": "button", "style": "link", "height": "sm",
                 "action": {"type": "message", "label": "← 重選地區", "text": "天氣"}})
    return [{"type": "flex", "altText": f"{region}天氣 — 選城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "styles": {"header": {"backgroundColor": "#37474F"}},
                 "header": {"type": "box", "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": f"🌤️ {region} — 選擇城市",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "contents": rows},
             }}]


def _build_morning_city_picker() -> list:
    """早安城市選擇（分北中南東離島）"""
    ACCENT = "#1A1F3A"

    def _btn(c: str, primary: bool = False) -> dict:
        btn: dict = {"type": "button", "style": "primary" if primary else "secondary",
               "height": "sm", "flex": 1,
               "action": {"type": "message", "label": c, "text": f"早安 {c}"}}
        if primary:
            btn["color"] = ACCENT
        return btn

    def _rows(cities: list, primary: bool = False) -> list:
        btns = [_btn(c, primary) for c in cities]
        return [{"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": btns[i:i+3]}
                for i in range(0, len(btns), 3)]

    def _section(label: str, cities: list, primary: bool = False) -> list:
        return [{"type": "text", "text": label, "size": "xs",
                 "color": "#8892B0", "margin": "md"}] + _rows(cities, primary)

    body: list = []
    body += _section("🏙️ 北部", ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"], True)
    body += _section("🌾 中部", ["台中", "彰化", "南投", "雲林"])
    body += _section("☀️ 南部", ["嘉義", "台南", "高雄", "屏東"])
    body += _section("🏔️ 東部 ＋ 離島", ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"])

    return [{"type": "flex", "altText": "早安！請選擇你的城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": ACCENT, "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "☀️ 早安！",
                                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                {"type": "text", "text": "選擇城市，之後每天自動顯示當地資訊",
                                 "color": "#8892B0", "size": "xs", "wrap": True, "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": body},
             }}]


def build_switch_city_picker(current_city: str = "") -> list:
    """切換城市卡片：按下後送 '切換城市 {city}'，同時清除 GPS 快取"""
    ACCENT = "#1A1F3A"

    def _btn(c: str) -> dict:
        style = "primary"
        btn: dict = {"type": "button", "style": style, "height": "sm", "flex": 1,
                     "color": "#2979FF" if c == current_city else ACCENT,
                     "action": {"type": "message", "label": c,
                                "text": f"切換城市 {c}"}}
        return btn

    def _rows(cities: list) -> list:
        btns = [_btn(c) for c in cities]
        return [{"type": "box", "layout": "horizontal", "spacing": "sm",
                 "contents": btns[i:i+3]}
                for i in range(0, len(btns), 3)]

    def _section(label: str, cities: list) -> list:
        return [{"type": "text", "text": label, "size": "xs",
                 "color": "#8892B0", "margin": "md"}] + _rows(cities)

    body: list = []
    body += _section("🏙️ 北部", ["台北", "新北", "基隆", "桃園", "新竹", "苗栗"])
    body += _section("🌾 中部", ["台中", "彰化", "南投", "雲林"])
    body += _section("☀️ 南部", ["嘉義", "台南", "高雄", "屏東"])
    body += _section("🏔️ 東部 ＋ 離島", ["宜蘭", "花蓮", "台東", "澎湖", "金門", "連江"])

    subtitle = f"目前城市：{current_city}" if current_city else "選擇後自動套用到美食、天氣、活動"
    return [{"type": "flex", "altText": "切換城市",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": ACCENT, "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": "📍 切換城市",
                                 "color": "#FFFFFF", "size": "xl", "weight": "bold"},
                                {"type": "text", "text": subtitle,
                                 "color": "#8892B0", "size": "xs", "wrap": True, "margin": "sm"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "12px", "contents": body},
             }}]


def build_morning_summary(text: str, user_id: str = "") -> list:
    """早安摘要：天氣 + 穿搭 + 匯率 + 油價 + 今日好康"""
    import threading as _thr
    import datetime as _dt

    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        city = city_m.group(1)
        _set_user_city(user_id, city)
    else:
        saved = _get_user_city(user_id)
        if saved:
            city = saved
        else:
            return _build_morning_city_picker()

    wx_result: dict = {}
    rates: dict = {}
    oil: dict = {}

    def _wx() -> None:
        nonlocal wx_result
        wx_result = _fetch_cwa_weather(city)

    def _rt() -> None:
        nonlocal rates
        rates = _fetch_quick_rates()

    def _oil_fn() -> None:
        nonlocal oil
        oil = _fetch_quick_oil()

    _t1 = _thr.Thread(target=_wx, daemon=True)
    _t2 = _thr.Thread(target=_rt, daemon=True)
    _t3 = _thr.Thread(target=_oil_fn, daemon=True)
    _t1.start(); _t2.start(); _t3.start()
    import time as _time
    _dl = _time.time() + 3
    _t1.join(timeout=max(0, _dl - _time.time()))
    _t2.join(timeout=max(0, _dl - _time.time()))
    _t3.join(timeout=max(0, _dl - _time.time()))

    today = _dt.date.today()
    doy   = today.timetuple().tm_yday
    _WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
    today_str = f"{today.month}月{today.day}日（星期{_WEEKDAYS[today.weekday()]}）"
    # 每次呼叫累加計數，讓同一天多次查詢顯示不同小驚喜
    _seq_key = f"morning_seq:{user_id}:{doy}"
    _seq = int(_redis_get(_seq_key) or 0)
    _redis_set(_seq_key, str(_seq + 1), ttl=86400)

    if wx_result.get("ok"):
        wx = wx_result
        wx_icon = _wx_icon(wx["wx"])
        pop = wx["pop"]
        wx_main = f"{wx_icon} {wx['wx']}　{wx['min_t']}–{wx['max_t']}°C"
        if pop >= 70:
            wx_hint = "☂️ 降雨機率高，記得帶傘！"
        elif pop >= 40:
            wx_hint = "🌂 可能有雨，建議帶傘備用"
        elif wx["max_t"] - wx["min_t"] >= 10:
            wx_hint = "早晚溫差大，注意保暖"
        elif wx["max_t"] >= 32:
            wx_hint = "中午很熱，注意防曬補水"
        else:
            wx_hint = "氣溫舒適，適合外出走走"
        outfit, _, _ = _outfit_advice(wx["max_t"], wx["min_t"], pop)
        parts = [outfit]
        if pop >= 40:
            parts.append("帶傘")
        if wx["max_t"] >= 28:
            parts.append("防曬必備")
        wx_outfit = "👔 " + "＋".join(parts)
        wx_night_icon = _wx_icon(wx.get("wx_night", ""))
        wx_night = f"今晚 {wx_night_icon} 雨{wx.get('pop_night', 0)}%"
        wx_tom_icon = _wx_icon(wx.get("wx_tom", ""))
        wx_tomorrow = f"明天 {wx_tom_icon} {wx.get('min_tom','?')}-{wx.get('max_tom','?')}°C 雨{wx.get('pop_tom',0)}%"
        wx_items = [
            {"type": "text", "text": wx_main,     "size": "md", "weight": "bold", "color": "#1A2D50"},
            {"type": "text", "text": wx_hint,     "size": "xs", "color": "#E65100", "wrap": True},
            {"type": "text", "text": wx_outfit,   "size": "xs", "color": "#37474F", "wrap": True, "margin": "sm"},
            {"type": "text", "text": wx_night,    "size": "xs", "color": "#607D8B", "margin": "xs"},
            {"type": "text", "text": wx_tomorrow, "size": "xs", "color": "#607D8B"},
        ]
    else:
        wx_main = "天氣資料暫時無法取得"
        wx_items = [
            {"type": "text", "text": "☁️ 天氣資料暫時無法取得", "size": "sm", "color": "#888"},
            {"type": "text", "text": f"可說「{city}天氣」查詢",  "size": "xs", "color": "#AAA"},
        ]

    info_items = []
    usd = rates.get("USD", {}) if rates else {}
    jpy = rates.get("JPY", {}) if rates else {}
    if usd.get("spot_sell"):
        r = usd["spot_sell"]
        tip = "🎉便宜" if r <= 29.5 else "⚖️普通" if r <= 31.0 else "⚠️偏高" if r <= 32.0 else "💸高點"
        info_items.append({"type": "text", "text": f"💵 美金 {r:.2f}　{tip}",
                           "size": "xs", "color": "#37474F", "wrap": True})
    if jpy.get("spot_sell"):
        r = jpy["spot_sell"]
        tip = "🎉超便宜" if r <= 0.215 else "😊不錯" if r <= 0.225 else "⚖️普通" if r <= 0.240 else "💸偏貴"
        info_items.append({"type": "text", "text": f"💴 日幣 {r:.4f}　{tip}",
                           "size": "xs", "color": "#37474F", "wrap": True})
    if oil and oil.get("92") and oil["92"] != "?":
        try:
            p = float(oil["92"])
            tip = "🎉便宜加滿" if p <= 28.5 else "⚖️普通" if p <= 30.5 else "⚠️略高" if p <= 32.0 else "💸高點"
            info_items.append({"type": "text",
                               "text": f"⛽ 92/{oil['92']}　95/{oil['95']}　98/{oil['98']}　{tip}",
                               "size": "xs", "color": "#37474F", "wrap": True})
        except Exception:
            pass
    if not info_items:
        info_items = [{"type": "text", "text": "匯率/油價暫時無法取得", "size": "xs", "color": "#AAA"}]

    deal_icon, deal_title, deal_body, deal_url = _get_daily_deal(city, seq=_seq)
    song_icon, song_title, song_body, song_url  = _get_today_song(seq=_seq)
    loc_icon,  loc_title,  loc_body,  loc_url   = _get_city_local_deal(city, user_id, seq=_seq)

    def _link(url: str, query: str) -> str:
        return url or "https://www.google.com/search?q=" + urllib.parse.quote(query)

    deal_link = _link(deal_url, deal_title)
    song_link = _link(song_url, song_body)
    loc_link  = _link(loc_url,  f"{loc_title} {city}")

    tip = _MORNING_ACTIONS[doy % len(_MORNING_ACTIONS)]

    _bot_invite = f"https://line.me/R/ti/p/{LINE_BOT_ID}" if LINE_BOT_ID else "https://line.me/R/"
    _share_text = (
        f"☀️ 早安！{city} {today_str}\n\n"
        f"🌤 {wx_main}\n\n"
        f"{nat_icon} {nat_title}：{nat_body}\n\n"
        f"👉 加「生活優轉」每天收到專屬好康：\n{_bot_invite}"
    )
    import urllib.parse as _up
    _share_url = f"https://social-plugins.line.me/lineit/share?url={_up.quote(_share_text)}"

    return [{"type": "flex", "altText": f"☀️ 早安！{city} {today_str}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": f"☀️ 早安！{city}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                {"type": "text", "text": today_str,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                          "paddingAll": "14px", "contents": [
                     {"type": "text", "text": "🌤 今日天氣", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0"},
                     *wx_items,
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "💹 今日匯率＋油價", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "md"},
                     *info_items,
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "🎁 今日小驚喜", "size": "xs",
                      "weight": "bold", "color": "#E65100", "margin": "md"},
                     *[item for icon, title, body, link in [
                         (loc_icon,  loc_title,  loc_body,  loc_link),
                         (deal_icon, deal_title, deal_body, deal_link),
                         (song_icon, song_title, song_body, song_link),
                       ] for item in [
                         {"type": "text", "text": f"{icon} {title}", "size": "xs",
                          "weight": "bold", "color": "#5C6BC0", "margin": "sm"},
                         {"type": "box", "layout": "vertical", "margin": "xs",
                          "action": {"type": "uri", "label": body[:40], "uri": link},
                          "contents": [{"type": "text", "text": body + "  🔍",
                                        "size": "xs", "color": "#1565C0",
                                        "wrap": True, "decoration": "underline"}]},
                     ]],
                     {"type": "separator", "margin": "md"},
                     {"type": "text", "text": "💡 今日健康提醒", "size": "xs",
                      "weight": "bold", "color": "#5C6BC0", "margin": "md"},
                     {"type": "text", "text": tip, "size": "xs",
                      "color": "#37474F", "wrap": True},
                 ]},
                 "footer": {"type": "box", "layout": "vertical",
                            "spacing": "xs", "paddingAll": "10px",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "吃什麼", "text": "今天吃什麼"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "查活動", "text": "近期活動"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "健康", "text": "健康小幫手"}},
                      ]},
                     {"type": "button", "style": "primary", "color": "#E65100", "height": "sm",
                      "action": {"type": "uri", "label": "📤 分享給朋友", "uri": _share_url}},
                     {"type": "button", "style": "secondary", "height": "sm",
                      "action": {"type": "message", "label": f"📍 換城市（{city}）",
                                 "text": "換城市"}},
                 ]},
             }}]


def build_weather_message(text: str, user_id: str = "") -> list:
    """天氣模組主路由"""
    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    if city_m:
        _set_user_city(user_id, city_m.group(1))
        return build_weather_flex(city_m.group(1), user_id=user_id)

    for r in _AREA_REGIONS:
        if r in text:
            return build_weather_city_picker(r)

    return build_weather_region_picker()
