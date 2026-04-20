"""
modules/parking.py — 找車位（TDX 停車 API）
==============================================
從 webhook.py 提取的獨立模組（原始行 8728–10079）。

對外接口：
  build_parking_flex(lat, lon, city="")         → list[dict]
  _build_post_parking_food(city, lat, lon, user_id="") → list[dict]
"""

import json
import os
import urllib.parse
import urllib.request

from utils.redis import redis_get as _redis_get, redis_set as _redis_set
from utils.google_places import nearby_places as _nearby_places_google
from utils.google_places import photo_url as _places_photo_url
from utils.google_places import GOOGLE_PLACES_API_KEY

# ─── 環境變數 ──────────────────────────────────────────────
TDX_CLIENT_ID     = os.environ.get("TDX_CLIENT_ID", "")
TDX_CLIENT_SECRET = os.environ.get("TDX_CLIENT_SECRET", "")

# ─── TDX Token 記憶體快取 ──────────────────────────────────
_tdx_token_cache: dict = {"token": "", "expires": 0.0}


def _get_tdx_token() -> str:
    """取得 TDX API Token（記憶體快取 50 分鐘 + Redis 快取 55 分鐘）"""
    import time
    now = time.time()
    # 1. 記憶體快取（同實例最快）
    if _tdx_token_cache["token"] and now < _tdx_token_cache["expires"]:
        return _tdx_token_cache["token"]
    if not TDX_CLIENT_ID or not TDX_CLIENT_SECRET:
        return ""
    # 2. Redis 跨實例快取（省去 OAuth 呼叫 ~1-2s）
    cached = _redis_get("tdx_token")
    if cached and isinstance(cached, str) and len(cached) > 20:
        print("[TDX] token Redis命中")
        _tdx_token_cache["token"]   = cached
        _tdx_token_cache["expires"] = now + 3000
        return cached
    try:
        payload = urllib.parse.urlencode({
            "grant_type":    "client_credentials",
            "client_id":     TDX_CLIENT_ID,
            "client_secret": TDX_CLIENT_SECRET,
        }).encode()
        req = urllib.request.Request(
            "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.loads(r.read())
        token = res.get("access_token", "")
        expires_in = int(res.get("expires_in", 3600))
        safe_ttl = max(expires_in - 60, 300)        # 提前 60 秒刷新，最少 5 分鐘
        _tdx_token_cache["token"]   = token
        _tdx_token_cache["expires"] = now + safe_ttl
        _redis_set("tdx_token", token, ttl=safe_ttl)
        print("[TDX] token 重新取得並存 Redis")
        return token
    except Exception as e:
        print(f"[TDX] token 失敗: {e}")
        return ""


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """兩點距離（公尺），Haversine 公式"""
    import math
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


def _tdx_get(path: str, token: str, timeout: int = 20) -> list:
    """呼叫 TDX API，回傳 list（支援 City 路徑的巢狀 JSON）"""
    url = "https://tdx.transportdata.tw/api/basic/v1/" + path
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            # TDX City 端點回傳 {"CarParks": [...]} 或 {"ParkingAvailabilities": [...]}
            for key in ("CarParks", "ParkingAvailabilities", "ParkingLots", "RoadSections"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # 最後嘗試第一個 list 值
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
    except Exception as e:
        print(f"[TDX] GET {path[:80]} 失敗: {e}")
        return []


# 台灣各縣市座標框（lat_min, lat_max, lon_min, lon_max, tdx_city）
# 越小的框排越前面，讓 min(area) 選最精確的城市
# TDX 實測可用城市名稱（2026-04 驗證）：
#   直轄市/省轄市不加 County：Taipei, Keelung, Hsinchu, Chiayi, Taichung, Tainan, Kaohsiung, Taoyuan
#   縣需要加 County：HsinchuCounty, MiaoliCounty, ChanghuaCounty, NantouCounty,
#                    YunlinCounty, ChiayiCounty, PingtungCounty, HualienCounty, TaitungCounty, PenghuCounty
#   NewTaipei：API 存在但目前無資料（count=0）
_TW_CITY_BOXES = [
    (25.044, 25.210, 121.460, 121.666, "Taipei"),           # 台北市 (113筆)
    (25.091, 25.199, 121.677, 121.803, "Keelung"),          # 基隆市 (39筆)
    (24.779, 24.852, 120.921, 121.018, "Hsinchu"),          # 新竹市 (24筆)
    (24.679, 24.832, 120.893, 121.082, "HsinchuCounty"),    # 新竹縣 (39筆)
    (24.683, 24.870, 120.620, 120.982, "MiaoliCounty"),     # 苗栗縣 (96筆)
    (24.820, 25.076, 121.139, 121.474, "Taoyuan"),          # 桃園市
    (23.958, 24.389, 120.530, 121.100, "Taichung"),         # 台中市
    (23.750, 24.150, 120.309, 120.745, "ChanghuaCounty"),   # 彰化縣 (176筆)
    (23.308, 23.870, 120.440, 121.070, "NantouCounty"),     # 南投縣 (23筆)
    (23.501, 23.830, 120.090, 120.722, "YunlinCounty"),     # 雲林縣 (4筆)
    (23.443, 23.521, 120.409, 120.520, "Chiayi"),           # 嘉義市 (30筆)
    (23.100, 23.580, 120.180, 120.795, "ChiayiCounty"),     # 嘉義縣 (51筆)
    (22.820, 23.450, 120.020, 120.763, "Tainan"),           # 台南市
    (22.447, 23.140, 120.160, 120.780, "Kaohsiung"),        # 高雄市 (262筆)
    (21.901, 22.809, 120.393, 120.904, "PingtungCounty"),   # 屏東縣 (20筆)
    (23.000, 24.500, 121.280, 121.720, "HualienCounty"),    # 花蓮縣 (81筆)
    (22.200, 23.500, 120.851, 121.554, "TaitungCounty"),    # 台東縣 (4筆)
    (23.200, 23.800, 119.300, 119.750, "PenghuCounty"),     # 澎湖縣
    (24.300, 25.050, 121.500, 122.000, "YilanCounty"),       # 宜蘭縣
    (24.045, 25.176, 121.120, 122.075, "NewTaipei"),        # 新北市（TDX 暫無資料）
]

# 各縣市行政中心座標（用於城市框重疊時的決勝）
_TW_CITY_CENTERS = {
    "Taipei":         (25.047, 121.517),
    "Keelung":        (25.129, 121.740),
    "NewTaipei":      (25.012, 121.465),
    "Taoyuan":        (24.993, 121.301),
    "Hsinchu":        (24.804, 120.971),
    "HsinchuCounty":  (24.839, 121.017),
    "MiaoliCounty":   (24.560, 120.820),
    "Taichung":       (24.147, 120.674),
    "ChanghuaCounty": (24.052, 120.516),
    "NantouCounty":   (23.960, 120.972),
    "YunlinCounty":   (23.707, 120.431),
    "Chiayi":         (23.480, 120.449),
    "ChiayiCounty":   (23.459, 120.432),
    "Tainan":         (22.999, 120.211),
    "Kaohsiung":      (22.627, 120.301),
    "PingtungCounty": (22.674, 120.490),
    "YilanCounty":    (24.700, 121.738),
    "HualienCounty":  (23.991, 121.611),
    "TaitungCounty":  (22.757, 121.144),
    "PenghuCounty":   (23.571, 119.579),
}


def _coords_to_tdx_city(lat: float, lon: float) -> str:
    """座標 → TDX City 路徑名稱
    多個框重疊時，用「最近城市行政中心」決勝，而非最小面積框
    （台灣縣市框大量重疊，最小面積法會把台南誤判成高雄等）
    """
    candidates = []
    for lat_min, lat_max, lon_min, lon_max, city in _TW_CITY_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            candidates.append(city)

    if not candidates:
        return "Taipei"
    if len(candidates) == 1:
        return candidates[0]

    # 多個候選：找行政中心距離最近的城市
    best, best_d = candidates[0], float("inf")
    for city in candidates:
        cx, cy = _TW_CITY_CENTERS.get(city, (25.047, 121.517))
        d = (lat - cx) ** 2 + (lon - cy) ** 2
        if d < best_d:
            best_d = d
            best = city
    return best


# 城市停車資料快取（避免同一次請求重複拉 API）
_tdx_lots_cache:  dict = {}   # city -> (timestamp, [lots])
_tdx_avail_cache: dict = {}   # city -> (timestamp, {pid: avail})
_TDX_CACHE_TTL = 90           # 快取 90 秒（即時性夠用）

# TDX v2 路邊停車快取
_TDX_STREET_CITIES = {
    "Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan",
    "HualienCounty", "PingtungCounty", "ChanghuaCounty",
}
_tdx_street_segs_cache:  dict = {}   # city -> (timestamp, [segs])
_tdx_street_avail_cache: dict = {}   # city -> (timestamp, {sid: {avail, total}})

# 停車結果快取（座標格子，約 2km×2km，共用結果避免重複計算）
_parking_result_cache: dict = {}   # "lat2_lon2" -> (timestamp, messages)
_PARKING_RESULT_TTL = 180          # 3 分鐘


def _peek_parking_cache(lat: float, lon: float):
    """快速查停車結果快取（不觸發任何 API）
    命中回傳 messages list；未命中回傳 None"""
    import time as _t
    ck  = _parking_cache_key(lat, lon)
    now = _t.time()
    r   = _redis_get(f"parking_{ck}")
    if r is not None:
        return r
    if ck in _parking_result_cache:
        ts, msgs = _parking_result_cache[ck]
        if now - ts < _PARKING_RESULT_TTL:
            return msgs
    return None


def _parking_cache_key(lat: float, lon: float) -> str:
    """四捨五入到 0.02 度（約 2km）作為快取 key"""
    return f"{round(lat / 0.02) * 0.02:.3f}_{round(lon / 0.02) * 0.02:.3f}"


def _get_tdx_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """TDX 路外停車場（城市路徑）+ 即時車位，type='lot'；城市資料快取 90 秒
    兩個 API 並行呼叫，避免超過 Vercel 10s 限制"""
    import time as _time, threading
    token = _get_tdx_token()
    if not token:
        return []

    city = _coords_to_tdx_city(lat, lon)
    now  = _time.time()
    print(f"[TDX] 查詢城市: {city}，座標: ({lat}, {lon})")

    # ── Redis 持久快取（跨 instance）優先，再 in-memory，最後才打 TDX ──
    lots     = _redis_get(f"tdx_lots_{city}")
    avail_map = _redis_get(f"tdx_avail_{city}")

    if lots is not None:
        print(f"[TDX] lots Redis命中 ({len(lots)} 筆)")
    elif city in _tdx_lots_cache and now - _tdx_lots_cache[city][0] < _TDX_CACHE_TTL:
        lots = _tdx_lots_cache[city][1]
        print(f"[TDX] lots 記憶體命中 ({len(lots)} 筆)")

    if avail_map is not None:
        print(f"[TDX] avail Redis命中 ({len(avail_map)} 筆)")
    elif city in _tdx_avail_cache and now - _tdx_avail_cache[city][0] < 60:
        avail_map = _tdx_avail_cache[city][1]
        print(f"[TDX] avail 記憶體命中")

    lots_buf:  list = []
    avail_buf: list = []

    def _fetch_lots():
        try:
            data = _tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=4)
            lots_buf.extend(data)
        except Exception as e:
            print(f"[TDX] lots 失敗: {e}")

    def _fetch_avail():
        try:
            data = _tdx_get(f"Parking/OffStreet/ParkingAvailability/City/{city}?$format=JSON", token, timeout=4)
            avail_buf.extend(data)
        except Exception as e:
            print(f"[TDX] avail 失敗: {e}")

    threads = []
    if lots is None:
        t1 = threading.Thread(target=_fetch_lots, daemon=True)
        threads.append(t1); t1.start()
    if avail_map is None:
        t2 = threading.Thread(target=_fetch_avail, daemon=True)
        threads.append(t2); t2.start()

    for t in threads:
        t.join(timeout=4)

    if lots is None:
        lots = lots_buf
        _tdx_lots_cache[city] = (now, lots)
        if lots:  # 只有非空才存 Redis，避免暫時失敗把空結果快取 24h
            _redis_set(f"tdx_lots_{city}", lots, ttl=86400)
    if avail_map is None:
        avail_map = {a.get("CarParkID", ""): a for a in avail_buf}
        _tdx_avail_cache[city] = (now, avail_map)
        if avail_map:  # 空結果不快取
            _redis_set(f"tdx_avail_{city}", avail_map, ttl=180)

    print(f"[TDX] CarParks: {len(lots)}, Availabilities: {len(avail_map)}")

    result = []
    for lot in lots:
        pos   = lot.get("CarParkPosition") or lot.get("ParkingPosition") or {}
        p_lat = pos.get("PositionLat") or lot.get("PositionLat")
        p_lon = pos.get("PositionLon") or lot.get("PositionLon")
        if not p_lat or not p_lon:
            continue
        dist = _haversine(lat, lon, float(p_lat), float(p_lon))
        if dist > radius:
            continue

        pid = lot.get("CarParkID", "")
        av  = avail_map.get(pid, {})

        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        name      = _zh(lot.get("CarParkName") or lot.get("ParkingName") or {}) or "停車場"
        addr      = _zh(lot.get("Address") or {})
        fare      = str(_zh(lot.get("FareDescription") or lot.get("PricingNote") or {}))[:30]
        total     = int(av.get("TotalSpaces") or lot.get("TotalCapacity") or 0)
        available = int(av.get("AvailableSpaces", -1))

        result.append({
            "name": name, "addr": addr, "fare": fare,
            "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
            "total": total, "available": available, "type": "lot",
        })

    result.sort(key=lambda x: x["dist"])
    return result


def _tdx_get_v2(path: str, token: str, timeout: int = 10) -> list:
    """呼叫 TDX v2 API，回傳 list"""
    url = "https://tdx.transportdata.tw/api/basic/v2/" + path
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return data
            for v in data.values():
                if isinstance(v, list):
                    return v
            return []
    except Exception as e:
        print(f"[TDX v2] GET {path[:80]} 失敗: {e}")
        return []


def _get_tdx_street_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """TDX v2 路邊停車路段 + 即時格位，type='street'
    路段靜態資料快取 24h；格位狀態快取 180 秒
    支援城市：Taipei, NewTaipei, Taoyuan, Taichung, Tainan,
             HualienCounty, PingtungCounty, ChanghuaCounty
    """
    import time as _time, threading

    token = _get_tdx_token()
    if not token:
        return []

    city = _coords_to_tdx_city(lat, lon)
    if city not in _TDX_STREET_CITIES:
        return []

    now        = _time.time()
    seg_rkey   = f"tdx_street_segs_{city}"
    avail_rkey = f"tdx_street_avail_{city}"

    segs      = _redis_get(seg_rkey)
    avail_map = _redis_get(avail_rkey)

    if segs is not None:
        print(f"[TDX street] segs Redis命中 ({len(segs)} 筆)")
    elif city in _tdx_street_segs_cache and now - _tdx_street_segs_cache[city][0] < 86400:
        segs = _tdx_street_segs_cache[city][1]
        print(f"[TDX street] segs 記憶體命中 ({len(segs)} 筆)")

    if avail_map is not None:
        print(f"[TDX street] avail Redis命中 ({len(avail_map)} 筆)")
    elif city in _tdx_street_avail_cache and now - _tdx_street_avail_cache[city][0] < 180:
        avail_map = _tdx_street_avail_cache[city][1]
        print(f"[TDX street] avail 記憶體命中")

    segs_buf:  list = []
    avail_buf: list = []

    def _fetch_segs():
        data = _tdx_get_v2(
            f"Parking/OnStreet/CurbParkingSegment/City/{city}?$format=JSON",
            token, timeout=5,
        )
        segs_buf.extend(data)

    def _fetch_avail():
        data = _tdx_get_v2(
            f"Parking/OnStreet/CurbParkingSpotAvailability/City/{city}"
            f"?$format=JSON&$top=2000",
            token, timeout=5,
        )
        avail_buf.extend(data)

    threads = []
    if segs is None:
        t1 = threading.Thread(target=_fetch_segs, daemon=True)
        threads.append(t1); t1.start()
    if avail_map is None:
        t2 = threading.Thread(target=_fetch_avail, daemon=True)
        threads.append(t2); t2.start()
    for t in threads:
        t.join(timeout=6)

    if segs is None:
        segs = segs_buf
        _tdx_street_segs_cache[city] = (now, segs)
        if segs:
            _redis_set(seg_rkey, segs, ttl=86400)

    if avail_map is None:
        # 每格位回傳 SegmentID + 狀態，統計各路段空位數
        # VacantStatus: "0"=空位, "1"=佔用（部分縣市用 IsVacant bool）
        tmp: dict = {}
        for sp in avail_buf:
            sid = sp.get("SegmentID", "")
            if not sid:
                continue
            if sid not in tmp:
                tmp[sid] = {"avail": 0, "total": 0}
            tmp[sid]["total"] += 1
            is_vacant = (
                sp.get("VacantStatus") in ("0", 0)
                or sp.get("IsVacant") is True
                or sp.get("Status") in ("Y", "Vacant", "Empty")
            )
            if is_vacant:
                tmp[sid]["avail"] += 1
        avail_map = tmp
        _tdx_street_avail_cache[city] = (now, avail_map)
        if avail_map:
            _redis_set(avail_rkey, avail_map, ttl=180)

    print(f"[TDX street] {city} Segments: {len(segs)}, AvailMap: {len(avail_map)}")

    def _zh(obj: object) -> str:
        if isinstance(obj, dict):
            return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
        return str(obj) if obj else ""

    result = []
    for seg in segs:
        pos = (
            seg.get("SegmentStartPosition")
            or seg.get("StartPosition")
            or seg.get("Position")
            or {}
        )
        p_lat = pos.get("PositionLat") or seg.get("PositionLat")
        p_lon = pos.get("PositionLon") or seg.get("PositionLon")
        if not p_lat or not p_lon:
            continue

        dist = _haversine(lat, lon, float(p_lat), float(p_lon))
        if dist > radius:
            continue

        sid       = seg.get("SegmentID", "")
        name      = (_zh(seg.get("SegmentName") or seg.get("RoadSectionName") or {})
                     or _zh(seg.get("RoadName") or {}) or "路邊停車")
        road      = _zh(seg.get("RoadName") or {})
        fare      = str(_zh(seg.get("FareDescription") or seg.get("Fare") or {}))[:30]
        total_seg = int(seg.get("TotalSpaces") or seg.get("SpaceQuantity") or 0)
        sp_info   = avail_map.get(sid, {})
        available = sp_info.get("avail", -1) if sp_info else -1
        if sp_info and total_seg == 0:
            total_seg = sp_info.get("total", 0)

        result.append({
            "name":      name,
            "addr":      road or name,
            "fare":      fare,
            "lat":       float(p_lat),
            "lon":       float(p_lon),
            "dist":      dist,
            "total":     total_seg,
            "available": available,
            "type":      "street",
        })

    result.sort(key=lambda x: x["dist"])
    return result


def _twd97tm2_to_wgs84(x: float, y: float):
    """TWD97 TM2 Zone 121 投影座標（公尺）→ WGS84 lat/lon
    台灣範圍內誤差 < 20m，停車場定位夠用"""
    import math
    lat = y / 110540.0
    lat_rad = math.radians(lat)
    lon = 121.0 + (x - 250000.0) / (111320.0 * math.cos(lat_rad))
    return lat, lon


_NTPC_LOT_STATIC: dict = {}  # ID -> {name, addr, fare, total, lat, lon}


def _get_ntpc_lot_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新北市路外公有停車場（靜態資料 + 即時車位合併）
    靜態 dataset: B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68（含 TWD97 座標）
    即時 dataset: e09b35a5-a738-48cc-b0f5-570b67ad9c78（每 3 分鐘更新）
    """
    global _NTPC_LOT_STATIC

    # ── 1. 靜態資料（記憶體 > Redis 24h > API）──
    static_data = _NTPC_LOT_STATIC or _redis_get("ntpc_lot_static") or {}
    if not static_data:
        try:
            req = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68/json?size=500",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                lots_raw = json.loads(r.read())
            for lot in lots_raw:
                lid = lot.get("ID", "")
                try:
                    tw_x = float(lot.get("TW97X", 0) or 0)
                    tw_y = float(lot.get("TW97Y", 0) or 0)
                    if not lid or tw_x < 100000:
                        continue
                    p_lat, p_lon = _twd97tm2_to_wgs84(tw_x, tw_y)
                    static_data[lid] = {
                        "name": lot.get("NAME", "停車場"),
                        "addr": lot.get("ADDRESS", ""),
                        "fare": str(lot.get("PAYEX", ""))[:30],
                        "total": int(lot.get("TOTALCAR", 0) or 0),
                        "lat": p_lat, "lon": p_lon,
                    }
                except Exception:
                    pass
            _NTPC_LOT_STATIC = static_data
            if static_data:  # 空結果不快取
                _redis_set("ntpc_lot_static", static_data, ttl=86400)
            print(f"[NTPC lot] 靜態資料 {len(static_data)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 靜態資料失敗: {e}")
            return []
    else:
        _NTPC_LOT_STATIC = static_data  # 同步記憶體
        print(f"[NTPC lot] 靜態快取命中 {len(static_data)} 筆")

    # ── 2. 即時車位（Redis 3min > API）──
    avail_map: dict = _redis_get("ntpc_lot_avail") or {}
    if not avail_map:
        try:
            req2 = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "e09b35a5-a738-48cc-b0f5-570b67ad9c78/json",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req2, timeout=5) as r:
                avail_list = json.loads(r.read())
            for av in avail_list:
                lid = av.get("ID", "")
                if lid:
                    try:
                        v = int(av.get("AVAILABLECAR", -1))
                        avail_map[lid] = max(v, -1)  # -9 表示未提供，統一設 -1
                    except (ValueError, TypeError):
                        avail_map[lid] = -1
            if avail_map:  # 空結果不快取
                _redis_set("ntpc_lot_avail", avail_map, ttl=180)
            print(f"[NTPC lot] 即時車位 {len(avail_map)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 即時車位失敗: {e}")

    # ── 3. 過濾半徑內的停車場 ──
    result = []
    for lid, info in static_data.items():
        d = _haversine(lat, lon, info["lat"], info["lon"])
        if d > radius:
            continue
        available = avail_map.get(lid, -1)
        result.append({
            "name":      info["name"],
            "addr":      info["addr"],
            "fare":      info["fare"],
            "lat":       info["lat"], "lon": info["lon"],
            "dist":      d,
            "total":     info["total"],
            "available": available,
            "type":      "lot",
        })
    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC lot] 半徑 {radius}m 內 {len(result)} 個停車場")
    return result


def _get_ntpc_street_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新北市路邊停車格即時狀態（NTPC open data）
    API 不支援空間過濾，採 5 頁並行下載後本地過濾，按路名分組回傳
    dataset: 54A507C4-C038-41B5-BF60-BBECB9D052C6
    cellstatus: Y=空位, N=有車
    """
    import math, threading

    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(lat)))
    lat_min, lat_max = lat - lat_delta, lat + lat_delta
    lon_min, lon_max = lon - lon_delta, lon + lon_delta

    DATASET_ID = "54A507C4-C038-41B5-BF60-BBECB9D052C6"
    PAGE_SIZE  = 1000
    MAX_PAGES  = 5
    pages_data = [[] for _ in range(MAX_PAGES)]

    def fetch_page(i):
        url = (f"https://data.ntpc.gov.tw/api/datasets/{DATASET_ID}/json"
               f"?size={PAGE_SIZE}&page={i}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                pages_data[i] = json.loads(r.read()) or []
        except Exception as e:
            print(f"[NTPC] 第{i}頁失敗: {e}")

    threads = [threading.Thread(target=fetch_page, args=(i,)) for i in range(MAX_PAGES)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=4)

    # 按路名分組
    from collections import defaultdict
    road_map: dict = defaultdict(lambda: {"spots": [], "lat": 0.0, "lon": 0.0, "fare": ""})

    for page_records in pages_data:
        for rec in page_records:
            try:
                p_lat = float(rec.get("latitude", 0))
                p_lon = float(rec.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if not (lat_min <= p_lat <= lat_max and lon_min <= p_lon <= lon_max):
                continue
            dist = _haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue

            road = rec.get("roadname") or "路邊停車格"
            status = rec.get("cellstatus", "")
            entry = road_map[road]
            entry["spots"].append({"status": status, "dist": dist, "lat": p_lat, "lon": p_lon})
            if not entry["lat"] or dist < _haversine(lat, lon, entry["lat"], entry["lon"]):
                entry["lat"] = p_lat
                entry["lon"] = p_lon
            if not entry["fare"] and rec.get("paycash"):
                entry["fare"] = rec["paycash"]

    if not road_map:
        print("[NTPC] 範圍內無路邊格資料（可能在這5頁內）")
        return []

    result = []
    for road, info in road_map.items():
        spots   = info["spots"]
        total   = len(spots)
        avail   = sum(1 for s in spots if s["status"] == "Y")
        nearest = min(spots, key=lambda s: s["dist"])
        result.append({
            "name":      road,
            "addr":      road,
            "fare":      info["fare"],
            "lat":       nearest["lat"],
            "lon":       nearest["lon"],
            "dist":      nearest["dist"],
            "total":     total,
            "available": avail,
            "type":      "street",
        })

    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC] 找到 {len(result)} 條路段，共 {sum(r['total'] for r in result)} 格")
    return result


def _get_tainan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """台南市公有停車場即時車位（parkweb.tainan.gov.tw）"""
    try:
        url = "https://parkweb.tainan.gov.tw/api/parking.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read()
            data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            # 可能包在 data key 內
            for k, v in data.items():
                if isinstance(v, list):
                    data = v
                    break
        result = []
        for lot in (data if isinstance(data, list) else []):
            lnglat = lot.get("lnglat", "")
            if not lnglat:
                continue
            try:
                # 格式: "lat,lng"（中文逗號或英文逗號）
                parts = lnglat.replace("，", ",").split(",")
                p_lat, p_lon = float(parts[0].strip()), float(parts[1].strip())
            except Exception:
                continue
            dist = _haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue
            name      = lot.get("name", "停車場")
            addr      = lot.get("address", "")
            fare      = str(lot.get("chargeFee") or lot.get("chargeTime") or "")[:30]
            total     = int(lot.get("car_total") or 0)
            available = int(lot.get("car") if lot.get("car") is not None else -1)
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": p_lat, "lon": p_lon, "dist": dist,
                "total": total, "available": available,
                "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Tainan] 找到 {len(result)} 個停車場（半徑 {radius}m）")
        return result
    except Exception as e:
        print(f"[Tainan] API 失敗: {e}")
        return []


def _get_yilan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """宜蘭縣停車場即時空位（opendataap2.e-land.gov.tw + TDX 座標）
    e-land API 有即時剩餘數但無座標；TDX YilanCounty 有座標但無即時空位。
    策略：TDX 取座標/名稱，e-land 補即時空位（按停車場名稱 fuzzy match）
    """
    try:
        # ── 1. TDX 取宜蘭縣停車場（有座標）──
        token = _get_tdx_token()
        tdx_lots = _redis_get("tdx_lots_YilanCounty")
        if tdx_lots is None:
            try:
                tdx_lots = _tdx_get("Parking/OffStreet/CarPark/City/YilanCounty?$format=JSON", token, timeout=5)
                if tdx_lots:  # 空結果不快取，避免 24h 鎖死
                    _redis_set("tdx_lots_YilanCounty", tdx_lots, ttl=86400)
            except Exception as e:
                print(f"[Yilan] TDX lots 失敗: {e}")
                tdx_lots = []

        # ── 2. e-land 即時空位（有剩餘數但無座標）──
        eland_map: dict = {}  # 名稱 → 剩餘數
        try:
            cached_avail = _redis_get("yilan_avail")
            if cached_avail:
                eland_map = cached_avail
            else:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                url = ("https://opendataap2.e-land.gov.tw/./resource/files/"
                       "2023-02-12/62f4d78b604ba16b8cc1e856dd28d2c3.json")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    raw_data = json.loads(r.read())
                for item in (raw_data if isinstance(raw_data, list) else []):
                    name = item.get("名稱", "")
                    try:
                        avail = int(item.get("小車位剩餘數") or -1)
                    except Exception:
                        avail = -1
                    try:
                        total = int(item.get("小車位總數") or 0)
                    except Exception:
                        total = 0
                    if name:
                        eland_map[name] = {"available": avail, "total": total}
                if eland_map:  # 空結果不快取
                    _redis_set("yilan_avail", eland_map, ttl=180)
                print(f"[Yilan] e-land 即時空位 {len(eland_map)} 筆")
        except Exception as e:
            print(f"[Yilan] e-land avail 失敗: {e}")

        # ── 3. 合併：TDX 座標 + e-land 空位 ──
        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        result = []
        for lot in (tdx_lots or []):
            pos   = lot.get("CarParkPosition") or {}
            p_lat = pos.get("PositionLat")
            p_lon = pos.get("PositionLon")
            if not p_lat or not p_lon:
                continue
            dist = _haversine(lat, lon, float(p_lat), float(p_lon))
            if dist > radius:
                continue
            name = _zh(lot.get("CarParkName") or {}) or "停車場"
            addr = _zh(lot.get("Address") or {})
            fare = str(_zh(lot.get("FareDescription") or {}))[:30]
            # fuzzy match：找 e-land 裡名稱包含 TDX 名稱的項目
            av_data = eland_map.get(name, {})
            if not av_data:
                for ename, edata in eland_map.items():
                    if name[:4] in ename or ename[:4] in name:
                        av_data = edata
                        break
            available = av_data.get("available", -1)
            total     = av_data.get("total", int(lot.get("TotalCapacity") or 0))
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
                "total": total, "available": available, "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Yilan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Yilan] 失敗: {e}")
        return []


def _get_hsinchu_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """新竹市路外停車場即時車位（hispark.hccg.gov.tw，即時更新）
    欄位：PARKINGNAME, ADDRESS, WEEKDAYS(費率), FREEQUANTITY(剩餘), TOTALQUANTITY(總),
          LONGITUDE, LATITUDE, UPDATETIME
    """
    try:
        cached = _redis_get("hsinchu_lots")
        if cached:
            data = cached
        else:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            req = urllib.request.Request(
                "https://hispark.hccg.gov.tw/OpenData/GetParkInfo",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                raw = r.read()
            data = json.loads(raw)
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        data = v
                        break
            if data:  # 空結果不快取
                _redis_set("hsinchu_lots", data, ttl=180)
            print(f"[Hsinchu] API 取得 {len(data)} 筆")

        result = []
        for lot in (data if isinstance(data, list) else []):
            try:
                p_lat = float(lot.get("LATITUDE") or 0)
                p_lon = float(lot.get("LONGITUDE") or 0)
                if not p_lat or not p_lon:
                    continue
                dist = _haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("FREEQUANTITY") or -1)
                total     = int(lot.get("TOTALQUANTITY") or 0)
                fare      = str(lot.get("WEEKDAYS") or "")
                # 費率欄位可能很長，只取第一行
                fare = fare.split("\n")[0].split("\r")[0][:30]
                result.append({
                    "name":      lot.get("PARKINGNAME", "停車場"),
                    "addr":      lot.get("ADDRESS", ""),
                    "fare":      fare,
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Hsinchu] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Hsinchu] API 失敗: {e}")
        return []


def _get_taoyuan_parking(lat: float, lon: float, radius: int = 1500) -> list:
    """桃園市路外停車場即時車位（桃園開放資料，每分鐘更新）
    API: opendata.tycg.gov.tw  wgsX=緯度, wgsY=經度（命名相反，請注意）
    """
    try:
        # Redis 2分鐘快取（此API每分鐘更新，2分鐘夠用）
        cached = _redis_get("taoyuan_lots")
        if cached:
            data = cached
        else:
            req = urllib.request.Request(
                "https://opendata.tycg.gov.tw/api/dataset/"
                "f4cc0b12-86ac-40f9-8745-885bddc18f79/resource/"
                "0381e141-f7ee-450e-99da-2240208d1773/download",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                raw = r.read().decode("utf-8", "ignore")
            # 防止 Extra data（有時回傳非標準 JSON）
            start, end = raw.find("["), raw.rfind("]")
            data = json.loads(raw[start:end+1]) if start >= 0 else []
            if data:  # 空結果不快取
                _redis_set("taoyuan_lots", data, ttl=120)
            print(f"[Taoyuan] API 取得 {len(data)} 筆")

        result = []
        for lot in data:
            try:
                # API 命名相反：wgsX=緯度, wgsY=經度
                p_lat = float(lot.get("wgsX", 0) or 0)
                p_lon = float(lot.get("wgsY", 0) or 0)
                if not p_lat or not p_lon:
                    continue
                dist = _haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("surplusSpace", -1) or -1)
                total     = int(lot.get("totalSpace", 0)    or 0)
                result.append({
                    "name":      lot.get("parkName", "停車場"),
                    "addr":      lot.get("address", ""),
                    "fare":      str(lot.get("payGuide", ""))[:30],
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Taoyuan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Taoyuan] API 失敗: {e}")
        return []


def _get_nearby_parking(lat: float, lon: float, radius: int = 1500) -> dict:
    """多來源停車資料整合，回傳 {'street': [...], 'lot': [...], 'city': str}"""
    import threading

    city = _coords_to_tdx_city(lat, lon)
    street_result: list = []
    lot_result:    list = []

    def _run_parallel(*fns, timeout=6):
        """並行執行多個函式，超時只記 log 不崩潰"""
        threads = [threading.Thread(target=fn, daemon=True) for fn in fns]
        for t in threads: t.start()
        for i, t in enumerate(threads):
            t.join(timeout=timeout)
            if t.is_alive(): print(f"[parking] thread{i+1} 超時仍在執行")

    if city == "YilanCounty":
        lot_result = _get_yilan_parking(lat, lon, radius)
    elif city == "NewTaipei":
        # NTPC 路邊停車格（感測器即時）優先；路外停車場並行
        def fetch_street(): street_result.extend(_get_ntpc_street_parking(lat, lon, radius))
        def fetch_lot():
            try:
                lot_result.extend(_get_ntpc_lot_parking(lat, lon, radius))
            except Exception as e:
                print(f"[NTPC lot] thread 異常: {e}")
        _run_parallel(fetch_street, fetch_lot)
    elif city == "Taoyuan":
        def fetch_tycg(): lot_result.extend(_get_taoyuan_parking(lat, lon, radius))
        def fetch_tdx_ty():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        def fetch_street_ty(): street_result.extend(_get_tdx_street_parking(lat, lon, radius))
        _run_parallel(fetch_tycg, fetch_tdx_ty, fetch_street_ty)
    elif city == "Hsinchu":
        def fetch_hsinchu(): lot_result.extend(_get_hsinchu_parking(lat, lon, radius))
        def fetch_tdx_hc():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_hsinchu, fetch_tdx_hc)
    elif city == "Tainan":
        def fetch_tainan(): lot_result.extend(_get_tainan_parking(lat, lon, radius))
        def fetch_tdx_tn():
            tdx = _get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        def fetch_street_tn(): street_result.extend(_get_tdx_street_parking(lat, lon, radius))
        _run_parallel(fetch_tainan, fetch_tdx_tn, fetch_street_tn)
    elif city in _TDX_STREET_CITIES:
        # Taipei, Taichung, HualienCounty, PingtungCounty, ChanghuaCounty
        def fetch_lots(): lot_result.extend(_get_tdx_parking(lat, lon, radius))
        def fetch_street_tdx(): street_result.extend(_get_tdx_street_parking(lat, lon, radius))
        _run_parallel(fetch_lots, fetch_street_tdx)
    else:
        lot_result = _get_tdx_parking(lat, lon, radius)

    return {
        "street": street_result[:8] if isinstance(street_result, list) else [],
        "lot":    lot_result[:6]    if isinstance(lot_result,    list) else [],
        "city":   city or "Unknown",
    }


def _build_restaurant_bubble(r: dict, lat: float, lon: float, city: str,
                              eaten_set: set, subtitle: str = "") -> dict:
    """單間餐廳 Flex Bubble（含照片 hero、評分、導航、吃過了按鈕）"""
    name = r.get("name", "")
    addr = r.get("addr", "") or r.get("town", "")
    rating = r.get("rating", 0)
    reviews = r.get("user_ratings_total", 0)
    eaten = name in eaten_set

    # 距離（換算步行分鐘，80m/min）
    dist_str = ""
    dist_m = r.get("dist")  # 已在 _build_post_parking_food 算好
    if dist_m is None and lat and lon and r.get("lat") and r.get("lng"):
        dist_m = _haversine(lat, lon, r["lat"], r["lng"])
    if dist_m is not None:
        walk_min = max(1, round(dist_m / 80))
        if dist_m < 1000:
            dist_str = f"步行約{walk_min}分鐘（{int(dist_m)}m）"
        else:
            dist_str = f"步行約{walk_min}分鐘（{dist_m/1000:.1f}km）"

    # 導航連結
    if r.get("place_id"):
        gmap_uri = f"https://maps.google.com/?q=place_id:{r['place_id']}"
    elif r.get("lat") and r.get("lng"):
        gmap_uri = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name)}&center={r['lat']},{r['lng']}"
    else:
        gmap_uri = (f"https://www.google.com/maps/search/"
                    f"{urllib.parse.quote(name + ' ' + city)}")

    # 推薦理由標籤
    tag = subtitle  # 傳入的強制標籤（如米其林）
    if not tag:
        if rating >= 4.5 and reviews >= 100:
            tag = "🔥 Google 高評分"
        elif rating >= 4.3:
            tag = "⭐ 評價優良"
        else:
            tag = "👥 在地人推薦"

    # 評分標章文字
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

    desc_raw = r.get("desc", "")
    # 過濾掉純粹是「米其林必比登推介」的無意義 desc
    desc = desc_raw if (desc_raw and "必比登推介" not in desc_raw) else ""
    # 無 desc 但有 type → 用 type 補足說明
    if not desc and r.get("type"):
        desc = r["type"]

    safe_name = name or "未命名餐廳"
    safe_tag  = tag  or "👥 在地推薦"
    # 沒有距離時：若有 desc 用前 20 字，否則用城市名
    if dist_str:
        safe_dist = dist_str
    elif desc:
        safe_dist = f"📍 {desc[:20]}"
    elif addr:
        safe_dist = addr[:20]
    else:
        safe_dist = city[:2] if city else "附近美食"
    safe_addr = addr[:28] if addr else ""

    body_contents = [
        # 推薦理由標籤
        {"type": "text", "text": safe_tag, "size": "xxs", "weight": "bold",
         "color": "#B8860B" if "必比登" in safe_tag else "#E65100",
         "margin": "none"},
        # 餐廳名稱
        {"type": "text", "text": safe_name, "size": "md", "weight": "bold",
         "wrap": True, "maxLines": 2,
         "color": "#3D2B1F" if not eaten else "#AAAAAA",
         "margin": "xs"},
        # 距離（步行分鐘）或區域提示
        {"type": "text", "text": safe_dist, "size": "xs",
         "color": "#1565C0", "wrap": False, "margin": "xs"},
    ]
    # 推薦描述（有才顯示，最多 2 行）
    if desc and dist_str:  # 有距離才另外顯示 desc，避免重複
        body_contents.append(
            {"type": "text", "text": desc[:45] + ("…" if len(desc) > 45 else ""),
             "size": "xxs", "color": "#555555", "wrap": True,
             "maxLines": 2, "margin": "xs"}
        )
    # 評分（有才顯示）
    if rating_str:
        body_contents.append(
            {"type": "text", "text": rating_str, "size": "xs",
             "color": rating_color, "margin": "xs"}
        )
    # 地址（有才顯示）
    if safe_addr:
        body_contents.append(
            {"type": "text", "text": safe_addr, "size": "xxs",
             "color": "#AAAAAA", "wrap": True, "maxLines": 1, "margin": "xs"}
        )

    # Postback data for eaten
    eaten_data = f"ate:{name}:{city[:5]}"

    bubble: dict = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "none",
            "paddingAll": "14px",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "paddingAll": "10px",
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

    # 有照片 → 加 hero image
    photo = ""
    if r.get("photo_ref"):
        photo = _places_photo_url(r["photo_ref"])
    if photo:
        bubble["hero"] = {
            "type": "image",
            "url": photo,
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        }

    return bubble


def _build_post_parking_food(city: str, lat: float = None, lon: float = None,
                              user_id: str = "", addr: str = "") -> list:
    """停車後 / 吃什麼 → 附近美食推薦
    優先使用 Google Places Nearby Search（即時、有照片）；
    無 API key 時 fallback 到靜態爬蟲資料，半徑 500m→1km→2km→3km 漸進放寬。
    套用個人化記憶：90 天內吃過的餐廳排到最後。

    依賴 webhook.py 全域資料的函式（_get_eaten, build_food_restaurant_flex,
    _RESTAURANT_CACHE, _BIB_GOURMAND, _random）以延遲 import 方式取得，
    避免循環依賴，且讓模組本身可獨立測試。
    """
    # 延遲 import，避免循環依賴
    try:
        import webhook as _wh
        _get_eaten = _wh._get_eaten
    except Exception:
        return []
    try:
        from modules.food import (
            build_food_restaurant_flex,
            _RESTAURANT_CACHE, _BIB_GOURMAND,
        )
        import random as _random
    except Exception:
        return []

    city2 = city[:2] if city else ""
    eaten_set = _get_eaten(user_id) if user_id else set()

    # ── 優先：Google Places Nearby Search ──
    picks = []
    if lat and lon and GOOGLE_PLACES_API_KEY:
        gp = _nearby_places_google(lat, lon, radius=3000)
        # 補充距離並由近到遠排序
        for r in gp:
            if r.get("lat") and r.get("lng"):
                r["dist"] = _haversine(lat, lon, r["lat"], r["lng"])
            else:
                r["dist"] = 9999
        gp.sort(key=lambda x: x["dist"])
        # 吃過的排後面
        fresh = [r for r in gp if r["name"] not in eaten_set]
        stale = [r for r in gp if r["name"] in eaten_set]
        picks = (fresh + stale)[:8]

    # ── Fallback：靜態爬蟲資料（漸進放寬半徑）──
    if not picks:
        pool = _RESTAURANT_CACHE.get(city, _RESTAURANT_CACHE.get(city2, []))
        if lat and lon and pool:
            for radius in (500, 1000, 2000, 3000):
                candidates = []
                for r in pool:
                    if r.get("lat") and r.get("lng"):
                        d = _haversine(lat, lon, r["lat"], r["lng"])
                        if d <= radius:
                            candidates.append((d, r))
                if len(candidates) >= 3:
                    candidates.sort(key=lambda x: x[0])
                    flat = [r for _, r in candidates[:8]]
                    fresh = [r for r in flat if r["name"] not in eaten_set]
                    stale = [r for r in flat if r["name"] in eaten_set]
                    picks = fresh + stale
                    break
        if not picks and pool:
            # 從地址萃取行政區（東區、中西區…），優先推同區餐廳
            import re as _re
            district_match = _re.search(r'[\u4e00-\u9fff]{1,3}[區鎮鄉市]', addr)
            district = district_match.group(0) if district_match else ""
            if district:
                district_pool = [r for r in pool if r.get("town", "") == district]
                if len(district_pool) >= 3:
                    pool = district_pool
            picks = _random.sample(pool, min(5, len(pool)))

    # ── 必比登精選：最多 2 家，有座標時只取 3km 內、由近到遠 ──
    bib_pool = _BIB_GOURMAND.get(city2, [])
    if lat and lon and bib_pool:
        bib_with_dist = []
        for b in bib_pool:
            if b.get("lat") and b.get("lng"):
                d = _haversine(lat, lon, float(b["lat"]), float(b["lng"]))
                if d <= 3000:
                    bib_with_dist.append((d, b))
        bib_with_dist.sort(key=lambda x: x[0])
        bib_pool_near = [b for _, b in bib_with_dist]
    else:
        bib_pool_near = bib_pool
    bib_picks = bib_pool_near[:2] if bib_pool_near else []
    for b in bib_picks:
        b.setdefault("_source", "bib")

    all_picks = bib_picks + picks

    if not all_picks:
        return build_food_restaurant_flex(city)

    # ── 組 carousel 卡片（最多 5 張 + 1 張更多）──
    bubbles = []
    for r in all_picks[:5]:
        sub = "⭐ 米其林必比登" if r.get("_source") == "bib" else ""
        bubbles.append(_build_restaurant_bubble(r, lat, lon, city, eaten_set, sub))

    # 最後加一張「看更多」卡
    more_bubble = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "justifyContent": "center",
            "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "還想看更多？", "size": "sm",
                 "weight": "bold", "align": "center", "color": "#666666"},
                {"type": "text", "text": "重新分享位置可抽不同餐廳",
                 "size": "xxs", "align": "center", "color": "#AAAAAA", "margin": "xs"},
                {"type": "button", "style": "primary", "color": "#FF6B35",
                 "margin": "md",
                 "action": {"type": "message", "label": "🔄 換一組",
                            "text": "換一組附近美食"}},
                {"type": "button", "style": "primary", "color": "#1565C0", "margin": "sm",
                 "action": {"type": "message", "label": "🗺️ 目的地美食查詢",
                            "text": f"目的地美食 {city2}"}},
                {"type": "button", "style": "secondary", "margin": "sm",
                 "action": {"type": "message", "label": "🍜 在地餐廳全覽",
                            "text": f"在地餐廳 {city2}"}},
            ],
        },
    }
    bubbles.append(more_bubble)

    count_str = f"找到 {len(all_picks)} 間" if all_picks else ""
    alt = f"{city2}附近美食推薦 🍜  {count_str}"
    return [{"type": "flex", "altText": alt,
             "contents": {
                 "type": "carousel",
                 "contents": bubbles,
             }}]


def build_parking_flex(lat: float, lon: float, city: str = "") -> list:
    """位置訊息 → 附近停車 Flex Carousel
    路邊格（路名分組）優先，再接停車場，最後加生活推薦卡
    結果快取 3 分鐘（同 2km 格子內共用）
    """
    import time as _time
    if not TDX_CLIENT_ID:
        return [{"type": "flex", "altText": "找車位",
                 "contents": {
                     "type": "bubble",
                     "header": {"type": "box", "layout": "vertical",
                                "backgroundColor": "#C62828", "contents": [
                                    {"type": "text", "text": "🅿️ 找車位",
                                     "color": "#FFFFFF", "weight": "bold"}]},
                     "body": {"type": "box", "layout": "vertical", "contents": [
                         {"type": "text",
                          "text": "找車位功能尚未設定 TDX API\n請管理員設定 TDX_CLIENT_ID / TDX_CLIENT_SECRET",
                          "wrap": True, "size": "sm", "color": "#555555"}]},
                 }}]

    # ── 結果快取（座標格子 2km，TTL 3 分鐘）
    ck  = _parking_cache_key(lat, lon)
    now = _time.time()
    # Redis 持久快取優先
    redis_result = _redis_get(f"parking_{ck}")
    if redis_result is not None:
        print(f"[parking] Redis結果快取命中 {ck}")
        return redis_result
    # in-memory 次之
    if ck in _parking_result_cache:
        ts, cached_msgs = _parking_result_cache[ck]
        if now - ts < _PARKING_RESULT_TTL:
            print(f"[parking] 記憶體快取命中 key={ck}")
            return cached_msgs

    # 查一次 2km，快取後快速過濾
    radius_used = 2000
    data = _get_nearby_parking(lat, lon, radius=2000)
    city   = data["city"]
    street = data["street"]
    lots   = data["lot"]
    all_parks = street + lots

    if not all_parks:
        # 官方資料無結果 → 雙卡片：公立 fallback + 私人停車場
        gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
        city_park_url = "https://www.cityparking.com.tw/"
        times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
        ipark_url     = "https://www.iparking.com.tw/"
        liff_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"

        bubble_public = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#1A1F3A", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🗺️", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "附近停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "Google Maps 整合查詢",
                                 "color": "#8892B0", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#26A69A", "height": "sm",
                          "action": {"type": "uri", "label": "🗺️ 查所有停車場（含私人）", "uri": gmap_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ iParking 即時空位", "uri": ipark_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "📍 換個位置重新查", "uri": liff_url}},
                         {"type": "text",
                          "text": "💡 此區公立開放資料暫無，已切換至地圖搜尋",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        bubble_private = {
            "type": "bubble", "size": "kilo",
            "header": {"type": "box", "layout": "horizontal",
                       "backgroundColor": "#37474F", "paddingAll": "14px",
                       "contents": [
                           {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                           {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                            "contents": [
                                {"type": "text", "text": "私人停車場",
                                 "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": "城市車旅 × Times",
                                 "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                            ]},
                       ]},
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                     "contents": [
                         {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                          "action": {"type": "uri", "label": "🏙️ 城市車旅 找車位",
                                     "uri": city_park_url}},
                         {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                          "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                     "uri": times_url}},
                         {"type": "text",
                          "text": "💡 私人車場通常不提供即時空位，建議先電話確認",
                          "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                     ]},
        }

        return [{"type": "flex", "altText": "🅿️ 幫你找附近停車場",
                 "contents": {"type": "carousel",
                              "contents": [bubble_public, bubble_private]}}]

    radius_label = {1500: "1.5公里", 3000: "3公里", 5000: "5公里"}.get(radius_used, f"{radius_used}m")
    source_note = (
        "資料來源：新北市開放資料 + TDX｜實際以現場為準" if city == "NewTaipei" else
        "資料來源：新竹市 HisPark 即時資料｜實際以現場為準" if city == "Hsinchu" else
        "資料來源：台南市停車資訊 + TDX｜實際以現場為準" if city == "Tainan" else
        "資料來源：宜蘭縣開放資料 + TDX｜實際以現場為準" if city == "YilanCounty" else
        f"資料來源：交通部 TDX 路邊+路外（{radius_label}內）｜實際以現場為準"
        if city in _TDX_STREET_CITIES else
        f"資料來源：交通部 TDX（{radius_label}內）｜實際以現場為準"
    )

    def _make_bubble(p: dict) -> dict:
        is_street  = p["type"] == "street"
        av, total  = p["available"], p["total"]
        hdr_color  = "#1B5E20" if is_street else "#1565C0"
        type_label = "🛣️ 路邊停車" if is_street else "🅿️ 停車場"

        if av < 0:
            av_text, av_color = "查無資料", "#888888"
        elif av == 0:
            av_text, av_color = "已滿 🔴", "#C62828"
        elif is_street:
            pct = av / total if total else 1
            av_text = f"{av}/{total} 格"
            av_color = "#E65100" if pct < 0.3 else "#2E7D32"
            av_text += " 🟡" if pct < 0.3 else " 🟢"
        else:
            pct = av / total if total > 0 else 1
            av_text = f"{av} 位"
            av_color = "#E65100" if pct < 0.2 else "#2E7D32"
            av_text += " 🟡" if pct < 0.2 else " 🟢"

        dist_text = f"{p['dist']} m" if p["dist"] < 1000 else f"{p['dist']/1000:.1f} km"
        maps_url  = f"https://www.google.com/maps/dir/?api=1&destination={p['lat']},{p['lon']}"

        rows = [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "空位", "size": "xs",
                 "color": "#888888", "flex": 2, "gravity": "center"},
                {"type": "text", "text": av_text, "size": "lg",
                 "weight": "bold", "color": av_color, "flex": 3, "align": "end"},
            ]},
            {"type": "separator", "margin": "sm"},
            {"type": "box", "layout": "horizontal", "margin": "sm", "contents": [
                {"type": "text", "text": "📍 距離", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": dist_text, "size": "xs", "flex": 3, "align": "end"},
            ]},
        ]
        if p.get("fare"):
            rows.append({"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": "💰 費率", "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": p["fare"][:25], "size": "xs",
                 "flex": 3, "align": "end", "wrap": True, "maxLines": 1},
            ]})
        rows.append({"type": "text", "text": source_note,
                     "size": "xxs", "color": "#AAAAAA", "margin": "sm", "wrap": True})

        return {
            "type": "bubble", "size": "kilo",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": hdr_color, "paddingAll": "md",
                "contents": [
                    {"type": "text", "text": type_label,
                     "color": "#FFFFFFBB", "size": "xxs"},
                    {"type": "text", "text": p["name"], "color": "#FFFFFF",
                     "size": "sm", "weight": "bold", "wrap": True, "maxLines": 2},
                ]
            },
            "body": {"type": "box", "layout": "vertical",
                     "spacing": "xs", "paddingAll": "md", "contents": rows},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "sm",
                       "contents": [
                           {"type": "button", "style": "primary", "color": hdr_color,
                            "height": "sm",
                            "action": {"type": "uri", "label": "🗺️ 導航前往", "uri": maps_url}},
                       ]}
        }

    bubbles = [_make_bubble(p) for p in all_parks]

    # ── 統計摘要文字
    street_avail = sum(p["available"] for p in street if p["available"] >= 0)
    lot_avail    = sum(p["available"] for p in lots   if p["available"] >= 0)
    summary = []
    if street: summary.append(f"路邊 {street_avail} 格可停")
    if lots:   summary.append(f"停車場 {lot_avail} 位可停")

    # ── 私人停車場補充卡（城市車旅/Times/iParking）
    # 公立 API 只涵蓋政府管理的停車場，私人業者（CITY PARKING、Times、台灣聯通等）
    # 不提供 Open Data，永遠需要補充這張卡讓使用者自行查詢
    _city_park_url = "https://www.cityparking.com.tw/"
    _times_url     = f"https://www.timespark.com.tw/tw/ParkingSearch?lat={lat}&lng={lon}"
    _ipark_url     = "https://www.iparking.com.tw/"
    _gmap_url      = f"https://www.google.com/maps/search/%E5%81%9C%E8%BB%8A%E5%A0%B4/@{lat},{lon},16z"
    bubble_private = {
        "type": "bubble", "size": "kilo",
        "header": {"type": "box", "layout": "horizontal",
                   "backgroundColor": "#37474F", "paddingAll": "14px",
                   "contents": [
                       {"type": "text", "text": "🏢", "size": "xl", "flex": 0},
                       {"type": "box", "layout": "vertical", "flex": 1, "paddingStart": "10px",
                        "contents": [
                            {"type": "text", "text": "私人停車場",
                             "color": "#FFFFFF", "size": "sm", "weight": "bold"},
                            {"type": "text", "text": "城市車旅 × Times × Google Maps",
                             "color": "#90A4AE", "size": "xxs", "margin": "xs"},
                        ]},
                   ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "paddingAll": "14px",
                 "contents": [
                     {"type": "button", "style": "primary", "color": "#455A64", "height": "sm",
                      "action": {"type": "uri", "label": "🏙️ 城市車旅 CITY PARKING",
                                 "uri": _city_park_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🅿️ Times 停車場查詢",
                                 "uri": _times_url}},
                     {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
                      "action": {"type": "uri", "label": "🗺️ Google Maps 查所有停車場",
                                 "uri": _gmap_url}},
                     {"type": "text",
                      "text": "💡 私人車場空位需至各平台確認，建議先電話洽詢",
                      "size": "xxs", "color": "#AAAAAA", "wrap": True, "margin": "sm"},
                 ]},
    }
    bubbles.append(bubble_private)

    # life card 已移除 — 美食卡片改由 inline push 緊接在停車結果後送出

    alt = f"已找到 {len(street)} 條路邊路段、{len(lots)} 個停車場"
    result_msgs = [{"type": "flex", "altText": alt,
                    "contents": {"type": "carousel", "contents": bubbles}}]

    # 存入快取
    _parking_result_cache[ck] = (now, result_msgs)
    _redis_set(f"parking_{ck}", result_msgs, ttl=180)  # 3 分鐘
    return result_msgs
