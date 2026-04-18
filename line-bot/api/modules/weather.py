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
from utils.redis import get_user_pref as _get_user_pref, update_user_pref as _update_user_pref

# ─── 靜態資料載入 ──────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_json(filename: str, default):
    """從 data/ 目錄讀取 JSON，失敗時回傳 default。"""
    try:
        with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as _f:
            return json.load(_f)
    except Exception:
        return default


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

# ─── 靜態內容（從 JSON 載入，加速冷啟動）────────────────────
_wd = _load_json("weather_content.json", {})
_MORNING_ACTIONS: list = _wd.get("_MORNING_ACTIONS", [])
_DAILY_CHALLENGES: dict = _wd.get("_DAILY_CHALLENGES", {})
_RELAX_SUGGESTIONS: list = _wd.get("_RELAX_SUGGESTIONS", [])
_DAILY_TOPICS: list = _wd.get("_DAILY_TOPICS", [])
_NEW_FINDS: list = _wd.get("_NEW_FINDS", [])

_dd = _load_json("weather_deals.json", {})
_WEEKLY_DEALS: dict = _dd.get("_WEEKLY_DEALS", {})
_SPECIAL_DEALS: dict = _dd.get("_SPECIAL_DEALS", {})
_SURPRISES_FALLBACK: list = _dd.get("_SURPRISES_FALLBACK", [])
_GENERIC_LOCAL_TIPS: list = _dd.get("_GENERIC_LOCAL_TIPS", [])
_GENERIC_LOCAL_DEALS: list = _dd.get("_GENERIC_LOCAL_DEALS", [])

_CITY_LOCAL_TIPS: dict = _load_json("city_local_tips.json", {})
_CITY_LOCAL_DEALS: dict = _load_json("city_local_deals.json", {})

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
            _redis_set(f"cwa_wx:{city}", json.dumps(result), ttl=3600)
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
    special = _SPECIAL_DEALS.get(f"{today.month}_{today.day}")
    if special:
        return _normalize4(special)
    pool: list[tuple] = []
    for t in _WEEKLY_DEALS.get(str(today.weekday()), []):
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
    """早安摘要：主卡（天氣+穿搭+微挑戰+streak）＋今日小驚喜 Carousel"""
    import threading as _thr
    import datetime as _dt

    _TW_TZ = _dt.timezone(_dt.timedelta(hours=8))
    today = _dt.datetime.now(_TW_TZ).date()
    today_date = today.isoformat()
    yesterday_date = (today - _dt.timedelta(days=1)).isoformat()
    _WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
    today_str = f"{today.month}月{today.day}日（星期{_WEEKDAYS[today.weekday()]}）"
    _seq_key = f"morning_seq:{user_id}:{today_date}"

    # ── 城市判斷（純文字，不需 I/O）──────────────────────────
    all_cities_pat = "|".join(_ALL_CITIES)
    city_m = re.search(rf"({all_cities_pat})", text)
    city_in_text = city_m.group(1) if city_m else None

    # ── 快取命中直接返回（跳過所有 I/O）──────────────────────
    if user_id and not city_in_text:
        _card_key = f"morning_card:v2:{user_id}:{today_date}"
        _cached = _redis_get(_card_key)
        if _cached:
            return _cached

    # ── 所有 I/O 並行（天氣 + city + pref + seq），總 deadline 2.0s ──
    wx_result: dict = {}
    _saved_city: list = [""]
    _pref_box:   list = [{}]
    _seq_box:    list = [0]

    def _t_wx() -> None:
        c = city_in_text or _saved_city[0]
        if c:
            wx_result.update(_fetch_cwa_weather(c))

    def _t_city() -> None:
        if not city_in_text and user_id:
            _saved_city[0] = _get_user_city(user_id) or ""

    def _t_pref() -> None:
        if user_id:
            _pref_box[0] = _get_user_pref(user_id) or {}

    def _t_seq() -> None:
        _seq_box[0] = int(_redis_get(_seq_key) or 0)

    if city_in_text:
        # 城市已知 → 4 個 I/O 全並行
        all_threads = [_thr.Thread(target=f, daemon=True)
                       for f in (_t_wx, _t_pref, _t_seq)]
        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join(timeout=2.0)
    else:
        # 需先取城市，再查天氣
        prep = [_thr.Thread(target=f, daemon=True) for f in (_t_city, _t_pref, _t_seq)]
        for t in prep:
            t.start()
        for t in prep:
            t.join(timeout=1.5)
        if _saved_city[0]:
            tw = _thr.Thread(target=_t_wx, daemon=True)
            tw.start()
            tw.join(timeout=2.0)

    city = city_in_text or _saved_city[0]
    if not city:
        return _build_morning_city_picker()

    if city_in_text:
        _thr.Thread(target=lambda: _set_user_city(user_id, city_in_text), daemon=True).start()

    _pref = _pref_box[0]
    _seq  = _seq_box[0]

    # streak 計算
    _last_date = _pref.get("last_checkin_date", "")
    _streak    = _pref.get("streak", 0)
    _visited   = _pref.get("visited_count", 0)
    if user_id and _last_date != today_date:
        _streak = (_streak + 1) if _last_date == yesterday_date else 1
        # 寫回 fire-and-forget
        _new_pref = {**_pref, "last_checkin_date": today_date,
                     "streak": _streak, "visited_count": _visited}
        _thr.Thread(
            target=lambda: (_redis_set(f"user_pref:{user_id}", _new_pref, ttl=0),
                            _redis_set(_seq_key, str(_seq + 1), ttl=86400)),
            daemon=True,
        ).start()
    else:
        _thr.Thread(
            target=lambda: _redis_set(_seq_key, str(_seq + 1), ttl=86400),
            daemon=True,
        ).start()

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
            {"type": "text", "text": wx_main,     "size": "lg", "weight": "bold", "color": "#1A2D50"},
            {"type": "text", "text": wx_hint,     "size": "sm", "color": "#E65100", "wrap": True},
            {"type": "text", "text": wx_outfit,   "size": "sm", "color": "#37474F", "wrap": True, "margin": "sm"},
            {"type": "text", "text": wx_night,    "size": "xs", "color": "#607D8B", "margin": "xs"},
            {"type": "text", "text": wx_tomorrow, "size": "xs", "color": "#607D8B"},
        ]
    else:
        wx_main = "天氣資料暫時無法取得"
        wx_items = [
            {"type": "text", "text": "☁️ 天氣資料暫時無法取得", "size": "sm", "color": "#888"},
            {"type": "text", "text": f"可說「{city}天氣」查詢",  "size": "xs", "color": "#AAA"},
        ]

    deal_icon, deal_title, deal_body, deal_url = _get_daily_deal(city, seq=_seq)
    song_icon, song_title, song_body, song_url  = _get_today_song(seq=_seq)
    loc_icon,  loc_title,  loc_body,  loc_url   = _get_city_local_deal(city, user_id, seq=_seq)

    _challenge_pool = _DAILY_CHALLENGES[str(today.weekday())]
    _challenge = _challenge_pool[_seq % len(_challenge_pool)]

    # 熱話題
    _topic_icon, _topic_q, _topic_tip = _DAILY_TOPICS[(today.toordinal() + _seq) % len(_DAILY_TOPICS)]

    # 新發現（冷知識輪播）
    _find_icon, _find_title, _find_body = _NEW_FINDS[(today.toordinal() + _seq * 3) % len(_NEW_FINDS)]

    import urllib.parse as _up

    def _link(url: str, query: str) -> str:
        return url or "https://www.google.com/search?q=" + _up.quote(query)

    def _row(icon: str, label: str, text: str, url: str) -> dict:
        """單行可點連結列"""
        return {"type": "box", "layout": "horizontal", "margin": "lg",
                "paddingTop": "8px",
                "action": {"type": "uri", "label": label, "uri": url},
                "contents": [
                    {"type": "text", "text": icon, "size": "sm", "flex": 0,
                     "color": "#5C6BC0"},
                    {"type": "box", "layout": "vertical", "flex": 1, "margin": "sm",
                     "contents": [
                         {"type": "text", "text": label, "size": "xs",
                          "weight": "bold", "color": "#777777"},
                         {"type": "text", "text": text, "size": "sm",
                          "color": "#1565C0", "wrap": True, "decoration": "underline",
                          "margin": "xs"},
                     ]},
                ]}

    streak_header = (
        [{"type": "text", "text": f"🔥 連續 {_streak} 天打卡！",
          "color": "#FFD54F", "size": "xs", "margin": "xs"}]
        if _streak >= 2 else []
    )

    result = [{"type": "flex", "altText": f"☀️ 早安！{city} {today_str}",
             "contents": {
                 "type": "bubble", "size": "mega",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1A1F3A", "paddingAll": "16px",
                            "contents": [
                                {"type": "text", "text": f"☀️ 早安！{city}",
                                 "color": "#FFFFFF", "size": "lg", "weight": "bold"},
                                {"type": "text", "text": today_str,
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                                *streak_header,
                            ]},
                 "body": {"type": "box", "layout": "vertical", "spacing": "md",
                          "paddingAll": "18px", "contents": [
                     # 天氣
                     {"type": "text", "text": "🌤 今日天氣＋穿搭", "size": "sm",
                      "weight": "bold", "color": "#5C6BC0"},
                     *wx_items,
                     {"type": "separator", "margin": "xl"},
                     # 微挑戰
                     {"type": "text", "text": "🎯 今日微挑戰", "size": "sm",
                      "weight": "bold", "color": "#2E7D32", "margin": "lg"},
                     {"type": "text", "text": _challenge, "size": "sm",
                      "color": "#37474F", "wrap": True, "margin": "sm"},
                     {"type": "separator", "margin": "xl"},
                     # 今日小驚喜（5行，每行可點）
                     {"type": "text", "text": "🎁 今日小驚喜", "size": "sm",
                      "weight": "bold", "color": "#E65100", "margin": "lg"},
                     _row("🏷️", f"{deal_title}｜{deal_body}",
                          deal_body, _link(deal_url, deal_title)),
                     _row(_topic_icon, f"話題：{_topic_q[:30]}",
                          _topic_tip,
                          "https://social-plugins.line.me/lineit/share?url=" + _up.quote(_topic_q)),
                     _row(loc_icon, f"{loc_title}｜{loc_body[:25]}",
                          loc_body, _link(loc_url, f"{loc_title} {city}")),
                     _row(song_icon, f"{song_title}｜{song_body[:25]}",
                          song_body, _link(song_url, song_body)),
                     _row(_find_icon, f"新發現：{_find_title}",
                          _find_body,
                          "https://www.google.com/search?q=" + _up.quote(_find_title)),
                 ]},
                 "footer": {"type": "box", "layout": "vertical",
                            "spacing": "xs", "paddingAll": "10px",
                            "contents": [
                     {"type": "box", "layout": "horizontal", "spacing": "sm",
                      "contents": [
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "吃什麼", "text": "今天吃什麼"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "話題", "text": "今日話題"}},
                          {"type": "button", "style": "secondary", "height": "sm", "flex": 1,
                           "action": {"type": "message", "label": "換城市", "text": "換城市"}},
                      ]},
                 ]},
             }}]

    # fire-and-forget 寫快取（不含城市切換的請求才快取，避免記錯城市）
    if user_id and not city_in_text:
        _thr.Thread(
            target=lambda: _redis_set(f"morning_card:v2:{user_id}:{today_date}", result, ttl=14400),
            daemon=True,
        ).start()
    return result




def build_relax_message(user_id: str = "") -> list:
    """今日放鬆建議（低壓力、無義務）"""
    import datetime as _dt
    _TW_TZ = _dt.timezone(_dt.timedelta(hours=8))
    today = _dt.datetime.now(_TW_TZ).date()
    today_date = today.isoformat()
    _seq_key = f"relax_seq:{user_id}:{today_date}"
    _seq = int(_redis_get(_seq_key) or 0)
    _redis_set(_seq_key, str(_seq + 1), ttl=86400)
    suggestion = _RELAX_SUGGESTIONS[(today.toordinal() + _seq) % len(_RELAX_SUGGESTIONS)]
    return [{"type": "flex", "altText": "今日放鬆建議",
             "contents": {
                 "type": "bubble", "size": "kilo",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#2C3E50", "paddingAll": "14px",
                            "contents": [
                                {"type": "text", "text": "🌙 放鬆一下",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "今天辛苦了，不用做任何事",
                                 "color": "#8892B0", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical", "paddingAll": "16px",
                          "contents": [
                     {"type": "text", "text": suggestion,
                      "size": "sm", "color": "#ECEFF1", "wrap": True, "lineSpacing": "6px"},
                 ]},
                 "footer": {"type": "box", "layout": "horizontal",
                            "spacing": "sm", "paddingAll": "10px",
                            "contents": [
                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "換一個", "text": "放鬆一下"}},
                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "今日話題", "text": "今日話題"}},
                 ]},
             }}]


def build_daily_topic(user_id: str = "") -> list:
    """今日話題：一個可以跟朋友開聊的問題"""
    import datetime as _dt
    _TW_TZ = _dt.timezone(_dt.timedelta(hours=8))
    today = _dt.datetime.now(_TW_TZ).date()
    today_date = today.isoformat()
    _seq_key = f"topic_seq:{user_id}:{today_date}"
    _seq = int(_redis_get(_seq_key) or 0)
    _redis_set(_seq_key, str(_seq + 1), ttl=86400)
    icon, question, tip = _DAILY_TOPICS[(today.toordinal() + _seq) % len(_DAILY_TOPICS)]
    share_text = f"{icon} 今天的話題：{question}"
    share_url = (
        "https://social-plugins.line.me/lineit/share?url="
        + urllib.parse.quote(share_text)
    )
    return [{"type": "flex", "altText": f"{icon} 今日話題",
             "contents": {
                 "type": "bubble", "size": "kilo",
                 "header": {"type": "box", "layout": "vertical",
                            "backgroundColor": "#1565C0", "paddingAll": "14px",
                            "contents": [
                                {"type": "text", "text": f"{icon} 今日話題",
                                 "color": "#FFFFFF", "size": "md", "weight": "bold"},
                                {"type": "text", "text": "找個話頭，跟朋友聊聊",
                                 "color": "#BBDEFB", "size": "xs", "margin": "xs"},
                            ]},
                 "body": {"type": "box", "layout": "vertical",
                          "paddingAll": "16px", "spacing": "sm",
                          "contents": [
                     {"type": "text", "text": question, "size": "sm",
                      "weight": "bold", "color": "#1A237E", "wrap": True},
                     {"type": "text", "text": tip, "size": "xs",
                      "color": "#607D8B", "wrap": True, "margin": "sm"},
                 ]},
                 "footer": {"type": "box", "layout": "horizontal",
                            "spacing": "sm", "paddingAll": "10px",
                            "contents": [
                     {"type": "button", "style": "primary", "flex": 1, "height": "sm",
                      "color": "#1565C0",
                      "action": {"type": "uri", "label": "📤 分享", "uri": share_url}},
                     {"type": "button", "style": "secondary", "flex": 1, "height": "sm",
                      "action": {"type": "message", "label": "換一個", "text": "今日話題"}},
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
